"""CAPTCHA con Cloudflare Turnstile en las acciones que cualquiera puede pedir sin sesión.

Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016):

- Cinco rutas lo piden: crear la cuenta, el primer paso de iniciar sesión, pedir el código de recuperar la contraseña,
  pedir otro código de verificación y corregir el correo de una cuenta sin comprobar. Los pasos en los que se
  escribe un código ya tienen límite de intentos y no lo piden.
- Siempre está activo: no hay interruptor. En la computadora de Sophia y en las pruebas se usan las llaves de prueba de
  Cloudflare, que siempre pasan.
- Si Cloudflare no responde, o la llave secreta falta o no sirve, la petición se rechaza (503). Nunca se deja pasar.

La página resuelve el desafío de Cloudflare y manda el resultado en el encabezado X-Captcha-Token. La API se lo
pregunta a Cloudflare con la llave secreta, que solo vive en el servidor. Un resultado sirve una sola vez y dura 5
minutos, así que la página pide uno nuevo antes de cada petición.

Una ruta lo pide así:

    @router.post("/ruta", dependencies=[Depends(require_captcha)])
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from enum import Enum
from typing import Protocol

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings

CAPTCHA_HEADER = "X-Captcha-Token"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Cloudflare nunca entrega un resultado de más de 2048 caracteres; uno más largo no puede ser suyo.
TOKEN_MAX_LENGTH = 2048
# Segundos que se espera la respuesta de Cloudflare antes de darla por caída.
TIMEOUT_SECONDS = 5
# Qué se lee como máximo de la respuesta de Cloudflare: es un texto corto.
RESPONSE_MAX_BYTES = 65536

MESSAGE = "No pudimos comprobar que eres una persona. Inténtalo de nuevo."

# Errores que son de nuestra configuración, no de la persona: con ellos nadie podría pasar.
CONFIGURATION_ERRORS = {"missing-input-secret", "invalid-input-secret", "internal-error"}

logger = logging.getLogger("integro.captcha")


class CaptchaResult(Enum):
    PASSED = "passed"
    # La persona no lo resolvió, el resultado no existe, venció o ya se usó: puede intentarlo de nuevo.
    FAILED = "failed"
    # Cloudflare no respondió o la llave secreta no sirve: no se puede comprobar, y se rechaza.
    UNAVAILABLE = "unavailable"


class CaptchaVerifier(Protocol):
    def verify(self, token: str | None) -> CaptchaResult:
        """Dice si el resultado del desafío vale. Nunca levanta error: si no puede comprobar, UNAVAILABLE."""
        ...


class TurnstileVerifier:
    """Le pregunta a Cloudflare si el resultado del desafío es bueno."""

    def __init__(self, secret_key: str, url: str = TURNSTILE_VERIFY_URL, timeout: float = TIMEOUT_SECONDS):
        self._secret_key = secret_key
        self._url = url
        self._timeout = timeout

    def verify(self, token: str | None) -> CaptchaResult:
        if not token or not token.strip() or len(token) > TOKEN_MAX_LENGTH:
            return CaptchaResult.FAILED
        form = urllib.parse.urlencode({"secret": self._secret_key, "response": token}).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=form, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read(RESPONSE_MAX_BYTES))
        except (OSError, ValueError) as error:
            # OSError cubre red caída, tiempo agotado y respuestas de error de HTTP. En el registro solo va la clase
            # del error: nunca el resultado de la persona ni la llave secreta.
            logger.warning("Cloudflare Turnstile no respondió: %s", type(error).__name__)
            return CaptchaResult.UNAVAILABLE
        if not isinstance(payload, dict):
            logger.warning("Cloudflare Turnstile contestó algo que no se entiende.")
            return CaptchaResult.UNAVAILABLE
        if payload.get("success") is True:
            return CaptchaResult.PASSED
        codes = payload.get("error-codes")
        codes = [code for code in codes if isinstance(code, str)] if isinstance(codes, list) else []
        if CONFIGURATION_ERRORS.intersection(codes):
            logger.error("Cloudflare Turnstile rechazó la configuración: %s", ", ".join(sorted(codes)))
            return CaptchaResult.UNAVAILABLE
        return CaptchaResult.FAILED


class UnconfiguredVerifier:
    """Sin llave secreta no hay con qué comprobar: toda petición se rechaza, nunca se deja pasar."""

    def verify(self, token: str | None) -> CaptchaResult:
        logger.error("Falta TURNSTILE_SECRET_KEY: las acciones que piden CAPTCHA se rechazan.")
        return CaptchaResult.UNAVAILABLE


def secret_key_of(settings: Settings) -> str | None:
    secret = settings.turnstile_secret_key.get_secret_value().strip() if settings.turnstile_secret_key else ""
    return secret or None


def site_key_of(settings: Settings) -> str | None:
    return (settings.turnstile_site_key or "").strip() or None


def create_captcha_verifier(settings: Settings) -> CaptchaVerifier:
    """Elige cómo se comprueba según la configuración."""
    secret = secret_key_of(settings)
    return TurnstileVerifier(secret) if secret else UnconfiguredVerifier()


class CaptchaRejected(Exception):
    """La petición no pasó el CAPTCHA. 400 si la persona puede reintentar; 503 si no se pudo comprobar."""

    def __init__(self, status_code: int, code: str):
        super().__init__(code)
        self.status_code = status_code
        self.code = code


def captcha_rejected_response(request: Request, error: CaptchaRejected) -> JSONResponse:
    # Misma forma que los demás avisos: la página lo muestra donde muestra los errores.
    body = {"errors": [{"field": "captcha", "code": error.code, "message": MESSAGE}]}
    return JSONResponse(status_code=error.status_code, content=body, headers={"Cache-Control": "no-store"})


def require_captcha(
    request: Request,
    captcha_token: str | None = Header(default=None, alias=CAPTCHA_HEADER, description="Resultado del desafío de Cloudflare Turnstile."),
) -> None:
    """Corta la petición si el resultado del CAPTCHA falta, no vale o no se pudo comprobar."""
    result = request.app.state.captcha.verify(captcha_token)
    if result is CaptchaResult.PASSED:
        return
    if result is CaptchaResult.UNAVAILABLE:
        raise CaptchaRejected(503, "captcha_unavailable")
    raise CaptchaRejected(400, "captcha_failed")
