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
tabla admins, que solo se llena a mano en pgAdmin. Todavía falta, para las rutas
del panel, el tope de 30 minutos sin uso y de 12 horas de sesión, y el segundo
factor (ADR 0014): una ruta de administrador no debe publicarse hasta tenerlos.
"""

from fastapi import Depends

from app.api.auth import require_session
from app.api.protection import Forbidden, require_session_for_change
from app.modules.accounts.sessions import CurrentSession

HOST_ONLY = ("host_only", "Esta función es solo para anfitriones.")
ADMIN_ONLY = ("admin_only", "Esta función es solo para el equipo de Íntegro.")


def _host(session: CurrentSession) -> CurrentSession:
    if not session.is_host:
        raise Forbidden(*HOST_ONLY)
    return session


def _admin(session: CurrentSession) -> CurrentSession:
    if not session.is_admin:
        raise Forbidden(*ADMIN_ONLY)
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
