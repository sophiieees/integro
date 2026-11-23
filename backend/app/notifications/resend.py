"""Envío real de correos con Resend (ADR 0017).

Cada código y cada aviso sale como un correo con una llamada HTTPS a la API de Resend, con la llave del servidor. La
llave y el remitente salen de EMAIL_API_KEY y EMAIL_FROM; el dominio del remitente tiene que estar verificado en Resend.

- Un código que no se pudo enviar levanta DeliveryFailed: quien lo pidió no lo va a recibir y la API se lo dice. Un
  aviso de seguridad nunca levanta error: ya pasó lo que avisa (el intento fallido, el cambio de contraseña) y no se
  deshace por no poder avisar; se anota en el registro del servidor y ya.
- Un envío que falla por la red, por tiempo (5 segundos), por exceso de peticiones (429) o por error de Resend (5xx) se
  intenta una vez más con la misma Idempotency-Key, que Resend recuerda 24 horas: si el primer intento sí llegó, el
  segundo no manda un correo repetido. Los demás errores (llave mala, dominio sin verificar, correo mal escrito) no se
  reintentan.
- En el registro del servidor solo van el código HTTP y el nombre del error de Resend. Nunca la llave, el destinatario,
  el código ni el texto del correo.

No usa ninguna dependencia: la biblioteca estándar de Python alcanza.
"""

import json
import logging
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from app.notifications.messages import Message, code_message, notice_message
from app.notifications.sender import DeliveryFailed

RESEND_URL = "https://api.resend.com/emails"
# Segundos que se espera la respuesta de Resend en cada intento.
TIMEOUT_SECONDS = 5
ATTEMPTS = 2
# Segundos entre un intento y el siguiente.
PAUSE_SECONDS = 0.3
USER_AGENT = "integro-api"
# Qué se lee como máximo de una respuesta de error: es un texto corto.
RESPONSE_MAX_BYTES = 4096
ERROR_NAME = re.compile(r"^[a-z_]{1,64}$")
# Cuáles códigos de error de Resend merecen otro intento: ya hay una petición igual en curso, demasiadas peticiones
# o un error del propio Resend.
RETRY_STATUSES = {409, 429}

logger = logging.getLogger("integro.email")


def error_name(error: urllib.error.HTTPError) -> str:
    """El nombre del error que Resend explica en su respuesta (por ejemplo validation_error), o vacío."""
    try:
        body = json.loads(error.read(RESPONSE_MAX_BYTES))
    except (OSError, ValueError):
        return ""
    name = body.get("name") if isinstance(body, dict) else None
    return name if isinstance(name, str) and ERROR_NAME.match(name) else ""


class ResendCodeSender:
    def __init__(
        self,
        api_key: str,
        from_address: str,
        *,
        url: str = RESEND_URL,
        timeout: float = TIMEOUT_SECONDS,
        attempts: int = ATTEMPTS,
        pause: float = PAUSE_SECONDS,
    ):
        self._api_key = api_key
        self._from = from_address
        self._url = url
        self._timeout = timeout
        self._attempts = attempts
        self._pause = pause

    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        self._check_channel(channel)
        self._deliver(destination, code_message(purpose, code, ttl_seconds))

    def send_notice(self, *, channel: str, destination: str, kind: str, details: dict[str, Any]) -> None:
        self._check_channel(channel)
        message = notice_message(kind, details)
        try:
            self._deliver(destination, message)
        except DeliveryFailed:
            # Ya se anotó por qué. Un aviso no puede deshacer lo que avisa.
            pass

    @staticmethod
    def _check_channel(channel: str) -> None:
        # WhatsApp está pendiente (ADR 0014). Llegar aquí con otro canal es un error del programa, no de Resend.
        if channel != "email":
            raise ValueError(f"Este envío solo sabe de correo, no de «{channel}».")

    def _deliver(self, destination: str, message: Message) -> None:
        payload = json.dumps(
            {"from": self._from, "to": [destination], "subject": message.subject, "text": message.text, "html": message.html}
        ).encode("utf-8")
        idempotency_key = uuid.uuid4().hex
        for attempt in range(1, self._attempts + 1):
            retry, reason = self._post(payload, idempotency_key)
            if reason is None:
                return
            if not retry or attempt == self._attempts:
                raise DeliveryFailed(reason)
            time.sleep(self._pause)

    def _post(self, payload: bytes, idempotency_key: str) -> tuple[bool, str | None]:
        """Un intento. Devuelve (vale la pena reintentar, por qué falló o None si se envió)."""
        request = urllib.request.Request(
            self._url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": idempotency_key,
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                response.read(RESPONSE_MAX_BYTES)
            return False, None
        except urllib.error.HTTPError as error:
            logger.warning("Resend no envió el correo: HTTP %s %s", error.code, error_name(error))
            return error.code in RETRY_STATUSES or error.code >= 500, f"HTTP {error.code}"
        except (OSError, ValueError) as error:
            # OSError cubre red caída y tiempo agotado. Solo va la clase del error, nunca su texto, que puede traer la dirección.
            logger.warning("Resend no respondió: %s", type(error).__name__)
            return True, type(error).__name__
