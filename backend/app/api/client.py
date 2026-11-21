"""Quién hace la petición y por dónde llegó: dirección IP y dirección propia de la API.

En la computadora de Sophia la petición llega directo y estos datos salen de la conexión. En Vercel llega por su
proxy: la dirección de quien pide y si fue por HTTPS vienen en X-Forwarded-For y X-Forwarded-Proto. Esos encabezados
los puede escribir cualquiera, así que solo se creen con TRUST_PROXY_HEADERS encendido (Settings.trust_proxy_headers),
que se enciende solo donde el proxy los reescribe siempre. Sin eso, una persona podría fingir otra dirección para
esquivar la espera por dispositivo (ADR 0014) o fingir el origen de la página.
"""

from urllib.parse import urlsplit

from fastapi import Request

from app.core.config import Settings


def origin_of(address: str | None) -> str | None:
    """El origen de una dirección: esquema, servidor y puerto. None si no tiene forma de dirección."""
    parts = urlsplit((address or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def first_value(header: str | None) -> str:
    """El primer valor de un encabezado de lista («a, b, c» es «a»). Vacío si no hay."""
    return (header or "").split(",")[0].strip()


def client_ip(request: Request, settings: Settings | None = None) -> str | None:
    """La dirección IP de quien hace la petición, o None si no se sabe.

    Con TRUST_PROXY_HEADERS, la primera de X-Forwarded-For (la de quien pidió, según el proxy); si no viene, la
    de la conexión. Lo que no sea una IP válida lo descarta quien la usa (login.clean_ip).
    """
    settings = settings or request.app.state.settings
    if settings.trust_proxy_headers:
        forwarded = first_value(request.headers.get("x-forwarded-for"))
        if forwarded:
            return forwarded
    return request.client.host if request.client else None


def own_origin(request: Request, settings: Settings | None = None) -> str | None:
    """El origen de la propia API: el que la página usa para hablarle y que el navegador manda en Origin.

    Con TRUST_PROXY_HEADERS se arma con X-Forwarded-Proto (http o https) y X-Forwarded-Host o Host: detrás de
    Vercel la API ve HTTP aunque la persona entró por HTTPS, y sin esto toda petición que cambia algo daría 403.
    """
    settings = settings or request.app.state.settings
    if settings.trust_proxy_headers:
        scheme = first_value(request.headers.get("x-forwarded-proto")).lower()
        host = first_value(request.headers.get("x-forwarded-host")) or request.headers.get("host", "")
        if scheme in ("http", "https") and host:
            return origin_of(f"{scheme}://{host}")
    return origin_of(str(request.base_url))
