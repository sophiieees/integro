"""Casos de la pieza "sesión en cookie".

Especificación aceptada por Sophia el 19 de noviembre de 2026 (ADR 0015):
la llave de sesión viaja en una cookie que la página no puede leer, y solo en
la cookie; el encabezado Authorization ya no se acepta.

    1. Código correcto: 200, llega la cookie integro_session con HttpOnly,
       SameSite=Strict, Path=/ y 30 días; el texto de la respuesta no trae la
       llave.
    2. /auth/me con la cookie: 200 con sus datos.
    3. /auth/me sin cookie: 401 not_authenticated.
    4. Cookie inventada, vencida o de sesión cerrada: 401.
    5. Anfitrión: la cookie dura 7 días.
    6. Con SESSION_COOKIE_SECURE encendida la cookie lleva Secure; apagada, no.
    7. Cada uso renueva la cookie.
    8. Código incorrecto: 400 y no llega ninguna cookie.

Corren contra la base real con rollback_pool: todo se deshace al terminar
cada prueba.
"""

import pytest
from conftest import session_cookie, with_session
from test_accounts_login import (
    DAY,
    LOGIN,
    LOGIN_VERIFY,
    ME,
    PASSWORD,
    age_codes,
    errors_of,
    login,
    make_host,
    one,
    register,
    run,
    wrong_code,
)

from app.api.auth import SESSION_COOKIE
from app.core.config import Settings
from app.modules.accounts.security import hash_session_token


def use_settings(api, **changes) -> None:
    """Cambia la configuración de la API solo para esta prueba."""
    api.client.app.state.settings = api.settings.model_copy(update=changes)


def verify(api, form: dict, **extra):
    """Hace los dos pasos y devuelve la respuesta del segundo, sin tocar las cookies del cliente."""
    age_codes(api, form["email"], 61)
    assert api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD}).status_code == 200
    return api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code}, **extra)


# --- Caso 1 ----------------------------------------------------------------


def test_right_code_delivers_the_key_in_a_cookie_the_page_cannot_read(api):
    form = register(api)

    response = verify(api, form)

    assert response.status_code == 200
    cookie = session_cookie(response)
    assert cookie is not None
    assert cookie["httponly"] is True
    assert cookie["samesite"].lower() == "strict"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == str(30 * DAY)
    # Sin Domain: la cookie es solo del servidor que la entregó.
    assert cookie["domain"] == ""


def test_the_response_text_does_not_carry_the_key(api):
    form = register(api)

    response = verify(api, form)

    token = session_cookie(response).value
    body = response.json()
    # csrf_token es la clave anti-falsificación de la pieza de cerrar sesión: no es la llave.
    assert set(body) == {"status", "expires_at", "csrf_token"}
    assert body["status"] == "session_opened"
    assert token not in response.text


def test_the_cookie_carries_the_key_whose_fingerprint_is_stored(api):
    form = register(api)

    token = session_cookie(verify(api, form)).value

    assert len(token) >= 43
    stored = one(api, "select token_hash from sessions where user_id = (select id from users where email = %s)", form["email"])[0]
    assert stored == hash_session_token(token)


def test_only_one_session_cookie_is_delivered(api):
    form = register(api)

    response = verify(api, form)

    assert len(response.headers.get_list("set-cookie")) == 1


# --- Caso 2 ----------------------------------------------------------------


def test_me_with_the_cookie_returns_the_person(api):
    form = register(api)
    token = login(api, form)

    response = api.client.get(ME, headers=with_session(token))

    assert response.status_code == 200
    assert (response.json()["first_name"], response.json()["email"]) == ("Ana", form["email"])


def test_a_browser_that_keeps_the_cookie_needs_nothing_else(api):
    """El cliente guarda la cookie como un navegador y la manda solo en la siguiente petición."""
    use_settings(api, session_cookie_secure=False)  # el cliente de pruebas no usa HTTPS
    form = register(api)
    api.client.cookies.clear()

    assert verify(api, form).status_code == 200
    response = api.client.get(ME)

    assert response.status_code == 200
    assert response.json()["email"] == form["email"]
    api.client.cookies.clear()


def test_the_cookie_does_not_leak_into_the_answer_of_me(api):
    form = register(api)
    token = login(api, form)

    response = api.client.get(ME, headers=with_session(token))

    assert token not in response.text


# --- Caso 3 ----------------------------------------------------------------


def test_me_without_cookie_is_401(api):
    register(api)

    response = api.client.get(ME)

    assert response.status_code == 401
    assert errors_of(response) == [("authorization", "not_authenticated")]
    assert session_cookie(response) is None
    assert "www-authenticate" not in response.headers


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "Token"])
def test_the_key_in_the_authorization_header_is_no_longer_accepted(api, scheme):
    """Solo la cookie: una llave que sirve, mandada en el encabezado, no abre nada."""
    form = register(api)
    token = login(api, form)

    response = api.client.get(ME, headers={"Authorization": f"{scheme} {token}"})

    assert response.status_code == 401
    # La misma llave en la cookie sí sirve.
    assert api.client.get(ME, headers=with_session(token)).status_code == 200


def test_a_cookie_with_another_name_is_ignored(api):
    form = register(api)
    token = login(api, form)

    assert api.client.get(ME, headers={"Cookie": f"session={token}"}).status_code == 401


# --- Caso 4 ----------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "llave-inventada", "x" * 43, "x" * 5000, "' or 1=1 --"])
def test_invented_cookie_is_401(api, value):
    register(api)

    response = api.client.get(ME, headers={"Cookie": f"{SESSION_COOKIE}={value}"})

    assert response.status_code == 401
    assert session_cookie(response) is None


def test_cookie_of_an_expired_session_is_401(api):
    form = register(api)
    token = login(api, form)
    # La sesión se abrió hace 40 días y venció hace un segundo.
    run(
        api,
        "update sessions set created_at = now() - interval '40 days', last_used_at = now() - interval '31 days', "
        "expires_at = now() - interval '1 second' where user_id = (select id from users where email = %s)",
        form["email"],
    )

    response = api.client.get(ME, headers=with_session(token))

    assert response.status_code == 401
    # Una sesión vencida no recibe una cookie nueva.
    assert session_cookie(response) is None


def test_cookie_of_a_closed_session_is_401(api):
    form = register(api)
    token = login(api, form)
    run(api, "update sessions set revoked_at = now() where user_id = (select id from users where email = %s)", form["email"])

    response = api.client.get(ME, headers=with_session(token))

    assert response.status_code == 401
    assert session_cookie(response) is None


def test_the_stored_fingerprint_in_the_cookie_does_not_work(api):
    form = register(api)
    token = login(api, form)

    assert api.client.get(ME, headers=with_session(hash_session_token(token))).status_code == 401


# --- Caso 5 ----------------------------------------------------------------


def test_the_cookie_of_a_host_lasts_7_days(api):
    form = register(api)
    make_host(api, form["email"])

    cookie = session_cookie(verify(api, form))

    assert cookie["max-age"] == str(7 * DAY)


def test_the_cookie_lasts_what_the_configuration_says(api):
    use_settings(api, session_idle_days_guest=3)
    form = register(api)

    cookie = session_cookie(verify(api, form))

    assert cookie["max-age"] == str(3 * DAY)


# --- Caso 6 ----------------------------------------------------------------


@pytest.mark.parametrize("secure", [True, False])
def test_the_cookie_is_secure_only_when_the_setting_says_so(api, secure):
    use_settings(api, session_cookie_secure=secure)
    form = register(api)

    opened = session_cookie(verify(api, form))
    renewed = session_cookie(api.client.get(ME, headers=with_session(opened.value)))

    assert bool(opened["secure"]) is secure
    assert bool(renewed["secure"]) is secure
    api.client.cookies.clear()


def test_the_cookie_is_secure_unless_it_is_turned_off_on_purpose(clean_environment):
    """Sin la variable, la cookie exige HTTPS."""
    values = dict(
        _env_file=None,
        database_host="127.0.0.1",
        database_port=5433,
        database_name="integro",
        database_user="integro_api",
        database_password="clave-inventada-para-la-prueba",
        code_hash_secret="llave-inventada-para-las-pruebas-0123456789",
        email_delivery="console",
    )

    assert Settings(**values).session_cookie_secure is True
    clean_environment.setenv("SESSION_COOKIE_SECURE", "false")
    assert Settings(**values).session_cookie_secure is False
    clean_environment.setenv("SESSION_COOKIE_SECURE", "quizas")
    with pytest.raises(Exception):
        Settings(**values)


# --- Caso 7 ----------------------------------------------------------------


def test_each_use_delivers_the_cookie_again_for_30_days(api):
    form = register(api)
    token = login(api, form)
    # La sesión vence mañana: quedaba un día.
    run(api, "update sessions set expires_at = now() + interval '1 day' where user_id = (select id from users where email = %s)", form["email"])

    response = api.client.get(ME, headers=with_session(token))

    cookie = session_cookie(response)
    assert response.status_code == 200
    assert cookie.value == token
    assert cookie["max-age"] == str(30 * DAY)
    assert cookie["httponly"] is True
    assert cookie["samesite"].lower() == "strict"
    assert cookie["path"] == "/"
    # La base renovó el mismo plazo.
    assert one(api, "select extract(epoch from expires_at - now())::int from sessions where user_id = (select id from users where email = %s)", form["email"])[0] == 30 * DAY


def test_a_person_who_becomes_host_gets_a_7_day_cookie_from_the_next_use(api):
    form = register(api)
    token = login(api, form)
    make_host(api, form["email"])

    cookie = session_cookie(api.client.get(ME, headers=with_session(token)))

    assert cookie["max-age"] == str(7 * DAY)


# --- Caso 8 ----------------------------------------------------------------


def test_wrong_code_delivers_no_cookie(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": wrong_code(api.sender.last_code)})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert session_cookie(response) is None
    assert response.headers.get_list("set-cookie") == []


def test_expired_code_delivers_no_cookie(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    age_codes(api, form["email"], 301)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})

    assert response.status_code == 400
    assert session_cookie(response) is None


def test_the_password_step_delivers_no_cookie(api):
    """El primer paso todavía no abre la sesión."""
    form = register(api)

    response = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert response.status_code == 200
    assert response.headers.get_list("set-cookie") == []


def test_login_verify_without_its_data_delivers_no_cookie(api):
    response = api.client.post(LOGIN_VERIFY, json={})

    assert response.status_code == 422
    assert response.headers.get_list("set-cookie") == []
