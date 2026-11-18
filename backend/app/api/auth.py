"""Quién hace la petición: lo que usa cualquier ruta que necesite una sesión.

La llave de sesión viaja en el encabezado de cada petición:

    Authorization: Bearer <llave>

Una ruta pide la sesión así:

    def my_route(session: CurrentSession = Depends(require_session)): ...

y después abre su transacción con user_transaction(pool, session.user_id),
para que la base solo le deje ver lo que es de esa persona.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.modules.accounts.sessions import CurrentSession, authenticate

SCHEME = "bearer"


class NotAuthenticated(Exception):
    """La petición no trae una sesión que sirva."""


def bearer_token(header: str | None) -> str | None:
    """Saca la llave del encabezado Authorization, o None si no viene bien."""
    parts = (header or "").split()
    if len(parts) != 2 or parts[0].lower() != SCHEME:
        return None
    return parts[1]


def require_session(request: Request) -> CurrentSession:
    """Dependencia de FastAPI: devuelve la sesión o corta la petición con 401."""
    state = request.app.state
    session = authenticate(state.pool, bearer_token(request.headers.get("authorization")), state.settings)
    if session is None:
        raise NotAuthenticated()
    return session


def not_authenticated_response(request: Request, error: NotAuthenticated) -> JSONResponse:
    """La misma respuesta para llave ausente, inventada, vencida o cerrada."""
    return JSONResponse(
        status_code=401,
        content={
            "errors": [
                {
                    "field": "authorization",
                    "code": "not_authenticated",
                    "message": "Inicia sesión para continuar.",
                }
            ]
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
