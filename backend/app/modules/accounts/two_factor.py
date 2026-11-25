"""El Authenticator de una cuenta: activarlo y comprobarlo (pieza 3.2).

Decisiones de Sophia del 24 y 25 de noviembre de 2026 (bitácora 41.11, 41.12 y la especificación de la pieza 3.2):

- Lo activan los anfitriones y los administradores. Se suma al código del correo; no lo reemplaza.
- Para empezar se pide la contraseña otra vez: quien tome una sesión abierta no puede ponerle su propio Authenticator
  a la cuenta. Una contraseña incorrecta cuenta como un intento fallido de entrar (ADR 0014): a los 3 se avisa al
  dueño y a los 6 ese dispositivo espera.
- Dos pasos: se genera la clave y queda pendiente; la persona la comprueba con un código de su aplicación y queda
  activa. Mientras está pendiente se puede volver a empezar, y la clave anterior deja de servir.
- A los 5 códigos incorrectos seguidos la persona espera 15 minutos (los dos números, en la configuración).
- Si ya está activo no se puede volver a activar aquí: cambiar de celular y los códigos de recuperación son la
  pieza 3.6. Exigirlo al iniciar sesión es la pieza 3.3.
- La clave se guarda cifrada con AES-256-GCM, amarrada al id de la persona (app/core/encryption.py). Sin la llave de
  cifrado no se puede activar ni comprobar: se contesta que no está disponible, nunca se guarda sin cifrar.

La tabla user_totp solo la lee y la escribe el sistema (database/migrations/20261124000006_user_totp.sql).
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.core.encryption import CURRENT_KEY_VERSION, DecryptionFailed, decrypt, encrypt
from app.database.transaction import system_transaction
from app.modules.accounts.attempts import (
    FailureNotice,
    Origin,
    clean_user_agent,
    note_attempt,
    note_failure,
    seconds_to_wait,
)
from app.modules.accounts.login import clean_ip
from app.modules.accounts.security import verify_password
from app.modules.accounts.totp import generate_secret, matching_step

# Para qué se usa la llave de cifrado: de la llave maestra sale una distinta para cada uso.
PURPOSE = "totp-secret"

logger = logging.getLogger("integro.two_factor")


def current_time() -> float:
    """La hora del servidor, en segundos desde 1970. Las pruebas la cambian para probar los periodos."""
    return time.time()


def master_key(settings: Settings) -> str | None:
    return settings.data_encryption_key.get_secret_value() if settings.data_encryption_key else None


def associated(user_id: UUID) -> bytes:
    """Lo que amarra la clave cifrada a su dueña: movida a la fila de otra persona, no se descifra."""
    return str(user_id).encode("ascii")


# ---------------------------------------------------------------------------
# Empezar la activación
# ---------------------------------------------------------------------------


class SetupOutcome(Enum):
    PENDING = "pending"
    INVALID_PASSWORD = "invalid_password"
    # Ese dispositivo juntó demasiadas contraseñas incorrectas y tiene que esperar.
    TRY_LATER = "try_later"
    ALREADY_ACTIVE = "already_active"
    # Falta la llave de cifrado.
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SetupResult:
    outcome: SetupOutcome
    # La clave en claro, solo con PENDING: se entrega una vez y no se vuelve a mostrar.
    secret: bytes | None = None
    email: str | None = None
    retry_after_seconds: int | None = None
    # El aviso para el dueño si con este fallo llegó al número de contraseñas incorrectas seguidas.
    notice: FailureNotice | None = None


def start_setup(
    pool: ConnectionPool,
    user_id: UUID,
    password: str,
    settings: Settings,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SetupResult:
    """Genera la clave del Authenticator de esa persona, la guarda cifrada y la deja pendiente de comprobar."""
    key = master_key(settings)
    if key is None:
        logger.error("Falta DATA_ENCRYPTION_KEY: no se puede activar el Authenticator.")
        return SetupResult(SetupOutcome.UNAVAILABLE)
    origin = Origin(ip_address=clean_ip(ip_address), user_agent=clean_user_agent(user_agent))

    with system_transaction(pool) as connection:
        wait = seconds_to_wait(connection, origin, settings)
        if wait is not None:
            return SetupResult(SetupOutcome.TRY_LATER, retry_after_seconds=wait)

        row = connection.execute(
            "select u.email, c.password_hash from users u join user_credentials c on c.user_id = u.id "
            "where u.id = %s for update of u",
            (user_id,),
        ).fetchone()
        email, password_hash = row if row else (None, None)
        if not verify_password(password, password_hash):
            notice = None
            if email is not None:
                notice = note_failure(
                    connection, written_email=email, user_id=user_id, origin=origin, settings=settings
                )
            return SetupResult(SetupOutcome.INVALID_PASSWORD, email=email, notice=notice)
        note_attempt(connection, written_email=email, user_id=user_id, succeeded=True, origin=origin)

        existing = connection.execute(
            "select confirmed_at is not null from user_totp where user_id = %s for update", (user_id,)
        ).fetchone()
        if existing is not None and existing[0]:
            return SetupResult(SetupOutcome.ALREADY_ACTIVE)

        secret = generate_secret()
        # Si ya había una clave pendiente, la misma fila recibe la nueva y la anterior deja de servir.
        connection.execute(
            "insert into user_totp (user_id, secret_ciphertext, key_version) values (%s, %s, %s) "
            "on conflict (user_id) do update set secret_ciphertext = excluded.secret_ciphertext, "
            "key_version = excluded.key_version, confirmed_at = null, last_used_step = null, "
            "failed_attempts = 0, locked_until = null",
            (user_id, encrypt(key, PURPOSE, secret, associated(user_id)), CURRENT_KEY_VERSION),
        )
    return SetupResult(SetupOutcome.PENDING, secret=secret, email=email)


# ---------------------------------------------------------------------------
# Comprobar la clave con un código
# ---------------------------------------------------------------------------


class ConfirmOutcome(Enum):
    ACTIVE = "active"
    INVALID_CODE = "invalid_code"
    # Demasiados códigos incorrectos: la persona espera.
    TRY_LATER = "try_later"
    # Todavía no empieza la activación.
    NOT_STARTED = "not_started"
    ALREADY_ACTIVE = "already_active"
    # Falta la llave de cifrado, o lo guardado no se pudo descifrar.
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ConfirmResult:
    outcome: ConfirmOutcome
    activated_at: datetime | None = None
    email: str | None = None
    attempts_left: int | None = None
    retry_after_seconds: int | None = None


def confirm_setup(
    pool: ConnectionPool, user_id: UUID, code: str, settings: Settings, *, now: float | None = None
) -> ConfirmResult:
    """Comprueba el código que muestra la aplicación. Si es el de la clave pendiente, el Authenticator queda activo."""
    key = master_key(settings)
    if key is None:
        logger.error("Falta DATA_ENCRYPTION_KEY: no se puede comprobar el Authenticator.")
        return ConfirmResult(ConfirmOutcome.UNAVAILABLE)
    timestamp = current_time() if now is None else now

    with system_transaction(pool) as connection:
        row = connection.execute(
            "select t.secret_ciphertext, t.confirmed_at is not null, t.failed_attempts, "
            "ceil(extract(epoch from (t.locked_until - now())))::int, u.email "
            "from user_totp t join users u on u.id = t.user_id where t.user_id = %s for update of t",
            (user_id,),
        ).fetchone()
        if row is None:
            return ConfirmResult(ConfirmOutcome.NOT_STARTED)
        ciphertext, active, failed_attempts, wait, email = row
        if active:
            return ConfirmResult(ConfirmOutcome.ALREADY_ACTIVE)
        if wait is not None and wait > 0:
            return ConfirmResult(ConfirmOutcome.TRY_LATER, retry_after_seconds=wait)

        try:
            secret = decrypt(key, PURPOSE, ciphertext, associated(user_id))
        except DecryptionFailed:
            # Solo el motivo general: nunca la clave ni lo guardado.
            logger.error("La clave del Authenticator de una cuenta no se pudo descifrar.")
            return ConfirmResult(ConfirmOutcome.UNAVAILABLE)

        step = matching_step(secret, code, timestamp)
        if step is None:
            failed_attempts += 1
            if failed_attempts >= settings.two_factor_max_attempts:
                # Empieza la espera y la cuenta vuelve a cero: al terminar tiene otra vez todos sus intentos.
                connection.execute(
                    "update user_totp set failed_attempts = 0, locked_until = now() + make_interval(mins => %s) "
                    "where user_id = %s",
                    (settings.two_factor_wait_minutes, user_id),
                )
                return ConfirmResult(
                    ConfirmOutcome.TRY_LATER, retry_after_seconds=settings.two_factor_wait_minutes * 60
                )
            connection.execute(
                "update user_totp set failed_attempts = %s, locked_until = null where user_id = %s",
                (failed_attempts, user_id),
            )
            return ConfirmResult(
                ConfirmOutcome.INVALID_CODE, attempts_left=settings.two_factor_max_attempts - failed_attempts
            )

        activated_at = connection.execute(
            "update user_totp set confirmed_at = now(), last_used_step = %s, failed_attempts = 0, "
            "locked_until = null where user_id = %s returning confirmed_at",
            (step, user_id),
        ).fetchone()[0]
    return ConfirmResult(ConfirmOutcome.ACTIVE, activated_at=activated_at, email=email)


# ---------------------------------------------------------------------------
# El estado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TwoFactorStatus:
    # inactive: nunca empezó. pending: tiene una clave sin comprobar. active: ya la comprobó.
    status: str
    activated_at: datetime | None = None


def read_status(pool: ConnectionPool, user_id: UUID) -> TwoFactorStatus:
    """Si el Authenticator de esa persona está inactivo, pendiente o activo. Nunca entrega la clave."""
    with system_transaction(pool) as connection:
        row = connection.execute("select confirmed_at from user_totp where user_id = %s", (user_id,)).fetchone()
    if row is None:
        return TwoFactorStatus("inactive")
    if row[0] is None:
        return TwoFactorStatus("pending")
    return TwoFactorStatus("active", activated_at=row[0])
