"""Casos de la pieza "CAPTCHA con Cloudflare Turnstile".

Especificación confirmada por Sophia el 22 de noviembre de 2026 (ADR 0016):

    Cinco rutas piden el resultado del desafío en el encabezado X-Captcha-Token:
    POST /auth/register, POST /auth/login, POST /auth/password-reset/request,
    POST /auth/resend-code y POST /auth/correct-unverified-email.
     1. Resultado válido: la acción se ejecuta como antes.
     2. Sin resultado, vacío, repetido o falso: 400, código captcha_failed, y no se
        crea ni se envía nada.
     3. Cloudflare no responde (red caída, tiempo agotado, error de su servidor,
        respuesta que no se entiende): 503, código captcha_unavailable, y no se crea
        ni se envía nada. Nunca se deja pasar.
     4. Sin llave secreta configurada: también 503, y la API arranca igual (la salud
        sigue respondiendo). No hay interruptor: no existe forma de apagar el CAPTCHA.
     5. Los pasos en los que se escribe un código (verify-email, login/verify,
        password-reset/confirm) no lo piden y ni siquiera le preguntan a Cloudflare.
    GET /auth/captcha
     6. Con llave pública configurada entrega {"site_key": ...}; sin ella, 503.
    Acción por ruta y llaves de prueba (sugerencias aceptadas por Sophia el 22 de noviembre de 2026)
     7. Cada ruta espera su acción (register, login, password_reset, resend_code, correct_email)
        y Cloudflare la devuelve: un resultado de otra acción, o sin acción, es captcha_failed.
     8. Las llaves de prueba de Cloudflare (1x, 2x, 3x) solo valen con SESSION_COOKIE_SECURE=false, es decir, en la
        computadora de Sophia; allí la acción no se compara, porque Cloudflare no la devuelve. Donde la cookie exige
        HTTPS (la nube), una llave de prueba, secreta o pública, se trata como si faltara: 503.

TurnstileVerifier se prueba contra un servidor HTTP local que hace de Cloudflare, con
respuestas de verdad (no con un doble de la función): así se comprueba lo que se manda
(llave secreta y resultado, como formulario) y cómo se lee lo que contesta. Las rutas se
prueban con la base real y rollback_pool, como las demás.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest
from fastapi.testclient import TestClient

from app.api.captcha import (
    CAPTCHA_HEADER,
    MESSAGE,
    TOKEN_MAX_LENGTH,
    CaptchaResult,
    TurnstileVerifier,
    UnconfiguredVerifier,
    create_captcha_verifier,
)
from app.core.config import Settings
from app.database.transaction import system_transaction
from app.main import create_app
from conftest import TEST_CAPTCHA_TOKEN, FakeCaptcha
from test_accounts_registration import new_form

SECRET = "llave-secreta-inventada-del-captcha"
TOKEN = "resultado-inventado-del-desafio"
ACTION = "login"
# Llaves de prueba de Cloudflare: públicas, siempre pasan y no devuelven la acción.
TEST_SECRET = "1x0000000000000000000000000000000AA"
TEST_SITE_KEY = "1x00000000000000000000AA"


# ---------------------------------------------------------------------------
# Un Cloudflare de mentira, en esta computadora
# ---------------------------------------------------------------------------


class FakeCloudflare:
    """Servidor HTTP local que contesta lo que la prueba le diga y anota lo que le llega."""

    def __init__(self):
        self.status = 200
        self.body = json.dumps({"success": True, "action": ACTION}).encode()
        self.delay = 0.0
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode()
                owner.requests.append(
                    {"path": self.path, "content_type": self.headers.get("Content-Type"), "form": parse_qs(raw)}
                )
                time.sleep(owner.delay)
                try:
                    self.send_response(owner.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(owner.body)))
                    self.end_headers()
                    self.wfile.write(owner.body)
                except OSError:
                    pass  # quien preguntó ya se cansó de esperar

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/turnstile/v0/siteverify"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, body, status=200):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.status = status

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def cloudflare():
    server = FakeCloudflare()
    yield server
    server.close()


@pytest.fixture
def verifier(cloudflare):
    return TurnstileVerifier(SECRET, url=cloudflare.url, timeout=2)


# ---------------------------------------------------------------------------
# TurnstileVerifier
# ---------------------------------------------------------------------------


def test_a_good_result_passes_and_cloudflare_gets_the_secret_and_the_result_as_a_form(verifier, cloudflare):
    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.PASSED

    assert len(cloudflare.requests) == 1
    sent = cloudflare.requests[0]
    assert sent["path"] == "/turnstile/v0/siteverify"
    assert sent["content_type"] == "application/x-www-form-urlencoded"
    assert sent["form"] == {"secret": [SECRET], "response": [TOKEN]}


def test_a_result_made_for_another_action_does_not_pass(verifier, cloudflare):
    """El resultado del registro no sirve para iniciar sesión."""
    cloudflare.answer({"success": True, "action": "register"})

    assert verifier.verify(TOKEN, "login") is CaptchaResult.FAILED
    assert verifier.verify(TOKEN, "register") is CaptchaResult.PASSED


@pytest.mark.parametrize("answer", [{"success": True}, {"success": True, "action": ""}, {"success": True, "action": None},
                                    {"success": True, "action": ["login"]}, {"success": True, "action": "LOGIN"}])
def test_a_result_without_the_action_or_with_another_one_fails_with_real_keys(verifier, cloudflare, answer):
    cloudflare.answer(answer)

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.FAILED


def test_with_test_keys_the_action_is_not_compared_because_cloudflare_does_not_return_it(cloudflare):
    without_check = TurnstileVerifier(TEST_SECRET, url=cloudflare.url, timeout=2, check_action=False)
    cloudflare.answer({"success": True, "hostname": "example.com"})

    assert without_check.verify(TOKEN, ACTION) is CaptchaResult.PASSED


@pytest.mark.parametrize("code", ["invalid-input-response", "missing-input-response", "timeout-or-duplicate", "bad-request"])
def test_a_result_cloudflare_refuses_fails_so_the_person_can_try_again(verifier, cloudflare, code):
    cloudflare.answer({"success": False, "error-codes": [code]})

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.FAILED


def test_a_refusal_without_codes_also_fails(verifier, cloudflare):
    cloudflare.answer({"success": False})

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.FAILED


@pytest.mark.parametrize("code", ["invalid-input-secret", "missing-input-secret", "internal-error"])
def test_a_problem_that_is_ours_or_cloudflares_is_unavailable_not_a_failure_of_the_person(verifier, cloudflare, code):
    cloudflare.answer({"success": False, "error-codes": [code]})

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE


@pytest.mark.parametrize("status", [400, 429, 500, 502, 503])
def test_an_error_answer_from_cloudflare_is_unavailable(verifier, cloudflare, status):
    cloudflare.answer({"success": True, "action": ACTION}, status=status)

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE


@pytest.mark.parametrize("body", [b"", b"<html>no soy json</html>", b"[1, 2]", b'"hola"', b"null", b"\xff\xfe"])
def test_an_answer_that_is_not_understood_is_unavailable(verifier, cloudflare, body):
    cloudflare.answer(body)

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE


@pytest.mark.parametrize("success", ["true", 1, "yes", None])
def test_only_a_real_true_passes(verifier, cloudflare, success):
    cloudflare.answer({"success": success, "action": ACTION})

    assert verifier.verify(TOKEN, ACTION) is CaptchaResult.FAILED


def test_nobody_listening_is_unavailable(closed_port):
    lost = TurnstileVerifier(SECRET, url=f"http://127.0.0.1:{closed_port}/turnstile/v0/siteverify", timeout=2)

    assert lost.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE


def test_a_cloudflare_that_does_not_answer_in_time_is_unavailable(cloudflare):
    cloudflare.delay = 1.5
    impatient = TurnstileVerifier(SECRET, url=cloudflare.url, timeout=0.3)

    started = time.monotonic()
    result = impatient.verify(TOKEN, ACTION)

    assert result is CaptchaResult.UNAVAILABLE
    assert time.monotonic() - started < 1.2


@pytest.mark.parametrize("token", [None, "", "   ", "x" * (TOKEN_MAX_LENGTH + 1)])
def test_a_missing_empty_or_oversized_result_fails_without_asking_cloudflare(verifier, cloudflare, token):
    assert verifier.verify(token, ACTION) is CaptchaResult.FAILED
    assert cloudflare.requests == []


def test_a_result_of_the_maximum_length_is_still_sent(verifier, cloudflare):
    assert verifier.verify("x" * TOKEN_MAX_LENGTH, ACTION) is CaptchaResult.PASSED
    assert len(cloudflare.requests) == 1


def test_the_log_never_carries_the_secret_or_the_result(cloudflare, caplog):
    caplog.set_level("DEBUG")
    cloudflare.answer({"success": False, "error-codes": ["invalid-input-secret"]})
    TurnstileVerifier(SECRET, url=cloudflare.url, timeout=2).verify(TOKEN, ACTION)
    cloudflare.answer(b"no es json")
    TurnstileVerifier(SECRET, url=cloudflare.url, timeout=2).verify(TOKEN, ACTION)

    assert "invalid-input-secret" in caplog.text
    assert SECRET not in caplog.text
    assert TOKEN not in caplog.text


# ---------------------------------------------------------------------------
# Qué verificador se elige y qué dice la configuración
# ---------------------------------------------------------------------------


def settings_with(settings_without_database: Settings, **changes) -> Settings:
    return settings_without_database.model_copy(update=changes)


def test_with_a_secret_key_the_real_verifier_is_used(settings_without_database):
    from pydantic import SecretStr

    chosen = create_captcha_verifier(settings_with(settings_without_database, turnstile_secret_key=SecretStr(SECRET)))

    assert isinstance(chosen, TurnstileVerifier)


@pytest.mark.parametrize("secret", [None, "", "   "])
def test_without_a_secret_key_everything_is_unavailable_never_allowed(settings_without_database, secret):
    from pydantic import SecretStr

    chosen = create_captcha_verifier(
        settings_with(settings_without_database, turnstile_secret_key=None if secret is None else SecretStr(secret))
    )

    assert isinstance(chosen, UnconfiguredVerifier)
    assert chosen.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE
    assert chosen.verify(None, ACTION) is CaptchaResult.UNAVAILABLE


def test_a_test_secret_key_is_accepted_only_on_sophias_computer(settings_without_database, cloudflare):
    from pydantic import SecretStr

    local = settings_with(settings_without_database, turnstile_secret_key=SecretStr(TEST_SECRET), session_cookie_secure=False)
    cloud = settings_with(settings_without_database, turnstile_secret_key=SecretStr(TEST_SECRET), session_cookie_secure=True)
    cloudflare.answer({"success": True, "hostname": "example.com"})  # como contesta con llaves de prueba: sin acción

    assert create_captcha_verifier(local, url=cloudflare.url).verify(TOKEN, ACTION) is CaptchaResult.PASSED
    refused = create_captcha_verifier(cloud, url=cloudflare.url)
    assert isinstance(refused, UnconfiguredVerifier)
    assert refused.verify(TOKEN, ACTION) is CaptchaResult.UNAVAILABLE
    assert len(cloudflare.requests) == 1  # a Cloudflare solo se le preguntó en la computadora de Sophia


@pytest.mark.parametrize("secure", [True, False])
def test_a_real_secret_key_always_checks_the_action(settings_without_database, cloudflare, secure):
    from pydantic import SecretStr

    settings = settings_with(settings_without_database, turnstile_secret_key=SecretStr("0x4AAAAAAAreal-inventada"),
                             session_cookie_secure=secure)
    cloudflare.answer({"success": True, "action": "register"})
    chosen = create_captcha_verifier(settings, url=cloudflare.url)

    assert chosen.verify(TOKEN, "login") is CaptchaResult.FAILED
    assert chosen.verify(TOKEN, "register") is CaptchaResult.PASSED


@pytest.mark.parametrize("key", ["1x00000000000000000000AA", "2x00000000000000000000AB", "3x00000000000000000000FF"])
def test_every_kind_of_test_key_is_recognized(key):
    from app.api.captcha import is_test_key

    assert is_test_key(key) is True
    assert is_test_key("0x4AAAAAAGNy2A7zsC9zvpyP") is False


def test_the_keys_are_read_from_the_environment_and_the_secret_is_not_printed(clean_environment):
    for name, value in {
        "DATABASE_HOST": "127.0.0.1", "DATABASE_PORT": "5433", "DATABASE_NAME": "integro",
        "DATABASE_USER": "integro_api", "DATABASE_PASSWORD": "clave-inventada",
        "CODE_HASH_SECRET": "x" * 32, "EMAIL_DELIVERY": "console",
        "TURNSTILE_SITE_KEY": "0xLLAVE-PUBLICA", "TURNSTILE_SECRET_KEY": SECRET,
    }.items():
        clean_environment.setenv(name, value)

    settings = Settings(_env_file=None)

    assert settings.turnstile_site_key == "0xLLAVE-PUBLICA"
    assert settings.turnstile_secret_key.get_secret_value() == SECRET
    assert SECRET not in repr(settings) and SECRET not in str(settings)


def test_the_keys_have_no_default(settings_without_database):
    assert settings_without_database.turnstile_site_key is None
    assert settings_without_database.turnstile_secret_key is None


# ---------------------------------------------------------------------------
# Las rutas
# ---------------------------------------------------------------------------

ROUTES = {
    "register": "/api/v1/auth/register",
    "login": "/api/v1/auth/login",
    "reset": "/api/v1/auth/password-reset/request",
    "resend": "/api/v1/auth/resend-code",
    "correct": "/api/v1/auth/correct-unverified-email",
}
ACTIONS = {"register": "register", "login": "login", "reset": "password_reset", "resend": "resend_code",
           "correct": "correct_email"}
WITHOUT_CAPTCHA = {
    "verify-email": "/api/v1/auth/verify-email",
    "login-verify": "/api/v1/auth/login/verify",
    "reset-confirm": "/api/v1/auth/password-reset/confirm",
}
CAPTCHA_BODY = {"errors": [{"field": "captcha", "code": "captcha_failed", "message": MESSAGE}]}
UNAVAILABLE_BODY = {"errors": [{"field": "captcha", "code": "captcha_unavailable", "message": MESSAGE}]}


def bodies(email="ana.captcha@prueba.invalid"):
    """Un cuerpo para cada ruta; con el CAPTCHA resuelto llegan a su propia revisión."""
    return {
        "register": new_form(email=email),
        "login": {"email": email, "password": "Ejemplo-2026"},
        "reset": {"email": email},
        "resend": {"email": email},
        "correct": {"email": email, "password": "Ejemplo-2026", "new_email": "otra." + email},
    }


def without_header(api):
    """El cliente sin el resultado del CAPTCHA que el fixture manda siempre."""
    api.client.headers.pop(CAPTCHA_HEADER, None)


def users_with(api, email):
    with system_transaction(api.pool) as connection:
        return connection.execute("select count(*) from users where email = %s", (email,)).fetchone()[0]


@pytest.mark.parametrize("name", ROUTES)
def test_without_the_result_the_route_says_400_and_does_nothing(api, name):
    without_header(api)
    body = bodies()[name]

    response = api.client.post(ROUTES[name], json=body)

    assert response.status_code == 400
    assert response.json() == CAPTCHA_BODY
    assert api.sender.sent == [] and api.sender.notices == []
    assert users_with(api, body["email"]) == 0
    assert api.captcha.seen == [None]


@pytest.mark.parametrize("name", ROUTES)
@pytest.mark.parametrize("token", ["", "   ", "otro-resultado", "x" * (TOKEN_MAX_LENGTH + 1)])
def test_a_wrong_result_says_400_and_does_nothing(api, name, token):
    body = bodies()[name]

    response = api.client.post(ROUTES[name], json=body, headers={CAPTCHA_HEADER: token})

    assert response.status_code == 400
    assert response.json() == CAPTCHA_BODY
    assert api.sender.sent == []
    assert users_with(api, body["email"]) == 0


@pytest.mark.parametrize("name", ROUTES)
def test_when_it_cannot_be_checked_the_route_says_503_and_does_nothing(api, name):
    from app.api.captcha import CaptchaResult

    api.captcha.result = CaptchaResult.UNAVAILABLE
    body = bodies()[name]

    response = api.client.post(ROUTES[name], json=body)

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE_BODY
    assert response.headers["cache-control"] == "no-store"
    assert api.sender.sent == [] and api.sender.notices == []
    assert users_with(api, body["email"]) == 0


@pytest.mark.parametrize("name", ROUTES)
def test_with_a_good_result_the_route_runs_its_own_checks(api, name):
    """Con el CAPTCHA resuelto la petición llega a la ruta: con un cuerpo vacío contesta su propio 422."""
    response = api.client.post(ROUTES[name], json={})

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "required"
    assert api.captcha.seen == [TEST_CAPTCHA_TOKEN]


def test_with_a_good_result_the_account_is_created_and_the_code_goes_out(api):
    body = bodies()["register"]

    response = api.client.post(ROUTES["register"], json=body)

    assert response.status_code == 201
    assert users_with(api, body["email"]) == 1
    assert len(api.sender.sent) == 1


def test_the_captcha_is_asked_before_the_form_is_checked(api):
    """Sin resultado, un formulario vacío contesta CAPTCHA y no 422: el servidor no ayuda a probar datos a un programa."""
    without_header(api)

    response = api.client.post(ROUTES["register"], json={})

    assert response.status_code == 400
    assert response.json() == CAPTCHA_BODY


@pytest.mark.parametrize("name", ROUTES)
def test_each_route_asks_for_its_own_action(api, name):
    api.client.post(ROUTES[name], json={})

    assert api.captcha.actions == [ACTIONS[name]]


def test_the_five_actions_are_different_and_valid_for_the_widget():
    import re

    assert len(set(ACTIONS.values())) == 5
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,32}", action) for action in ACTIONS.values())


@pytest.mark.parametrize("name", WITHOUT_CAPTCHA)
def test_the_steps_that_ask_for_a_code_do_not_ask_for_the_captcha(api, name):
    without_header(api)
    api.captcha.result = CaptchaResult.UNAVAILABLE

    response = api.client.post(WITHOUT_CAPTCHA[name], json={})

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "required"
    assert api.captcha.seen == []


def test_the_documentation_of_the_api_lists_the_header_and_the_two_answers(api):
    paths = api.client.get("/openapi.json").json()["paths"]

    for path in ROUTES.values():
        operation = paths[path]["post"]
        assert "X-Captcha-Token" in [parameter["name"] for parameter in operation.get("parameters", [])], path
        assert "400" in operation["responses"] and "503" in operation["responses"], path
    for path in WITHOUT_CAPTCHA.values():
        operation = paths[path]["post"]
        assert "X-Captcha-Token" not in [p["name"] for p in operation.get("parameters", [])], path


# --- De la página a Cloudflare, de punta a punta, con el verificador de verdad ----------------------------


@pytest.mark.parametrize("name", ROUTES)
def test_the_whole_chain_from_the_header_to_cloudflare(api, cloudflare, name):
    api.client.app.state.captcha = TurnstileVerifier(SECRET, url=cloudflare.url, timeout=2)

    cloudflare.answer({"success": True, "action": ACTIONS[name]})
    passed = api.client.post(ROUTES[name], json={}, headers={CAPTCHA_HEADER: TOKEN})
    cloudflare.answer({"success": True, "action": "otra_accion"})
    other_action = api.client.post(ROUTES[name], json={}, headers={CAPTCHA_HEADER: TOKEN})
    cloudflare.answer({"success": False, "error-codes": ["timeout-or-duplicate"]})
    repeated = api.client.post(ROUTES[name], json={}, headers={CAPTCHA_HEADER: TOKEN})
    cloudflare.answer({}, status=500)
    down = api.client.post(ROUTES[name], json={}, headers={CAPTCHA_HEADER: TOKEN})

    assert (passed.status_code, other_action.status_code, repeated.status_code, down.status_code) == (422, 400, 400, 503)
    assert [request["form"]["response"] for request in cloudflare.requests] == [[TOKEN]] * 4


# --- Sin llave secreta ---------------------------------------------------------------------------------


def test_without_a_secret_key_the_api_starts_but_the_five_routes_say_503(settings_without_database):
    with TestClient(create_app(settings_without_database)) as client:
        assert client.get("/api/v1/health").status_code == 200
        for name, path in ROUTES.items():
            response = client.post(path, json={}, headers={CAPTCHA_HEADER: TOKEN})
            assert response.status_code == 503, name
            assert response.json() == UNAVAILABLE_BODY, name


def test_there_is_no_way_to_switch_it_off(settings_without_database):
    """Ninguna configuración ni encabezado deja pasar sin comprobar."""
    assert not [name for name in Settings.model_fields if "captcha" in name.lower() and "turnstile" not in name]
    with TestClient(create_app(settings_without_database)) as client:
        for header in ({"X-Captcha-Token": "off"}, {"X-Captcha-Skip": "1"}, {"X-Forwarded-For": "127.0.0.1"}):
            response = client.post(ROUTES["login"], json={"email": "a@b.co", "password": "x"}, headers=header)
            assert response.status_code == 503


# --- La llave pública -----------------------------------------------------------------------------------


def test_the_site_key_is_given_to_the_pages_and_the_secret_never(settings_without_database):
    from pydantic import SecretStr

    settings = settings_with(
        settings_without_database, turnstile_site_key="0xLLAVE-PUBLICA", turnstile_secret_key=SecretStr(SECRET)
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/auth/captcha")

    assert response.status_code == 200
    assert response.json() == {"site_key": "0xLLAVE-PUBLICA"}
    assert SECRET not in response.text


@pytest.mark.parametrize("site_key", [None, "", "  "])
def test_without_a_site_key_the_page_is_told_503(settings_without_database, site_key):
    with TestClient(create_app(settings_with(settings_without_database, turnstile_site_key=site_key))) as client:
        response = client.get("/api/v1/auth/captcha")

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE_BODY
    assert response.headers["cache-control"] == "no-store"


def test_a_test_site_key_is_given_only_on_sophias_computer(settings_without_database):
    local = settings_with(settings_without_database, turnstile_site_key=TEST_SITE_KEY, session_cookie_secure=False)
    cloud = settings_with(settings_without_database, turnstile_site_key=TEST_SITE_KEY, session_cookie_secure=True)

    with TestClient(create_app(local)) as client:
        assert client.get("/api/v1/auth/captcha").json() == {"site_key": TEST_SITE_KEY}
    with TestClient(create_app(cloud)) as client:
        response = client.get("/api/v1/auth/captcha")
        assert response.status_code == 503
        assert TEST_SITE_KEY not in response.text


def test_the_routes_refuse_everything_when_the_cloud_has_a_test_secret_key(settings_without_database):
    from pydantic import SecretStr

    cloud = settings_with(settings_without_database, turnstile_secret_key=SecretStr(TEST_SECRET), session_cookie_secure=True)
    with TestClient(create_app(cloud)) as client:
        assert client.get("/api/v1/health").status_code == 200
        for name, path in ROUTES.items():
            response = client.post(path, json={}, headers={CAPTCHA_HEADER: "XXXX.DUMMY.TOKEN.XXXX"})
            assert response.status_code == 503, name
            assert response.json() == UNAVAILABLE_BODY, name


def test_the_site_key_route_only_reads(settings_without_database):
    with TestClient(create_app(settings_with(settings_without_database, turnstile_site_key="0xLLAVE"))) as client:
        assert client.post("/api/v1/auth/captcha", json={}).status_code == 405
