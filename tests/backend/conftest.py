"""Preparación común de las pruebas del backend."""

import socket
import sys
from pathlib import Path

import pytest

# Las pruebas viven en tests/backend/ y el código en backend/. Se agrega esa
# carpeta a la ruta de Python para poder escribir "from app...".
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.core.config import Settings  # noqa: E402

DATABASE_VARIABLES = (
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
)


@pytest.fixture
def closed_port() -> int:
    """Un puerto de esta computadora donde no escucha nadie."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def settings_without_database(closed_port: int) -> Settings:
    """Configuración que apunta a una base que no existe. No usa la base real."""
    return Settings(
        _env_file=None,
        database_host="127.0.0.1",
        database_port=closed_port,
        database_name="integro",
        database_user="integro_api",
        database_password="clave-inventada-para-la-prueba",
    )


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Quita las variables DATABASE_* para que la prueba ponga las suyas."""
    for variable in DATABASE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch
