"""Rutas del Authenticator: empezar la activación, comprobarla y ver el estado (pieza 3.2), y escribir el código
de una sesión en espera al iniciar sesión (pieza 3.3).

Los avisos salen con la misma forma que los demás de Cuentas:

    {"errors": [{"field": "code", "code": "invalid_code", "message": "..."}], "attempts_left": 4}
"""

import re
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import require_session
from app.api.client import client_ip
from app.api.protection import require_session_for_change, require_session_for_change_even_pending
from app.modules.accounts.sessions import CurrentSession
from app.modules.accounts.totp import DIGITS, PERIOD_SECONDS, provisioning_uri, to_base32
from app.modules.accounts.two_factor import (
    ConfirmOutcome,
    SetupOutcome,
    VerifyOutcome,
    confirm_setup,
    read_status,
    start_setup,
    verify_session,
)

router = APIRouter(prefix="/auth/2fa", tags=["accounts"])

CHANNEL_EMAIL = "email"
NOTICE_FAILED_LOGINS = "failed_logins"
NOTICE_ENABLED = "two_factor_enabled"
NOTICE_LOCKED = "two_factor_locked"
# Las aplicaciones muestran el código con un espacio en medio («123 456»): se acepta escrito así.
CODE = re.compile(r"^[0-9]{6}$")
NO_STORE = {"Cache-Control": "no-store"}


class SetupRequest(BaseModel):
    password: Any = Field(default=None, examples=["Ejemplo-2026"])


class SetupResponse(BaseModel):
    status: Literal["pending"]
    # La clave, para escribirla a mano en la aplicación. Se entrega solo aquí.
    secret: str
    # La misma clave como dirección otpauth://, que es lo que lleva el código QR.
    otpauth_uri: str
    digits: int
    period: int


class ConfirmRequest(BaseModel):
    code: Any = Field(default=None, examples=["123456"])


class ConfirmResponse(BaseModel):
    status: Literal["active"]
    activated_at: datetime


class VerifyRequest(BaseModel):
    code: Any = Field(default=None, examples=["123456"])


class VerifyResponse(BaseModel):
    status: Literal["verified"]
    verified_at: datetime


class StatusResponse(BaseModel):
    status: Literal["inactive", "pending", "active"]
    activated_at: datetime | None = None


class ErrorItem(BaseModel):
    field: str
    code: str
    message: str


class ErrorResponse(BaseModel):
    errors: list[ErrorItem]


def error(status_code: int, field: str, code: str, message: str, **extra) -> JSONResponse:
    headers = dict(NO_STORE)
    if "retry_after" in extra:
        headers["Retry-After"] = str(extra["retry_after"])
    body = {"errors": [{"field": field, "code": code, "message": message}], **extra}
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def try_later(seconds: int) -> JSONResponse:
    minutes = -(-seconds // 60)
    wait = "1 minuto" if minutes == 1 else f"{minutes} minutos"
    return error(429, "credentials", "try_later", f"Demasiados intentos. Inténtalo nuevamente en {wait}.", retry_after=seconds)


def unavailable() -> JSONResponse:
    return error(
        503, "two_factor", "two_factor_unavailable", "No pudimos usar el Authenticator en este momento. Inténtalo más tarde."
    )


def not_allowed(session: CurrentSession) -> JSONResponse | None:
    """El Authenticator es de anfitriones y administradores (bitácora 41.11). El papel se lee en cada petición."""
    if session.is_host or session.is_admin:
        return None
    return error(
        403, "request", "two_factor_not_allowed", "El Authenticator es para anfitriones y para el equipo de Íntegro."
    )


ERRORS = {
    401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
    422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
}


@router.post("/setup", response_model=SetupResponse, responses=ERRORS, summary="Authenticator, paso 1: empezar la activación")
def setup(body: SetupRequest, request: Request, session: CurrentSession = Depends(require_session_for_change)):
    """Genera la clave del Authenticator de la persona con sesión y la entrega **una sola vez**, como texto y como
    dirección `otpauth://`. Queda pendiente hasta comprobarla con un código en `/auth/2fa/confirm`. Pide la contraseña
    otra vez. Solo para anfitriones y administradores. Si ya estaba pendiente, la clave nueva reemplaza a la anterior;
    si ya está activo responde `409`."""
    refused = not_allowed(session)
    if refused is not None:
        return refused
    if not isinstance(body.password, str) or body.password == "":
        return error(422, "password", "required", "Este dato es obligatorio.")

    state = request.app.state
    result = start_setup(
        state.pool,
        session.user_id,
        body.password,
        state.settings,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if result.notice is not None:
        # El mismo aviso que al iniciar sesión: varias contraseñas incorrectas seguidas contra la cuenta (ADR 0014).
        state.code_sender.send_notice(
            channel=CHANNEL_EMAIL,
            destination=result.email,
            kind=NOTICE_FAILED_LOGINS,
            details={
                "failures": result.notice.failures,
                "at": result.notice.at,
                "ip_address": result.notice.ip_address,
                "user_agent": result.notice.user_agent,
            },
        )

    if result.outcome is SetupOutcome.UNAVAILABLE:
        return unavailable()
    if result.outcome is SetupOutcome.TRY_LATER:
        return try_later(result.retry_after_seconds)
    if result.outcome is SetupOutcome.INVALID_PASSWORD:
        return error(403, "password", "invalid_password", "La contraseña no es correcta.")
    if result.outcome is SetupOutcome.ALREADY_ACTIVE:
        return error(409, "two_factor", "two_factor_already_active", "Tu Authenticator ya está activo.")

    content = SetupResponse(
        status="pending",
        secret=to_base32(result.secret),
        otpauth_uri=provisioning_uri(result.secret, result.email),
        digits=DIGITS,
        period=PERIOD_SECONDS,
    )
    # La clave no debe quedarse guardada en ningún lugar intermedio.
    return JSONResponse(status_code=200, content=content.model_dump(), headers=NO_STORE)


@router.post(
    "/confirm", response_model=ConfirmResponse,
    responses={**ERRORS, 400: {"model": ErrorResponse}}, summary="Authenticator, paso 2: comprobar con un código",
)
def confirm(body: ConfirmRequest, request: Request, session: CurrentSession = Depends(require_session_for_change)):
    """Comprueba el código de 6 dígitos que muestra la aplicación. Si corresponde a la clave pendiente, el
    Authenticator queda activo y se avisa por correo. `400` con `invalid_code` y `attempts_left` si no es correcto;
    a los 5 fallos seguidos, `429` y 15 minutos de espera. `409` si no se ha empezado la activación o ya está activo."""
    refused = not_allowed(session)
    if refused is not None:
        return refused
    if not isinstance(body.code, str) or body.code.strip() == "":
        return error(422, "code", "required", "Este dato es obligatorio.")
    code = "".join(body.code.split())
    if not CODE.match(code):
        return error(422, "code", "invalid_format", "El código tiene 6 números.")

    state = request.app.state
    result = confirm_setup(state.pool, session.user_id, code, state.settings, session_id=session.session_id)

    if result.outcome is ConfirmOutcome.UNAVAILABLE:
        return unavailable()
    if result.outcome is ConfirmOutcome.NOT_STARTED:
        return error(409, "two_factor", "two_factor_not_started", "Primero empieza la activación del Authenticator.")
    if result.outcome is ConfirmOutcome.ALREADY_ACTIVE:
        return error(409, "two_factor", "two_factor_already_active", "Tu Authenticator ya está activo.")
    if result.outcome is ConfirmOutcome.TRY_LATER:
        return try_later(result.retry_after_seconds)
    if result.outcome is ConfirmOutcome.INVALID_CODE:
        return error(400, "code", "invalid_code", "El código no es correcto.", attempts_left=result.attempts_left)

    # El aviso sale hasta que quedó guardado. Si no se puede enviar, el Authenticator queda activo igual.
    state.code_sender.send_notice(
        channel=CHANNEL_EMAIL,
        destination=result.email,
        kind=NOTICE_ENABLED,
        details={"at": result.activated_at, "ip_address": client_ip(request), "user_agent": request.headers.get("user-agent")},
    )
    return ConfirmResponse(status="active", activated_at=result.activated_at)


@router.post(
    "/verify", response_model=VerifyResponse,
    responses={**ERRORS, 400: {"model": ErrorResponse}}, summary="Authenticator al iniciar sesión: escribir el código",
)
def verify(
    body: VerifyRequest, request: Request, session: CurrentSession = Depends(require_session_for_change_even_pending)
):
    """Completa una sesión que está en espera del Authenticator: se manda `code`, los 6 números de la aplicación.
    `200 {"status": "verified", "verified_at": "..."}` y la sesión ya sirve. `400` con `invalid_code` y
    `attempts_left`; a los 5 fallos seguidos, `429`, 15 minutos de espera y un aviso por correo al dueño. `409` si la
    persona no tiene el Authenticator activo. Es de las pocas rutas que aceptan una sesión en espera."""
    if not isinstance(body.code, str) or body.code.strip() == "":
        return error(422, "code", "required", "Este dato es obligatorio.")
    code = "".join(body.code.split())
    if not CODE.match(code):
        return error(422, "code", "invalid_format", "El código tiene 6 números.")

    state = request.app.state
    result = verify_session(state.pool, session.user_id, session.session_id, code, state.settings)

    if result.locked_after is not None:
        # Quien llegó hasta aquí ya escribió la contraseña y el código del correo: el dueño tiene que saberlo.
        state.code_sender.send_notice(
            channel=CHANNEL_EMAIL,
            destination=result.email,
            kind=NOTICE_LOCKED,
            details={
                "failures": result.locked_after,
                "at": datetime.now(timezone.utc),
                "ip_address": client_ip(request),
                "user_agent": request.headers.get("user-agent"),
            },
        )
    if result.outcome is VerifyOutcome.UNAVAILABLE:
        return unavailable()
    if result.outcome is VerifyOutcome.NOT_ACTIVE:
        return error(409, "two_factor", "two_factor_not_active", "No tienes el Authenticator activo.")
    if result.outcome is VerifyOutcome.TRY_LATER:
        return try_later(result.retry_after_seconds)
    if result.outcome is VerifyOutcome.INVALID_CODE:
        return error(400, "code", "invalid_code", "El código no es correcto.", attempts_left=result.attempts_left)
    return VerifyResponse(status="verified", verified_at=result.verified_at)


@router.get("", response_model=StatusResponse, responses={401: {"model": ErrorResponse}}, summary="Ver si mi Authenticator está activo")
def status(request: Request, session: CurrentSession = Depends(require_session)):
    """`inactive` (nunca empezó), `pending` (tiene una clave sin comprobar) o `active`, con la fecha en que se activó.
    Nunca entrega la clave."""
    current = read_status(request.app.state.pool, session.user_id)
    return StatusResponse(status=current.status, activated_at=current.activated_at)
