"""Modo desarrollo: el código o el aviso se escribe en la ventana del servidor.

Sirve mientras no haya una empresa contratada para enviar correos (ADR 0014).
No debe usarse con personas reales: el código queda a la vista de quien vea
esa ventana.
"""

from typing import Any


def failed_logins_text(details: dict[str, Any]) -> str:
    """El texto del aviso de intentos fallidos. No lleva ninguna contraseña."""
    when = details["at"].strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    return (
        f"Hubo {details['failures']} intentos fallidos de entrar a tu cuenta. "
        f"Último intento: {when}. "
        f"Navegador: {details.get('user_agent') or 'desconocido'}. "
        f"Dirección: {details.get('ip_address') or 'desconocida'}. "
        "Si no fuiste tú, cambia tu contraseña."
    )


class ConsoleCodeSender:
    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        minutes = ttl_seconds // 60
        print(
            f"[MODO DESARROLLO] Código para {destination} ({channel}, {purpose}): "
            f"{code}. Vence en {minutes} minutos.",
            flush=True,
        )

    def send_notice(self, *, channel: str, destination: str, kind: str, details: dict[str, Any]) -> None:
        text = failed_logins_text(details) if kind == "failed_logins" else str(details)
        print(f"[MODO DESARROLLO] Aviso para {destination} ({channel}, {kind}): {text}", flush=True)
