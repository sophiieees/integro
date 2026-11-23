"""Cuando un código no se pudo enviar por correo.

El correo sale después de guardar lo que la persona pidió (registro, código de inicio de sesión, otro código). Si el
proveedor falla, el código existe pero no va a llegar. Cada ruta decide qué hacer (ADR 0017):

- Pedir otro código (resend-code) y el primer paso de iniciar sesión: contestan 503 con el código email_unavailable, y
  la persona vuelve a pedirlo.
- Registrarse y corregir el correo: lo ya guardado queda guardado (volver a mandar el formulario daría «ya existe una
  cuenta»), así que contestan lo de siempre con email_sent en false, y la persona usa «Enviar otro código».
- Recuperar la contraseña: contesta lo mismo de siempre. Si fallara distinto cuando la cuenta existe, la respuesta
  diría quién tiene cuenta.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.notifications.sender import DeliveryFailed

MESSAGE = "No pudimos enviar el correo. Espera un minuto e inténtalo de nuevo."


def delivery_failed_response(request: Request, error: DeliveryFailed) -> JSONResponse:
    # Misma forma que los demás avisos. El motivo (el código HTTP de Resend) no se le dice a nadie: está en el registro.
    body = {"errors": [{"field": "email", "code": "email_unavailable", "message": MESSAGE}]}
    return JSONResponse(status_code=503, content=body, headers={"Cache-Control": "no-store"})
