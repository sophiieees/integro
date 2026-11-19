"""Sesiones: reconocer a la persona en cada petición (ADR 0014 y ADR 0015).

La sesión vive en la tabla sessions. La persona manda su llave en cada
petición; aquí se busca la huella de esa llave. La sesión sirve mientras
exista, no se haya cerrado y no haya pasado su tiempo sin uso: 30 días para
un huésped y 7 para un anfitrión. Cada uso renueva ese plazo.
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
    expires_at: datetime


def idle_days(is_host: bool, settings: Settings) -> int:
    """Días sin uso que aguanta una sesión. El anfitrión maneja dinero y
    propiedades, por eso la suya dura menos."""
    return settings.session_idle_days_host if is_host else settings.session_idle_days_guest


def authenticate(pool: ConnectionPool, token: str | None, settings: Settings) -> CurrentSession | None:
    """Devuelve la sesión de esa llave, o None si no sirve.

    No sirve si no existe, si se cerró o si ya venció. Cuando sirve, anota el
    uso y renueva el plazo. Es anfitrión quien tiene perfil de anfitrión en
    ese momento, aunque haya abierto la sesión siendo huésped.
    """
    if not isinstance(token, str) or not token or len(token) > TOKEN_MAX_LENGTH:
        return None
    with system_transaction(pool) as connection:
        row = connection.execute(
            "select s.id, s.user_id, exists (select 1 from host_profiles h where h.user_id = s.user_id) "
            "from sessions s where s.token_hash = %s and s.revoked_at is null and s.expires_at > now() "
            "for update of s",
            (hash_session_token(token),),
        ).fetchone()
        if row is None:
            return None
        session_id, user_id, is_host = row
        expires_at = connection.execute(
            "update sessions set last_used_at = now(), expires_at = now() + make_interval(days => %s) "
            "where id = %s returning expires_at",
            (idle_days(is_host, settings), session_id),
        ).fetchone()[0]
    return CurrentSession(session_id=session_id, user_id=user_id, is_host=is_host, expires_at=expires_at)


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
