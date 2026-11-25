"""Rutas del módulo de Anfitriones: pedir el perfil de anfitrión y verlo (pieza 3.1).

Los avisos salen con la misma forma que los de Cuentas:

    {"errors": [{"field": "host_profile", "code": "no_host_profile", "message": "..."}]}
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.auth import require_session
from app.api.protection import require_session_for_change
from app.modules.accounts.sessions import CurrentSession
from app.modules.hosts.profile import HostProfile, RequestOutcome, read_host_profile, request_host_profile

router = APIRouter(prefix="/host-profile", tags=["hosts"])


class HostProfileResponse(BaseModel):
    # new: recién pedido. verified: identidad comprobada. suspended: suspendido por la plataforma.
    level: Literal["new", "verified", "suspended"]
    created_at: datetime


class ErrorItem(BaseModel):
    field: str
    code: str
    message: str


class ErrorResponse(BaseModel):
    errors: list[ErrorItem]


def error(status_code: int, field: str, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"errors": [{"field": field, "code": code, "message": message}]})


def body_of(profile: HostProfile) -> HostProfileResponse:
    return HostProfileResponse(level=profile.level, created_at=profile.created_at)


@router.post(
    "",
    status_code=201,
    response_model=HostProfileResponse,
    responses={
        200: {"model": HostProfileResponse, "description": "Ya tenía perfil de anfitrión: se entrega el que tiene."},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Pedir ser anfitrión",
)
def request_profile(
    request: Request, response: Response, session: CurrentSession = Depends(require_session_for_change)
):
    """Crea el perfil de anfitrión de la persona con sesión, con nivel `new`. No lleva cuerpo: quién lo pide sale
    de la sesión. Responde `201` al crearlo y `200`, con el perfil que ya tiene, si lo vuelve a pedir. `403` con
    `email_not_verified` si su correo no está comprobado. Como toda ruta que cambia algo, pide las tres defensas
    contra peticiones hechas desde páginas ajenas."""
    result = request_host_profile(request.app.state.pool, session.user_id)
    if result.outcome is RequestOutcome.EMAIL_NOT_VERIFIED:
        return error(403, "email", "email_not_verified", "Comprueba tu correo antes de pedir tu perfil de anfitrión.")
    if result.outcome is RequestOutcome.EXISTING:
        response.status_code = 200
    return body_of(result.profile)


@router.get(
    "",
    response_model=HostProfileResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Ver mi perfil de anfitrión",
)
def my_profile(request: Request, session: CurrentSession = Depends(require_session)):
    """El perfil de anfitrión de la persona con sesión: su nivel y cuándo se creó. `404` con `no_host_profile` si
    todavía no lo ha pedido. Nunca entrega la cuenta de Stripe ni datos de otra persona."""
    profile = read_host_profile(request.app.state.pool, session.user_id)
    if profile is None:
        return error(404, "host_profile", "no_host_profile", "Todavía no tienes perfil de anfitrión.")
    return body_of(profile)
