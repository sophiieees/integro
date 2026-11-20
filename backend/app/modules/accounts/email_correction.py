"""Corregir el correo de una cuenta que todavía no lo ha comprobado.

Decisión de Sophia del 20 de noviembre de 2026: quien se equivoca de correo al
registrarse puede corregirlo. Sin esto, esa cuenta se queda ocupando el correo
y el teléfono sin que su dueña pueda recibir el código.

Reglas:

- Hay que demostrar que la cuenta es de quien la corrige: se pide la
  contraseña con la que se registró. Sin ella, cualquiera que conociera un
  correo sin comprobar podría quitárselo a otra persona.
- Cuenta como un intento de entrar: si la contraseña falla se anota y cuenta
  para la espera por dispositivo (ADR 0014); si acierta, se anota el acierto.
  Una contraseña incorrecta y un correo sin cuenta contestan igual.
- Solo sirve para una cuenta sin comprobar. Una cuenta comprobada cambia de
  correo por otro camino, con segundo factor, que todavía no existe.
- El correo nuevo no puede ser de otra cuenta.
- El código nuevo deja sin efecto a los anteriores y va al correo nuevo. No se
  espera un minuto desde el envío anterior, porque el anterior fue a un correo
  equivocado; sí vale el máximo de códigos por hora.

Todo lo hace el sistema (integro_service): la persona todavía no tiene sesión.
"""

from dataclasses import dataclass
from enum import Enum

import psycopg
from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.database.transaction import system_transaction
from app.modules.accounts.attempts import Origin, clean_user_agent, note_attempt, note_failure, seconds_to_wait
from app.modules.accounts.codes import CHANNEL_EMAIL, SendLimit, create_code, send_limit, void_previous_codes
from app.modules.accounts.login import clean_ip
from app.modules.accounts.registration import PURPOSE
from app.modules.accounts.security import verify_password
from app.notifications.sender import CodeSender


class CorrectionOutcome(Enum):
    CODE_SENT = "code_sent"
    TRY_LATER = "try_later"
    INVALID_CREDENTIALS = "invalid_credentials"
    ALREADY_VERIFIED = "already_verified"
    SAME_EMAIL = "same_email"
    EMAIL_TAKEN = "email_taken"
    HOURLY_LIMIT = "hourly_limit"


@dataclass(frozen=True)
class CorrectionResult:
    outcome: CorrectionOutcome
    # Segundos que le faltan al dispositivo para poder intentar; solo con TRY_LATER.
    retry_after_seconds: int | None = None


def correct_unverified_email(
    pool: ConnectionPool,
    email: str,
    password: str,
    new_email: str,
    settings: Settings,
    sender: CodeSender,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CorrectionResult:
    """Cambia el correo de una cuenta sin comprobar y envía el código al correo nuevo."""
    written_email = email
    email = email.strip().lower()
    new_email = new_email.strip().lower()
    origin = Origin(ip_address=clean_ip(ip_address), user_agent=clean_user_agent(user_agent))
    code = None

    try:
        with system_transaction(pool) as connection:
            wait = seconds_to_wait(connection, origin, settings)
            if wait is not None:
                return CorrectionResult(CorrectionOutcome.TRY_LATER, retry_after_seconds=wait)

            row = connection.execute(
                "select u.id, u.email_verified_at, c.password_hash from users u "
                "join user_credentials c on c.user_id = u.id where u.email = %s for update of u",
                (email,),
            ).fetchone()
            user_id, verified_at, password_hash = row if row else (None, None, None)

            if not verify_password(password, password_hash):
                note_failure(
                    connection, written_email=written_email, user_id=user_id, origin=origin, settings=settings
                )
                return CorrectionResult(CorrectionOutcome.INVALID_CREDENTIALS)
            note_attempt(connection, written_email=written_email, user_id=user_id, succeeded=True, origin=origin)

            if verified_at is not None:
                return CorrectionResult(CorrectionOutcome.ALREADY_VERIFIED)
            if new_email == email:
                return CorrectionResult(CorrectionOutcome.SAME_EMAIL)
            if connection.execute("select 1 from users where email = %s", (new_email,)).fetchone():
                return CorrectionResult(CorrectionOutcome.EMAIL_TAKEN)
            # El máximo por hora cuenta; la espera de un minuto no (ver arriba).
            if send_limit(connection, user_id, PURPOSE, settings, ignore_wait=True).outcome is SendLimit.HOURLY_LIMIT:
                return CorrectionResult(CorrectionOutcome.HOURLY_LIMIT)

            connection.execute("update users set email = %s where id = %s", (new_email, user_id))
            void_previous_codes(connection, user_id, PURPOSE)
            code = create_code(connection, user_id, PURPOSE, new_email, settings)
    except psycopg.errors.UniqueViolation as error:
        # Alguien registró ese correo entre la revisión y el cambio.
        if error.diag.constraint_name != "users_email_unique":
            raise
        return CorrectionResult(CorrectionOutcome.EMAIL_TAKEN)

    # El código se envía hasta que el cambio quedó guardado.
    sender.send_code(
        channel=CHANNEL_EMAIL,
        destination=new_email,
        code=code,
        purpose=PURPOSE,
        ttl_seconds=settings.code_ttl_seconds,
    )
    return CorrectionResult(CorrectionOutcome.CODE_SENT)
