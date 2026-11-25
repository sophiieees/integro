"""Cifrado de datos sensibles con AES-256-GCM (regla de seguridad de CLAUDE.md).

La llave maestra vive en la variable de entorno DATA_ENCRYPTION_KEY, fuera del repositorio y de la base: al menos 43
caracteres al azar. De ella se saca, con HKDF-SHA256, una llave distinta de 32 bytes para cada uso (por ejemplo, la
clave del Authenticator): así lo cifrado para un uso no se puede descifrar ni hacer pasar como si fuera de otro.

Cada cifrado lleva 12 bytes al azar que lo hacen único, y 16 bytes al final que delatan cualquier cambio: si alguien
altera lo guardado, o lo mueve a la fila de otra persona, el descifrado falla en lugar de entregar otra cosa. Eso
último lo logra `associated`: un dato que no se cifra pero queda amarrado a lo cifrado (aquí, el id de la persona).

Lo que sale es texto en base64: los 12 bytes, lo cifrado y los 16 bytes, en ese orden.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# La versión de la llave con la que se cifra hoy. Si un día se cambia la llave, lo ya guardado dice con cuál se cifró.
CURRENT_KEY_VERSION = 1
NONCE_BYTES = 12
TAG_BYTES = 16
KEY_BYTES = 32


class EncryptionUnavailable(Exception):
    """Falta la llave de cifrado: no se puede cifrar ni descifrar."""


class DecryptionFailed(Exception):
    """Lo guardado no se pudo descifrar: se alteró, es de otra persona o de otro uso, o la llave cambió."""


def derive_key(master_key: str | None, purpose: str) -> bytes:
    """La llave de 32 bytes para ese uso, sacada de la llave maestra."""
    if not master_key:
        raise EncryptionUnavailable("Falta DATA_ENCRYPTION_KEY.")
    info = f"integro/{purpose}/v{CURRENT_KEY_VERSION}".encode("utf-8")
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=info).derive(master_key.encode("utf-8"))


def encrypt(master_key: str | None, purpose: str, plaintext: bytes, associated: bytes) -> str:
    """Cifra. Dos cifrados del mismo dato nunca salen iguales."""
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(derive_key(master_key, purpose)).encrypt(nonce, plaintext, associated)
    return base64.b64encode(nonce + sealed).decode("ascii")


def decrypt(master_key: str | None, purpose: str, token: str, associated: bytes) -> bytes:
    """Descifra, o levanta DecryptionFailed si lo guardado no es lo que se cifró para esa persona y ese uso."""
    key = derive_key(master_key, purpose)
    try:
        raw = base64.b64decode(token, validate=True)
    except (binascii.Error, ValueError):
        raise DecryptionFailed("no es base64") from None
    if len(raw) < NONCE_BYTES + TAG_BYTES:
        raise DecryptionFailed("demasiado corto")
    try:
        return AESGCM(key).decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], associated)
    except InvalidTag:
        raise DecryptionFailed("no coincide") from None
