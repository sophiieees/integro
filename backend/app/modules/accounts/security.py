"""Contraseñas y códigos: lo que se guarda nunca es lo que la persona escribe.

- La contraseña se convierte con Argon2id (regla de seguridad de CLAUDE.md).
- El código de un solo uso se guarda como huella calculada con una llave
  secreta del servidor (HMAC-SHA-256). Sin la llave, quien robe la base no
  puede probar el millón de combinaciones de un código de seis dígitos.
"""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Convierte la contraseña con Argon2id. El resultado empieza con $argon2id$."""
    return _password_hasher.hash(password)


# Contraseña convertida que no es de nadie. Cuando el correo no tiene cuenta se
# compara contra ella, para tardar lo mismo que con una cuenta real y que el
# tiempo de respuesta no revele qué correos existen.
_NOBODY_HASH = _password_hasher.hash(secrets.token_hex(16))


def verify_password(password: str, password_hash: str | None) -> bool:
    """Dice si la contraseña escrita corresponde a la guardada.

    Con password_hash en None (el correo no tiene cuenta) hace el mismo
    trabajo y responde que no.
    """
    try:
        _password_hasher.verify(password_hash or _NOBODY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def generate_session_token() -> str:
    """Llave de sesión al azar (256 bits). Es lo que recibe la persona."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Huella de la llave de sesión (SHA-256 en hexadecimal). Es lo que se guarda.

    La llave tiene 256 bits al azar, así que no hace falta una llave secreta
    como con los códigos de seis dígitos.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_code(length: int) -> str:
    """Código al azar de solo dígitos, con ceros a la izquierda si tocan."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_code(code: str, *, secret: str, purpose: str, destination: str) -> str:
    """Huella del código, en hexadecimal (64 caracteres).

    Entran también el propósito y el destino: la misma cifra para otra persona
    o para otro uso da otra huella.
    """
    message = f"{purpose}:{destination}:{code}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def same_hash(first: str, second: str) -> bool:
    """Compara dos huellas sin revelar por el tiempo en qué carácter difieren."""
    return hmac.compare_digest(first, second)
