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
USER_AGENT_MAX_LENGTH = 500


class LoginOutcome(Enum):
    CODE_SENT = "code_sent"
    # Contraseña incorrecta o correo sin cuenta: se responde lo mismo.
    INVALID_CREDENTIALS = "invalid_credentials"
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
    # La llave de sesión. Solo existe aquí y en la respuesta: en la base queda su huella.
    token: str | None = None
    expires_at: datetime | None = None
    attempts_left: int | None = None


def clean_ip(address: str | None) -> str | None:
    """Devuelve la dirección si es una IP válida; si no, None."""
    try:
        return str(ipaddress.ip_address((address or "").strip()))
    except ValueError:
        return None


def start_login(
    pool: ConnectionPool, email: str, password: str, settings: Settings, sender: CodeSender
) -> LoginResult:
    """Primer paso: comprueba correo y contraseña y envía el código.

    No abre ninguna sesión. Un correo sin cuenta y una contraseña incorrecta
    dan la misma respuesta. El correo debe estar comprobado.
    """
    email = email.strip().lower()
    with system_transaction(pool) as connection:
        row = connection.execute(
            "select u.id, u.email_verified_at, c.password_hash from users u "
            "join user_credentials c on c.user_id = u.id where u.email = %s",
            (email,),
        ).fetchone()
        user_id, verified_at, password_hash = row if row else (None, None, None)
        if not verify_password(password, password_hash):
            return LoginResult(LoginOutcome.INVALID_CREDENTIALS)
        if verified_at is None:
            return LoginResult(LoginOutcome.EMAIL_NOT_VERIFIED)

        limit = send_limit(connection, user_id, PURPOSE, settings)
        if limit.outcome is SendLimit.WAIT:
            return LoginResult(LoginOutcome.WAIT, retry_after_seconds=limit.retry_after_seconds)
        if limit.outcome is SendLimit.HOURLY_LIMIT:
            return LoginResult(LoginOutcome.HOURLY_LIMIT)

        void_previous_codes(connection, user_id, PURPOSE)
        code = create_code(connection, user_id, PURPOSE, email, settings)

    sender.send_code(
        channel=CHANNEL_EMAIL,
        destination=email,
        code=code,
        purpose=PURPOSE,
        ttl_seconds=settings.code_ttl_seconds,
    )
    return LoginResult(LoginOutcome.CODE_SENT)


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
        expires_at = connection.execute(
            "insert into sessions (user_id, token_hash, expires_at, ip_address, user_agent) "
            "values (%s, %s, now() + make_interval(days => %s), %s, %s) returning expires_at",
            (
                user_id,
                hash_session_token(token),
                idle_days(is_host, settings),
                clean_ip(ip_address),
                (user_agent or "")[:USER_AGENT_MAX_LENGTH] or None,
            ),
        ).fetchone()[0]
    return SessionResult(SessionOutcome.OPENED, token=token, expires_at=expires_at)
