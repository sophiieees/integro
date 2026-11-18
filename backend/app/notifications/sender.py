"""Contrato que cumple todo lo que envía un código a una persona."""

from typing import Protocol


class CodeSender(Protocol):
    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        """Entrega el código por ese canal (email o whatsapp) a ese destino."""
        ...
