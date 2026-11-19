"""Defensas de las peticiones con sesión que cambian algo.

La llave de sesión viaja en una cookie, y una cookie viaja sola: una página
ajena podría hacer que el navegador de la persona mande una petición a
Íntegro con su sesión, sin que ella se dé cuenta. Sophia eligió las tres
defensas (19 de noviembre de 2026):

1. La cookie solo se manda desde el mismo sitio (SameSite=Strict, en auth.py).
2. Se revisa de dónde viene la petición: el navegador lo dice en el
   encabezado Origin. Tiene que ser la dirección de la propia API o una de la
   lista ALLOWED_ORIGINS.
3. Clave anti-falsificación: la API le entrega a la página un valor ligado a
   su sesión (en /auth/login/verify y en /auth/me) y la página lo manda en el
   encabezado X-CSRF-Token. Una página ajena no puede leerlo.

Una ruta que cambia algo pide la sesión así:

    def my_route(session: CurrentSession = Depends(require_session_for_change)): ...

Las rutas que solo leen siguen usando require_session.
"""

import hashlib
import hmac
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.api.auth import SESSION_COOKIE, require_session
from app.core.config import Settings
from app.modules.accounts.sessions import CurrentSession

CSRF_HEADER = "X-CSRF-Token"
# Separa este uso de la llave secreta del de los códigos de un solo uso.
CSRF_LABEL = b"csrf:"


class Forbidden(Exception):
    """La petición trae sesión, pero no pasó una de las defensas."""

    def __init__(self, code: str, message: str):
        super().__init__(code)
        self.code = code
        self.message = message


def csrf_token(session_token: str, settings: Settings) -> str:
    """La clave anti-falsificación de una sesión.

    Se calcula con la llave secreta del servidor a partir de la llave de
    sesión: no se guarda en ningún lado, es distinta para cada sesión y de
    ella no se puede sacar la llave de sesión.
    """
    key = settings.code_hash_secret.get_secret_value().encode("utf-8")
    return hmac.new(key, CSRF_LABEL + session_token.encode("utf-8"), hashlib.sha256).hexdigest()


def origin_of(address: str | None) -> str | None:
    """El origen de una dirección: esquema, servidor y puerto. None si no tiene forma de dirección."""
    parts = urlsplit((address or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def allowed_origins(request: Request, settings: Settings) -> set[str]:
    """La dirección de la propia API y las de la lista de la configuración."""
    origins = {origin_of(str(request.base_url))}
    origins.update(origin_of(item) for item in settings.allowed_origins.split(","))
    origins.discard(None)
    return origins


def check_origin(request: Request, settings: Settings) -> None:
    """Corta la petición si no viene de una dirección de Íntegro.

    El navegador manda Origin en toda petición que cambia algo. Si no viene
    se mira Referer; si tampoco, la petición se rechaza.
    """
    header = request.headers.get("origin")
    # Con Origin presente solo cuenta Origin, aunque no tenga forma de dirección (por ejemplo "null").
    origin = origin_of(header) if header is not None else origin_of(request.headers.get("referer"))
    if origin is None or origin not in allowed_origins(request, settings):
        raise Forbidden("origin_not_allowed", "La petición no viene de una página de Íntegro.")


def require_session_for_change(request: Request, response: Response) -> CurrentSession:
    """Dependencia de FastAPI para las rutas con sesión que cambian algo.

    Primero se revisa de dónde viene la petición, sin tocar la sesión: una
    petición ajena no renueva nada. Después la sesión (401 si no la hay) y al
    final la clave anti-falsificación.
    """
    settings = request.app.state.settings
    check_origin(request, settings)
    session = require_session(request, response)
    sent = request.headers.get(CSRF_HEADER) or ""
    expected = csrf_token(request.cookies[SESSION_COOKIE], settings)
    if not hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8")):
        raise Forbidden("csrf_failed", "Falta la clave de la página o no es la de esta sesión. Recarga la página.")
    return session


def forbidden_response(request: Request, error: Forbidden) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"errors": [{"field": "request", "code": error.code, "message": error.message}]},
    )
