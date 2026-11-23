"""Modo desarrollo: el código o el aviso se escribe en la ventana del servidor.

Sirve mientras no haya una empresa contratada para enviar correos (ADR 0014).
No debe usarse con personas reales: el código queda a la vista de quien vea
esa ventana.
"""

from typing import Any

from app.notifications.messages import KIND_TEXTS, failed_logins_text, password_changed_text  # noqa: F401


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
        text = KIND_TEXTS[kind](details) if kind in KIND_TEXTS else str(details)
        print(f"[MODO DESARROLLO] Aviso para {destination} ({channel}, {kind}): {text}", flush=True)
