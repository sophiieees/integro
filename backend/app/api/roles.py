"""Quién puede entrar a cada vista: anfitrión y administrador.

Las vistas de la web (docs/diseno/vistas.md) cambian según quién es la persona,
pero la cabecera es comodidad, no seguridad: el permiso lo da la API en cada
ruta. Una ruta de anfitrión o de administrador lo pide así:

    def my_route(session: CurrentSession = Depends(require_host)): ...
    def my_other_route(session: CurrentSession = Depends(require_admin_for_change)): ...

- Sin sesión responde 401, como cualquier ruta con sesión.
- Con sesión pero sin el papel responde 403, con el código host_only o admin_only.
- Cada petición revisa el papel en la base: quien deja de ser administrador deja
  de poder entrar en su siguiente petición, aunque su sesión siga abierta.

Las variantes _for_change son para las rutas que cambian algo: además piden las
tres defensas contra peticiones hechas desde páginas ajenas (protection.py).

Anfitrión es quien tiene perfil de anfitrión. Administrador es quien está en la
tabla admins, que solo se llena a mano en pgAdmin. Los dos necesitan tener el
Authenticator activo (ADR 0018): sin él responden 403 con el código
two_factor_setup_required. Y una sesión en espera del Authenticator ni siquiera
llega aquí: require_session la corta antes con second_factor_required.
"""

from fastapi import Depends

from app.api.auth import require_session
from app.api.protection import Forbidden, require_session_for_change
from app.modules.accounts.sessions import CurrentSession

HOST_ONLY = ("host_only", "Esta función es solo para anfitriones.")
ADMIN_ONLY = ("admin_only", "Esta función es solo para el equipo de Íntegro.")
# Decisión de Sophia del 25 de noviembre de 2026 (bitácora 42.2 y la pieza 3.3): un anfitrión o un administrador que
# todavía no activa su Authenticator entra y usa lo de cliente, pero no las funciones de anfitrión ni las del equipo.
SETUP_REQUIRED = ("two_factor_setup_required", "Activa tu Authenticator para usar esta función.")


def _host(session: CurrentSession) -> CurrentSession:
    if not session.is_host:
        raise Forbidden(*HOST_ONLY)
    if not session.has_second_factor:
        raise Forbidden(*SETUP_REQUIRED)
    return session


def _admin(session: CurrentSession) -> CurrentSession:
    if not session.is_admin:
        raise Forbidden(*ADMIN_ONLY)
    if not session.has_second_factor:
        raise Forbidden(*SETUP_REQUIRED)
    return session


def require_host(session: CurrentSession = Depends(require_session)) -> CurrentSession:
    """Una ruta que solo lee y es de quien tiene perfil de anfitrión."""
    return _host(session)


def require_admin(session: CurrentSession = Depends(require_session)) -> CurrentSession:
    """Una ruta que solo lee y es del equipo."""
    return _admin(session)


def require_host_for_change(session: CurrentSession = Depends(require_session_for_change)) -> CurrentSession:
    """Una ruta que cambia algo y es de quien tiene perfil de anfitrión."""
    return _host(session)


def require_admin_for_change(session: CurrentSession = Depends(require_session_for_change)) -> CurrentSession:
    """Una ruta que cambia algo y es del equipo."""
    return _admin(session)
