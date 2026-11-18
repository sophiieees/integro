"""Modo desarrollo: el código se escribe en la ventana del servidor.

Sirve mientras no haya una empresa contratada para enviar correos (ADR 0014).
No debe usarse con personas reales: el código queda a la vista de quien vea
esa ventana.
"""


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
