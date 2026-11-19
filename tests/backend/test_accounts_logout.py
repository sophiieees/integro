"""Casos de la pieza "cerrar sesión".

Especificación aceptada por Sophia el 19 de noviembre de 2026: terminar la
sesión actual y poder cerrar las demás, con lista de sesiones y dos formas de
cerrar, y con las tres defensas contra peticiones hechas desde páginas ajenas
(la cookie solo desde el mismo sitio, revisar de dónde viene la petición y la
clave anti-falsificación).

    1. Cerrar sesión: 200; la sesión queda cerrada en la base, la cookie se
       borra y /auth/me responde 401.
    2. Cerrar sesión sin sesión: 401.
    3. Ver mis sesiones: la lista de las abiertas, con fecha, navegador,
       dirección y cuál es la actual; nunca las de otra persona ni las ya
       cerradas.
    4. Cerrar una de mis sesiones: 200 y esa deja de servir; la de otra
       persona o una inventada: 404.
    5. Cerrar todas las demás: 200; solo queda la actual.
    6. Petición que viene de otra página: 403, y no cambia nada.
    7. Petición sin la clave anti-falsificación, o con una clave equivocada o
       de otra sesión: 403.
    8. Una sesión cerrada no vuelve a servir.

Corren contra la base real con rollback_pool: todo se deshace al terminar
cada prueba.
"""

from uuid import uuid4

import pytest
from conftest import session_cookie, with_session
from pydantic import SecretStr
from test_accounts_login import LOGIN, LOGIN_VERIFY, ME, PASSWORD, age_codes, errors_of, login, one, register, run

from app.api.protection import CSRF_HEADER, csrf_token, origin_of
from app.modules.accounts.security import hash_session_token

LOGOUT = "/api/v1/auth/logout"
SESSIONS = "/api/v1/auth/sessions"
CLOSE_OTHERS = "/api/v1/auth/sessions/close-others"

# La dirección del cliente de pruebas: para la API, su propia dirección.
OWN_ORIGIN = "http://testserver"
OTHER_SITE = "https://pagina-ajena.example"


def change(api, token: str, **extra) -> dict:
    """Los encabezados que manda una página de Íntegro al pedir un cambio con esa sesión."""
    headers = {**with_session(token), "Origin": OWN_ORIGIN, CSRF_HEADER: csrf_token(token, api.settings)}
    headers.update(extra)
    return {name: value for name, value in headers.items() if value is not None}


def login_from(api, form: dict, browser: str) -> str:
    """Inicia sesión diciendo qué navegador es, y devuelve la llave."""
    age_codes(api, form["email"], 61)
    assert api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD}).status_code == 200
    response = api.client.post(
        LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code}, headers={"User-Agent": browser}
    )
    token = session_cookie(response).value
    api.client.cookies.clear()
    return token


def is_open(api, token: str) -> bool:
    return one(api, "select revoked_at is null from sessions where token_hash = %s", hash_session_token(token))[0]


def works(api, token: str) -> bool:
    status = api.client.get(ME, headers=with_session(token)).status_code
    assert status in (200, 401)
    return status == 200


def ids(api, token: str) -> dict:
    """Las sesiones que ve esa llave, por navegador."""
    listed = api.client.get(SESSIONS, headers=with_session(token)).json()["sessions"]
    return {item["user_agent"]: item["id"] for item in listed}


# --- Caso 1 ----------------------------------------------------------------


def test_logout_closes_the_session_and_deletes_the_cookie(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token))

    assert response.status_code == 200
    assert response.json() == {"status": "signed_out"}
    assert is_open(api, token) is False
    assert one(api, "select revoked_at is not null from sessions where token_hash = %s", hash_session_token(token))[0] is True
    assert works(api, token) is False


def test_logout_asks_the_browser_to_delete_the_cookie(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token))

    headers = response.headers.get_list("set-cookie")
    cookie = session_cookie(response)
    assert len(headers) == 1
    assert cookie.value == ""
    assert cookie["max-age"] == "0"
    assert cookie["path"] == "/"
    assert cookie["httponly"] is True
    assert cookie["samesite"].lower() == "strict"
    assert token not in response.text and token not in headers[0]


def test_logout_closes_only_that_session(api):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)

    assert api.client.post(LOGOUT, headers=change(api, phone)).status_code == 200

    assert (works(api, phone), works(api, computer)) == (False, True)


def test_logout_of_one_person_does_not_touch_another(api):
    ana = login(api, register(api, "Ana"))
    beto = login(api, register(api, "Beto"))

    api.client.post(LOGOUT, headers=change(api, ana))

    assert (works(api, ana), works(api, beto)) == (False, True)


# --- Caso 2 ----------------------------------------------------------------


def test_logout_without_session_is_401(api):
    response = api.client.post(LOGOUT, headers={"Origin": OWN_ORIGIN})

    assert response.status_code == 401
    assert errors_of(response) == [("authorization", "not_authenticated")]


@pytest.mark.parametrize("value", ["llave-inventada", "x" * 43, ""])
def test_logout_with_an_invented_cookie_is_401(api, value):
    register(api)

    response = api.client.post(
        LOGOUT, headers={"Cookie": f"integro_session={value}", "Origin": OWN_ORIGIN, CSRF_HEADER: "x"}
    )

    assert response.status_code == 401


# --- Caso 3 ----------------------------------------------------------------


def test_my_sessions_lists_the_open_ones_and_marks_the_current(api):
    form = register(api)
    phone = login_from(api, form, "Celular de prueba")
    computer = login_from(api, form, "Computadora de prueba")

    response = api.client.get(SESSIONS, headers=with_session(computer))

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 2
    assert all(
        set(item) == {"id", "created_at", "last_used_at", "expires_at", "ip_address", "user_agent", "current"}
        for item in sessions
    )
    assert {item["user_agent"]: item["current"] for item in sessions} == {
        "Celular de prueba": False,
        "Computadora de prueba": True,
    }
    # Desde el celular, la actual es la del celular.
    from_phone = api.client.get(SESSIONS, headers=with_session(phone)).json()["sessions"]
    assert {item["user_agent"]: item["current"] for item in from_phone} == {
        "Celular de prueba": True,
        "Computadora de prueba": False,
    }


def test_my_sessions_never_shows_the_key_or_its_fingerprint(api):
    form = register(api)
    token = login(api, form)

    response = api.client.get(SESSIONS, headers=with_session(token))

    assert token not in response.text
    assert hash_session_token(token) not in response.text
    assert "token" not in response.text


def test_my_sessions_shows_the_address_when_there_is_one(api):
    form = register(api)
    token = login(api, form)
    run(api, "update sessions set ip_address = '203.0.113.7' where token_hash = %s", hash_session_token(token))

    session = api.client.get(SESSIONS, headers=with_session(token)).json()["sessions"][0]

    assert session["ip_address"] == "203.0.113.7"


def test_my_sessions_never_shows_those_of_another_person(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    ana_key = login_from(api, ana, "Navegador de Ana")
    login_from(api, beto, "Navegador de Beto")

    sessions = api.client.get(SESSIONS, headers=with_session(ana_key)).json()["sessions"]

    assert [item["user_agent"] for item in sessions] == ["Navegador de Ana"]


def test_my_sessions_leaves_out_closed_and_expired_ones(api):
    form = register(api)
    closed = login_from(api, form, "Cerrada")
    expired = login_from(api, form, "Vencida")
    current = login_from(api, form, "Actual")
    run(api, "update sessions set revoked_at = now() where token_hash = %s", hash_session_token(closed))
    run(
        api,
        "update sessions set created_at = now() - interval '40 days', last_used_at = now() - interval '31 days', "
        "expires_at = now() - interval '1 second' where token_hash = %s",
        hash_session_token(expired),
    )

    sessions = api.client.get(SESSIONS, headers=with_session(current)).json()["sessions"]

    assert [item["user_agent"] for item in sessions] == ["Actual"]


def test_my_sessions_without_session_is_401(api):
    assert api.client.get(SESSIONS).status_code == 401


def test_reading_my_sessions_needs_no_key_of_the_page(api):
    """Ver no cambia nada: basta la cookie, sin Origin ni clave anti-falsificación."""
    form = register(api)
    token = login(api, form)

    assert api.client.get(SESSIONS, headers=with_session(token)).status_code == 200
    assert api.client.get(ME, headers=with_session(token)).status_code == 200


# --- Caso 4 ----------------------------------------------------------------


def test_closing_one_of_my_sessions_stops_it_and_leaves_the_rest(api):
    form = register(api)
    phone = login_from(api, form, "Celular")
    tablet = login_from(api, form, "Tableta")
    computer = login_from(api, form, "Computadora")
    phone_id = ids(api, computer)["Celular"]

    response = api.client.delete(f"{SESSIONS}/{phone_id}", headers=change(api, computer))

    assert response.status_code == 200
    assert response.json() == {"status": "closed", "closed": 1}
    assert (works(api, phone), works(api, tablet), works(api, computer)) == (False, True, True)
    # La que se cierra es otra: la cookie actual no se borra.
    assert session_cookie(response) is None or session_cookie(response).value == computer


def test_the_session_of_another_person_cannot_be_closed(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    ana_key = login_from(api, ana, "Navegador de Ana")
    beto_key = login_from(api, beto, "Navegador de Beto")
    beto_id = ids(api, beto_key)["Navegador de Beto"]

    response = api.client.delete(f"{SESSIONS}/{beto_id}", headers=change(api, ana_key))

    assert response.status_code == 404
    assert errors_of(response) == [("session", "not_found")]
    assert works(api, beto_key) is True


@pytest.mark.parametrize("session_id", [str(uuid4()), "no-es-un-id", "0", "' or 1=1 --"])
def test_an_invented_session_is_404(api, session_id):
    form = register(api)
    token = login(api, form)

    response = api.client.delete(f"{SESSIONS}/{session_id}", headers=change(api, token))

    assert response.status_code == 404
    assert works(api, token) is True


def test_a_session_already_closed_is_404(api):
    form = register(api)
    phone = login_from(api, form, "Celular")
    computer = login_from(api, form, "Computadora")
    phone_id = ids(api, computer)["Celular"]
    assert api.client.delete(f"{SESSIONS}/{phone_id}", headers=change(api, computer)).status_code == 200

    again = api.client.delete(f"{SESSIONS}/{phone_id}", headers=change(api, computer))

    assert again.status_code == 404
    assert works(api, phone) is False


def test_closing_the_current_session_by_its_id_also_deletes_the_cookie(api):
    form = register(api)
    token = login_from(api, form, "Computadora")
    own_id = ids(api, token)["Computadora"]

    response = api.client.delete(f"{SESSIONS}/{own_id}", headers=change(api, token))

    assert response.status_code == 200
    assert session_cookie(response)["max-age"] == "0"
    assert works(api, token) is False


# --- Caso 5 ----------------------------------------------------------------


def test_closing_all_the_others_leaves_only_the_current(api):
    form = register(api)
    phone = login_from(api, form, "Celular")
    tablet = login_from(api, form, "Tableta")
    computer = login_from(api, form, "Computadora")

    response = api.client.post(CLOSE_OTHERS, headers=change(api, computer))

    assert response.status_code == 200
    assert response.json() == {"status": "closed", "closed": 2}
    assert (works(api, phone), works(api, tablet), works(api, computer)) == (False, False, True)
    assert list(ids(api, computer)) == ["Computadora"]


def test_closing_all_the_others_does_not_touch_another_person(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    ana_phone = login(api, ana)
    ana_computer = login(api, ana)
    beto_key = login(api, beto)

    api.client.post(CLOSE_OTHERS, headers=change(api, ana_computer))

    assert (works(api, ana_phone), works(api, ana_computer), works(api, beto_key)) == (False, True, True)


def test_closing_all_the_others_with_none_open_closes_nothing(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(CLOSE_OTHERS, headers=change(api, token))

    assert response.json() == {"status": "closed", "closed": 0}
    assert works(api, token) is True


def test_closing_all_the_others_without_session_is_401(api):
    assert api.client.post(CLOSE_OTHERS, headers={"Origin": OWN_ORIGIN}).status_code == 401


# --- Caso 6 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [OTHER_SITE, "http://testserver.pagina-ajena.example", "https://testserver", "http://testserver:8000", "null", ""],
)
def test_a_request_from_another_page_is_403_and_changes_nothing(api, origin):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)

    logout = api.client.post(LOGOUT, headers=change(api, computer, Origin=origin))
    others = api.client.post(CLOSE_OTHERS, headers=change(api, computer, Origin=origin))

    assert (logout.status_code, others.status_code) == (403, 403)
    assert errors_of(logout) == [("request", "origin_not_allowed")]
    assert session_cookie(logout) is None
    assert (works(api, phone), works(api, computer)) == (True, True)


def test_closing_a_session_from_another_page_is_403(api):
    form = register(api)
    phone = login_from(api, form, "Celular")
    computer = login_from(api, form, "Computadora")
    phone_id = ids(api, computer)["Celular"]

    response = api.client.delete(f"{SESSIONS}/{phone_id}", headers=change(api, computer, Origin=OTHER_SITE))

    assert response.status_code == 403
    assert works(api, phone) is True


def test_a_request_that_does_not_say_where_it_comes_from_is_403(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token, Origin=None))

    assert response.status_code == 403
    assert works(api, token) is True


def test_the_page_address_is_used_when_the_browser_sends_no_origin(api):
    """Algunos navegadores viejos no mandan Origin: se mira la dirección de la página (Referer)."""
    form = register(api)
    token = login(api, form)

    from_outside = api.client.post(LOGOUT, headers=change(api, token, Origin=None, Referer=f"{OTHER_SITE}/x.html"))
    from_integro = api.client.post(LOGOUT, headers=change(api, token, Origin=None, Referer=f"{OWN_ORIGIN}/index.html"))

    assert (from_outside.status_code, from_integro.status_code) == (403, 200)


def test_a_wrong_origin_is_not_saved_by_a_good_page_address(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(
        LOGOUT, headers=change(api, token, Origin="null", Referer=f"{OWN_ORIGIN}/index.html")
    )

    assert response.status_code == 403


def test_a_rejected_request_does_not_renew_the_session(api):
    form = register(api)
    token = login(api, form)
    run(
        api,
        "update sessions set expires_at = now() + interval '1 day' where token_hash = %s",
        hash_session_token(token),
    )

    api.client.post(LOGOUT, headers=change(api, token, Origin=OTHER_SITE))

    left = one(
        api, "select extract(epoch from expires_at - now())::int from sessions where token_hash = %s", hash_session_token(token)
    )[0]
    assert left == 24 * 60 * 60


def test_an_address_of_the_allowed_list_can_ask_for_changes(api):
    api.client.app.state.settings = api.settings.model_copy(
        update={"allowed_origins": "https://integro.example, https://www.integro.example"}
    )
    form = register(api)
    first = login(api, form)
    second = login(api, form)

    listed = api.client.post(LOGOUT, headers=change(api, first, Origin="https://www.integro.example"))
    unlisted = api.client.post(LOGOUT, headers=change(api, second, Origin="https://otra.integro.example"))

    assert (listed.status_code, unlisted.status_code) == (200, 403)


@pytest.mark.parametrize(
    "address, origin",
    [
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
        ("https://Integro.Example/pagina.html?x=1", "https://integro.example"),
        ("https://integro.example:8443", "https://integro.example:8443"),
        ("null", None),
        ("", None),
        (None, None),
        ("integro.example", None),
        ("ftp://integro.example", None),
        ("javascript:alert(1)", None),
    ],
)
def test_reading_the_origin_of_an_address(address, origin):
    assert origin_of(address) == origin


# --- Caso 7 ----------------------------------------------------------------


@pytest.mark.parametrize("sent", [None, "", "clave-inventada", "0" * 64])
def test_a_request_without_the_right_page_key_is_403_and_changes_nothing(api, sent):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)

    logout = api.client.post(LOGOUT, headers=change(api, computer, **{CSRF_HEADER: sent}))
    others = api.client.post(CLOSE_OTHERS, headers=change(api, computer, **{CSRF_HEADER: sent}))

    assert (logout.status_code, others.status_code) == (403, 403)
    assert errors_of(logout) == [("request", "csrf_failed")]
    assert (works(api, phone), works(api, computer)) == (True, True)


def test_the_page_key_of_another_session_does_not_work(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    ana_phone = login(api, ana)
    ana_computer = login(api, ana)
    beto_key = login(api, beto)

    own_other = api.client.post(LOGOUT, headers=change(api, ana_computer, **{CSRF_HEADER: csrf_token(ana_phone, api.settings)}))
    of_beto = api.client.post(LOGOUT, headers=change(api, ana_computer, **{CSRF_HEADER: csrf_token(beto_key, api.settings)}))

    assert (own_other.status_code, of_beto.status_code) == (403, 403)
    assert works(api, ana_computer) is True


def test_the_session_key_itself_does_not_work_as_page_key(api):
    form = register(api)
    token = login(api, form)

    response = api.client.post(LOGOUT, headers=change(api, token, **{CSRF_HEADER: token}))

    assert response.status_code == 403


def test_the_page_receives_its_key_when_the_session_opens_and_in_me(api):
    form = register(api)
    age_codes(api, form["email"], 61)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    opened = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})
    token = session_cookie(opened).value
    api.client.cookies.clear()
    me = api.client.get(ME, headers=with_session(token))

    page_key = opened.json()["csrf_token"]
    assert me.json()["csrf_token"] == page_key == csrf_token(token, api.settings)
    assert len(page_key) == 64
    # No es la llave de sesión ni su huella, y con ella sí se puede pedir un cambio.
    assert page_key != token and page_key != hash_session_token(token)
    assert api.client.post(LOGOUT, headers={**with_session(token), "Origin": OWN_ORIGIN, CSRF_HEADER: page_key}).status_code == 200


def test_each_session_has_its_own_page_key(api):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)

    assert csrf_token(phone, api.settings) != csrf_token(computer, api.settings)
    assert csrf_token(phone, api.settings) == csrf_token(phone, api.settings)


def test_the_page_key_depends_on_the_secret_of_the_server(api):
    other = api.settings.model_copy(
        update={"code_hash_secret": SecretStr("otra-llave-inventada-para-las-pruebas-98765")}
    )

    assert csrf_token("una-llave", api.settings) != csrf_token("una-llave", other)


# --- Caso 8 ----------------------------------------------------------------


def test_a_closed_session_does_not_work_again(api):
    form = register(api)
    token = login(api, form)
    assert api.client.post(LOGOUT, headers=change(api, token)).status_code == 200

    assert api.client.get(ME, headers=with_session(token)).status_code == 401
    assert api.client.get(SESSIONS, headers=with_session(token)).status_code == 401
    assert api.client.post(LOGOUT, headers=change(api, token)).status_code == 401
    assert api.client.post(CLOSE_OTHERS, headers=change(api, token)).status_code == 401
    assert is_open(api, token) is False


def test_after_logout_the_person_can_log_in_again_with_a_new_session(api):
    form = register(api)
    old = login(api, form)
    api.client.post(LOGOUT, headers=change(api, old))

    new = login(api, form)

    assert new != old
    assert (works(api, old), works(api, new)) == (False, True)


def test_logout_routes_are_documented(api):
    paths = api.client.get("/openapi.json").json()["paths"]

    assert "post" in paths[LOGOUT] and "get" in paths[SESSIONS] and "post" in paths[CLOSE_OTHERS]
    assert "delete" in paths[SESSIONS + "/{session_id}"]
