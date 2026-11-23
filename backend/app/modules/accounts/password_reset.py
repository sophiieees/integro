"""Recuperar la contraseña con un código de 6 dígitos al correo.

Decisiones de Sophia del 21 de noviembre de 2026:

- Es un código de 6 dígitos, no un enlace. Vence a los 30 minutos y se bloquea
  a los 5 intentos fallidos, como los demás códigos (ADR 0014).
- Solo una cuenta con el correo comprobado puede recuperar la contraseña. Quien
  no lo ha comprobado primero lo comprueba, o lo corrige.

Reglas que se agregan para que no sirva para averiguar quién tiene cuenta ni
para adivinar códigos:

- Pedir el código contesta siempre lo mismo, exista o no la cuenta, esté o no
  comprobada, y aunque todavía haya que esperar un minuto o ya se haya llegado
  al máximo por hora: en esos casos simplemente no se envía otro.
- Al cambiar la contraseña, todas las sesiones abiertas de esa cuenta se
  cierran: quien la tuviera abierta por haber conocido la contraseña vieja
  pierde el acceso. La persona entra de nuevo con su código de siempre.
- Un código equivocado cuenta como un intento fallido de ese dispositivo
  (ADR 0014): si junta demasiados espera, igual que al iniciar sesión. Un
  correo sin cuenta cuenta igual, para que no se note la diferencia. No se
  avisa al dueño de la cuenta, porque no fue un intento de entrar.
- El código nuevo deja sin efecto a los anteriores.
- Al cambiar la contraseña se le avisa por correo al dueño de la cuenta (decisión de Sophia del 21 de noviembre de
  2026): cuándo, desde qué navegador y qué dirección, y que se cerraron las sesiones. Así, si alguien más la cambió, se
  entera. El aviso sale hasta que el cambio quedó guardado y no lleva contraseñas ni códigos.
- La contraseña nueva cumple lo mismo que pide el registro: las reglas de formato y no ser
  fácil de adivinar (al menos nivel medio, sin el nombre ni el correo de la persona).

Todo lo hace el sistema (integro_service): la persona no tiene sesión.
"""

from dataclasses import dataclass
from enum import Enum

from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.database.transaction import system_transaction
from app.modules.accounts.attempts import Origin, clean_user_agent, note_attempt, seconds_to_wait
from app.modules.accounts.codes import (
    CHANNEL_EMAIL,
    CodeCheck,
    SendLimit,
    check_code,
    create_code,
    send_limit,
    void_previous_codes,
)
from app.modules.accounts.login import clean_ip
from app.modules.accounts.password_strength import password_strength
from app.modules.accounts.security import hash_password
from app.notifications.sender import CodeSender, DeliveryFailed

PURPOSE = "password_reset"
# Aviso al dueño de la cuenta: su contraseña se cambió.
NOTICE_PASSWORD_CHANGED = "password_changed"


class ResetOutcome(Enum):
    CHANGED = "changed"
    # Código incorrecto, o correo sin cuenta o sin comprobar: se responde lo mismo.
    INVALID_CODE = "invalid_code"
    CODE_EXPIRED = "code_expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    # Ese dispositivo juntó demasiados fallos y tiene que esperar.
    TRY_LATER = "try_later"
    # Cumple las reglas de formato pero es fácil de adivinar. No gasta el código.
    TOO_WEAK = "too_weak"


@dataclass(frozen=True)
class ResetResult:
    outcome: ResetOutcome
    attempts_left: int | None = None
    # Segundos que le faltan al dispositivo para poder intentar; solo con TRY_LATER.
    retry_after_seconds: int | None = None
    # Consejos para una contraseña más difícil de adivinar; solo con TOO_WEAK.
    hints: tuple[str, ...] = ()


def request_password_reset(pool: ConnectionPool, email: str, settings: Settings, sender: CodeSender) -> bool:
    """Envía el código si la cuenta existe, tiene el correo comprobado y los límites lo permiten.

    Devuelve si se envió algo, solo para las pruebas: a quien lo pidió se le
    responde lo mismo en todos los casos, también si el proveedor del correo
    falla (si fallara distinto cuando la cuenta existe, la respuesta diría
    quién tiene cuenta; el motivo queda en el registro del servidor).
    """
    email = email.strip().lower()
    code = None
    with system_transaction(pool) as connection:
        user = connection.execute(
            "select id from users where email = %s and email_verified_at is not null for update", (email,)
        ).fetchone()
        if user is not None:
            user_id = user[0]
            if send_limit(connection, user_id, PURPOSE, settings).outcome is SendLimit.ALLOWED:
                void_previous_codes(connection, user_id, PURPOSE)
                code = create_code(
                    connection, user_id, PURPOSE, email, settings, ttl_seconds=settings.password_reset_ttl_seconds
                )

    # El código se envía hasta que quedó guardado.
    if code is None:
        return False
    try:
        sender.send_code(
            channel=CHANNEL_EMAIL,
            destination=email,
            code=code,
            purpose=PURPOSE,
            ttl_seconds=settings.password_reset_ttl_seconds,
        )
    except DeliveryFailed:
        return False
    return True


def reset_password(
    pool: ConnectionPool,
    email: str,
    code: str,
    new_password: str,
    settings: Settings,
    sender: CodeSender,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ResetResult:
    """Comprueba el código y cambia la contraseña.

    El formato de la contraseña nueva ya se revisó antes (las reglas del registro).
    Aquí se revisa que no sea fácil de adivinar, que necesita el nombre de la
    persona: una contraseña débil no gasta el código ni cuenta como intento. Si el código es correcto se guarda la
    contraseña nueva con Argon2id, el código queda gastado, se cierran todas
    las sesiones de la cuenta y se avisa por correo al dueño.
    """
    written_email = email
    email = email.strip().lower()
    origin = Origin(ip_address=clean_ip(ip_address), user_agent=clean_user_agent(user_agent))

    with system_transaction(pool) as connection:
        wait = seconds_to_wait(connection, origin, settings)
        if wait is not None:
            return ResetResult(ResetOutcome.TRY_LATER, retry_after_seconds=wait)

        user = connection.execute(
            "select id, first_name, last_name from users where email = %s and email_verified_at is not null for update",
            (email,),
        ).fetchone()
        # Un correo sin cuenta se revisa igual, solo sin nombres: no se nota la diferencia.
        strength = password_strength(
            new_password,
            first_name=user[1] if user else None,
            last_name=user[2] if user else None,
            email=email,
        )
        if not strength.is_enough:
            return ResetResult(ResetOutcome.TOO_WEAK, hints=tuple(strength.hints))
        if user is None:
            note_attempt(connection, written_email=written_email, user_id=None, succeeded=False, origin=origin)
            return ResetResult(ResetOutcome.INVALID_CODE)
        user_id = user[0]

        checked = check_code(connection, user_id, PURPOSE, email, code, settings)
        if checked.outcome is CodeCheck.EXPIRED:
            return ResetResult(ResetOutcome.CODE_EXPIRED)
        if checked.outcome is CodeCheck.TOO_MANY_ATTEMPTS:
            return ResetResult(ResetOutcome.TOO_MANY_ATTEMPTS)
        if checked.outcome is CodeCheck.INVALID:
            note_attempt(connection, written_email=written_email, user_id=user_id, succeeded=False, origin=origin)
            return ResetResult(ResetOutcome.INVALID_CODE, attempts_left=checked.attempts_left)

        connection.execute(
            "update user_credentials set password_hash = %s where user_id = %s",
            (hash_password(new_password), user_id),
        )
        void_previous_codes(connection, user_id, PURPOSE)
        connection.execute(
            "update sessions set revoked_at = now() where user_id = %s and revoked_at is null", (user_id,)
        )
        changed_at = connection.execute("select clock_timestamp()").fetchone()[0]

    # El aviso sale hasta que el cambio quedó guardado.
    sender.send_notice(
        channel=CHANNEL_EMAIL,
        destination=email,
        kind=NOTICE_PASSWORD_CHANGED,
        details={"at": changed_at, "ip_address": origin.ip_address, "user_agent": origin.user_agent},
    )
    return ResetResult(ResetOutcome.CHANGED)
