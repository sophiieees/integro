"""Configuración del backend, leída de variables de entorno.

Ningún valor de conexión vive en el código. En desarrollo salen del archivo
backend/.env, que git ignora; en la nube saldrán de las variables de entorno
del proveedor. Si una variable de entorno y el archivo .env traen el mismo
nombre, gana la variable de entorno.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta backend/, sin importar desde dónde se arranque el servidor.
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIRECTORY / ".env"
# Carpeta web/ del repositorio: las páginas que la API puede mostrar.
WEB_DIRECTORY = BACKEND_DIRECTORY.parent / "web"


class ConfigurationError(RuntimeError):
    """Falta una variable de entorno o trae un valor que no sirve."""


class Settings(BaseSettings):
    """Variables que el backend necesita para arrancar.

    Las de conexión, la llave de los códigos y el modo de envío no tienen valor
    por defecto: si falta una, el backend no arranca y dice cuál. Así nunca se
    conecta por descuido a una base que no es ni envía códigos de una forma
    que nadie eligió.
    """

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    database_host: str = Field(min_length=1)
    database_port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1)
    database_user: str = Field(min_length=1)
    # SecretStr evita que la contraseña aparezca al imprimir la configuración.
    database_password: SecretStr = Field(min_length=1)
    # Cifrado de la conexión con la base. «prefer» cifra si el servidor lo ofrece y sigue sin cifrar si no: sirve en
    # la computadora de Sophia, donde PostgreSQL no tiene SSL. En la nube (Neon) va «require»: sin cifrado no conecta.
    database_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    # Segundos que se espera una conexión antes de dar la base por no disponible. En la nube, la primera conexión
    # después de que la base se suspendió tarda más (Neon despierta en unos cientos de milisegundos o más).
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=60)

    # Llave secreta con la que se calcula la huella de los códigos de un solo
    # uso. Sin ella, quien robe la base adivina un código de seis dígitos.
    code_hash_secret: SecretStr = Field(min_length=32)
    # Cómo salen los correos. "console": modo desarrollo, el código se escribe
    # en la ventana del servidor en lugar de enviarse (ADR 0014). "resend": correo
    # real con Resend (ADR 0017); pide EMAIL_API_KEY y EMAIL_FROM, y si falta una
    # el backend no arranca y dice cuál.
    email_delivery: Literal["console", "resend"]
    # La llave de Resend, solo en las variables de entorno del proveedor. SecretStr evita que aparezca al imprimir.
    email_api_key: SecretStr | None = None
    # El remitente, por ejemplo «Íntegro <no-responder@tu-dominio>». Su dominio tiene que estar verificado en Resend.
    email_from: str | None = None

    # Límites de los códigos (ADR 0014). Son los valores decididos; se pueden
    # cambiar con una variable de entorno sin tocar el código.
    code_length: int = Field(default=6, ge=4, le=10)
    code_ttl_seconds: int = Field(default=300, ge=30)
    code_max_attempts: int = Field(default=5, ge=1)
    code_resend_wait_seconds: int = Field(default=60, ge=0)
    code_max_per_hour: int = Field(default=5, ge=1)
    # El código de recuperar la contraseña dura más que los demás (decisión del 21 de noviembre de 2026: 30 minutos).
    password_reset_ttl_seconds: int = Field(default=1800, ge=30)

    # Contraseñas incorrectas (ADR 0014). La cuenta nunca se bloquea: a tantos
    # fallos seguidos se avisa al dueño, y a tantos fallos dentro de los
    # minutos de espera, el dispositivo que intenta espera esos minutos.
    login_notice_after_failures: int = Field(default=3, ge=1)
    login_wait_after_failures: int = Field(default=6, ge=1)
    login_wait_minutes: int = Field(default=15, ge=1)

    # Días sin uso que aguanta una sesión antes de cerrarse sola (ADR 0014).
    # El anfitrión maneja dinero y propiedades, por eso la suya dura menos.
    session_idle_days_guest: int = Field(default=30, ge=1)
    session_idle_days_host: int = Field(default=7, ge=1)
    # Quien es administrador (tabla admins) tiene una sesión corta en todo el sitio: se cierra sola a los
    # 30 minutos sin uso y, aunque se use todo el tiempo, a las 12 horas de haber iniciado sesión.
    # Decisión de Sophia del 21 de noviembre de 2026 (ADR 0014).
    session_idle_minutes_admin: int = Field(default=30, ge=1)
    session_max_hours_admin: int = Field(default=12, ge=1)
    # La llave de sesión viaja en una cookie (ADR 0015). Con esto encendido el
    # navegador solo la manda por HTTPS. Va encendido salvo que se apague a
    # propósito, y solo se apaga en desarrollo, donde el servidor local no
    # tiene HTTPS.
    session_cookie_secure: bool = True
    # Direcciones desde las que una página puede pedir cambios con sesión,
    # además de la dirección de la propia API, que siempre vale. Separadas por
    # comas, por ejemplo: https://integro.mx,https://www.integro.mx
    allowed_origins: str = ""

    # La API muestra también las páginas de web/ en su misma dirección, para
    # que la página y la API compartan sitio y la cookie de sesión viaje
    # (decisión de Sophia del 19 de noviembre de 2026). Solo ocurre si la
    # carpeta web/ existe junto a backend/. Se apaga con SERVE_WEB=false.
    serve_web: bool = True

    # Detrás de un proxy (en Vercel, quien contesta primero es Vercel), la dirección de quien pide y si la
    # página llegó por HTTPS vienen en los encabezados X-Forwarded-For y X-Forwarded-Proto. Cualquiera puede escribir
    # esos encabezados, por eso solo se creen si esto está encendido, y solo se enciende donde el proxy los
    # reescribe siempre (Vercel). En la computadora de Sophia va apagado.
    trust_proxy_headers: bool = False

    # CAPTCHA con Cloudflare Turnstile (ADR 0016). La llave pública va dentro de las páginas, que la piden a la API; la
    # secreta solo la usa el servidor. Siempre hay CAPTCHA: no hay interruptor, y si falta alguna llave las acciones que
    # lo piden se rechazan en lugar de dejar pasar. En desarrollo y en pruebas valen las llaves de prueba de Cloudflare.
    turnstile_site_key: str | None = None
    turnstile_secret_key: SecretStr | None = None

    # Llave maestra para cifrar datos sensibles con AES-256-GCM (app/core/encryption.py); hoy, la clave del
    # Authenticator. Al menos 43 caracteres al azar. Vive solo en las variables de entorno, nunca en el repositorio ni
    # en la base, y cada ambiente tiene la suya. Si falta, la API arranca y lo que necesita cifrar contesta 503; si
    # viene pero es más corta, el backend no arranca y lo dice.
    data_encryption_key: SecretStr | None = Field(default=None, min_length=43)
    # Authenticator (bitácora 41.11 y la pieza 3.2): a tantos códigos incorrectos seguidos, la persona espera esos minutos.
    two_factor_max_attempts: int = Field(default=5, ge=1)
    two_factor_wait_minutes: int = Field(default=15, ge=1)


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    """Lee y valida la configuración.

    El error de validación original incluye los valores recibidos, entre ellos
    la contraseña. Por eso se reemplaza por uno que solo nombra las variables.
    """
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        problems = []
        for detail in error.errors():
            variable = str(detail["loc"][0]).upper()
            reason = "falta" if detail["type"] == "missing" else "valor no válido"
            problems.append(f"{variable} ({reason})")
        raise ConfigurationError(
            "Configuración incompleta. Revisa backend/.env o las variables de "
            "entorno: " + ", ".join(problems) + "."
        ) from None
