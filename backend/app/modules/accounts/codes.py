"""Códigos de un solo uso: crear, comprobar y limitar los envíos.

Lo usan el registro (comprobar el correo) y el inicio de sesión. Las reglas
son las del ADR 0014 y sus valores salen de la configuración: un código sirve
una vez, vence, se bloquea al llegar al máximo de intentos fallidos, y hay que
esperar entre un envío y otro, con un máximo por hora.

Todas las funciones reciben una transacción ya abierta como el sistema. Las
horas se toman del reloj de la base de datos.
"""

from dataclasses import dataclass
from enum import Enum

from app.core.config import Settings
from app.modules.accounts.security import generate_code, hash_code, same_hash

CHANNEL_EMAIL = "email"


class CodeCheck(Enum):
    OK = "ok"
    # No hay un código vigente que comprobar, o el que se escribió no es.
    INVALID = "invalid_code"
    EXPIRED = "code_expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


@dataclass(frozen=True)
class CodeCheckResult:
    outcome: CodeCheck
    # Intentos que le quedan a ese código; solo cuando se escribió uno incorrecto.
    attempts_left: int | None = None


class SendLimit(Enum):
    ALLOWED = "allowed"
    WAIT = "wait"
    HOURLY_LIMIT = "hourly_limit"


@dataclass(frozen=True)
class SendLimitResult:
    outcome: SendLimit
    # Segundos que faltan para poder pedir otro; solo con WAIT.
    retry_after_seconds: int | None = None


def create_code(
    connection, user_id, purpose: str, email: str, settings: Settings, *, ttl_seconds: int | None = None
) -> str:
    """Guarda la huella de un código nuevo y devuelve el código para enviarlo.

    Dura lo que dice code_ttl_seconds, salvo que se pida otra duración (el
    código de recuperar la contraseña dura más).
    """
    code = generate_code(settings.code_length)
    connection.execute(
        "insert into one_time_codes (user_id, purpose, channel, destination, code_hash, expires_at) "
        "values (%s, %s, %s, %s, %s, now() + make_interval(secs => %s))",
        (
            user_id,
            purpose,
            CHANNEL_EMAIL,
            email,
            hash_code(
                code,
                secret=settings.code_hash_secret.get_secret_value(),
                purpose=purpose,
                destination=email,
            ),
            settings.code_ttl_seconds if ttl_seconds is None else ttl_seconds,
        ),
    )
    return code


def check_code(
    connection, user_id, purpose: str, email: str, written: str, settings: Settings
) -> CodeCheckResult:
    """Comprueba el código que la persona escribió contra el último vigente.

    Si es correcto lo da por gastado. Si no, cuenta el intento. Un código de
    otro propósito no sirve: cada propósito tiene los suyos.
    """
    row = connection.execute(
        "select id, code_hash, attempts, expires_at > now() from one_time_codes "
        "where user_id = %s and purpose = %s and used_at is null "
        "order by created_at desc, id desc limit 1 for update",
        (user_id, purpose),
    ).fetchone()
    if row is None:
        return CodeCheckResult(CodeCheck.INVALID)
    code_id, code_hash, attempts, alive = row
    if not alive:
        return CodeCheckResult(CodeCheck.EXPIRED)
    if attempts >= settings.code_max_attempts:
        return CodeCheckResult(CodeCheck.TOO_MANY_ATTEMPTS)

    fingerprint = hash_code(
        written.strip(),
        secret=settings.code_hash_secret.get_secret_value(),
        purpose=purpose,
        destination=email,
    )
    if not same_hash(fingerprint, code_hash):
        connection.execute(
            "update one_time_codes set attempts = attempts + 1 where id = %s", (code_id,)
        )
        return CodeCheckResult(
            CodeCheck.INVALID, attempts_left=settings.code_max_attempts - attempts - 1
        )

    connection.execute("update one_time_codes set used_at = now() where id = %s", (code_id,))
    return CodeCheckResult(CodeCheck.OK)


def send_limit(
    connection, user_id, purpose: str, settings: Settings, *, ignore_wait: bool = False
) -> SendLimitResult:
    """Dice si ya se puede enviar otro código de ese propósito a esa persona.

    ignore_wait salta la espera entre un envío y otro y deja solo el máximo por
    hora. Lo usa la corrección del correo: el envío anterior fue a un correo
    equivocado.
    """
    seconds_since_last, sent_last_hour = connection.execute(
        "select extract(epoch from now() - max(created_at)), "
        "count(*) filter (where created_at > now() - interval '1 hour') "
        "from one_time_codes where user_id = %s and purpose = %s",
        (user_id, purpose),
    ).fetchone()
    if (
        not ignore_wait
        and seconds_since_last is not None
        and seconds_since_last < settings.code_resend_wait_seconds
    ):
        wait = settings.code_resend_wait_seconds - int(seconds_since_last)
        return SendLimitResult(SendLimit.WAIT, retry_after_seconds=max(wait, 1))
    if sent_last_hour >= settings.code_max_per_hour:
        return SendLimitResult(SendLimit.HOURLY_LIMIT)
    return SendLimitResult(SendLimit.ALLOWED)


def void_previous_codes(connection, user_id, purpose: str) -> None:
    """Los códigos anteriores de ese propósito dejan de servir: se dan por gastados."""
    connection.execute(
        "update one_time_codes set used_at = now() "
        "where user_id = %s and purpose = %s and used_at is null",
        (user_id, purpose),
    )
