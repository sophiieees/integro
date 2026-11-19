"""Preparación común de las pruebas del backend."""

import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from http.cookies import Morsel, SimpleCookie
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Las pruebas viven en tests/backend/ y el código en backend/. Se agrega esa
# carpeta a la ruta de Python para poder escribir "from app...".
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.api.auth import SESSION_COOKIE  # noqa: E402
from app.core.config import ENV_FILE, Settings, load_settings  # noqa: E402
from app.database.connection import create_pool  # noqa: E402
from app.main import create_app  # noqa: E402

SETTINGS_VARIABLES = (
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "CODE_HASH_SECRET",
    "EMAIL_DELIVERY",
    "CODE_LENGTH",
    "CODE_TTL_SECONDS",
    "CODE_MAX_ATTEMPTS",
    "CODE_RESEND_WAIT_SECONDS",
    "CODE_MAX_PER_HOUR",
    "SESSION_COOKIE_SECURE",
)

# Llave inventada, solo para pruebas que no usan la configuración real.
TEST_CODE_HASH_SECRET = "llave-inventada-para-las-pruebas-0123456789"


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
        code_hash_secret=TEST_CODE_HASH_SECRET,
        email_delivery="console",
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


class RecordingSender:
    """En lugar de enviar el código lo anota, para que la prueba pueda leerlo."""

    def __init__(self):
        self.sent = []
        self.notices = []

    def send_code(self, **message):
        self.sent.append(message)

    def send_notice(self, **notice):
        self.notices.append(notice)

    @property
    def last_code(self) -> str:
        return self.sent[-1]["code"]


def session_cookie(response) -> Morsel | None:
    """La cookie de sesión que entrega una respuesta, con sus atributos, o None si no trae."""
    for header in response.headers.get_list("set-cookie"):
        cookies = SimpleCookie()
        cookies.load(header)
        if SESSION_COOKIE in cookies:
            return cookies[SESSION_COOKIE]
    return None


def with_session(token: str) -> dict:
    """El encabezado con el que un navegador manda la cookie de sesión."""
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


@dataclass
class Api:
    """La API completa para una prueba: cliente, base que se deshace y códigos enviados."""

    client: TestClient
    pool: SingleConnectionPool
    sender: RecordingSender
    settings: Settings


@pytest.fixture
def api(rollback_pool):
    """La API real sobre la base real, con todo lo que escriba deshecho al terminar."""
    settings = load_settings()
    application = create_app(settings)
    with TestClient(application) as client:
        sender = RecordingSender()
        application.state.pool = rollback_pool
        application.state.code_sender = sender
        yield Api(client=client, pool=rollback_pool, sender=sender, settings=settings)


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Quita las variables de configuración para que la prueba ponga las suyas."""
    for variable in SETTINGS_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch
