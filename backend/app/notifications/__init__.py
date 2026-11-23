"""Envío de códigos y avisos a las personas.

Canales decididos en el ADR 0014: correo, que va primero, y WhatsApp, que
queda pendiente. El SMS está fuera.
"""

from app.core.config import ConfigurationError, Settings
from app.notifications.console import ConsoleCodeSender
from app.notifications.resend import ResendCodeSender
from app.notifications.sender import CodeSender


def create_code_sender(settings: Settings) -> CodeSender:
    """Elige cómo salen los códigos según la configuración."""
    if settings.email_delivery == "console":
        return ConsoleCodeSender()
    if settings.email_delivery == "resend":
        api_key = settings.email_api_key.get_secret_value().strip() if settings.email_api_key else ""
        sender = (settings.email_from or "").strip()
        missing = [name for name, value in (("EMAIL_API_KEY", api_key), ("EMAIL_FROM", sender)) if not value]
        if missing:
            # Con el modo elegido a propósito y sin con qué enviar, mejor no arrancar que fingir que se envía.
            raise ConfigurationError(
                "Con EMAIL_DELIVERY=resend hacen falta estas variables de entorno: " + ", ".join(missing) + "."
            )
        return ResendCodeSender(api_key, sender)
    raise ValueError(f"Modo de envío sin construir: {settings.email_delivery}")
