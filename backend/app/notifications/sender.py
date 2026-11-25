"""Contrato que cumple todo lo que envía un código o un aviso a una persona."""

from typing import Any, Protocol


class DeliveryFailed(Exception):
    """Un código no se pudo enviar y la persona no lo va a recibir. Los avisos de seguridad nunca la levantan."""


class CodeSender(Protocol):
    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        """Entrega el código por ese canal (email o whatsapp) a ese destino. Si no se puede, levanta DeliveryFailed."""
        ...

    def send_notice(self, *, channel: str, destination: str, kind: str, details: dict[str, Any]) -> None:
        """Entrega un aviso de seguridad. kind dice cuál es; details trae sus datos.

        Avisos que existen: failed_logins (varios intentos fallidos de entrar a
        la cuenta), con failures, at, ip_address y user_agent; y password_changed
        (la contraseña de la cuenta se cambió al recuperarla), con at, ip_address
        y user_agent; y two_factor_enabled (se activó el Authenticator de la cuenta),
        con at, ip_address y user_agent. Ningún aviso lleva contraseñas ni códigos. Un aviso que no se pudo enviar no levanta error: lo
        que avisa ya pasó y no se deshace.
        """
        ...
