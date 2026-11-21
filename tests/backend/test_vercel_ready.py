"""Casos de la pieza "la API lista para correr en Vercel".

Plan: docs/despliegue-vercel-neon.md. Decisiones de Sophia del 21 de noviembre de 2026: la API en Vercel y la base en
Neon (Ohio), en un solo proyecto de Vercel, con la web y la API en el mismo dominio.

     1. Configuración nueva: DATABASE_SSLMODE (por defecto «prefer», en la nube «require»), el tiempo de espera de la
        conexión y TRUST_PROXY_HEADERS (por defecto apagado). Llegan al grupo de conexiones.
     2. Detrás de un proxy, la IP de quien pide sale de X-Forwarded-For, solo con TRUST_PROXY_HEADERS. Sin eso, ese
        encabezado se ignora: nadie puede fingir otra dirección para esquivar la espera por dispositivo.
     3. Detrás de un proxy, el origen propio de la API sale de X-Forwarded-Proto y Host, solo con
        TRUST_PROXY_HEADERS: sin eso, en Vercel toda petición que cambia algo daría 403 (la API ve HTTP y el
        navegador manda Origin con HTTPS). Sin la configuración, esos encabezados no abren nada.
     4. El punto de entrada api/index.py arranca la misma aplicación, contesta en /api/v1/... y no muestra las páginas
        (las entrega Vercel).
     5. vercel.json, .vercelignore, requirements.txt y .python-version dicen lo que tienen que decir y no suben secretos.

Corren contra la base real con rollback_pool cuando hace falta; las demás no la usan.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from conftest import with_session
from starlette.requests import Request
from test_accounts_login import LOGIN, errors_of, login, one, register
from test_accounts_logout import change
from test_config import VALID, set_variables
from test_session_cookie import use_settings

from fastapi.testclient import TestClient

from app.api.client import client_ip, first_value, origin_of, own_origin
from app.core.config import ConfigurationError, load_settings
from app.database.connection import create_pool

REPO = Path(__file__).resolve().parents[2]
LOGOUT = "/api/v1/auth/logout"


def request_with(headers: dict, client=("203.0.113.9", 5000), host="midominio.vercel.app", scheme="http") -> Request:
    """Una petición como la ve la API, sin pasar por la red."""
    raw = [(k.lower().encode(), v.encode()) for k, v in {"host": host, **headers}.items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw, "client": client, "scheme": scheme,
                    "server": (host, 80 if scheme == "http" else 443), "query_string": b"", "root_path": ""})


# --- Caso 1: configuración ----------------------------------------------------------------------------------


def test_the_new_settings_have_values_that_keep_the_local_behavior(clean_environment):
    set_variables(clean_environment)

    settings = load_settings(env_file=None)

    assert (settings.database_sslmode, settings.database_connect_timeout_seconds, settings.trust_proxy_headers) == ("prefer", 3, False)


def test_the_new_settings_can_be_changed_with_variables(clean_environment):
    set_variables(clean_environment, DATABASE_SSLMODE="require", DATABASE_CONNECT_TIMEOUT_SECONDS="10", TRUST_PROXY_HEADERS="true")

    settings = load_settings(env_file=None)

    assert (settings.database_sslmode, settings.database_connect_timeout_seconds, settings.trust_proxy_headers) == ("require", 10, True)


@pytest.mark.parametrize("variable, value", [
    ("DATABASE_SSLMODE", "si"), ("DATABASE_SSLMODE", "REQUIRE "), ("DATABASE_SSLMODE", ""),
    ("DATABASE_CONNECT_TIMEOUT_SECONDS", "0"), ("DATABASE_CONNECT_TIMEOUT_SECONDS", "61"), ("DATABASE_CONNECT_TIMEOUT_SECONDS", "diez"),
    ("TRUST_PROXY_HEADERS", "tal vez"),
])
def test_a_wrong_value_stops_the_start_and_names_only_the_variable(clean_environment, variable, value):
    set_variables(clean_environment, **{variable: value})

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert variable in str(raised.value)
    assert "clave-inventada-para-la-prueba" not in str(raised.value)


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"])
def test_every_ssl_mode_of_the_driver_is_accepted(clean_environment, mode):
    set_variables(clean_environment, DATABASE_SSLMODE=mode)

    assert load_settings(env_file=None).database_sslmode == mode


def test_the_pool_uses_the_ssl_mode_and_the_waits_of_the_settings(clean_environment):
    set_variables(clean_environment, DATABASE_SSLMODE="require", DATABASE_CONNECT_TIMEOUT_SECONDS="12")

    pool = create_pool(load_settings(env_file=None))

    assert pool.kwargs["sslmode"] == "require"
    assert pool.kwargs["connect_timeout"] == 12
    assert pool.timeout == 12
    assert "password" in pool.kwargs and pool.kwargs["user"] == VALID["DATABASE_USER"]


# --- Caso 2: la IP de quien pide -----------------------------------------------------------------------------------


def settings_with(clean_environment, **changes):
    set_variables(clean_environment, **changes)
    return load_settings(env_file=None)


def test_without_trusting_the_proxy_the_ip_is_the_one_of_the_connection(clean_environment):
    settings = settings_with(clean_environment)

    assert client_ip(request_with({"x-forwarded-for": "198.51.100.1"}), settings) == "203.0.113.9"


def test_trusting_the_proxy_the_ip_is_the_first_of_the_list(clean_environment):
    settings = settings_with(clean_environment, TRUST_PROXY_HEADERS="true")

    assert client_ip(request_with({"x-forwarded-for": "198.51.100.1, 10.0.0.2, 10.0.0.3"}), settings) == "198.51.100.1"
    assert client_ip(request_with({"x-forwarded-for": "  198.51.100.1  "}), settings) == "198.51.100.1"


def test_trusting_the_proxy_without_the_header_falls_back_to_the_connection(clean_environment):
    settings = settings_with(clean_environment, TRUST_PROXY_HEADERS="true")

    assert client_ip(request_with({}), settings) == "203.0.113.9"
    assert client_ip(request_with({"x-forwarded-for": ""}), settings) == "203.0.113.9"
    assert client_ip(request_with({}, client=None), settings) is None


def attempt_ip(api, email) -> str | None:
    return one(api, "select host(ip_address) from login_attempts where email = %s order by created_at desc limit 1", email)[0]


def test_a_forged_forwarded_address_does_not_change_the_device_when_the_proxy_is_not_trusted(api):
    form = register(api)

    api.client.post(LOGIN, json={"email": form["email"], "password": "Mala-2026!x"}, headers={"X-Forwarded-For": "198.51.100.77"})

    assert attempt_ip(api, form["email"]) is None  # el cliente de pruebas no tiene una IP: se ignoró el encabezado


def test_the_wait_per_device_follows_the_forwarded_address_when_the_proxy_is_trusted(api):
    use_settings(api, trust_proxy_headers=True)
    form = register(api)
    headers = {"X-Forwarded-For": "198.51.100.77, 10.1.1.1"}
    for _ in range(6):
        assert api.client.post(LOGIN, json={"email": form["email"], "password": "Mala-2026!x"}, headers=headers).status_code == 401

    stored = attempt_ip(api, form["email"])
    waiting = api.client.post(LOGIN, json={"email": form["email"], "password": "Ejemplo-2026"}, headers=headers)
    other_person = api.client.post(
        LOGIN, json={"email": form["email"], "password": "Ejemplo-2026"}, headers={"X-Forwarded-For": "198.51.100.78"}
    )

    assert stored == "198.51.100.77"
    assert waiting.status_code == 429 and errors_of(waiting) == [("credentials", "try_later")]
    assert other_person.status_code == 200  # otra dirección, aunque el mismo proxy: no espera


def test_a_garbage_forwarded_address_is_not_stored_as_an_ip(api):
    use_settings(api, trust_proxy_headers=True)
    form = register(api)

    api.client.post(LOGIN, json={"email": form["email"], "password": "Mala-2026!x"}, headers={"X-Forwarded-For": "no-soy-una-ip"})

    assert attempt_ip(api, form["email"]) is None


# --- Caso 3: el origen propio ------------------------------------------------------------------------------------------


def test_the_own_origin_without_trust_is_the_one_the_server_sees(clean_environment):
    settings = settings_with(clean_environment)

    assert own_origin(request_with({"x-forwarded-proto": "https"}), settings) == "http://midominio.vercel.app"


def test_the_own_origin_trusting_the_proxy_uses_the_forwarded_protocol_and_host(clean_environment):
    settings = settings_with(clean_environment, TRUST_PROXY_HEADERS="true")

    assert own_origin(request_with({"x-forwarded-proto": "https"}), settings) == "https://midominio.vercel.app"
    assert own_origin(request_with({"x-forwarded-proto": "https", "x-forwarded-host": "integro.example"}), settings) == "https://integro.example"
    assert own_origin(request_with({"x-forwarded-proto": "HTTPS, http"}), settings) == "https://midominio.vercel.app"


@pytest.mark.parametrize("proto", ["", "javascript", "ftp", "file", "https://evil.example"])
def test_a_strange_forwarded_protocol_is_ignored(clean_environment, proto):
    settings = settings_with(clean_environment, TRUST_PROXY_HEADERS="true")

    assert own_origin(request_with({"x-forwarded-proto": proto}), settings) == "http://midominio.vercel.app"


def test_a_change_from_the_https_page_is_refused_behind_a_proxy_that_is_not_configured(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token, Origin="https://testserver"))

    assert response.status_code == 403 and errors_of(response) == [("request", "origin_not_allowed")]


def test_a_change_from_the_https_page_works_behind_the_proxy_when_it_is_trusted(api):
    use_settings(api, trust_proxy_headers=True)
    form = register(api)
    token = login(api, form)
    headers = change(api, token, Origin="https://testserver", **{"X-Forwarded-Proto": "https"})

    response = api.client.post(LOGOUT, headers=headers)

    assert response.status_code == 200


def test_trusting_the_proxy_does_not_let_another_site_in(api):
    use_settings(api, trust_proxy_headers=True)
    form = register(api)
    token = login(api, form)

    forged_origin = api.client.post(LOGOUT, headers=change(api, token, Origin="https://pagina-ajena.example", **{"X-Forwarded-Proto": "https"}))
    forged_host = api.client.post(
        LOGOUT, headers=change(api, token, Origin="https://pagina-ajena.example", **{"X-Forwarded-Proto": "https", "X-Forwarded-Host": "otro.example"})
    )

    assert (forged_origin.status_code, forged_host.status_code) == (403, 403)
    assert api.client.get("/api/v1/auth/me", headers=with_session(token)).status_code == 200  # la sesión sigue abierta


def test_the_list_of_allowed_origins_still_works_behind_the_proxy(api):
    use_settings(api, trust_proxy_headers=True, allowed_origins="https://integro.example")
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token, Origin="https://integro.example"))

    assert response.status_code == 200


def test_reading_the_origin_and_the_first_value():
    assert origin_of("HTTPS://Midominio.Vercel.app/ruta?x=1") == "https://midominio.vercel.app"
    assert origin_of("javascript:alert(1)") is None and origin_of(None) is None and origin_of("") is None
    assert first_value("a, b, c") == "a" and first_value(None) == "" and first_value("") == ""


# --- Caso 4: el punto de entrada ---------------------------------------------------------------------------------------


@pytest.fixture
def entry_point(clean_environment):
    """api/index.py importado como lo importaría Vercel, con la configuración de variables de entorno."""
    set_variables(clean_environment, DATABASE_HOST="127.0.0.1", DATABASE_PORT="1", CODE_HASH_SECRET="x" * 40)
    clean_environment.setenv("EMAIL_DELIVERY", "console")
    spec = importlib.util.spec_from_file_location("api_index_para_pruebas", REPO / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_entry_point_exposes_the_same_application_under_api_v1(entry_point):
    assert entry_point.app.title == "Íntegro API"
    with TestClient(entry_point.app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200 and response.json()["status"] == "ok"
        # Sin la base (puerto 1), la API sigue arriba y lo dice en el aviso de la base.
        assert client.get("/api/v1/health/database").status_code in (200, 503)


def test_the_entry_point_does_not_show_the_pages_because_vercel_does(entry_point):
    with TestClient(entry_point.app) as client:
        assert client.get("/index.html").status_code == 404
        assert client.get("/registro.html").status_code == 404
        assert client.get("/").status_code == 404


def test_the_entry_point_reads_nothing_from_a_file_it_could_leak():
    code = (REPO / "api" / "index.py").read_text(encoding="utf-8")

    assert ".env" not in code and "password" not in code.lower() and "secret" not in code.lower()


# --- Caso 5: los archivos de Vercel -----------------------------------------------------------------------------------


def test_vercel_json_sends_api_to_the_function_serves_the_pages_and_keeps_the_region_with_the_database():
    config = json.loads((REPO / "vercel.json").read_text(encoding="utf-8"))

    assert config["outputDirectory"] == "web"
    assert {"source": "/api/(.*)", "destination": "/api/index"} in config["rewrites"]
    assert config["regions"] == ["cle1"]  # Cleveland: la región de AWS us-east-2, la misma de la base en Neon (Ohio)
    function = config["functions"]["api/index.py"]
    assert function["includeFiles"] == "backend/app/**"
    assert 1 <= function["maxDuration"] <= 60


def test_the_rewrite_only_catches_the_api_so_the_pages_come_from_the_cdn():
    config = json.loads((REPO / "vercel.json").read_text(encoding="utf-8"))

    sources = [rule["source"] for rule in config["rewrites"]]

    assert all(source.startswith("/api/") for source in sources)
    for page in ("/index.html", "/registro.html", "/assets/js/cuenta.js"):
        assert not any(re.fullmatch(source, page) for source in sources), page


def test_the_entry_file_is_where_the_rewrite_and_the_function_say():
    assert (REPO / "api" / "index.py").is_file()
    assert (REPO / "web" / "index.html").is_file()  # lo que sirve outputDirectory


def test_secrets_and_what_is_not_needed_do_not_go_up_to_vercel():
    lines = {line.strip() for line in (REPO / ".vercelignore").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}

    for ignored in (".env", ".env.*", "backend/.env", "backend/.env.*", "backend/.venv", ".venv", "tests", "docs", "database", "herramientas", "tools", ".git"):
        assert ignored in lines, ignored
    for needed in ("web", "api", "backend", "backend/app", "requirements.txt", "vercel.json", ".python-version"):
        assert needed not in lines, needed


def test_the_dependencies_are_the_same_list_as_the_backend():
    root = [line for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]

    assert root == ["-r backend/requirements.txt"]
    backend = (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8")
    for package in ("fastapi==", "psycopg[binary]==", "psycopg-pool==", "pydantic-settings==", "argon2-cffi==", "tzdata=="):
        assert package in backend, package


def test_the_python_version_is_the_one_the_code_is_tested_with():
    wanted = (REPO / ".python-version").read_text(encoding="utf-8").strip()

    assert wanted == f"{sys.version_info.major}.{sys.version_info.minor}"


def test_the_environment_example_names_the_new_variables_without_values_that_are_secrets():
    example = (REPO / "backend" / ".env.example").read_text(encoding="utf-8")

    for variable in ("DATABASE_SSLMODE", "DATABASE_CONNECT_TIMEOUT_SECONDS", "TRUST_PROXY_HEADERS"):
        assert variable in example, variable
