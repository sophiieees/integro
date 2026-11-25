"""Los correos de Íntegro: el asunto y el texto de cada código y de cada aviso.

Todo en español y de tú. Ningún correo lleva contraseñas, y el código va solo en el cuerpo, no en el asunto: el asunto
se ve en la pantalla bloqueada. Cada mensaje sale en texto y en HTML (con los colores de la marca). Lo que viene de
fuera, como el navegador de quien intentó entrar, se escapa antes de ir al HTML.

Los textos de los avisos también los usa el modo desarrollo (console.py).
"""

import html
from dataclasses import dataclass
from typing import Any

# Colores de la web (web/assets/css/estilos.css).
GREEN = "#1F4D3A"
SAND = "#F3EEE4"
INK = "#142A21"

SIGNATURE = "Equipo de Íntegro"
NEVER_ASK = "Íntegro nunca te pedirá este código por teléfono, mensaje ni correo."

# Para qué sirve cada código: lo que dice el cuerpo y el asunto.
CODE_PURPOSES = {
    "verify_email": ("comprobar tu correo", "Tu código para comprobar tu correo en Íntegro"),
    "login": ("iniciar sesión", "Tu código para iniciar sesión en Íntegro"),
    "password_reset": ("recuperar tu contraseña", "Tu código para recuperar tu contraseña de Íntegro"),
}

NOTICE_SUBJECTS = {
    "failed_logins": "Hubo intentos fallidos de entrar a tu cuenta de Íntegro",
    "password_changed": "Cambiaste la contraseña de tu cuenta de Íntegro",
    "two_factor_enabled": "Activaste el Authenticator en tu cuenta de Íntegro",
}


@dataclass(frozen=True)
class Message:
    subject: str
    text: str
    html: str


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


def password_changed_text(details: dict[str, Any]) -> str:
    """El texto del aviso de que la contraseña cambió. No lleva ninguna contraseña ni código."""
    when = details["at"].strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    return (
        f"La contraseña de tu cuenta de Íntegro se cambió el {when}. "
        f"Navegador: {details.get('user_agent') or 'desconocido'}. "
        f"Dirección: {details.get('ip_address') or 'desconocida'}. "
        "Por seguridad cerramos todas tus sesiones. "
        "Si no fuiste tú, vuelve a recuperar tu contraseña desde «¿Olvidaste tu contraseña?»."
    )


def two_factor_enabled_text(details: dict[str, Any]) -> str:
    """El texto del aviso de que se activó el Authenticator. No lleva la clave ni ningún código."""
    when = details["at"].strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    return (
        f"El Authenticator de tu cuenta de Íntegro se activó el {when}. "
        f"Navegador: {details.get('user_agent') or 'desconocido'}. "
        f"Dirección: {details.get('ip_address') or 'desconocida'}. "
        "Si no fuiste tú, cambia tu contraseña de inmediato."
    )


KIND_TEXTS = {
    "failed_logins": failed_logins_text,
    "password_changed": password_changed_text,
    "two_factor_enabled": two_factor_enabled_text,
}


def minutes_text(ttl_seconds: int) -> str:
    """«5 minutos», «30 minutos» o «1 minuto»: lo que dura un código, redondeado hacia arriba."""
    minutes = max(1, -(-ttl_seconds // 60))
    return "1 minuto" if minutes == 1 else f"{minutes} minutos"


def _page(title: str, body_html: str) -> str:
    """El marco de todos los correos: un recuadro blanco sobre fondo arena, con el nombre arriba."""
    return (
        '<!doctype html><html lang="es-MX"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title></head>"
        f'<body style="margin:0;padding:24px;background:{SAND};font-family:Arial,Helvetica,sans-serif;color:{INK};">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;margin:0 auto;">'
        f'<tr><td style="padding:0 0 12px 0;font-size:20px;font-weight:bold;color:{GREEN};">Íntegro</td></tr>'
        '<tr><td style="background:#FFFFFF;padding:24px;border-radius:6px;font-size:16px;line-height:1.5;">'
        f"{body_html}"
        "</td></tr>"
        f'<tr><td style="padding:12px 0 0 0;font-size:13px;color:{INK};">{html.escape(SIGNATURE)}</td></tr>'
        "</table></body></html>"
    )


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;">{html.escape(text)}</p>'


def code_message(purpose: str, code: str, ttl_seconds: int) -> Message:
    """El correo con un código de un solo uso. purpose dice para qué es: verify_email, login o password_reset."""
    if purpose not in CODE_PURPOSES:
        raise ValueError(f"Código sin correo: {purpose}")
    action, subject = CODE_PURPOSES[purpose]
    lasts = f"Vence en {minutes_text(ttl_seconds)}. Escríbelo en la pantalla de Íntegro donde lo pediste."
    ignore = "Si no fuiste tú, ignora este correo."
    text = "\n\n".join(
        ["Hola,", f"Tu código para {action} es:", code, lasts, f"{ignore} {NEVER_ASK}", SIGNATURE]
    )
    body = (
        _paragraph("Hola,")
        + _paragraph(f"Tu código para {action} es:")
        + f'<p style="margin:0 0 16px 0;font-family:Consolas,Menlo,monospace;font-size:32px;letter-spacing:8px;'
        f'font-weight:bold;color:{GREEN};">{html.escape(code)}</p>'
        + _paragraph(lasts)
        + _paragraph(f"{ignore} {NEVER_ASK}")
    )
    return Message(subject=subject, text=text, html=_page(subject, body))


def notice_message(kind: str, details: dict[str, Any]) -> Message:
    """El correo de un aviso de seguridad: failed_logins o password_changed."""
    if kind not in KIND_TEXTS:
        raise ValueError(f"Aviso sin correo: {kind}")
    subject = NOTICE_SUBJECTS[kind]
    paragraph = KIND_TEXTS[kind](details)
    text = "\n\n".join(["Hola,", paragraph, SIGNATURE])
    return Message(subject=subject, text=text, html=_page(subject, _paragraph("Hola,") + _paragraph(paragraph)))
