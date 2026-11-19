"""Casos de la pieza "la API muestra también la web".

Decisión de Sophia del 19 de noviembre de 2026: en su computadora, con el
mismo comando con el que arranca la API, http://127.0.0.1:8000/ muestra la
portada y las demás páginas de web/. Página y API quedan en la misma dirección.

    1. GET / entrega la portada; las otras páginas y los archivos de assets/
       salen con su tipo.
    2. Las rutas de la API siguen siendo de la API: /api/v1/health, /docs.
    3. Lo que no existe responde 404, en la web y en la API.
    4. Nada que esté fuera de web/ se puede pedir.
    5. Con SERVE_WEB=false, o si la carpeta no existe, la API arranca igual y
       no muestra páginas.

Ninguna de estas pruebas usa la base de datos.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import WEB_DIRECTORY
from app.main import create_app


@pytest.fixture(scope="module")
def client():
    """La API con la carpeta web/ del repositorio. Se arranca una vez para todo el archivo."""
    from conftest import TEST_CODE_HASH_SECRET

    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        database_host="127.0.0.1",
        database_port=1,
        database_name="integro",
        database_user="integro_api",
        database_password="clave-inventada-para-la-prueba",
        code_hash_secret=TEST_CODE_HASH_SECRET,
        email_delivery="console",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


# --- Caso 1 ----------------------------------------------------------------


def test_the_web_folder_of_the_repository_is_the_one_served():
    assert WEB_DIRECTORY.name == "web"
    assert (WEB_DIRECTORY / "index.html").is_file()
    assert (WEB_DIRECTORY.parent / "backend").is_dir()


def test_root_shows_the_home_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Íntegro</title>" in response.text
    assert response.content == (WEB_DIRECTORY / "index.html").read_bytes()


@pytest.mark.parametrize("page", ["index.html", "propiedad.html", "anfitriones.html", "como-funciona.html"])
def test_each_page_is_served_as_html(client, page):
    response = client.get(f"/{page}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.content == (WEB_DIRECTORY / page).read_bytes()


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("assets/css/estilos.css", "text/css"),
        ("assets/js/app.js", "javascript"),
        ("assets/js/datos.js", "javascript"),
    ],
)
def test_styles_and_scripts_are_served_with_their_type(client, path, content_type):
    response = client.get(f"/{path}")

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.content == (WEB_DIRECTORY / path).read_bytes()


def test_the_page_with_its_parameter_is_served(client):
    assert client.get("/propiedad.html?id=1").status_code == 200


def test_the_browser_always_asks_if_a_file_changed(client):
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/assets/css/estilos.css").headers["cache-control"] == "no-cache"


# --- Caso 2 ----------------------------------------------------------------


def test_the_api_routes_still_belong_to_the_api(client):
    health = client.get("/api/v1/health")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert "/api/v1/auth/login" in client.get("/openapi.json").json()["paths"]


def test_an_api_route_keeps_its_own_answer_for_a_post(client):
    """Las páginas no se tragan las peticiones de la API."""
    response = client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "required"


# --- Caso 3 ----------------------------------------------------------------


@pytest.mark.parametrize("path", ["/no-existe.html", "/assets/css/no-existe.css", "/api/v1/no-existe", "/api"])
def test_what_does_not_exist_is_404(client, path):
    assert client.get(path).status_code == 404


def test_pages_can_only_be_read(client):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert client.request(method, "/index.html", content=b"otra cosa").status_code == 404
    assert "<title>Íntegro</title>" in client.get("/index.html").text
    assert client.head("/index.html").status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/login/verify", "/api/v1/auth/password-strength"],
)
def test_an_api_route_still_says_when_a_method_is_not_allowed(client, path):
    """Pedir con GET una ruta que solo acepta POST sigue siendo 405: las páginas no lo tapan."""
    assert client.get(path).status_code == 405


def test_a_get_only_api_route_still_rejects_a_post(client):
    assert client.post("/api/v1/health").status_code == 405


# --- Caso 4 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/../backend/.env.example",
        "/%2e%2e/backend/.env.example",
        "/..%2fbackend%2f.env.example",
        "/assets/../../backend/.env.example",
        "/assets/%2e%2e/%2e%2e/backend/.env.example",
        "/..%5cbackend%5c.env.example",
        "/assets/..%5c..%5cCLAUDE.md",
        "//backend/.env.example",
        "/C:/Windows/win.ini",
    ],
)
def test_nothing_outside_the_web_folder_can_be_asked_for(client, path):
    response = client.get(path)

    assert response.status_code in (400, 404)
    assert "DATABASE_" not in response.text and "Reglas de trabajo" not in response.text


# --- Caso 5 ----------------------------------------------------------------


def test_with_serve_web_off_there_are_no_pages_and_the_api_works(settings_without_database):
    settings = settings_without_database.model_copy(update={"serve_web": False})

    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/").status_code == 404
        assert test_client.get("/index.html").status_code == 404
        assert test_client.get("/api/v1/health").status_code == 200


def test_pages_are_served_unless_turned_off_on_purpose(settings_without_database):
    assert settings_without_database.serve_web is True


def test_without_the_folder_the_api_starts_and_shows_no_pages(settings_without_database, tmp_path):
    with TestClient(create_app(settings_without_database, web_directory=tmp_path / "no-existe")) as test_client:
        assert test_client.get("/").status_code == 404
        assert test_client.get("/api/v1/health").status_code == 200

    with TestClient(create_app(settings_without_database, web_directory=None)) as test_client:
        assert test_client.get("/").status_code == 404
        assert test_client.get("/api/v1/health").status_code == 200


def test_the_folder_that_is_served_is_the_one_given(settings_without_database, tmp_path):
    (tmp_path / "index.html").write_text("<p>portada de prueba</p>", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("fuera", encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<p>portada de prueba</p>", encoding="utf-8")

    with TestClient(create_app(settings_without_database, web_directory=web)) as test_client:
        assert test_client.get("/").text == "<p>portada de prueba</p>"
        assert test_client.get("/../secreto.txt").status_code == 404
        assert test_client.get("/%2e%2e/secreto.txt").status_code == 404


def test_starting_twice_does_not_add_the_pages_twice(settings_without_database):
    application = create_app(settings_without_database)

    with TestClient(application) as test_client:
        assert test_client.get("/").status_code == 200
    first = application.router.default
    with TestClient(application) as test_client:
        assert test_client.get("/").status_code == 200

    assert application.router.default is first
