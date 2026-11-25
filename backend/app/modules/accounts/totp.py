"""Los códigos del Authenticator (TOTP), sin base de datos ni red: se prueban solos.

Es el estándar que usan Google Authenticator y Microsoft Authenticator (RFC 6238 sobre RFC 4226): una clave secreta
que comparten la aplicación y el servidor, y un código de 6 dígitos que sale de esa clave y de la hora, y cambia cada
30 segundos. Con SHA-1, que es lo que todas las aplicaciones entienden; aquí SHA-1 no firma nada, solo mezcla la clave
con la hora, y el estándar lo sigue considerando seguro para este uso.

- Un «periodo» es el número de bloques de 30 segundos desde 1970. El código de un periodo sirve durante ese periodo.
- Se aceptan también el periodo anterior y el siguiente, por si el reloj del celular va un poco desfasado.
- Un código no sirve dos veces: quien comprueba dice cuál fue el último periodo aceptado y no se acepta ese ni uno
  anterior.
"""

import base64
import hashlib
import hmac
import os
import struct
from urllib.parse import quote, urlencode

DIGITS = 6
PERIOD_SECONDS = 30
# Cuántos periodos antes y después del actual se aceptan.
WINDOW = 1
# 20 bytes (160 bits), lo que recomienda el estándar para SHA-1.
SECRET_BYTES = 20
ISSUER = "Íntegro"


def generate_secret() -> bytes:
    """Una clave nueva, al azar."""
    return os.urandom(SECRET_BYTES)


def to_base32(secret: bytes) -> str:
    """La clave como la escribe una persona en su aplicación: letras mayúsculas y números del 2 al 7, sin «=»."""
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def step_at(timestamp: float) -> int:
    """El periodo de 30 segundos al que pertenece ese instante (segundos desde 1970)."""
    return int(timestamp // PERIOD_SECONDS)


def code_at(secret: bytes, step: int, digits: int = DIGITS) -> str:
    """El código de ese periodo (RFC 4226, con el periodo como contador)."""
    digest = hmac.new(secret, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % (10**digits)).zfill(digits)


def matching_step(secret: bytes, code: str, timestamp: float, last_used_step: int | None = None) -> int | None:
    """El periodo cuyo código es el que se escribió, o None si no es de ninguno que valga.

    Valen el periodo actual, el anterior y el siguiente, siempre que sean posteriores a last_used_step. La comparación
    tarda lo mismo acierte o no, para que el tiempo no diga qué tan cerca estuvo.
    """
    if len(code) != DIGITS or not code.isascii() or not code.isdigit():
        return None
    current = step_at(timestamp)
    found = None
    for step in range(current - WINDOW, current + WINDOW + 1):
        if step < 0 or (last_used_step is not None and step <= last_used_step):
            continue
        if hmac.compare_digest(code_at(secret, step), code) and found is None:
            found = step
    return found


def provisioning_uri(secret: bytes, account: str) -> str:
    """La dirección otpauth:// que una aplicación Authenticator lee (de un código QR) para dar de alta la clave."""
    label = quote(f"{ISSUER}:{account}", safe="")
    query = urlencode(
        {"secret": to_base32(secret), "issuer": ISSUER, "algorithm": "SHA1", "digits": DIGITS, "period": PERIOD_SECONDS},
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{query}"
