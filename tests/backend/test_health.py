"""Casos de la pieza "esqueleto del backend": la API responde.

Especificación aceptada por Sophia el 17 de noviembre de 2026:

    GET /api/v1/health           -> 200 {"status": "ok"}
    GET /api/v1/health/database  -> 200 {"status": "ok", "database": "integro",
                                         "port": 5433, "server_version": "18.x"}
                                    503 {"status": "unavailable"} si la base no
                                    responde, sin el motivo ni datos de conexión
    GET /docs                    -> 200 documentación OpenAPI
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.core.config import ENV_FILE, load_settings
from app.main import create_app


# ---------------------------------------------------------------------------
# La API está viva
# ---------------------------------------------------------------------------


def test_health_responds_ok_without_database(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# La base de datos responde
# ---------------------------------------------------------------------------


def test_database_health_with_real_database():
    """Usa la base real: integro en el puerto 5433, con el usuario de backend/.env."""
    if not ENV_FILE.exists():
        pytest.skip("Falta backend/.env: sin él no hay con qué conectarse a la base real.")

    with TestClient(create_app(load_settings())) as client:
        response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "database", "port", "server_version"}
    assert body["status"] == "ok"
    assert body["database"] == "integro"
    assert body["port"] == 5433
    assert body["server_version"].startswith("18.")


def test_database_health_unavailable_when_database_is_down(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    # El cuerpo es exactamente este: sin motivo, sin host, sin usuario.
    assert response.json() == {"status": "unavailable"}
    assert "clave-inventada-para-la-prueba" not in response.text
    assert "integro_api" not in response.text


class FakeCursor:
    def fetchone(self):
        return ("integro", 5433, "18.7")


class FakeConnection:
    def execute(self, query):
        return FakeCursor()


class FakePool:
    """Sustituye al grupo de conexiones para probar la forma de la respuesta."""

    @contextmanager
    def connection(self, timeout=None):
        yield FakeConnection()


def test_database_health_response_shape(settings_without_database):
    application = create_app(settings_without_database)
    with TestClient(application) as client:
        application.state.pool = FakePool()
        response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "integro",
        "port": 5433,
        "server_version": "18.7",
    }


# ---------------------------------------------------------------------------
# Documentación OpenAPI
# ---------------------------------------------------------------------------


def test_docs_page_responds(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_lists_both_health_routes(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    # Desde la pieza del registro hay más rutas; las dos de comprobación siguen ahí.
    assert {"/api/v1/health", "/api/v1/health/database"} <= set(paths)


# ---------------------------------------------------------------------------
# Límites
# ---------------------------------------------------------------------------


def test_unknown_route_is_404(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404


def test_health_outside_versioned_prefix_is_404(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        response = client.get("/health")

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/database"])
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_health_routes_only_accept_get(settings_without_database, path, method):
    with TestClient(create_app(settings_without_database)) as client:
        response = getattr(client, method)(path)

    assert response.status_code == 405
