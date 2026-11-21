"""Rutas del módulo de Cuentas: registro y comprobación del correo.

Los avisos salen siempre con la misma forma, para que el formulario los
ponga junto a su campo:

    {"errors": [{"field": "password", "code": "too_short", "message": "..."}]}
"""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import SESSION_COOKIE, clear_session_cookie, require_session, set_session_cookie
from app.api.protection import csrf_token, require_session_for_change
from app.database.transaction import user_transaction
from app.modules.accounts.email_correction import CorrectionOutcome, correct_unverified_email
from app.modules.accounts.login import LoginOutcome, SessionOutcome, finish_login, start_login
from app.modules.accounts.password_reset import ResetOutcome, request_password_reset, reset_password
from app.modules.accounts.sessions import (
    CurrentSession,
    list_sessions,
    revoke_other_sessions,
    revoke_session,
)
from app.modules.accounts.registration import (
    AlreadyRegistered,
    ResendOutcome,
    VerifyOutcome,
    register_account,
    resend_code,
    verify_email,
)
from app.modules.accounts.password_strength import LABELS, PasswordStrength, password_strength
from app.modules.accounts.validation import (
    EMAIL_MAX_LENGTH,
    EMAIL_PATTERN,
    FieldError,
    password_errors,
    validate_registration,
)

router = APIRouter(prefix="/auth", tags=["accounts"])

# Los campos se reciben sin tipo para que un dato faltante o mal escrito salga
# como aviso por campo, con la misma forma que los demás.
class RegisterRequest(BaseModel):
    first_name: Any = Field(default=None, examples=["Ana"])
    last_name: Any = Field(default=None, examples=["Torres"])
    email: Any = Field(default=None, examples=["ana@example.com"])
    password: Any = Field(default=None, examples=["Ejemplo-2026"])
    phone: Any = Field(default=None, examples=["+525512345678"])
    country: Any = Field(default=None, examples=["MX"])
    birth_date: Any = Field(default=None, examples=["1995-03-14"])
    preferred_language: Any = Field(default=None, examples=["es"])


class RegisterResponse(BaseModel):
    status: Literal["verification_required"]
    email: str


class VerifyEmailRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])
    code: Any = Field(default=None, examples=["123456"])


class VerifyEmailResponse(BaseModel):
    status: Literal["verified"]


class ResendCodeRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])


class ResendCodeResponse(BaseModel):
    status: Literal["sent"]


class ErrorItem(BaseModel):
    field: str
    code: str
    message: str


class ErrorResponse(BaseModel):
    errors: list[ErrorItem]


def error_response(status_code: int, errors: list[FieldError], **extra) -> JSONResponse:
    body = {
        "errors": [
            {"field": error.field, "code": error.code, "message": error.message}
            for error in errors
        ],
        **extra,
    }
    headers = {"Retry-After": str(extra["retry_after"])} if "retry_after" in extra else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def required_text(body: BaseModel, fields: tuple[str, ...]) -> tuple[dict[str, str], list[FieldError]]:
    """Toma campos de texto obligatorios de una petición corta."""
    values, errors = {}, []
    for field in fields:
        value = getattr(body, field)
        if not isinstance(value, str) or value.strip() == "":
            errors.append(FieldError(field, "required", "Este dato es obligatorio."))
        else:
            values[field] = value
    return values, errors


@router.post(
    "/register",
    status_code=201,
    response_model=RegisterResponse,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Crear una cuenta",
)
def register(body: RegisterRequest, request: Request):
    """Crea la cuenta y envía un código al correo. La cuenta no puede iniciar
    sesión hasta que el correo se compruebe con ese código."""
    # La edad se cuenta con la fecha del país de la persona en este instante.
    data, errors = validate_registration(body.model_dump(), datetime.now(timezone.utc))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    try:
        register_account(state.pool, data, state.settings, state.code_sender)
    except AlreadyRegistered as error:
        messages = {
            "email": "Ya existe una cuenta con este correo.",
            "phone": "Ya existe una cuenta con este teléfono.",
        }
        return error_response(
            409, [FieldError(error.field, "already_registered", messages[error.field])]
        )
    return RegisterResponse(status="verification_required", email=data.email)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Comprobar el correo con el código",
)
def verify(body: VerifyEmailRequest, request: Request):
    values, errors = required_text(body, ("email", "code"))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = verify_email(state.pool, values["email"], values["code"], state.settings)

    if result.outcome is VerifyOutcome.VERIFIED:
        return VerifyEmailResponse(status="verified")
    if result.outcome is VerifyOutcome.ALREADY_VERIFIED:
        return error_response(
            409, [FieldError("email", "already_verified", "Este correo ya estaba comprobado.")]
        )
    if result.outcome is VerifyOutcome.CODE_EXPIRED:
        return error_response(
            400, [FieldError("code", "code_expired", "El código venció. Pide uno nuevo.")]
        )
    if result.outcome is VerifyOutcome.TOO_MANY_ATTEMPTS:
        return error_response(
            400,
            [FieldError("code", "too_many_attempts", "Demasiados intentos. Pide un código nuevo.")],
        )
    extra = {} if result.attempts_left is None else {"attempts_left": result.attempts_left}
    return error_response(
        400, [FieldError("code", "invalid_code", "El código no es correcto.")], **extra
    )


@router.post(
    "/resend-code",
    response_model=ResendCodeResponse,
    responses={422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Pedir otro código para comprobar el correo",
)
def resend(body: ResendCodeRequest, request: Request):
    values, errors = required_text(body, ("email",))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = resend_code(state.pool, values["email"], state.settings, state.code_sender)

    if result.outcome is ResendOutcome.WAIT:
        return error_response(
            429,
            [
                FieldError(
                    "email",
                    "wait",
                    f"Espera {result.retry_after_seconds} segundos para pedir otro código.",
                )
            ],
            retry_after=result.retry_after_seconds,
        )
    if result.outcome is ResendOutcome.HOURLY_LIMIT:
        return error_response(
            429,
            [FieldError("email", "hourly_limit", "Ya pediste demasiados códigos. Intenta más tarde.")],
        )
    return ResendCodeResponse(status="sent")


class CorrectEmailRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])
    password: Any = Field(default=None, examples=["Ejemplo-2026"])
    new_email: Any = Field(default=None, examples=["ana.torres@example.com"])


@router.post(
    "/correct-unverified-email",
    response_model=RegisterResponse,
    responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
               429: {"model": ErrorResponse}},
    summary="Corregir el correo de una cuenta que todavía no lo ha comprobado",
)
def correct_email(body: CorrectEmailRequest, request: Request):
    """Quien se equivocó de correo al registrarse lo corrige: manda su correo, la
    contraseña con la que se registró y el correo correcto. El código nuevo va
    al correo nuevo y deja sin efecto a los anteriores. Solo sirve para una
    cuenta sin comprobar; una contraseña incorrecta y un correo sin cuenta
    contestan igual."""
    values, errors = required_text(body, ("email", "password", "new_email"))
    if not errors:
        candidate = values["new_email"].strip().lower()
        if len(candidate) > EMAIL_MAX_LENGTH or not EMAIL_PATTERN.match(candidate):
            errors.append(FieldError("new_email", "invalid", "El correo no tiene un formato válido."))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = correct_unverified_email(
        state.pool,
        values["email"],
        values["password"],
        values["new_email"],
        state.settings,
        state.code_sender,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    if result.outcome is CorrectionOutcome.CODE_SENT:
        return RegisterResponse(status="verification_required", email=values["new_email"].strip().lower())
    if result.outcome is CorrectionOutcome.TRY_LATER:
        minutes = -(-result.retry_after_seconds // 60)
        wait = "1 minuto" if minutes == 1 else f"{minutes} minutos"
        return error_response(
            429,
            [FieldError("credentials", "try_later", f"Demasiados intentos. Inténtalo nuevamente en {wait}.")],
            retry_after=result.retry_after_seconds,
        )
    if result.outcome is CorrectionOutcome.ALREADY_VERIFIED:
        return error_response(
            409, [FieldError("email", "already_verified", "Este correo ya está comprobado: no se puede corregir.")]
        )
    if result.outcome is CorrectionOutcome.EMAIL_TAKEN:
        return error_response(
            409, [FieldError("new_email", "already_registered", "Ya existe una cuenta con este correo.")]
        )
    if result.outcome is CorrectionOutcome.SAME_EMAIL:
        return error_response(
            422, [FieldError("new_email", "same_email", "Es el mismo correo con el que te registraste.")]
        )
    if result.outcome is CorrectionOutcome.HOURLY_LIMIT:
        return error_response(
            429, [FieldError("email", "hourly_limit", "Ya pediste demasiados códigos. Inténtalo nuevamente más tarde.")]
        )
    return error_response(
        401, [FieldError("credentials", "invalid_credentials", "El correo o la contraseña no son correctos.")]
    )


# ---------------------------------------------------------------------------
# Recuperar la contraseña (decisiones del 21 de noviembre de 2026)
# ---------------------------------------------------------------------------


class PasswordResetRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])


class PasswordResetRequestResponse(BaseModel):
    status: Literal["code_requested"]


class PasswordResetConfirmRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])
    code: Any = Field(default=None, examples=["123456"])
    new_password: Any = Field(default=None, examples=["Ejemplo-2027"])


class PasswordResetConfirmResponse(BaseModel):
    status: Literal["password_changed"]


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Recuperar la contraseña, paso 1: pedir el código",
)
def password_reset_request(body: PasswordResetRequest, request: Request):
    """Envía un código de 6 dígitos al correo, que dura 30 minutos. Contesta
    siempre lo mismo, tenga o no cuenta ese correo, esté comprobado o no, para
    no revelar quién tiene cuenta. Solo una cuenta con el correo comprobado
    recibe el código."""
    values, errors = required_text(body, ("email",))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    request_password_reset(state.pool, values["email"], state.settings, state.code_sender)
    return PasswordResetRequestResponse(status="code_requested")


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetConfirmResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Recuperar la contraseña, paso 2: el código y la contraseña nueva",
)
def password_reset_confirm(body: PasswordResetConfirmRequest, request: Request):
    """Con el código correcto cambia la contraseña y cierra todas las sesiones
    de la cuenta; la persona inicia sesión de nuevo. La contraseña nueva cumple
    las mismas reglas del registro (formato y no ser fácil de adivinar) y se revisa antes de gastar el código. Un
    correo sin cuenta contesta igual que un código incorrecto."""
    values, errors = required_text(body, ("email", "code", "new_password"))
    if not errors:
        errors = [
            FieldError("new_password", error.code, error.message) for error in password_errors(values["new_password"])
        ]
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = reset_password(
        state.pool,
        values["email"],
        values["code"],
        values["new_password"],
        state.settings,
        state.code_sender,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    if result.outcome is ResetOutcome.CHANGED:
        return PasswordResetConfirmResponse(status="password_changed")
    if result.outcome is ResetOutcome.TRY_LATER:
        minutes = -(-result.retry_after_seconds // 60)
        wait = "1 minuto" if minutes == 1 else f"{minutes} minutos"
        return error_response(
            429,
            [FieldError("credentials", "try_later", f"Demasiados intentos. Inténtalo nuevamente en {wait}.")],
            retry_after=result.retry_after_seconds,
        )
    if result.outcome is ResetOutcome.TOO_WEAK:
        return error_response(
            422,
            [FieldError("new_password", "too_weak", " ".join(("La contraseña es muy fácil de adivinar.", *result.hints)))],
        )
    if result.outcome is ResetOutcome.CODE_EXPIRED:
        return error_response(
            400, [FieldError("code", "code_expired", "El código venció. Pide uno nuevo.")]
        )
    if result.outcome is ResetOutcome.TOO_MANY_ATTEMPTS:
        return error_response(
            400, [FieldError("code", "too_many_attempts", "Demasiados intentos. Pide un código nuevo.")]
        )
    extra = {} if result.attempts_left is None else {"attempts_left": result.attempts_left}
    return error_response(
        400, [FieldError("code", "invalid_code", "El código no es correcto.")], **extra
    )


# ---------------------------------------------------------------------------
# Inicio de sesión y sesión (ADR 0014)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])
    password: Any = Field(default=None, examples=["Ejemplo-2026"])


class LoginResponse(BaseModel):
    status: Literal["code_required"]


class LoginVerifyRequest(BaseModel):
    email: Any = Field(default=None, examples=["ana@example.com"])
    code: Any = Field(default=None, examples=["123456"])


class SessionResponse(BaseModel):
    # La llave no va aquí: viaja en la cookie de sesión, que la página no puede leer.
    status: Literal["session_opened"]
    expires_at: datetime
    # Clave anti-falsificación de esta sesión: la página la manda en el
    # encabezado X-CSRF-Token en cada petición que cambie algo.
    csrf_token: str


class MeResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    country: str
    preferred_language: str
    # Qué vistas tiene la persona (docs/diseno/vistas.md): todas tienen la de cliente.
    is_host: bool
    is_admin: bool
    session_expires_at: datetime
    csrf_token: str


def wait_response(seconds: int | None) -> JSONResponse:
    return error_response(
        429,
        [FieldError("email", "wait", f"Espera {seconds} segundos para pedir otro código.")],
        retry_after=seconds,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
               422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Iniciar sesión, paso 1: correo y contraseña",
)
def login(body: LoginRequest, request: Request):
    """Comprueba el correo y la contraseña y envía un código al correo.
    Todavía no abre la sesión: falta escribir el código en /auth/login/verify."""
    values, errors = required_text(body, ("email", "password"))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = start_login(
        state.pool,
        values["email"],
        values["password"],
        state.settings,
        state.code_sender,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    if result.outcome is LoginOutcome.CODE_SENT:
        return LoginResponse(status="code_required")
    if result.outcome is LoginOutcome.TRY_LATER:
        minutes = -(-result.retry_after_seconds // 60)
        wait = "1 minuto" if minutes == 1 else f"{minutes} minutos"
        return error_response(
            429,
            [FieldError("credentials", "try_later", f"Demasiados intentos. Intenta de nuevo en {wait}.")],
            retry_after=result.retry_after_seconds,
        )
    if result.outcome is LoginOutcome.EMAIL_NOT_VERIFIED:
        return error_response(
            403,
            [FieldError("email", "email_not_verified", "Comprueba tu correo antes de iniciar sesión.")],
        )
    if result.outcome is LoginOutcome.WAIT:
        return wait_response(result.retry_after_seconds)
    if result.outcome is LoginOutcome.HOURLY_LIMIT:
        return error_response(
            429,
            [FieldError("email", "hourly_limit", "Ya pediste demasiados códigos. Intenta más tarde.")],
        )
    return error_response(
        401,
        [FieldError("credentials", "invalid_credentials", "El correo o la contraseña no son correctos.")],
    )


@router.post(
    "/login/verify",
    response_model=SessionResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Iniciar sesión, paso 2: el código",
)
def login_verify(body: LoginVerifyRequest, request: Request, response: Response):
    """Comprueba el código y abre la sesión. La llave se entrega en la cookie
    integro_session, que el código de la página no puede leer; el navegador la
    manda sola en cada petición. El texto de la respuesta no trae la llave."""
    values, errors = required_text(body, ("email", "code"))
    if errors:
        return error_response(422, errors)
    state = request.app.state
    result = finish_login(
        state.pool,
        values["email"],
        values["code"],
        state.settings,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    if result.outcome is SessionOutcome.OPENED:
        set_session_cookie(response, result.token, result.idle_days, state.settings)
        return SessionResponse(
            status="session_opened",
            expires_at=result.expires_at,
            csrf_token=csrf_token(result.token, state.settings),
        )
    if result.outcome is SessionOutcome.CODE_EXPIRED:
        return error_response(
            400, [FieldError("code", "code_expired", "El código venció. Inicia sesión de nuevo.")]
        )
    if result.outcome is SessionOutcome.TOO_MANY_ATTEMPTS:
        return error_response(
            400,
            [FieldError("code", "too_many_attempts", "Demasiados intentos. Inicia sesión de nuevo.")],
        )
    extra = {} if result.attempts_left is None else {"attempts_left": result.attempts_left}
    return error_response(
        400, [FieldError("code", "invalid_code", "El código no es correcto.")], **extra
    )


@router.get(
    "/me",
    response_model=MeResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Quién soy: los datos de la persona con sesión",
)
def me(request: Request, session: CurrentSession = Depends(require_session)):
    """Devuelve los datos de quien tiene la sesión, que llega en la cookie
    integro_session. Los lee como esa persona, así que la base solo le deja
    ver su propia fila. Cada uso renueva la cookie."""
    with user_transaction(request.app.state.pool, session.user_id) as connection:
        row = connection.execute(
            "select id, first_name, last_name, email, country, preferred_language from users"
        ).fetchone()
    return MeResponse(
        id=str(row[0]),
        first_name=row[1],
        last_name=row[2],
        email=row[3],
        country=row[4],
        preferred_language=row[5],
        is_host=session.is_host,
        is_admin=session.is_admin,
        session_expires_at=session.expires_at,
        csrf_token=csrf_token(request.cookies[SESSION_COOKIE], request.app.state.settings),
    )


# ---------------------------------------------------------------------------
# Cerrar sesión y ver las sesiones abiertas (ADR 0015)
# ---------------------------------------------------------------------------


class SessionItem(BaseModel):
    id: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    current: bool


class SessionsResponse(BaseModel):
    sessions: list[SessionItem]


class SignedOutResponse(BaseModel):
    status: Literal["signed_out"]


class ClosedResponse(BaseModel):
    status: Literal["closed"]
    closed: int


def without_cookie(body: dict, settings) -> JSONResponse:
    """Una respuesta que además le pide al navegador borrar la cookie de sesión."""
    response = JSONResponse(status_code=200, content=body)
    clear_session_cookie(response, settings)
    return response


@router.post(
    "/logout",
    response_model=SignedOutResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Cerrar la sesión actual",
)
def logout(request: Request, session: CurrentSession = Depends(require_session_for_change)):
    """Cierra la sesión con la que llega la petición y borra su cookie. La
    llave deja de servir en ese instante y no vuelve a servir."""
    state = request.app.state
    revoke_session(state.pool, session.user_id, session.session_id)
    return without_cookie({"status": "signed_out"}, state.settings)


@router.get(
    "/sessions",
    response_model=SessionsResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Mis sesiones abiertas",
)
def my_sessions(request: Request, session: CurrentSession = Depends(require_session)):
    """Dónde tiene sesión abierta la persona: cuándo se abrió cada una, su
    último uso, el navegador, la dirección y cuál es la actual. Nunca trae la
    llave ni su huella, ni sesiones de otra persona."""
    return SessionsResponse(
        sessions=[
            SessionItem(
                id=str(item.session_id),
                created_at=item.created_at,
                last_used_at=item.last_used_at,
                expires_at=item.expires_at,
                ip_address=item.ip_address,
                user_agent=item.user_agent,
                current=item.current,
            )
            for item in list_sessions(request.app.state.pool, session)
        ]
    )


@router.post(
    "/sessions/close-others",
    response_model=ClosedResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Cerrar todas mis demás sesiones",
)
def close_other_sessions(request: Request, session: CurrentSession = Depends(require_session_for_change)):
    """Cierra todas las sesiones de la persona menos la actual."""
    closed = revoke_other_sessions(request.app.state.pool, session.user_id, session.session_id)
    return ClosedResponse(status="closed", closed=closed)


@router.delete(
    "/sessions/{session_id}",
    response_model=ClosedResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Cerrar una de mis sesiones",
)
def close_session(session_id: str, request: Request, session: CurrentSession = Depends(require_session_for_change)):
    """Cierra una sesión de la persona, por su id. La de otra persona, una
    que no existe o una ya cerrada responden igual: 404. Si es la actual,
    además se borra la cookie."""
    state = request.app.state
    try:
        target = UUID(session_id)
    except ValueError:
        target = None
    if target is None or not revoke_session(state.pool, session.user_id, target):
        return error_response(404, [FieldError("session", "not_found", "Esa sesión no existe o ya estaba cerrada.")])
    if target == session.session_id:
        return without_cookie({"status": "closed", "closed": 1}, state.settings)
    return ClosedResponse(status="closed", closed=1)


# ---------------------------------------------------------------------------
# Qué tan confiable es una contraseña
# ---------------------------------------------------------------------------


class PasswordStrengthRequest(BaseModel):
    password: Any = Field(default=None, examples=["Lluvia-Verde-26"])
    first_name: Any = Field(default=None, examples=["Ana"])
    last_name: Any = Field(default=None, examples=["Torres"])
    email: Any = Field(default=None, examples=["ana@example.com"])


class PasswordStrengthResponse(BaseModel):
    level: Literal["low", "medium", "reliable", "very_reliable"]
    label: str
    weaknesses: list[str]
    hints: list[str]
    # Lo que suma: lo que ya le subió el nivel y cómo subirlo todavía.
    strengths: list[str]
    raise_hints: list[str]
    meets_rules: bool
    accepted: bool
    errors: list[ErrorItem]


def optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


@router.post(
    "/password-strength",
    response_model=PasswordStrengthResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Qué tan confiable es una contraseña",
)
def strength(body: PasswordStrengthRequest):
    """Califica una contraseña mientras la persona la escribe: bajo, medio,
    confiable o muy confiable. No guarda ni anota nada. accepted dice si el
    registro la aceptaría: cumple las reglas y alcanza al menos el nivel medio.
    weaknesses y hints dicen lo que le resta; strengths y raise_hints, lo que
    le suma."""
    if not isinstance(body.password, str) or body.password == "":
        return error_response(422, [FieldError("password", "required", "Este dato es obligatorio.")])

    rule_errors = password_errors(body.password)
    # Una contraseña que no cumple las reglas no se puede usar: sale como baja.
    if rule_errors:
        result = PasswordStrength(level="low", label=LABELS["low"], weaknesses=())
    else:
        result = password_strength(
            body.password,
            first_name=optional_text(body.first_name),
            last_name=optional_text(body.last_name),
            email=optional_text(body.email),
        )
    return PasswordStrengthResponse(
        level=result.level,
        label=result.label,
        weaknesses=list(result.weaknesses),
        hints=list(result.hints),
        strengths=list(result.strengths),
        raise_hints=list(result.raise_hints),
        meets_rules=not rule_errors,
        accepted=not rule_errors and result.is_enough,
        errors=[ErrorItem(field=e.field, code=e.code, message=e.message) for e in rule_errors],
    )
