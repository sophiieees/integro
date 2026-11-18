"""Rutas del módulo de Cuentas: registro y comprobación del correo.

Los avisos salen siempre con la misma forma, para que el formulario los
ponga junto a su campo:

    {"errors": [{"field": "password", "code": "too_short", "message": "..."}]}
"""

from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.modules.accounts.registration import (
    AlreadyRegistered,
    ResendOutcome,
    VerifyOutcome,
    register_account,
    resend_code,
    verify_email,
)
from app.modules.accounts.validation import FieldError, validate_registration

router = APIRouter(prefix="/auth", tags=["accounts"])

# La edad se calcula con la fecha de la Ciudad de México, no con la del servidor.
PLATFORM_TIME_ZONE = ZoneInfo("America/Mexico_City")


def today_on_the_platform() -> date:
    return datetime.now(PLATFORM_TIME_ZONE).date()


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
    data, errors = validate_registration(body.model_dump(), today_on_the_platform())
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
