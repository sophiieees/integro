"""WhatsApp: segundo canal de los códigos, todavía sin construir.

Queda pendiente por decisión de Sophia del 17 de noviembre de 2026: hoy no hay
un número de WhatsApp para Íntegro y falta platicarlo con sus socias. Cuando
se decida, aquí va el envío con la plantilla que Meta apruebe; la tabla
one_time_codes ya admite el canal "whatsapp".
"""


class WhatsAppCodeSender:
    def send_code(
        self, *, channel: str, destination: str, code: str, purpose: str, ttl_seconds: int
    ) -> None:
        raise NotImplementedError("El envío por WhatsApp está pendiente (ADR 0014).")
