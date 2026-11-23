"""Registro de una cuenta y comprobación de su correo.

Todo lo hace el sistema (integro_service): la persona todavía no tiene sesión.
Las horas se toman del reloj de la base de datos, para que el vencimiento y
las esperas no dependan del reloj de la computadora donde corre la API.
"""

from dataclasses import dataclass
from enum import Enum

import psycopg
from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.database.transaction import system_transaction
from app.modules.accounts.codes import (
    CHANNEL_EMAIL,
    CodeCheck,
    SendLimit,
    check_code,
    create_code,
    send_limit,
    void_previous_codes,
)
from app.modules.accounts.security import hash_password
from app.modules.accounts.validation import RegistrationData
from app.notifications.sender import CodeSender, DeliveryFailed

PURPOSE = "verify_email"
CHANNEL = CHANNEL_EMAIL

# Regla de la base que se rompe cuando el dato ya existe, y campo del formulario.
UNIQUE_RULES = {
    "users_email_unique": "email",
    "user_phones_phone_unique": "phone",
}


class AlreadyRegistered(Exception):
    """El correo o el teléfono ya pertenecen a una cuenta."""

    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


class VerifyOutcome(Enum):
    VERIFIED = "verified"
    ALREADY_VERIFIED = "already_verified"
    INVALID_CODE = "invalid_code"
    CODE_EXPIRED = "code_expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


@dataclass(frozen=True)
class VerifyResult:
    outcome: VerifyOutcome
    # Intentos que le quedan a ese código; solo cuando el código fue incorrecto.
    attempts_left: int | None = None


class ResendOutcome(Enum):
    SENT = "sent"
    # No hay nada que enviar: el correo no tiene cuenta o ya está comprobado.
    # Se responde igual que SENT para no revelar qué correos tienen cuenta.
    NOTHING_TO_SEND = "nothing_to_send"
    WAIT = "wait"
    HOURLY_LIMIT = "hourly_limit"


@dataclass(frozen=True)
class ResendResult:
    outcome: ResendOutcome
    # Segundos que faltan para poder pedir otro; solo con WAIT.
    retry_after_seconds: int | None = None


def register_account(
    pool: ConnectionPool, data: RegistrationData, settings: Settings, sender: CodeSender
) -> bool:
    """Crea la cuenta y envía el código para comprobar el correo.

    Guarda en una sola operación a la persona, su teléfono principal, su
    contraseña ya convertida y la huella del código. Si el correo o el
    teléfono ya existen no se guarda nada y se lanza AlreadyRegistered.

    Devuelve si el código salió. Si el proveedor del correo falla, la cuenta
    ya quedó guardada: no se deshace (volver a mandar el formulario diría
    «ya existe una cuenta»), y la persona pide otro código (ADR 0017).
    """
    password_hash = hash_password(data.password)
    try:
        with system_transaction(pool) as connection:
            user_id = connection.execute(
                "insert into users (first_name, last_name, email, country, birth_date, preferred_language) "
                "values (%s, %s, %s, %s, %s, %s) returning id",
                (
                    data.first_name,
                    data.last_name,
                    data.email,
                    data.country,
                    data.birth_date,
                    data.preferred_language,
                ),
            ).fetchone()[0]
            connection.execute(
                "insert into user_phones (user_id, phone, is_primary) values (%s, %s, true)",
                (user_id, data.phone),
            )
            connection.execute(
                "insert into user_credentials (user_id, password_hash) values (%s, %s)",
                (user_id, password_hash),
            )
            code = create_code(connection, user_id, PURPOSE, data.email, settings)
    except psycopg.errors.UniqueViolation as error:
        field = UNIQUE_RULES.get(error.diag.constraint_name)
        if field is None:
            raise
        raise AlreadyRegistered(field) from None

    # El código se envía hasta que la cuenta quedó guardada.
    try:
        sender.send_code(
            channel=CHANNEL,
            destination=data.email,
            code=code,
            purpose=PURPOSE,
            ttl_seconds=settings.code_ttl_seconds,
        )
    except DeliveryFailed:
        return False
    return True


def verify_email(pool: ConnectionPool, email: str, code: str, settings: Settings) -> VerifyResult:
    """Comprueba el código que la persona escribió.

    Un código sirve una vez, vence, y se bloquea al llegar al máximo de
    intentos fallidos aunque después se escriba el correcto. Un correo sin
    cuenta se responde igual que un código incorrecto.
    """
    email = email.strip().lower()
    with system_transaction(pool) as connection:
        user = connection.execute(
            "select id, email_verified_at from users where email = %s", (email,)
        ).fetchone()
        if user is None:
            return VerifyResult(VerifyOutcome.INVALID_CODE)
        user_id, verified_at = user
        if verified_at is not None:
            return VerifyResult(VerifyOutcome.ALREADY_VERIFIED)

        checked = check_code(connection, user_id, PURPOSE, email, code, settings)
        if checked.outcome is CodeCheck.EXPIRED:
            return VerifyResult(VerifyOutcome.CODE_EXPIRED)
        if checked.outcome is CodeCheck.TOO_MANY_ATTEMPTS:
            return VerifyResult(VerifyOutcome.TOO_MANY_ATTEMPTS)
        if checked.outcome is CodeCheck.INVALID:
            return VerifyResult(VerifyOutcome.INVALID_CODE, attempts_left=checked.attempts_left)

        connection.execute("update users set email_verified_at = now() where id = %s", (user_id,))
        return VerifyResult(VerifyOutcome.VERIFIED)


def resend_code(
    pool: ConnectionPool, email: str, settings: Settings, sender: CodeSender
) -> ResendResult:
    """Envía otro código para comprobar el correo, dentro de los límites.

    Hay que esperar entre un envío y otro, y hay un máximo por hora. El código
    nuevo deja sin efecto a los anteriores.
    """
    email = email.strip().lower()
    with system_transaction(pool) as connection:
        user = connection.execute(
            "select id, email_verified_at from users where email = %s for update", (email,)
        ).fetchone()
        if user is None or user[1] is not None:
            return ResendResult(ResendOutcome.NOTHING_TO_SEND)
        user_id = user[0]

        limit = send_limit(connection, user_id, PURPOSE, settings)
        if limit.outcome is SendLimit.WAIT:
            return ResendResult(ResendOutcome.WAIT, retry_after_seconds=limit.retry_after_seconds)
        if limit.outcome is SendLimit.HOURLY_LIMIT:
            return ResendResult(ResendOutcome.HOURLY_LIMIT)

        void_previous_codes(connection, user_id, PURPOSE)
        code = create_code(connection, user_id, PURPOSE, email, settings)

    sender.send_code(
        channel=CHANNEL,
        destination=email,
        code=code,
        purpose=PURPOSE,
        ttl_seconds=settings.code_ttl_seconds,
    )
    return ResendResult(ResendOutcome.SENT)
