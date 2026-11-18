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

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Convierte la contraseña con Argon2id. El resultado empieza con $argon2id$."""
    return _password_hasher.hash(password)


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
