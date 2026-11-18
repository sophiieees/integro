"""Contrato que cumple todo lo que envía un código o un aviso a una persona."""

from typing import Any, Protocol


class CodeSender(Protocol):
    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        """Entrega el código por ese canal (email o whatsapp) a ese destino."""
        ...

    def send_notice(self, *, channel: str, destination: str, kind: str, details: dict[str, Any]) -> None:
        """Entrega un aviso de seguridad. kind dice cuál es; details trae sus datos.

        Avisos que existen: failed_logins (varios intentos fallidos de entrar a
        la cuenta), con failures, at, ip_address y user_agent.
        """
        ...
