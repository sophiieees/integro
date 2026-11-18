"""Envío de códigos y avisos a las personas.

Canales decididos en el ADR 0014: correo, que va primero, y WhatsApp, que
queda pendiente. El SMS está fuera.
"""

from app.core.config import Settings
from app.notifications.console import ConsoleCodeSender
from app.notifications.sender import CodeSender


def create_code_sender(settings: Settings) -> CodeSender:
    """Elige cómo salen los códigos según la configuración."""
    if settings.email_delivery == "console":
        return ConsoleCodeSender()
    raise ValueError(f"Modo de envío sin construir: {settings.email_delivery}")
