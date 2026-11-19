"""Rutas del módulo de Cuentas: registro y comprobación del correo.

Los avisos salen siempre con la misma forma, para que el formulario los
ponga junto a su campo:

    {"errors": [{"field": "password", "code": "too_short", "message": "..."}]}
"""

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import require_session
from app.database.transaction import user_transaction
from app.modules.accounts.login import LoginOutcome, SessionOutcome, finish_login, start_login
from app.modules.accounts.sessions import CurrentSession
from app.modules.accounts.registration import (
    AlreadyRegistered,
    ResendOutcome,
    VerifyOutcome,
    register_account,
    resend_code,
    verify_email,
)
from app.modules.accounts.password_strength import LABELS, PasswordStrength, password_strength
from app.modules.accounts.validation import FieldError, password_errors, validate_registration

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
    token: str
    token_type: Literal["Bearer"]
    expires_at: datetime


class MeResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    country: str
    preferred_language: str
    is_host: bool
    session_expires_at: datetime


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
def login_verify(body: LoginVerifyRequest, request: Request):
    """Comprueba el código y entrega la llave de la sesión. La llave se manda
    después en cada petición, en el encabezado Authorization: Bearer."""
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
        return SessionResponse(token=result.token, token_type="Bearer", expires_at=result.expires_at)
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
    """Devuelve los datos de quien tiene la sesión. Los lee como esa persona,
    así que la base solo le deja ver su propia fila."""
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
        session_expires_at=session.expires_at,
    )


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
