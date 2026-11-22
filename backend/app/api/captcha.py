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

- Cada ruta espera una acción distinta (login, register...), que el widget de su pantalla declara. Cloudflare la
  devuelve al comprobar, y un resultado de una acción no sirve en otra.
- Las llaves de prueba de Cloudflare (empiezan con 1x, 2x o 3x) siempre pasan, así que solo se aceptan en la computadora
  de Sophia (SESSION_COOKIE_SECURE=false). En la nube se rechazan: dejarían pasar a cualquiera sin que nadie lo notara.
  Con ellas Cloudflare no devuelve la acción, y por eso solo con ellas no se compara.

Una ruta lo pide así:

    @router.post("/ruta", dependencies=[Depends(require_captcha("login"))])
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
    def verify(self, token: str | None, action: str) -> CaptchaResult:
        """Dice si el resultado del desafío vale para esa acción. Nunca levanta error: si no puede comprobar, UNAVAILABLE."""
        ...


class TurnstileVerifier:
    """Le pregunta a Cloudflare si el resultado del desafío es bueno."""

    def __init__(
        self,
        secret_key: str,
        url: str = TURNSTILE_VERIFY_URL,
        timeout: float = TIMEOUT_SECONDS,
        check_action: bool = True,
    ):
        self._secret_key = secret_key
        self._url = url
        self._timeout = timeout
        # Con las llaves de prueba Cloudflare no devuelve la acción, y no hay con qué compararla.
        self._check_action = check_action

    def verify(self, token: str | None, action: str) -> CaptchaResult:
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
            # Un resultado de otra acción (por ejemplo, el del registro usado en el inicio de sesión) no vale.
            if self._check_action and payload.get("action") != action:
                return CaptchaResult.FAILED
            return CaptchaResult.PASSED
        codes = payload.get("error-codes")
        codes = [code for code in codes if isinstance(code, str)] if isinstance(codes, list) else []
        if CONFIGURATION_ERRORS.intersection(codes):
            logger.error("Cloudflare Turnstile rechazó la configuración: %s", ", ".join(sorted(codes)))
            return CaptchaResult.UNAVAILABLE
        return CaptchaResult.FAILED


class UnconfiguredVerifier:
    """Sin una llave que sirva no hay con qué comprobar: toda petición se rechaza, nunca se deja pasar."""

    def __init__(self, reason: str = "Falta TURNSTILE_SECRET_KEY"):
        self._reason = reason

    def verify(self, token: str | None, action: str) -> CaptchaResult:
        logger.error("%s: las acciones que piden CAPTCHA se rechazan.", self._reason)
        return CaptchaResult.UNAVAILABLE


def is_test_key(key: str) -> bool:
    """Las llaves de prueba de Cloudflare empiezan con 1x, 2x o 3x; las reales, con 0x."""
    return key.startswith(("1x", "2x", "3x"))


def allows_test_keys(settings: Settings) -> bool:
    """Las llaves de prueba solo valen donde la cookie de sesión puede viajar sin HTTPS: la computadora de Sophia."""
    return not settings.session_cookie_secure


def secret_key_of(settings: Settings) -> str | None:
    secret = settings.turnstile_secret_key.get_secret_value().strip() if settings.turnstile_secret_key else ""
    return secret or None


def site_key_of(settings: Settings) -> str | None:
    """La llave pública, o None si falta o es de prueba donde no se aceptan."""
    key = (settings.turnstile_site_key or "").strip()
    if not key or (is_test_key(key) and not allows_test_keys(settings)):
        return None
    return key


def create_captcha_verifier(settings: Settings, url: str = TURNSTILE_VERIFY_URL) -> CaptchaVerifier:
    """Elige cómo se comprueba según la configuración."""
    secret = secret_key_of(settings)
    if secret is None:
        return UnconfiguredVerifier()
    if is_test_key(secret):
        if not allows_test_keys(settings):
            return UnconfiguredVerifier("TURNSTILE_SECRET_KEY es una llave de prueba y aquí no se aceptan")
        return TurnstileVerifier(secret, url=url, check_action=False)
    return TurnstileVerifier(secret, url=url)


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


def require_captcha(action: str):
    """La dependencia de una ruta: corta la petición si el resultado del CAPTCHA falta, no vale para esa acción o no
    se pudo comprobar. La acción es la que declara el widget de la pantalla (letras, números, _ y -)."""

    def dependency(
        request: Request,
        captcha_token: str | None = Header(
            default=None, alias=CAPTCHA_HEADER, description="Resultado del desafío de Cloudflare Turnstile."
        ),
    ) -> None:
        result = request.app.state.captcha.verify(captcha_token, action)
        if result is CaptchaResult.PASSED:
            return
        if result is CaptchaResult.UNAVAILABLE:
            raise CaptchaRejected(503, "captcha_unavailable")
        raise CaptchaRejected(400, "captcha_failed")

    return dependency
