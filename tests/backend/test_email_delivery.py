"""Casos de la pieza "correo real con Resend".

Especificación confirmada por Sophia el 22 de noviembre de 2026 (ADR 0017): con EMAIL_DELIVERY=resend, los códigos y los
avisos de seguridad salen por correo, en español y de tú, sin contraseñas.

    Los mensajes
     1. Cada código (verify_email, login, password_reset) sale con su asunto, el código en el cuerpo (nunca en el asunto),
        cuánto dura y que Íntegro nunca lo pide por otro medio. Cada aviso (failed_logins, password_changed) con su texto.
     2. Texto y HTML. Lo que viene de fuera, como el navegador de quien intentó entrar, se escapa en el HTML.
    El envío
     3. Una llamada HTTPS a Resend con la llave, el remitente, el destinatario y una Idempotency-Key.
     4. Si falla por red, tiempo, 429, 409 o 5xx, se intenta otra vez con la misma Idempotency-Key. Los demás errores
        (llave mala, dominio sin verificar, correo mal escrito) no se reintentan.
     5. Un código que no se pudo enviar levanta DeliveryFailed. Un aviso nunca levanta error.
     6. En el registro del servidor solo van el código HTTP y el nombre del error: nunca la llave, el destinatario, el
        código ni el texto del correo.
    La configuración
     7. EMAIL_DELIVERY=resend sin EMAIL_API_KEY o sin EMAIL_FROM: la API no arranca y dice cuál falta.
    Lo que dicen las rutas si el correo no sale
     8. resend-code y el primer paso de iniciar sesión: 503 con email_unavailable.
     9. register y correct-unverified-email: lo guardado queda guardado, contestan lo de siempre con email_sent en false y
        la persona pide otro código.
    10. password-reset/request: contesta exactamente lo mismo que si el correo no tuviera cuenta.
    11. Un aviso que no sale no cambia lo que contesta la ruta (la contraseña cambió; el intento fallido fue un 401).

El proveedor es un servidor HTTP local que contesta lo que la prueba diga y anota lo que le llega: así se comprueba lo
que de verdad se manda por la red. Las rutas corren con la base real y rollback_pool, como las demás.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from test_accounts_login import LOGIN, PASSWORD, VERIFY_EMAIL, errors_of, one, register
from test_accounts_password_reset import ask, confirm
from test_accounts_registration import new_form

from app.api.delivery import MESSAGE
from app.core.config import ConfigurationError, Settings, load_settings
from app.main import create_app
from app.notifications import create_code_sender
from app.notifications.console import ConsoleCodeSender
from app.notifications.messages import Message, code_message, minutes_text, notice_message
from app.notifications.resend import ResendCodeSender, error_name
from app.notifications.sender import DeliveryFailed

API_KEY = "re_llave-inventada-del-correo-0123456789"
FROM = "Íntegro <no-responder@prueba.invalid>"
DESTINATION = "ana.torres@prueba.invalid"
RESEND_REGISTER = "/api/v1/auth/register"
RESEND_CODE = "/api/v1/auth/resend-code"
RESET_REQUEST = "/api/v1/auth/password-reset/request"
CORRECT = "/api/v1/auth/correct-unverified-email"
UNAVAILABLE = {"errors": [{"field": "email", "code": "email_unavailable", "message": MESSAGE}]}


# ---------------------------------------------------------------------------
# Un Resend de mentira, en esta computadora
# ---------------------------------------------------------------------------


class FakeResend:
    """Servidor HTTP local. Contesta las respuestas de `answers` en orden (la última se repite) y anota lo que recibe."""

    def __init__(self):
        self.answers = [(200, {"id": "correo-1"})]
        self.delay = 0.0
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                number = len(owner.requests)
                owner.requests.append(
                    {
                        "path": self.path,
                        "headers": {name.lower(): value for name, value in self.headers.items()},
                        "json": json.loads(raw),
                    }
                )
                status, body = owner.answers[min(number, len(owner.answers) - 1)]
                body = body if isinstance(body, bytes) else json.dumps(body).encode()
                time.sleep(owner.delay)
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass  # quien preguntó ya se cansó de esperar

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/emails"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def resend():
    server = FakeResend()
    yield server
    server.close()


@pytest.fixture
def sender(resend):
    return ResendCodeSender(API_KEY, FROM, url=resend.url, timeout=2, pause=0)


def send_login_code(sender, destination=DESTINATION, code="482913", purpose="login", ttl=300):
    sender.send_code(channel="email", destination=destination, code=code, purpose=purpose, ttl_seconds=ttl)


NOTICE_DETAILS = {
    "failures": 3,
    "at": datetime(2026, 11, 22, 18, 30, 5, tzinfo=timezone.utc),
    "ip_address": "203.0.113.7",
    "user_agent": "Firefox/140",
}


# ---------------------------------------------------------------------------
# Los mensajes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "purpose,subject,action",
    [
        ("verify_email", "Tu código para comprobar tu correo en Íntegro", "comprobar tu correo"),
        ("login", "Tu código para iniciar sesión en Íntegro", "iniciar sesión"),
        ("password_reset", "Tu código para recuperar tu contraseña de Íntegro", "recuperar tu contraseña"),
    ],
)
def test_each_code_has_its_subject_and_says_what_it_is_for(purpose, subject, action):
    message = code_message(purpose, "482913", 300)

    assert message.subject == subject
    assert f"Tu código para {action} es:" in message.text
    assert f"Tu código para {action} es:" in message.html


@pytest.mark.parametrize("purpose", ["verify_email", "login", "password_reset"])
def test_the_code_is_in_the_body_never_in_the_subject_and_the_message_says_how_long_it_lasts(purpose):
    message = code_message(purpose, "482913", 300)

    assert "482913" in message.text and "482913" in message.html
    assert "482913" not in message.subject
    assert "Vence en 5 minutos." in message.text and "Vence en 5 minutos." in message.html
    assert "nunca te pedirá este código por teléfono, mensaje ni correo" in message.text
    assert "Si no fuiste tú, ignora este correo." in message.text


@pytest.mark.parametrize("seconds,text", [(1800, "30 minutos"), (300, "5 minutos"), (60, "1 minuto"), (61, "2 minutos"), (30, "1 minuto")])
def test_the_time_a_code_lasts_is_said_in_minutes_rounded_up(seconds, text):
    assert minutes_text(seconds) == text
    assert f"Vence en {text}." in code_message("login", "123456", seconds).text


def test_the_texts_are_in_formal_tu_never_usted():
    messages = [code_message(p, "123456", 300) for p in ("verify_email", "login", "password_reset")]
    messages += [notice_message("failed_logins", NOTICE_DETAILS), notice_message("password_changed", NOTICE_DETAILS)]

    for message in messages:
        assert not re.search(r"\busted(es)?\b", message.text + message.subject, re.I)
        assert message.text.startswith("Hola,")
        assert message.text.endswith("Equipo de Íntegro")


def test_the_failed_logins_notice_says_when_from_where_and_what_to_do_and_carries_no_password():
    message = notice_message("failed_logins", NOTICE_DETAILS)

    assert message.subject == "Hubo intentos fallidos de entrar a tu cuenta de Íntegro"
    for text in (message.text, message.html):
        assert "Hubo 3 intentos fallidos de entrar a tu cuenta." in text
        assert "2026-11-22 18:30:05 UTC" in text
        assert "Navegador: Firefox/140." in text
        assert "Dirección: 203.0.113.7." in text
        assert "Si no fuiste tú, cambia tu contraseña." in text


def test_the_password_changed_notice_says_everything_was_closed_and_how_to_recover_it_again():
    message = notice_message("password_changed", NOTICE_DETAILS)

    assert message.subject == "Cambiaste la contraseña de tu cuenta de Íntegro"
    assert "se cambió el 2026-11-22 18:30:05 UTC" in message.text
    assert "cerramos todas tus sesiones" in message.text
    assert "¿Olvidaste tu contraseña?" in message.text


def test_what_is_unknown_is_said_so():
    message = notice_message("password_changed", {"at": NOTICE_DETAILS["at"]})

    assert "Navegador: desconocido." in message.text and "Dirección: desconocida." in message.text


def test_what_comes_from_outside_is_escaped_in_the_html_and_left_alone_in_the_text():
    hostile = {**NOTICE_DETAILS, "user_agent": '<script>alert("hola")</script>', "ip_address": "<img src=x onerror=1>"}

    for kind in ("failed_logins", "password_changed"):
        message = notice_message(kind, hostile)
        assert "<script>" not in message.html and "<img" not in message.html
        assert "&lt;script&gt;" in message.html and "&lt;img" in message.html
        assert '<script>alert("hola")</script>' in message.text


def test_the_html_is_a_whole_page_with_the_colors_of_the_site():
    html = code_message("login", "482913", 300).html

    assert html.startswith("<!doctype html>") and html.endswith("</html>")
    assert '<html lang="es-MX">' in html and "#1F4D3A" in html and "#F3EEE4" in html


def test_a_code_or_a_notice_that_does_not_exist_is_a_mistake_of_the_program():
    with pytest.raises(ValueError):
        code_message("otro_proposito", "123456", 300)
    with pytest.raises(ValueError):
        notice_message("otro_aviso", NOTICE_DETAILS)


def test_the_development_console_says_the_same_notices_as_the_email():
    from app.notifications.console import KIND_TEXTS, failed_logins_text

    assert failed_logins_text(NOTICE_DETAILS) in notice_message("failed_logins", NOTICE_DETAILS).text
    assert set(KIND_TEXTS) == {"failed_logins", "password_changed"}
    assert isinstance(ConsoleCodeSender(), ConsoleCodeSender)


# ---------------------------------------------------------------------------
# El envío
# ---------------------------------------------------------------------------


def test_a_code_goes_out_as_one_post_with_the_key_the_sender_and_the_message(sender, resend):
    send_login_code(sender)

    assert len(resend.requests) == 1
    request = resend.requests[0]
    assert request["path"] == "/emails"
    assert request["headers"]["authorization"] == f"Bearer {API_KEY}"
    assert request["headers"]["content-type"] == "application/json"
    assert request["headers"]["user-agent"] == "integro-api"
    assert re.fullmatch(r"[0-9a-f]{32}", request["headers"]["idempotency-key"])
    body = request["json"]
    assert set(body) == {"from", "to", "subject", "text", "html"}
    assert body["from"] == FROM
    assert body["to"] == [DESTINATION]
    expected = code_message("login", "482913", 300)
    assert (body["subject"], body["text"], body["html"]) == (expected.subject, expected.text, expected.html)


def test_a_notice_goes_out_the_same_way(sender, resend):
    sender.send_notice(channel="email", destination=DESTINATION, kind="failed_logins", details=NOTICE_DETAILS)

    body = resend.requests[0]["json"]
    assert body["to"] == [DESTINATION]
    assert body["subject"] == "Hubo intentos fallidos de entrar a tu cuenta de Íntegro"
    assert "Hubo 3 intentos fallidos" in body["text"]


def test_every_message_has_its_own_idempotency_key(sender, resend):
    send_login_code(sender)
    send_login_code(sender)

    keys = {request["headers"]["idempotency-key"] for request in resend.requests}
    assert len(keys) == 2


def test_the_key_does_not_travel_anywhere_but_the_authorization_header(sender, resend):
    send_login_code(sender)

    request = resend.requests[0]
    assert API_KEY not in json.dumps(request["json"])
    assert [name for name, value in request["headers"].items() if API_KEY in value] == ["authorization"]


@pytest.mark.parametrize("status", [400, 401, 403, 422])
def test_an_error_that_waiting_will_not_fix_is_not_retried(sender, resend, status):
    resend.answers = [(status, {"statusCode": status, "name": "validation_error", "message": "x"})]

    with pytest.raises(DeliveryFailed) as raised:
        send_login_code(sender)

    assert str(raised.value) == f"HTTP {status}"
    assert len(resend.requests) == 1


@pytest.mark.parametrize("status", [409, 429, 500, 502, 503])
def test_a_failure_that_may_pass_is_retried_once_with_the_same_key(sender, resend, status):
    resend.answers = [(status, {"name": "application_error", "message": "x"}), (200, {"id": "correo-2"})]

    send_login_code(sender)

    assert len(resend.requests) == 2
    first, second = resend.requests
    assert first["headers"]["idempotency-key"] == second["headers"]["idempotency-key"]
    assert first["json"] == second["json"]


def test_two_failures_in_a_row_are_a_failed_delivery_after_exactly_two_tries(sender, resend):
    resend.answers = [(500, {"name": "application_error"})]

    with pytest.raises(DeliveryFailed) as raised:
        send_login_code(sender)

    assert str(raised.value) == "HTTP 500"
    assert len(resend.requests) == 2
    assert len({request["headers"]["idempotency-key"] for request in resend.requests}) == 1


def test_nobody_listening_is_a_failed_delivery(closed_port):
    lost = ResendCodeSender(API_KEY, FROM, url=f"http://127.0.0.1:{closed_port}/emails", timeout=2, pause=0)

    with pytest.raises(DeliveryFailed):
        send_login_code(lost)


def test_a_provider_that_does_not_answer_in_time_is_a_failed_delivery(resend):
    resend.delay = 1.5
    impatient = ResendCodeSender(API_KEY, FROM, url=resend.url, timeout=0.3, pause=0)

    started = time.monotonic()
    with pytest.raises(DeliveryFailed):
        send_login_code(impatient)

    assert time.monotonic() - started < 1.4
    assert len(resend.requests) == 2


@pytest.mark.parametrize("body", [b"", b"<html>no soy json</html>", b"[1, 2]"])
def test_a_success_whose_body_is_odd_is_still_a_success(sender, resend, body):
    resend.answers = [(200, body)]

    send_login_code(sender)

    assert len(resend.requests) == 1


def test_a_notice_that_does_not_go_out_never_raises(sender, resend, closed_port):
    resend.answers = [(500, {"name": "application_error"})]
    sender.send_notice(channel="email", destination=DESTINATION, kind="password_changed", details=NOTICE_DETAILS)
    assert len(resend.requests) == 2

    lost = ResendCodeSender(API_KEY, FROM, url=f"http://127.0.0.1:{closed_port}/emails", timeout=2, pause=0)
    assert lost.send_notice(channel="email", destination=DESTINATION, kind="failed_logins", details=NOTICE_DETAILS) is None


def test_only_email_is_known_so_another_channel_is_a_mistake_of_the_program(sender, resend):
    with pytest.raises(ValueError):
        sender.send_code(channel="whatsapp", destination="+525512345678", code="123456", purpose="login", ttl_seconds=300)
    with pytest.raises(ValueError):
        sender.send_notice(channel="whatsapp", destination="+525512345678", kind="failed_logins", details=NOTICE_DETAILS)
    assert resend.requests == []


def test_a_code_without_a_message_sends_nothing(sender, resend):
    with pytest.raises(ValueError):
        send_login_code(sender, purpose="otro_proposito")
    assert resend.requests == []


# --- Lo que va al registro del servidor ---------------------------------------------------------------------------


def test_the_log_has_the_http_code_and_the_name_of_the_error_and_nothing_else(sender, resend, caplog):
    caplog.set_level("DEBUG")
    resend.answers = [
        (422, {"statusCode": 422, "name": "validation_error", "message": f"The `to` field must be valid: {DESTINATION}"})
    ]

    with pytest.raises(DeliveryFailed):
        send_login_code(sender, code="482913")

    assert "422" in caplog.text and "validation_error" in caplog.text
    for secret in (API_KEY, DESTINATION, "482913", "must be valid", FROM, "Hola"):
        assert secret not in caplog.text


def test_a_network_failure_is_logged_by_class_alone(closed_port, caplog):
    caplog.set_level("DEBUG")
    lost = ResendCodeSender(API_KEY, FROM, url=f"http://127.0.0.1:{closed_port}/emails", timeout=2, pause=0)

    with pytest.raises(DeliveryFailed):
        send_login_code(lost)

    assert "URLError" in caplog.text
    for secret in (API_KEY, DESTINATION, "482913", "127.0.0.1"):
        assert secret not in caplog.text


@pytest.mark.parametrize("body,name", [
    ({"name": "validation_error"}, "validation_error"),
    ({"name": "<script>alert(1)</script>"}, ""),
    ({"name": "x" * 200}, ""),
    ({"name": 7}, ""),
    ({}, ""),
    ([1], ""),
])
def test_only_a_plain_error_name_is_read_from_the_answer(resend, body, name):
    import urllib.error
    import urllib.request

    resend.answers = [(422, body)]
    request = urllib.request.Request(resend.url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=2)

    assert error_name(raised.value) == name


# ---------------------------------------------------------------------------
# La configuración
# ---------------------------------------------------------------------------


def settings_with(settings_without_database: Settings, **changes) -> Settings:
    return settings_without_database.model_copy(update=changes)


def test_console_is_still_the_development_mode(settings_without_database):
    assert isinstance(create_code_sender(settings_without_database), ConsoleCodeSender)


def test_resend_with_its_key_and_its_sender_is_the_real_one(settings_without_database):
    from pydantic import SecretStr

    settings = settings_with(settings_without_database, email_delivery="resend", email_api_key=SecretStr(API_KEY), email_from=FROM)

    assert isinstance(create_code_sender(settings), ResendCodeSender)


@pytest.mark.parametrize(
    "key,sender_address,missing",
    [
        (None, FROM, ["EMAIL_API_KEY"]),
        (API_KEY, None, ["EMAIL_FROM"]),
        (None, None, ["EMAIL_API_KEY", "EMAIL_FROM"]),
        ("   ", FROM, ["EMAIL_API_KEY"]),
        (API_KEY, "  ", ["EMAIL_FROM"]),
    ],
)
def test_resend_without_what_it_needs_does_not_start_and_says_what_is_missing(settings_without_database, key, sender_address, missing):
    from pydantic import SecretStr

    settings = settings_with(
        settings_without_database, email_delivery="resend", email_api_key=None if key is None else SecretStr(key),
        email_from=sender_address,
    )

    with pytest.raises(ConfigurationError) as raised:
        create_code_sender(settings)

    for name in ("EMAIL_API_KEY", "EMAIL_FROM"):
        assert (name in str(raised.value)) == (name in missing)
    assert API_KEY not in str(raised.value)


def test_the_api_itself_does_not_start_with_resend_and_no_key(settings_without_database):
    settings = settings_with(settings_without_database, email_delivery="resend", email_from=FROM)

    with pytest.raises(ConfigurationError, match="EMAIL_API_KEY"):
        with TestClient(create_app(settings)):
            pass


def test_the_variables_are_read_from_the_environment_and_the_key_is_not_printed(clean_environment):
    for name, value in {
        "DATABASE_HOST": "127.0.0.1", "DATABASE_PORT": "5433", "DATABASE_NAME": "integro",
        "DATABASE_USER": "integro_api", "DATABASE_PASSWORD": "clave-inventada", "CODE_HASH_SECRET": "x" * 32,
        "EMAIL_DELIVERY": "resend", "EMAIL_API_KEY": API_KEY, "EMAIL_FROM": FROM,
    }.items():
        clean_environment.setenv(name, value)

    settings = load_settings(None)

    assert settings.email_delivery == "resend"
    assert settings.email_from == FROM
    assert settings.email_api_key.get_secret_value() == API_KEY
    assert API_KEY not in repr(settings) and API_KEY not in str(settings)


def test_a_mode_that_does_not_exist_is_refused_naming_the_variable(clean_environment):
    for name, value in {
        "DATABASE_HOST": "127.0.0.1", "DATABASE_PORT": "5433", "DATABASE_NAME": "integro",
        "DATABASE_USER": "integro_api", "DATABASE_PASSWORD": "clave-inventada", "CODE_HASH_SECRET": "x" * 32,
        "EMAIL_DELIVERY": "paloma-mensajera",
    }.items():
        clean_environment.setenv(name, value)

    with pytest.raises(ConfigurationError, match=r"EMAIL_DELIVERY \(valor no válido\)"):
        load_settings(None)


def test_the_keys_have_no_default(settings_without_database):
    assert settings_without_database.email_api_key is None
    assert settings_without_database.email_from is None


# ---------------------------------------------------------------------------
# Lo que dicen las rutas si el correo no sale
# ---------------------------------------------------------------------------


class FailingSender:
    """Un proveedor caído: ningún código sale. Anota lo que se le pidió y los avisos que le llegaron."""

    def __init__(self):
        self.asked = []
        self.notices = []

    def send_code(self, **message):
        self.asked.append(message)
        raise DeliveryFailed("HTTP 500")

    def send_notice(self, **notice):
        self.notices.append(notice)


def swap_in(api, sender):
    api.client.app.state.code_sender = sender
    return sender


def user_exists(api, email) -> bool:
    return one(api, "select count(*) from users where email = %s", email)[0] == 1


def test_register_keeps_the_account_and_says_the_email_did_not_go_out(api):
    failing = swap_in(api, FailingSender())
    form = new_form()

    response = api.client.post(RESEND_REGISTER, json=form)

    assert response.status_code == 201
    assert response.json() == {"status": "verification_required", "email": form["email"], "email_sent": False}
    assert user_exists(api, form["email"])
    assert len(failing.asked) == 1


def test_register_answers_as_always_when_the_email_goes_out(api):
    form = new_form()

    response = api.client.post(RESEND_REGISTER, json=form)

    assert response.status_code == 201
    assert response.json() == {"status": "verification_required", "email": form["email"]}


def test_after_a_failed_email_the_person_asks_for_another_code_and_finishes_registering(api):
    swap_in(api, FailingSender())
    form = new_form()
    assert api.client.post(RESEND_REGISTER, json=form).json()["email_sent"] is False
    # Ya no se puede volver a mandar el formulario: la cuenta existe.
    assert api.client.post(RESEND_REGISTER, json=form).status_code == 409

    swap_in(api, api.sender)
    from test_accounts_login import age_codes

    age_codes(api, form["email"], 120)
    assert api.client.post(RESEND_CODE, json={"email": form["email"]}).status_code == 200
    verified = api.client.post(VERIFY_EMAIL, json={"email": form["email"], "code": api.sender.last_code})

    assert verified.status_code == 200


def test_asking_for_another_code_says_503_when_the_email_does_not_go_out(api):
    form = register(api, verified=False)
    from test_accounts_login import age_codes

    age_codes(api, form["email"], 120)
    failing = swap_in(api, FailingSender())

    response = api.client.post(RESEND_CODE, json={"email": form["email"]})

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert response.headers["cache-control"] == "no-store"
    assert len(failing.asked) == 1


def test_the_first_step_of_signing_in_says_503_when_the_email_does_not_go_out(api):
    form = register(api)
    failing = swap_in(api, FailingSender())

    response = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert len(failing.asked) == 1


def test_a_wrong_password_still_says_401_when_the_provider_is_down(api):
    form = register(api)
    failing = swap_in(api, FailingSender())

    response = api.client.post(LOGIN, json={"email": form["email"], "password": "Otra-contrasena-1!"})

    assert response.status_code == 401
    assert errors_of(response) == [("credentials", "invalid_credentials")]
    assert failing.asked == []


def test_recovering_the_password_answers_exactly_the_same_when_the_email_does_not_go_out(api):
    form = register(api)
    unknown = api.client.post(RESET_REQUEST, json={"email": "nadie.existe@prueba.invalid"})
    swap_in(api, FailingSender())

    response = api.client.post(RESET_REQUEST, json={"email": form["email"]})

    assert (response.status_code, response.json()) == (unknown.status_code, unknown.json()) == (200, {"status": "code_requested"})
    assert dict(response.headers).keys() == dict(unknown.headers).keys()


def test_correcting_the_email_keeps_the_change_and_says_the_email_did_not_go_out(api):
    form = register(api, verified=False)
    new_email = f"corregida.{form['email']}"
    from test_accounts_login import age_codes

    age_codes(api, form["email"], 120)
    failing = swap_in(api, FailingSender())

    response = api.client.post(CORRECT, json={"email": form["email"], "password": PASSWORD, "new_email": new_email})

    assert response.status_code == 200
    assert response.json() == {"status": "verification_required", "email": new_email, "email_sent": False}
    assert user_exists(api, new_email) and not user_exists(api, form["email"])
    assert len(failing.asked) == 1

    swap_in(api, api.sender)
    age_codes(api, new_email, 120)
    assert api.client.post(RESEND_CODE, json={"email": new_email}).status_code == 200
    assert api.client.post(VERIFY_EMAIL, json={"email": new_email, "code": api.sender.last_code}).status_code == 200


def test_correcting_the_email_answers_as_always_when_the_email_goes_out(api):
    form = register(api, verified=False)
    new_email = f"corregida.{form['email']}"
    from test_accounts_login import age_codes

    age_codes(api, form["email"], 120)

    response = api.client.post(CORRECT, json={"email": form["email"], "password": PASSWORD, "new_email": new_email})

    assert response.json() == {"status": "verification_required", "email": new_email}


# --- Los avisos que no salen no cambian lo que contesta la ruta ----------------------------------------------------


def real_sender_with_a_provider_that_fails(resend):
    resend.answers = [(500, {"name": "application_error", "message": "x"})]
    return ResendCodeSender(API_KEY, FROM, url=resend.url, timeout=2, pause=0)


def test_the_password_changes_even_if_the_notice_cannot_be_sent(api, resend):
    form = register(api)
    assert ask(api, form["email"]).status_code == 200
    code = api.sender.last_code
    swap_in(api, real_sender_with_a_provider_that_fails(resend))

    response = confirm(api, form["email"], code)

    assert response.status_code == 200
    assert response.json() == {"status": "password_changed"}
    assert len(resend.requests) == 2  # el aviso se intentó dos veces y no se pudo, sin cambiar la respuesta


def test_three_wrong_passwords_still_say_401_when_the_notice_cannot_be_sent(api, resend):
    form = register(api)
    swap_in(api, real_sender_with_a_provider_that_fails(resend))

    answers = [
        api.client.post(LOGIN, json={"email": form["email"], "password": f"Equivocada-{n}-contrasena!"}) for n in range(3)
    ]

    assert [answer.status_code for answer in answers] == [401, 401, 401]
    assert len(resend.requests) >= 2  # el aviso de los tres intentos se quiso mandar


def test_with_the_real_sender_and_a_working_provider_the_whole_sign_in_sends_one_email(api, resend):
    form = register(api)
    swap_in(api, ResendCodeSender(API_KEY, FROM, url=resend.url, timeout=2, pause=0))

    response = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert response.status_code == 200
    assert len(resend.requests) == 1
    body = resend.requests[0]["json"]
    assert body["to"] == [form["email"]]
    assert body["subject"] == "Tu código para iniciar sesión en Íntegro"
    assert re.search(r"\n\n\d{6}\n\n", body["text"])
