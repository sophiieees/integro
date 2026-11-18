"""Contraseñas incorrectas: contar los intentos sin bloquear nunca la cuenta.

Reglas del ADR 0014, decididas por Sophia el 18 de noviembre de 2026:

- Aviso: a los 3 fallos seguidos contra una misma cuenta, vengan de donde
  vengan, se le avisa a su dueño. Entrar bien reinicia esa cuenta de fallos.
- Espera: a los 6 fallos en 15 minutos desde el mismo dispositivo y la misma
  dirección, contra la cuenta que sea, ese dispositivo espera 15 minutos para
  cualquier cuenta. La cuenta no se bloquea: desde otro dispositivo se entra
  normal.

Un dispositivo es la pareja de dirección IP y navegador. Los números salen de
la configuración. Cada intento queda en login_attempts, que solo admite filas
nuevas.

Aquí se usa la hora del reloj (clock_timestamp) y no la de inicio de la
transacción, para que dos intentos seguidos queden en su orden real.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.config import Settings
from app.modules.accounts.validation import EMAIL_MAX_LENGTH, EMAIL_PATTERN

USER_AGENT_MAX_LENGTH = 500


@dataclass(frozen=True)
class Origin:
    """Quién está intentando: desde qué dirección y con qué navegador."""

    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True)
class FailureNotice:
    """Lo que se le dice al dueño de la cuenta cuando llega al número de fallos del aviso."""

    failures: int
    at: datetime
    ip_address: str | None
    user_agent: str | None


def clean_user_agent(user_agent: str | None) -> str | None:
    """El nombre del navegador, cortado al largo que admite la base. Vacío es None."""
    return (user_agent or "")[:USER_AGENT_MAX_LENGTH] or None


def email_for_record(written: str) -> str | None:
    """El correo como se anota: en minúsculas, o None si lo escrito no tenía forma de correo."""
    email = written.strip().lower()
    if len(email) <= EMAIL_MAX_LENGTH and EMAIL_PATTERN.match(email):
        return email
    return None


def seconds_to_wait(connection, origin: Origin, settings: Settings) -> int | None:
    """Segundos que le faltan a ese dispositivo para poder intentar, o None si puede.

    Tiene que esperar si su último fallo fue hace menos del tiempo de espera y
    con él juntó el número de fallos dentro de ese mismo tiempo. Mientras
    espera no se anotan sus intentos, así que la espera no se alarga.
    """
    left, failures = connection.execute(
        "with mine as ("
        "  select created_at from login_attempts where not succeeded "
        "  and ip_address is not distinct from %(ip)s::inet and user_agent is not distinct from %(agent)s"
        "), last as (select max(created_at) as at from mine) "
        "select extract(epoch from last.at + make_interval(mins => %(minutes)s) - clock_timestamp()), "
        "  (select count(*) from mine where created_at > last.at - make_interval(mins => %(minutes)s)) "
        "from last",
        {"ip": origin.ip_address, "agent": origin.user_agent, "minutes": settings.login_wait_minutes},
    ).fetchone()
    if left is None or left <= 0 or failures < settings.login_wait_after_failures:
        return None
    return math.ceil(left)


def note_attempt(
    connection, *, written_email: str, user_id: UUID | None, succeeded: bool, origin: Origin
) -> datetime:
    """Anota un intento y devuelve su hora."""
    return connection.execute(
        "insert into login_attempts (email, user_id, succeeded, ip_address, user_agent, created_at) "
        "values (%s, %s, %s, %s, %s, clock_timestamp()) returning created_at",
        (email_for_record(written_email), user_id, succeeded, origin.ip_address, origin.user_agent),
    ).fetchone()[0]


def failures_in_a_row(connection, user_id: UUID, settings: Settings) -> int:
    """Fallos seguidos contra esa cuenta: desde su último acierto y dentro del tiempo que se cuenta."""
    return connection.execute(
        "select count(*) from login_attempts where user_id = %(user)s and not succeeded "
        "and created_at > clock_timestamp() - make_interval(mins => %(minutes)s) "
        "and created_at > coalesce("
        "  (select max(created_at) from login_attempts where user_id = %(user)s and succeeded), '-infinity')",
        {"user": user_id, "minutes": settings.login_wait_minutes},
    ).fetchone()[0]


def note_failure(
    connection, *, written_email: str, user_id: UUID | None, origin: Origin, settings: Settings
) -> FailureNotice | None:
    """Anota un fallo. Devuelve el aviso para el dueño si con este fallo la
    cuenta llegó justo al número del aviso; si no, None.

    El aviso sale una vez por racha: en el fallo que completa el número, no en
    los siguientes. Un correo sin cuenta no tiene a quién avisar.
    """
    at = note_attempt(connection, written_email=written_email, user_id=user_id, succeeded=False, origin=origin)
    if user_id is None:
        return None
    failures = failures_in_a_row(connection, user_id, settings)
    if failures != settings.login_notice_after_failures:
        return None
    return FailureNotice(failures=failures, at=at, ip_address=origin.ip_address, user_agent=origin.user_agent)
