"""Inicio de sesión con correo, contraseña y código al correo (ADR 0014).

Son dos pasos. En el primero la persona escribe su correo y su contraseña y,
si son correctos, se le envía un código. En el segundo escribe el código y
recibe la llave de su sesión. Esos tres datos se piden en cada inicio de
sesión; no se recuerdan dispositivos.

Todo lo hace el sistema (integro_service): la persona todavía no tiene sesión.
"""

import ipaddress
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.database.transaction import system_transaction
from app.modules.accounts.attempts import (
    Origin,
    clean_user_agent,
    note_attempt,
    note_failure,
    seconds_to_wait,
)
from app.modules.accounts.codes import (
    CHANNEL_EMAIL,
    CodeCheck,
    SendLimit,
    check_code,
    create_code,
    send_limit,
    void_previous_codes,
)
from app.modules.accounts.security import (
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.modules.accounts.sessions import idle_days
from app.notifications.sender import CodeSender

PURPOSE = "login"
# Aviso al dueño de la cuenta: hubo varios intentos fallidos seguidos.
NOTICE_FAILED_LOGINS = "failed_logins"


class LoginOutcome(Enum):
    CODE_SENT = "code_sent"
    # Contraseña incorrecta o correo sin cuenta: se responde lo mismo.
    INVALID_CREDENTIALS = "invalid_credentials"
    # Ese dispositivo juntó demasiados fallos y tiene que esperar.
    TRY_LATER = "try_later"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    WAIT = "wait"
    HOURLY_LIMIT = "hourly_limit"


@dataclass(frozen=True)
class LoginResult:
    outcome: LoginOutcome
    retry_after_seconds: int | None = None


class SessionOutcome(Enum):
    OPENED = "opened"
    INVALID_CODE = "invalid_code"
    CODE_EXPIRED = "code_expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


@dataclass(frozen=True)
class SessionResult:
    outcome: SessionOutcome
    # La llave de sesión. Solo existe aquí y en la cookie: en la base queda su huella.
    token: str | None = None
    expires_at: datetime | None = None
    # Días sin uso que aguanta la sesión que se abrió: lo que dura la cookie.
    idle_days: int | None = None
    attempts_left: int | None = None


def clean_ip(address: str | None) -> str | None:
    """Devuelve la dirección si es una IP válida; si no, None."""
    try:
        return str(ipaddress.ip_address((address or "").strip()))
    except ValueError:
        return None


def start_login(
    pool: ConnectionPool,
    email: str,
    password: str,
    settings: Settings,
    sender: CodeSender,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LoginResult:
    """Primer paso: comprueba correo y contraseña y envía el código.

    No abre ninguna sesión. Un correo sin cuenta y una contraseña incorrecta
    dan la misma respuesta. El correo debe estar comprobado.

    Cada intento se anota. Si ese dispositivo juntó demasiados fallos tiene
    que esperar, y mientras espera ni siquiera se mira la contraseña. La
    cuenta nunca se bloquea: desde otro dispositivo se entra normal. Al
    fallo que completa el número del aviso se le avisa al dueño de la cuenta.
    """
    written_email = email
    email = email.strip().lower()
    origin = Origin(ip_address=clean_ip(ip_address), user_agent=clean_user_agent(user_agent))
    code = None
    notice = None

    with system_transaction(pool) as connection:
        wait = seconds_to_wait(connection, origin, settings)
        if wait is not None:
            return LoginResult(LoginOutcome.TRY_LATER, retry_after_seconds=wait)

        row = connection.execute(
            "select u.id, u.email_verified_at, c.password_hash from users u "
            "join user_credentials c on c.user_id = u.id where u.email = %s",
            (email,),
        ).fetchone()
        user_id, verified_at, password_hash = row if row else (None, None, None)

        if not verify_password(password, password_hash):
            notice = note_failure(
                connection, written_email=written_email, user_id=user_id, origin=origin, settings=settings
            )
            # Solo se avisa a un correo que ya se comprobó que es de la persona.
            if verified_at is None:
                notice = None
            result = LoginResult(LoginOutcome.INVALID_CREDENTIALS)
        else:
            note_attempt(connection, written_email=written_email, user_id=user_id, succeeded=True, origin=origin)
            limit = send_limit(connection, user_id, PURPOSE, settings)
            if verified_at is None:
                result = LoginResult(LoginOutcome.EMAIL_NOT_VERIFIED)
            elif limit.outcome is SendLimit.WAIT:
                result = LoginResult(LoginOutcome.WAIT, retry_after_seconds=limit.retry_after_seconds)
            elif limit.outcome is SendLimit.HOURLY_LIMIT:
                result = LoginResult(LoginOutcome.HOURLY_LIMIT)
            else:
                void_previous_codes(connection, user_id, PURPOSE)
                code = create_code(connection, user_id, PURPOSE, email, settings)
                result = LoginResult(LoginOutcome.CODE_SENT)

    # Los envíos van después de guardar: el intento queda anotado aunque el envío falle.
    if notice is not None:
        sender.send_notice(
            channel=CHANNEL_EMAIL,
            destination=email,
            kind=NOTICE_FAILED_LOGINS,
            details={
                "failures": notice.failures,
                "at": notice.at,
                "ip_address": notice.ip_address,
                "user_agent": notice.user_agent,
            },
        )
    if code is not None:
        sender.send_code(
            channel=CHANNEL_EMAIL,
            destination=email,
            code=code,
            purpose=PURPOSE,
            ttl_seconds=settings.code_ttl_seconds,
        )
    return result


def finish_login(
    pool: ConnectionPool,
    email: str,
    code: str,
    settings: Settings,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SessionResult:
    """Segundo paso: comprueba el código y abre la sesión.

    El código de inicio de sesión solo se crea después de una contraseña
    correcta, así que quien lo tiene ya pasó el primer paso. Guarda la huella
    de la llave, desde dónde se abrió y cuándo vence si no se usa.
    """
    email = email.strip().lower()
    with system_transaction(pool) as connection:
        user = connection.execute(
            "select u.id, exists (select 1 from host_profiles h where h.user_id = u.id) "
            "from users u where u.email = %s and u.email_verified_at is not null",
            (email,),
        ).fetchone()
        if user is None:
            return SessionResult(SessionOutcome.INVALID_CODE)
        user_id, is_host = user

        checked = check_code(connection, user_id, PURPOSE, email, code, settings)
        if checked.outcome is CodeCheck.EXPIRED:
            return SessionResult(SessionOutcome.CODE_EXPIRED)
        if checked.outcome is CodeCheck.TOO_MANY_ATTEMPTS:
            return SessionResult(SessionOutcome.TOO_MANY_ATTEMPTS)
        if checked.outcome is CodeCheck.INVALID:
            return SessionResult(SessionOutcome.INVALID_CODE, attempts_left=checked.attempts_left)

        token = generate_session_token()
        days = idle_days(is_host, settings)
        expires_at = connection.execute(
            "insert into sessions (user_id, token_hash, expires_at, ip_address, user_agent) "
            "values (%s, %s, now() + make_interval(days => %s), %s, %s) returning expires_at",
            (
                user_id,
                hash_session_token(token),
                days,
                clean_ip(ip_address),
                clean_user_agent(user_agent),
            ),
        ).fetchone()[0]
    return SessionResult(SessionOutcome.OPENED, token=token, expires_at=expires_at, idle_days=days)
