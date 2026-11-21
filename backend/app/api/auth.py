"""Quién hace la petición: lo que usa cualquier ruta que necesite una sesión.

La llave de sesión viaja en una cookie que el código de la página no puede
leer (ADR 0015, decisión de Sophia del 19 de noviembre de 2026):

    Set-Cookie: integro_session=<llave>; HttpOnly; SameSite=Strict; Path=/; Max-Age=...; Secure

- HttpOnly: un script de la página no puede leerla.
- SameSite=Strict: el navegador solo la manda en peticiones hechas desde el
  mismo sitio, no desde una página ajena.
- Max-Age: el plazo sin uso de la sesión (30 días huésped, 7 anfitrión). Cada
  petición con sesión la vuelve a entregar, para renovar ese plazo.
- Secure: solo viaja por HTTPS. La apaga SESSION_COOKIE_SECURE=false, que es
  para desarrollo, donde el servidor local no tiene HTTPS.

Ya no se acepta la llave en el encabezado Authorization.

Una ruta pide la sesión así:

    def my_route(session: CurrentSession = Depends(require_session)): ...

y después abre su transacción con user_transaction(pool, session.user_id),
para que la base solo le deje ver lo que es de esa persona.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.modules.accounts.sessions import CurrentSession, authenticate, idle_days

SESSION_COOKIE = "integro_session"
SECONDS_PER_DAY = 24 * 60 * 60


class NotAuthenticated(Exception):
    """La petición no trae una sesión que sirva."""


def set_session_cookie(
    response: Response, token: str, days: int, settings: Settings, *, seconds: int | None = None
) -> None:
    """Entrega la llave al navegador en la cookie de sesión, por esos días.

    La sesión de un administrador es corta: su cookie dura los segundos que le quedan (seconds).
    """
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=days * SECONDS_PER_DAY if seconds is None else seconds,
        path="/",
        httponly=True,
        samesite="strict",
        secure=settings.session_cookie_secure,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    """Le pide al navegador que borre la cookie de sesión. La página no puede borrarla sola."""
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=settings.session_cookie_secure,
    )


def require_session(request: Request, response: Response) -> CurrentSession:
    """Dependencia de FastAPI: devuelve la sesión o corta la petición con 401.

    Cuando la sesión sirve, vuelve a entregar la cookie para que dure lo mismo
    que el plazo que la base acaba de renovar. La cookie se agrega a la
    respuesta de la ruta siempre que la ruta devuelva sus datos y no una
    respuesta armada a mano.
    """
    state = request.app.state
    token = request.cookies.get(SESSION_COOKIE)
    session = authenticate(state.pool, token, state.settings)
    if session is None:
        raise NotAuthenticated()
    set_session_cookie(
        response, token, idle_days(session.is_host, state.settings), state.settings, seconds=session.cookie_seconds
    )
    return session


def not_authenticated_response(request: Request, error: NotAuthenticated) -> JSONResponse:
    """La misma respuesta para cookie ausente, inventada, vencida o de sesión cerrada."""
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
    )
