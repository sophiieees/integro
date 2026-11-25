"""Sesiones: reconocer a la persona en cada petición (ADR 0014 y ADR 0015).

La sesión vive en la tabla sessions. La persona manda su llave en cada
petición; aquí se busca la huella de esa llave. La sesión sirve mientras
exista, no se haya cerrado y no haya pasado su tiempo sin uso: 30 días para
un huésped y 7 para un anfitrión. Cada uso renueva ese plazo.

Quien es administrador (tabla admins) tiene una sesión corta en todo el sitio,
no solo en las pantallas de administración (decisión de Sophia del 21 de
noviembre de 2026): se cierra a los 30 minutos sin uso y, aunque la use todo
el tiempo, a las 12 horas de haber iniciado sesión. Eso vale también para una
sesión que se abrió antes de que la persona fuera administradora: el papel se
lee en cada petición. Si es anfitrión y administrador a la vez, gana el límite
del administrador. Una sesión vencida por estos límites se cierra en la base.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.database.transaction import system_transaction, user_transaction
from app.modules.accounts.security import hash_session_token

# Una llave de sesión real mide 43 caracteres. Lo que pase de este largo ni se busca.
TOKEN_MAX_LENGTH = 200


@dataclass(frozen=True)
class CurrentSession:
    """La sesión con la que llegó la petición."""

    session_id: UUID
    user_id: UUID
    is_host: bool
    # Está en la tabla admins (solo se llena a mano). Se revisa en cada petición.
    is_admin: bool
    expires_at: datetime
    # Segundos que debe durar la cookie de un administrador (lo que le queda a la sesión). None para los demás,
    # cuya cookie dura los días de su tipo de sesión.
    cookie_seconds: int | None = None
    # La persona tiene el Authenticator activo (pieza 3.2). Se revisa en cada petición.
    has_second_factor: bool = False
    # La sesión está en espera: la persona tiene el Authenticator activo y esta sesión todavía no lo pasa, o ya
    # pasaron los días para volver a pedirlo (pieza 3.3). Una sesión en espera no sirve para nada más que para
    # escribir el código o cerrar la sesión.
    second_factor_pending: bool = False


def idle_days(is_host: bool, settings: Settings) -> int:
    """Días sin uso que aguanta una sesión. El anfitrión maneja dinero y
    propiedades, por eso la suya dura menos."""
    return settings.session_idle_days_host if is_host else settings.session_idle_days_guest


def authenticate(pool: ConnectionPool, token: str | None, settings: Settings) -> CurrentSession | None:
    """Devuelve la sesión de esa llave, o None si no sirve.

    No sirve si no existe, si se cerró o si ya venció. Cuando sirve, anota el
    uso y renueva el plazo. Es anfitrión quien tiene perfil de anfitrión en
    ese momento, aunque haya abierto la sesión siendo huésped, y es
    administrador quien está en la tabla admins en ese momento.
    """
    if not isinstance(token, str) or not token or len(token) > TOKEN_MAX_LENGTH:
        return None
    with system_transaction(pool) as connection:
        row = connection.execute(
            "select s.id, s.user_id, h.is_host, a.is_admin, "
            # Un administrador pierde la sesión si pasó el tiempo sin uso o el tope desde que la abrió.
            "(a.is_admin and (s.last_used_at < now() - make_interval(mins => %s) "
            "  or s.created_at < now() - make_interval(hours => %s))), "
            # Quien tiene el Authenticator activo necesita que esta sesión lo haya pasado, y no hace demasiado.
            "t.active, "
            "(t.active and (s.second_factor_at is null or s.second_factor_at <= now() - make_interval(days => %s))) "
            "from sessions s "
            "cross join lateral (select exists (select 1 from host_profiles h where h.user_id = s.user_id) as is_host) h "
            "cross join lateral (select exists (select 1 from admins a where a.user_id = s.user_id) as is_admin) a "
            "cross join lateral (select exists (select 1 from user_totp t where t.user_id = s.user_id "
            "  and t.confirmed_at is not null) as active) t "
            "where s.token_hash = %s and s.revoked_at is null and s.expires_at > now() "
            "for update of s",
            (
                settings.session_idle_minutes_admin,
                settings.session_max_hours_admin,
                settings.two_factor_reverify_days,
                hash_session_token(token),
            ),
        ).fetchone()
        if row is None:
            return None
        session_id, user_id, is_host, is_admin, admin_timed_out, has_second_factor, second_factor_pending = row
        if admin_timed_out:
            connection.execute("update sessions set revoked_at = now() where id = %s", (session_id,))
            return None
        if is_admin:
            expires_at, cookie_seconds = connection.execute(
                "update sessions set last_used_at = now(), "
                "expires_at = least(now() + make_interval(mins => %s), created_at + make_interval(hours => %s)) "
                "where id = %s returning expires_at, greatest(1, ceil(extract(epoch from expires_at - now()))::int)",
                (settings.session_idle_minutes_admin, settings.session_max_hours_admin, session_id),
            ).fetchone()
        else:
            cookie_seconds = None
            expires_at = connection.execute(
                "update sessions set last_used_at = now(), expires_at = now() + make_interval(days => %s) "
                "where id = %s returning expires_at",
                (idle_days(is_host, settings), session_id),
            ).fetchone()[0]
    return CurrentSession(
        session_id=session_id,
        user_id=user_id,
        is_host=is_host,
        is_admin=is_admin,
        expires_at=expires_at,
        cookie_seconds=cookie_seconds,
        has_second_factor=has_second_factor,
        second_factor_pending=second_factor_pending,
    )


@dataclass(frozen=True)
class SessionInfo:
    """Una sesión abierta, como la ve su dueño. Sin la llave ni su huella."""

    session_id: UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    current: bool


def list_sessions(pool: ConnectionPool, session: CurrentSession) -> list[SessionInfo]:
    """Las sesiones abiertas de la persona, de la más usada recientemente a la menos.

    Se leen como esa persona: la base solo le deja ver las suyas, y no le
    deja leer la huella de la llave. Las cerradas y las vencidas no salen.
    """
    with user_transaction(pool, session.user_id) as connection:
        rows = connection.execute(
            "select id, created_at, last_used_at, expires_at, host(ip_address), user_agent from sessions "
            "where revoked_at is null and expires_at > now() "
            "order by last_used_at desc, created_at desc, id"
        ).fetchall()
    return [
        SessionInfo(
            session_id=row[0],
            created_at=row[1],
            last_used_at=row[2],
            expires_at=row[3],
            ip_address=row[4],
            user_agent=row[5],
            current=row[0] == session.session_id,
        )
        for row in rows
    ]


def revoke_session(pool: ConnectionPool, user_id: UUID, session_id: UUID) -> bool:
    """Cierra una sesión de esa persona. Devuelve si había algo que cerrar.

    Cerrar lo hace el sistema, y siempre con el id de la persona: nadie
    cierra la sesión de otro. Una sesión cerrada no vuelve a abrirse.
    """
    with system_transaction(pool) as connection:
        row = connection.execute(
            "update sessions set revoked_at = now() "
            "where id = %s and user_id = %s and revoked_at is null and expires_at > now() returning id",
            (session_id, user_id),
        ).fetchone()
    return row is not None


def revoke_other_sessions(pool: ConnectionPool, user_id: UUID, current_session_id: UUID) -> int:
    """Cierra todas las sesiones abiertas de la persona menos la actual. Devuelve cuántas cerró."""
    with system_transaction(pool) as connection:
        rows = connection.execute(
            "update sessions set revoked_at = now() "
            "where user_id = %s and id <> %s and revoked_at is null and expires_at > now() returning id",
            (user_id, current_session_id),
        ).fetchall()
    return len(rows)
