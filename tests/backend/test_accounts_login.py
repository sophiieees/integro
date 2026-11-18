"""Casos de la pieza "inicio de sesión y sesión".

Especificación aceptada por Sophia el 18 de noviembre de 2026 (ADR 0014):

    POST /api/v1/auth/login   (correo y contraseña)
     1. Correctos y correo comprobado: 200, pide el código; llega un código de
        6 dígitos al correo (5 minutos). Todavía no hay sesión.
     2. Contraseña incorrecta, o correo sin cuenta: 401, la misma respuesta en
        los dos casos; no se envía código.
     3. Correo sin comprobar: 403; no se envía.
     4. Pedir otro código antes de 60 segundos: 429.
    POST /api/v1/auth/login/verify   (correo y código)
     5. Código correcto: 200 con la llave de sesión. En la base queda la huella
        de la llave (no la llave), la IP y el navegador. Vence a los 30 días
        sin uso (huésped) o a los 7 (anfitrión).
     6. Código incorrecto: 400; al quinto fallo se bloquea ese código. Vencido:
        400. El código no sirve dos veces.
     7. Un código de comprobar correo no sirve para iniciar sesión, ni al revés.
    GET /api/v1/auth/me   (con la llave)
     8. Llave válida: 200 con sus datos; cada uso renueva el plazo de 30 o 7 días.
     9. Sin llave, llave inventada, sesión vencida o sesión revocada: 401.
    10. Dos sesiones a la vez (celular y computadora) funcionan; cada persona
        ve solo lo suyo.

Corren contra la base real con rollback_pool: todo se deshace al terminar
cada prueba. Los códigos no se envían: la prueba los lee de un anotador.
"""

from uuid import uuid4

import pytest

from app.api.auth import bearer_token
from app.database.transaction import system_transaction
from app.modules.accounts.codes import create_code
from app.modules.accounts.login import clean_ip
from app.modules.accounts.security import (
    generate_session_token,
    hash_session_token,
    verify_password,
    hash_password,
)

REGISTER = "/api/v1/auth/register"
VERIFY_EMAIL = "/api/v1/auth/verify-email"
LOGIN = "/api/v1/auth/login"
LOGIN_VERIFY = "/api/v1/auth/login/verify"
ME = "/api/v1/auth/me"

PASSWORD = "Ejemplo-2026"
DAY = 24 * 60 * 60


def errors_of(response) -> list[tuple[str, str]]:
    return [(error["field"], error["code"]) for error in response.json()["errors"]]


def one(api, query: str, *parameters):
    """Lee una fila como el sistema."""
    with system_transaction(api.pool) as connection:
        return connection.execute(query, parameters).fetchone()


def run(api, query: str, *parameters) -> None:
    """Cambia algo como el sistema, para preparar un caso."""
    with system_transaction(api.pool) as connection:
        connection.execute(query, parameters)


def register(api, first_name: str = "Ana", verified: bool = True) -> dict:
    """Crea una cuenta por la API y, si se pide, comprueba su correo."""
    tag = uuid4().hex[:12]
    form = {
        "first_name": first_name,
        "last_name": "Torres",
        "email": f"{first_name.lower()}.{tag}@prueba.invalid",
        "password": PASSWORD,
        "phone": "+52" + str(int(tag, 16))[:10].rjust(10, "5"),
        "country": "MX",
        "birth_date": "1995-03-14",
    }
    assert api.client.post(REGISTER, json=form).status_code == 201
    if verified:
        code = api.sender.last_code
        assert api.client.post(VERIFY_EMAIL, json={"email": form["email"], "code": code}).status_code == 200
    return form


def make_host(api, email: str) -> None:
    run(api, "insert into host_profiles (user_id) select id from users where email = %s", email)


def age_codes(api, email: str, seconds: int) -> None:
    """Hace que los códigos de esa persona parezcan creados hace tantos segundos."""
    run(
        api,
        "update one_time_codes set created_at = created_at - make_interval(secs => %s), "
        "expires_at = expires_at - make_interval(secs => %s) "
        "where user_id = (select id from users where email = %s)",
        seconds, seconds, email,
    )


def login(api, form: dict) -> str:
    """Hace los dos pasos y devuelve la llave de la sesión."""
    age_codes(api, form["email"], 61)  # para no chocar con la espera entre códigos
    first = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    assert first.status_code == 200, first.text
    second = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})
    assert second.status_code == 200, second.text
    return second.json()["token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sessions_of(api, email: str) -> int:
    return one(
        api, "select count(*) from sessions where user_id = (select id from users where email = %s)", email
    )[0]


# ===========================================================================
# POST /auth/login
# ===========================================================================

# --- Caso 1 ----------------------------------------------------------------


def test_login_with_right_password_asks_for_the_code_and_opens_no_session(api):
    form = register(api)
    sent_before = len(api.sender.sent)

    response = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"status": "code_required"}
    assert len(api.sender.sent) == sent_before + 1
    message = api.sender.sent[-1]
    assert (message["channel"], message["destination"], message["purpose"], message["ttl_seconds"]) == (
        "email", form["email"], "login", 300,
    )
    assert len(message["code"]) == 6 and message["code"].isdigit()
    assert sessions_of(api, form["email"]) == 0


def test_login_accepts_the_email_in_any_case(api):
    form = register(api)

    response = api.client.post(LOGIN, json={"email": f"  {form['email'].upper()} ", "password": PASSWORD})

    assert response.status_code == 200


# --- Caso 2 ----------------------------------------------------------------


@pytest.mark.parametrize("password", ["Ejemplo-2027", "ejemplo-2026", "Ejemplo-2026 ", "x"])
def test_login_with_wrong_password_is_rejected_and_sends_nothing(api, password):
    form = register(api)
    sent_before = len(api.sender.sent)

    response = api.client.post(LOGIN, json={"email": form["email"], "password": password})

    assert response.status_code == 401
    assert errors_of(response) == [("credentials", "invalid_credentials")]
    assert len(api.sender.sent) == sent_before


def test_login_for_an_email_without_account_answers_exactly_the_same(api):
    form = register(api)
    wrong_password = api.client.post(LOGIN, json={"email": form["email"], "password": "Ejemplo-2027"})

    no_account = api.client.post(
        LOGIN, json={"email": f"nadie.{uuid4().hex[:8]}@prueba.invalid", "password": PASSWORD}
    )

    assert no_account.status_code == wrong_password.status_code == 401
    assert no_account.json() == wrong_password.json()


# --- Caso 3 ----------------------------------------------------------------


def test_login_with_unverified_email_is_rejected_and_sends_no_login_code(api):
    form = register(api, verified=False)

    response = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert response.status_code == 403
    assert errors_of(response) == [("email", "email_not_verified")]
    assert [message["purpose"] for message in api.sender.sent] == ["verify_email"]


def test_unverified_email_with_wrong_password_looks_like_any_wrong_password(api):
    form = register(api, verified=False)

    response = api.client.post(LOGIN, json={"email": form["email"], "password": "Ejemplo-2027"})

    assert response.status_code == 401


# --- Caso 4 ----------------------------------------------------------------


def test_asking_for_another_login_code_before_60_seconds_is_rejected(api):
    form = register(api)
    body = {"email": form["email"], "password": PASSWORD}
    assert api.client.post(LOGIN, json=body).status_code == 200

    response = api.client.post(LOGIN, json=body)

    assert response.status_code == 429
    assert errors_of(response) == [("email", "wait")]
    assert response.json()["retry_after"] == 60
    assert response.headers["retry-after"] == "60"


def test_after_60_seconds_a_new_login_code_replaces_the_old_one(api):
    form = register(api)
    body = {"email": form["email"], "password": PASSWORD}
    api.client.post(LOGIN, json=body)
    old_code = api.sender.last_code
    age_codes(api, form["email"], 61)

    assert api.client.post(LOGIN, json=body).status_code == 200
    new_code = api.sender.last_code

    if old_code != new_code:  # uno en un millón: salió el mismo
        old = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": old_code})
        assert old.status_code == 400
    assert api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": new_code}).status_code == 200


def test_more_than_five_login_codes_in_an_hour_is_rejected(api):
    form = register(api)
    body = {"email": form["email"], "password": PASSWORD}
    for _ in range(5):
        assert api.client.post(LOGIN, json=body).status_code == 200
        age_codes(api, form["email"], 61)

    response = api.client.post(LOGIN, json=body)

    assert response.status_code == 429
    assert errors_of(response) == [("email", "hourly_limit")]


@pytest.mark.parametrize(
    "body, fields",
    [
        ({}, ["email", "password"]),
        ({"email": "ana@prueba.invalid"}, ["password"]),
        ({"password": PASSWORD}, ["email"]),
        ({"email": "", "password": ""}, ["email", "password"]),
        ({"email": 5, "password": None}, ["email", "password"]),
    ],
)
def test_login_without_its_data_is_rejected(api, body, fields):
    response = api.client.post(LOGIN, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required") for field in fields]


# ===========================================================================
# POST /auth/login/verify
# ===========================================================================

# --- Caso 5 ----------------------------------------------------------------


def test_right_code_opens_a_session_and_stores_only_the_fingerprint(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    response = api.client.post(
        LOGIN_VERIFY,
        json={"email": form["email"], "code": api.sender.last_code},
        headers={"User-Agent": "Navegador de prueba"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "token_type", "expires_at"}
    assert body["token_type"] == "Bearer"
    token = body["token"]
    assert len(token) >= 40

    row = one(
        api,
        "select token_hash, user_agent, revoked_at, extract(epoch from expires_at - created_at)::int, "
        "last_used_at = created_at from sessions "
        "where user_id = (select id from users where email = %s)",
        form["email"],
    )
    assert row[0] == hash_session_token(token)
    assert row[0] != token and token not in row[0]
    assert row[1:] == ("Navegador de prueba", None, 30 * DAY, True)


def test_session_of_a_host_lasts_7_days(api):
    form = register(api)
    make_host(api, form["email"])

    login(api, form)

    seconds = one(
        api,
        "select extract(epoch from expires_at - created_at)::int from sessions "
        "where user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert seconds == 7 * DAY


def test_very_long_browser_name_is_cut_to_500_characters(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    response = api.client.post(
        LOGIN_VERIFY,
        json={"email": form["email"], "code": api.sender.last_code},
        headers={"User-Agent": "x" * 900},
    )

    assert response.status_code == 200
    assert one(api, "select char_length(user_agent) from sessions where user_id = (select id from users where email = %s)", form["email"])[0] == 500


@pytest.mark.parametrize(
    "address, expected",
    [
        ("203.0.113.7", "203.0.113.7"),
        (" 203.0.113.7 ", "203.0.113.7"),
        ("2001:db8::1", "2001:db8::1"),
        ("testclient", None),
        ("", None),
        (None, None),
        ("999.1.1.1", None),
        ("203.0.113.7; drop table sessions", None),
    ],
)
def test_only_a_real_ip_address_is_stored(address, expected):
    assert clean_ip(address) == expected


# --- Caso 6 ----------------------------------------------------------------


def wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def test_wrong_code_counts_the_attempt_and_opens_no_session(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    response = api.client.post(
        LOGIN_VERIFY, json={"email": form["email"], "code": wrong_code(api.sender.last_code)}
    )

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert response.json()["attempts_left"] == 4
    assert sessions_of(api, form["email"]) == 0


def test_after_five_wrong_codes_the_right_one_no_longer_works(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    code = api.sender.last_code
    for expected_left in (4, 3, 2, 1, 0):
        response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": wrong_code(code)})
        assert response.json()["attempts_left"] == expected_left

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": code})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "too_many_attempts")]
    assert sessions_of(api, form["email"]) == 0


def test_expired_login_code_is_rejected(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    age_codes(api, form["email"], 301)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "code_expired")]
    assert sessions_of(api, form["email"]) == 0


def test_login_code_one_second_before_expiring_still_works(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    age_codes(api, form["email"], 299)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})

    assert response.status_code == 200


def test_the_same_login_code_does_not_open_two_sessions(api):
    form = register(api)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    body = {"email": form["email"], "code": api.sender.last_code}
    assert api.client.post(LOGIN_VERIFY, json=body).status_code == 200

    response = api.client.post(LOGIN_VERIFY, json=body)

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert sessions_of(api, form["email"]) == 1


def test_code_without_the_password_step_opens_nothing(api):
    """Sin el paso de la contraseña no existe ningún código de inicio de sesión."""
    form = register(api)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": "123456"})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert "attempts_left" not in response.json()


def test_login_verify_for_an_email_without_account_looks_like_a_wrong_code(api):
    response = api.client.post(
        LOGIN_VERIFY, json={"email": f"nadie.{uuid4().hex[:8]}@prueba.invalid", "code": "123456"}
    )

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]


@pytest.mark.parametrize(
    "body, fields",
    [({}, ["email", "code"]), ({"email": "ana@prueba.invalid"}, ["code"]), ({"code": 123456, "email": ""}, ["email", "code"])],
)
def test_login_verify_without_its_data_is_rejected(api, body, fields):
    response = api.client.post(LOGIN_VERIFY, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required") for field in fields]


# --- Caso 7 ----------------------------------------------------------------


def test_a_verify_email_code_does_not_open_a_session(api):
    form = register(api, verified=False)
    email_code = api.sender.last_code
    api.client.post(VERIFY_EMAIL, json={"email": form["email"], "code": email_code})
    # Otro código de comprobar correo, vigente, creado a mano para esta prueba.
    with system_transaction(api.pool) as connection:
        user_id = connection.execute("select id from users where email = %s", (form["email"],)).fetchone()[0]
        fresh = create_code(connection, user_id, "verify_email", form["email"], api.settings)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": fresh})

    assert response.status_code == 400
    assert sessions_of(api, form["email"]) == 0


def test_a_login_code_does_not_verify_an_email(api):
    form = register(api, verified=False)
    # Un código de inicio de sesión, creado a mano: una cuenta sin comprobar no puede pedirlo.
    with system_transaction(api.pool) as connection:
        user_id = connection.execute("select id from users where email = %s", (form["email"],)).fetchone()[0]
        connection.execute(
            "update one_time_codes set used_at = now() where user_id = %s", (user_id,)
        )
        login_code = create_code(connection, user_id, "login", form["email"], api.settings)

    response = api.client.post(VERIFY_EMAIL, json={"email": form["email"], "code": login_code})

    assert response.status_code == 400
    assert one(api, "select email_verified_at from users where email = %s", form["email"])[0] is None


# ===========================================================================
# GET /auth/me
# ===========================================================================

# --- Caso 8 ----------------------------------------------------------------


def test_me_with_a_valid_key_returns_the_person(api):
    form = register(api)
    token = login(api, form)

    response = api.client.get(ME, headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id", "first_name", "last_name", "email", "country", "preferred_language", "is_host", "session_expires_at",
    }
    assert (body["first_name"], body["last_name"], body["email"], body["country"]) == (
        "Ana", "Torres", form["email"], "MX",
    )
    assert body["preferred_language"] == "es"
    assert body["is_host"] is False
    assert PASSWORD not in response.text and "argon2" not in response.text


def test_each_use_renews_the_30_days(api):
    form = register(api)
    token = login(api, form)
    # La sesión se abrió hace 29 días y vence mañana.
    run(
        api,
        "update sessions set created_at = now() - interval '29 days', last_used_at = now() - interval '29 days', "
        "expires_at = now() + interval '1 day' where user_id = (select id from users where email = %s)",
        form["email"],
    )

    assert api.client.get(ME, headers=bearer(token)).status_code == 200

    left, used_now = one(
        api,
        "select extract(epoch from expires_at - now())::int, last_used_at = now() from sessions where user_id = (select id from users where email = %s)",
        form["email"],
    )
    assert (left, used_now) == (30 * DAY, True)


def test_a_person_who_becomes_host_gets_the_7_days_from_the_next_use(api):
    form = register(api)
    token = login(api, form)
    make_host(api, form["email"])

    response = api.client.get(ME, headers=bearer(token))

    assert response.json()["is_host"] is True
    assert one(
        api, "select extract(epoch from expires_at - now())::int from sessions where user_id = (select id from users where email = %s)", form["email"]
    )[0] == 7 * DAY


def test_the_authorization_scheme_is_not_case_sensitive(api):
    form = register(api)
    token = login(api, form)

    assert api.client.get(ME, headers={"Authorization": f"bearer {token}"}).status_code == 200


# --- Caso 9 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer llave-inventada"},
        {"Authorization": "Bearer " + "x" * 43},
        {"Authorization": "Bearer " + "x" * 5000},
        {"Authorization": "Token abc"},
        {"Authorization": "Basic YW5hOmNsYXZl"},
        {"Authorization": "Bearer a b"},
        {"Authorization": "Bearer ' or 1=1 --"},
    ],
)
def test_me_without_a_working_key_is_401(api, headers):
    register(api)

    response = api.client.get(ME, headers=headers)

    assert response.status_code == 401
    assert errors_of(response) == [("authorization", "not_authenticated")]
    assert response.headers["www-authenticate"] == "Bearer"


def test_the_stored_fingerprint_does_not_work_as_a_key(api):
    form = register(api)
    token = login(api, form)

    response = api.client.get(ME, headers=bearer(hash_session_token(token)))

    assert response.status_code == 401


def test_expired_session_is_401(api):
    form = register(api)
    token = login(api, form)
    run(
        api,
        "update sessions set created_at = now() - interval '40 days', last_used_at = now() - interval '31 days', "
        "expires_at = now() - interval '1 second' where user_id = (select id from users where email = %s)",
        form["email"],
    )

    response = api.client.get(ME, headers=bearer(token))

    assert response.status_code == 401
    # Una sesión vencida no revive por intentar usarla.
    assert one(api, "select expires_at < now() from sessions where user_id = (select id from users where email = %s)", form["email"])[0] is True


def test_session_one_second_before_expiring_still_works(api):
    form = register(api)
    token = login(api, form)
    run(api, "update sessions set expires_at = now() + interval '1 second' where user_id = (select id from users where email = %s)", form["email"])

    assert api.client.get(ME, headers=bearer(token)).status_code == 200


def test_revoked_session_is_401(api):
    form = register(api)
    token = login(api, form)
    run(api, "update sessions set revoked_at = now() where user_id = (select id from users where email = %s)", form["email"])

    response = api.client.get(ME, headers=bearer(token))

    assert response.status_code == 401


# --- Caso 10 ---------------------------------------------------------------


def test_two_sessions_of_the_same_person_work_at_once(api):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)

    assert phone != computer
    assert sessions_of(api, form["email"]) == 2
    assert api.client.get(ME, headers=bearer(phone)).status_code == 200
    assert api.client.get(ME, headers=bearer(computer)).status_code == 200


def test_each_key_shows_only_its_own_person(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    ana_key = login(api, ana)
    beto_key = login(api, beto)

    as_ana = api.client.get(ME, headers=bearer(ana_key)).json()
    as_beto = api.client.get(ME, headers=bearer(beto_key)).json()

    assert (as_ana["first_name"], as_ana["email"]) == ("Ana", ana["email"])
    assert (as_beto["first_name"], as_beto["email"]) == ("Beto", beto["email"])
    assert as_ana["id"] != as_beto["id"]


def test_revoking_one_session_leaves_the_other_working(api):
    form = register(api)
    phone = login(api, form)
    computer = login(api, form)
    run(api, "update sessions set revoked_at = now() where token_hash = %s", hash_session_token(phone))

    assert api.client.get(ME, headers=bearer(phone)).status_code == 401
    assert api.client.get(ME, headers=bearer(computer)).status_code == 200


# ===========================================================================
# Piezas sueltas, sin base de datos
# ===========================================================================


def test_password_check():
    stored = hash_password(PASSWORD)

    assert verify_password(PASSWORD, stored) is True
    assert verify_password("Ejemplo-2027", stored) is False
    assert verify_password("", stored) is False
    # Sin cuenta: nunca acierta, ni con la contraseña que sea.
    assert verify_password(PASSWORD, None) is False
    # Un valor guardado que no es de Argon2 tampoco acierta ni rompe.
    assert verify_password(PASSWORD, "no-es-un-hash") is False


def test_session_keys_are_long_random_and_different():
    keys = {generate_session_token() for _ in range(200)}

    assert len(keys) == 200
    assert all(len(key) >= 43 for key in keys)


def test_session_fingerprint_has_the_format_the_database_expects():
    fingerprint = hash_session_token("una-llave")

    assert len(fingerprint) == 64 and all(character in "0123456789abcdef" for character in fingerprint)
    assert hash_session_token("una-llave") == fingerprint
    assert hash_session_token("otra-llave") != fingerprint


@pytest.mark.parametrize(
    "header, token",
    [
        ("Bearer abc", "abc"),
        ("bearer abc", "abc"),
        ("BEARER   abc", "abc"),
        ("Bearer", None),
        ("abc", None),
        ("Token abc", None),
        ("Bearer a b", None),
        ("", None),
        (None, None),
    ],
)
def test_reading_the_key_from_the_header(header, token):
    assert bearer_token(header) == token


def test_login_routes_are_documented(api):
    paths = api.client.get("/openapi.json").json()["paths"]

    assert {LOGIN, LOGIN_VERIFY, ME} <= set(paths)
    assert "post" in paths[LOGIN] and "post" in paths[LOGIN_VERIFY] and "get" in paths[ME]
