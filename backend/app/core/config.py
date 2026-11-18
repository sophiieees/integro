"""Configuración del backend, leída de variables de entorno.

Ningún valor de conexión vive en el código. En desarrollo salen del archivo
backend/.env, que git ignora; en la nube saldrán de las variables de entorno
del proveedor. Si una variable de entorno y el archivo .env traen el mismo
nombre, gana la variable de entorno.
"""

from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta backend/, sin importar desde dónde se arranque el servidor.
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIRECTORY / ".env"


class ConfigurationError(RuntimeError):
    """Falta una variable de entorno o trae un valor que no sirve."""


class Settings(BaseSettings):
    """Variables que el backend necesita para arrancar.

    Ninguna tiene valor por defecto: si falta una, el backend no arranca y dice
    cuál. Así nunca se conecta por descuido a una base que no es.
    """

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    database_host: str = Field(min_length=1)
    database_port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1)
    database_user: str = Field(min_length=1)
    # SecretStr evita que la contraseña aparezca al imprimir la configuración.
    database_password: SecretStr = Field(min_length=1)


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
