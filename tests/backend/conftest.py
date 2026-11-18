"""Preparación común de las pruebas del backend."""

import socket
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

# Las pruebas viven en tests/backend/ y el código en backend/. Se agrega esa
# carpeta a la ruta de Python para poder escribir "from app...".
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.core.config import ENV_FILE, Settings, load_settings  # noqa: E402
from app.database.connection import create_pool  # noqa: E402

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


@pytest.fixture(scope="session")
def real_pool():
    """Grupo de conexiones a la base real: integro, con el usuario de backend/.env."""
    if not ENV_FILE.exists():
        pytest.skip("Falta backend/.env: sin él no hay con qué conectarse a la base real.")
    pool = create_pool(load_settings())
    pool.open(wait=True, timeout=10)
    yield pool
    pool.close()


class SingleConnectionPool:
    """Se hace pasar por el grupo y entrega siempre la misma conexión.

    Esa conexión ya tiene una transacción abierta que la prueba deshace al
    final. Lo que el código "confirma" dentro queda como punto de guardado y
    desaparece con ella: nada llega a guardarse en la base.
    """

    def __init__(self, connection):
        self._connection = connection

    @contextmanager
    def connection(self, timeout=None):
        yield self._connection


@pytest.fixture
def rollback_pool(real_pool):
    """Un grupo para pruebas que escriben: todo se deshace al terminar la prueba."""
    with real_pool.connection() as connection:
        with connection.transaction(force_rollback=True):
            yield SingleConnectionPool(connection)


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Quita las variables DATABASE_* para que la prueba ponga las suyas."""
    for variable in DATABASE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch
