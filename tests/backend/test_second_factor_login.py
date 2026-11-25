"""Casos de la pieza 3.3, "pedir el Authenticator al iniciar sesión".

Especificación confirmada por Sophia el 25 de noviembre de 2026 (bitácora 41.12 y 42.4, con todas las recomendaciones
aceptadas):

     1. Con el Authenticator activo, la sesión se abre con el código del correo pero queda en espera: /auth/me y toda
        ruta con sesión responden 403 con second_factor_required, sin ningún dato. Tras POST /auth/2fa/verify con el
        código correcto, la sesión sirve.
     2. Sin el Authenticator activo, iniciar sesión funciona igual que antes.
     3. Código incorrecto: 400 y la sesión sigue en espera. Al quinto: 429, 15 minutos de espera y aviso por correo.
     4. El mismo código no se acepta dos veces.
     5. A los 30 días la misma sesión vuelve a pedirlo; a los 29, no. Cada inicio de sesión nuevo lo pide siempre.
     6. Cerrar sesión funciona aunque la sesión esté en espera.
     7. Al activar el Authenticator, la sesión con la que se activó ya lo pasó; las otras sesiones de la persona quedan
        en espera.
     8. Un anfitrión o un administrador sin el Authenticator activo entra y usa lo de cliente (las rutas de anfitrión
        y de administrador se prueban en test_view_roles.py).

No van aquí: las pantallas ni recuperar el acceso (pieza 3.6).

Corren contra la base real con rollback_pool: todo se deshace al terminar cada prueba. La llave de cifrado de las
pruebas es inventada.
"""

import pytest
from conftest import session_cookie, with_session
from pydantic import SecretStr
from test_accounts_login import LOGIN, LOGIN_VERIFY, ME, PASSWORD, age_codes, errors_of, login, one, register, run
from test_accounts_logout import LOGOUT, SESSIONS, change
from test_two_factor import CONFIRM, HOST_PROFILE, SETUP, STATUS, TEST_KEY, secret_of
from test_view_roles import make_admin

from app.modules.accounts import two_factor
from app.modules.accounts.security import hash_session_token
from app.modules.accounts.totp import code_at, step_at

VERIFY = "/api/v1/auth/2fa/verify"
MIGRATION = "20261125000007_session_second_factor.sql"
START = 1_800_000_015.0
PENDING = {
    "field": "second_factor", "code": "second_factor_required",
    "message": "Escribe el código de tu Authenticator para continuar.",
}


@pytest.fixture(scope="module", autouse=True)
def migration_applied(real_pool):
    """Si las migraciones no se han corrido en la base, las pruebas se omiten y lo dicen."""
    with real_pool.connection() as connection:
        ready = connection.execute(
            # pg_attribute y no information_schema: esa vista solo enseña lo que el usuario de conexión puede leer.
            "select to_regclass('public.user_totp') is not null and exists (select 1 from pg_attribute "
            "where attrelid = to_regclass('public.sessions') and attname = 'second_factor_at' and not attisdropped)"
        ).fetchone()[0]
    if not ready:
        pytest.skip(f"Falta correr en pgAdmin la migración {MIGRATION} sobre la base integro.")


class Clock:
    """El reloj del servidor para los códigos: la prueba lo adelanta de periodo en periodo."""

    def __init__(self):
        self.now = START

    def advance(self, periods: int = 1) -> None:
        self.now += 30 * periods

    def code(self, secret: bytes, offset: int = 0) -> str:
        return code_at(secret, step_at(self.now) + offset)


@pytest.fixture
def sf(api, monkeypatch):
    """La API con una llave de cifrado inventada y un reloj que la prueba controla."""
    settings = api.settings.model_copy(update={"data_encryption_key": SecretStr(TEST_KEY)})
    api.client.app.state.settings = settings
    api.settings = settings
    api.clock = Clock()
    monkeypatch.setattr(two_factor, "current_time", lambda: api.clock.now)
    return api


def enrolled(api, first_name="Ana", admin=False):
    """Una persona con el Authenticator ya activo: (formulario, clave). Su sesión de activación queda cerrada."""
    form = register(api, first_name=first_name)
    token = login(api, form)
    if admin:
        make_admin(api, form["email"])
    else:
        assert api.client.post(HOST_PROFILE, headers=change(api, token)).status_code == 201
    started = api.client.post(SETUP, json={"password": PASSWORD}, headers=change(api, token))
    assert started.status_code == 200, started.text
    secret = secret_of(started)
    assert api.client.post(CONFIRM, json={"code": api.clock.code(secret)}, headers=change(api, token)).status_code == 200
    assert api.client.post(LOGOUT, headers=change(api, token)).status_code == 200
    api.sender.notices.clear()
    # El código de la activación ya se usó: el siguiente inicio de sesión necesita el del periodo que sigue.
    api.clock.advance()
    return form, secret


def sign_in(api, form):
    """Los dos primeros pasos del inicio de sesión: (respuesta del segundo paso, llave de la sesión)."""
    age_codes(api, form["email"], 61)
    assert api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD}).status_code == 200
    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})
    assert response.status_code == 200, response.text
    token = session_cookie(response).value
    api.client.cookies.clear()
    return response, token


def verify(api, token, code, **extra):
    return api.client.post(VERIFY, json={"code": code}, headers=change(api, token, **extra))


def me(api, token):
    return api.client.get(ME, headers=with_session(token))


def second_factor_at(api, token):
    return one(api, "select second_factor_at from sessions where token_hash = %s", hash_session_token(token))[0]


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


# --- Caso 1: la sesión nace en espera --------------------------------------------------------------------------------


def test_the_second_step_of_signing_in_says_the_authenticator_is_still_missing(sf):
    form, secret = enrolled(sf)

    response, token = sign_in(sf, form)

    body = response.json()
    assert body["status"] == "session_opened"
    assert body["second_factor_required"] is True
    assert set(body) == {"status", "expires_at", "csrf_token", "second_factor_required"}
    assert second_factor_at(sf, token) is None


def test_while_waiting_me_says_403_and_gives_no_data_only_the_page_key(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    response = me(sf, token)

    assert response.status_code == 403
    body = response.json()
    assert set(body) == {"errors", "csrf_token"}
    assert body["errors"] == [PENDING]
    assert response.headers["cache-control"] == "no-store"
    for private in (form["email"], form["first_name"], form["last_name"], "is_host", "first_name"):
        assert private not in response.text
    # La clave de la página es la de esta sesión: sirve para mandar el código.
    assert verify(sf, token, sf.clock.code(secret), **{"X-CSRF-Token": body["csrf_token"]}).status_code == 200


@pytest.mark.parametrize(
    "method,path,changes",
    [
        ("GET", SESSIONS, False),
        ("GET", HOST_PROFILE, False),
        ("GET", STATUS, False),
        ("POST", HOST_PROFILE, True),
        ("POST", SETUP, True),
        ("POST", CONFIRM, True),
        ("POST", "/api/v1/auth/sessions/close-others", True),
    ],
)
def test_while_waiting_every_other_route_with_a_session_says_403_and_nothing_else(sf, method, path, changes):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    headers = change(sf, token) if changes else with_session(token)

    response = sf.client.request(method, path, headers=headers, json={"password": PASSWORD, "code": "123456"} if changes else None)

    assert response.status_code == 403
    assert response.json() == {"errors": [PENDING]}
    assert form["email"] not in response.text


def test_the_right_code_completes_the_session(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    response = verify(sf, token, sf.clock.code(secret))

    assert response.status_code == 200
    assert set(response.json()) == {"status", "verified_at"}
    assert response.json()["status"] == "verified"
    assert second_factor_at(sf, token) is not None
    profile = me(sf, token)
    assert profile.status_code == 200
    assert profile.json()["email"] == form["email"] and profile.json()["is_host"] is True
    assert sf.client.get(STATUS, headers=with_session(token)).json()["status"] == "active"


def test_the_code_may_be_written_with_the_space_the_app_shows(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    code = sf.clock.code(secret)

    assert verify(sf, token, f"{code[:3]} {code[3:]}").status_code == 200


def test_an_administrator_with_the_authenticator_goes_through_the_same_step(sf):
    form, secret = enrolled(sf, admin=True)
    response, token = sign_in(sf, form)
    assert response.json()["second_factor_required"] is True
    assert me(sf, token).status_code == 403

    assert verify(sf, token, sf.clock.code(secret)).status_code == 200

    assert me(sf, token).json()["is_admin"] is True


# --- Caso 2: sin el Authenticator activo -----------------------------------------------------------------------------


def test_without_the_authenticator_signing_in_is_what_it_always_was(sf):
    form = register(sf)

    response, token = sign_in(sf, form)

    assert set(response.json()) == {"status", "expires_at", "csrf_token"}
    assert me(sf, token).status_code == 200


def test_there_is_nothing_to_verify_without_an_active_authenticator(sf):
    form = register(sf)
    _, token = sign_in(sf, form)

    response = verify(sf, token, "123456")

    assert response.status_code == 409
    assert errors_of(response) == [("two_factor", "two_factor_not_active")]
    assert me(sf, token).status_code == 200


def test_an_authenticator_that_is_only_pending_does_not_put_sessions_on_hold(sf):
    form = register(sf)
    token = login(sf, form)
    sf.client.post(HOST_PROFILE, headers=change(sf, token))
    assert sf.client.post(SETUP, json={"password": PASSWORD}, headers=change(sf, token)).status_code == 200

    response, other = sign_in(sf, form)

    assert "second_factor_required" not in response.json()
    assert me(sf, other).status_code == 200 and me(sf, token).status_code == 200


def test_a_host_without_the_authenticator_gets_in_and_uses_what_a_client_uses(sf):
    form = register(sf)
    token = login(sf, form)
    assert sf.client.post(HOST_PROFILE, headers=change(sf, token)).status_code == 201

    assert me(sf, token).json()["is_host"] is True
    assert sf.client.get(HOST_PROFILE, headers=with_session(token)).status_code == 200
    assert sf.client.get(STATUS, headers=with_session(token)).json()["status"] == "inactive"
    assert sf.client.post(SETUP, json={"password": PASSWORD}, headers=change(sf, token)).status_code == 200


# --- Caso 3: códigos incorrectos -------------------------------------------------------------------------------------


def test_a_wrong_code_says_how_many_attempts_are_left_and_the_session_keeps_waiting(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    response = verify(sf, token, wrong(sf.clock.code(secret)))

    assert response.status_code == 400
    assert response.json() == {
        "errors": [{"field": "code", "code": "invalid_code", "message": "El código no es correcto."}], "attempts_left": 4,
    }
    assert me(sf, token).status_code == 403
    assert second_factor_at(sf, token) is None
    assert sf.sender.notices == []


def test_the_fifth_wrong_code_starts_the_wait_and_warns_the_owner_by_email(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    bad = wrong(sf.clock.code(secret))

    answers = [verify(sf, token, bad) for _ in range(5)]

    assert [answer.status_code for answer in answers] == [400, 400, 400, 400, 429]
    assert answers[4].headers["retry-after"] == "900"
    assert errors_of(answers[4]) == [("credentials", "try_later")]
    assert [notice["kind"] for notice in sf.sender.notices] == ["two_factor_locked"]
    notice = sf.sender.notices[0]
    assert (notice["channel"], notice["destination"]) == ("email", form["email"])
    assert set(notice["details"]) == {"failures", "at", "ip_address", "user_agent"}
    assert notice["details"]["failures"] == 5

    waiting = verify(sf, token, sf.clock.code(secret))
    assert waiting.status_code == 429
    assert me(sf, token).status_code == 403
    # El aviso sale una vez, cuando empieza la espera; no en cada intento durante la espera.
    assert len(sf.sender.notices) == 1


def test_after_the_wait_the_right_code_works(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    for _ in range(5):
        verify(sf, token, wrong(sf.clock.code(secret)))
    run(sf, "update user_totp set locked_until = now() - interval '1 second' where user_id = (select id from users where email = %s)", form["email"])

    assert verify(sf, token, sf.clock.code(secret)).status_code == 200
    assert me(sf, token).status_code == 200


def test_the_attempts_belong_to_the_person_so_another_session_does_not_reset_them(sf):
    form, secret = enrolled(sf)
    _, first = sign_in(sf, form)
    _, second = sign_in(sf, form)
    bad = wrong(sf.clock.code(secret))

    answers = [verify(sf, first, bad) for _ in range(3)] + [verify(sf, second, bad) for _ in range(2)]

    assert [answer.status_code for answer in answers] == [400, 400, 400, 400, 429]
    assert answers[3].json()["attempts_left"] == 1


@pytest.mark.parametrize("body,code", [
    ({}, "required"), ({"code": ""}, "required"), ({"code": None}, "required"), ({"code": 123456}, "required"),
    ({"code": "12345"}, "invalid_format"), ({"code": "1234567"}, "invalid_format"), ({"code": "abcdef"}, "invalid_format"),
])
def test_what_is_not_six_numbers_is_rejected_without_spending_an_attempt(sf, body, code):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    response = sf.client.post(VERIFY, json=body, headers=change(sf, token))

    assert response.status_code == 422
    assert errors_of(response) == [("code", code)]
    assert verify(sf, token, wrong(sf.clock.code(secret))).json()["attempts_left"] == 4


# --- Caso 4: un código no sirve dos veces ----------------------------------------------------------------------------


def test_the_code_that_activated_it_cannot_open_the_next_session(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    used = verify(sf, token, sf.clock.code(secret, -1))

    assert used.status_code == 400
    assert me(sf, token).status_code == 403


def test_the_same_code_cannot_complete_two_sessions(sf):
    form, secret = enrolled(sf)
    _, first = sign_in(sf, form)
    _, second = sign_in(sf, form)
    code = sf.clock.code(secret)

    assert verify(sf, first, code).status_code == 200
    again = verify(sf, second, code)

    assert again.status_code == 400
    assert me(sf, second).status_code == 403
    sf.clock.advance()
    assert verify(sf, second, sf.clock.code(secret)).status_code == 200


def test_the_code_of_another_person_does_not_work(sf):
    form, secret = enrolled(sf)
    other_form, other_secret = enrolled(sf, first_name="Beatriz")
    _, token = sign_in(sf, form)

    assert verify(sf, token, sf.clock.code(other_secret)).status_code == 400
    assert me(sf, token).status_code == 403


# --- Caso 5: los 30 días ---------------------------------------------------------------------------------------------


def age_verification(api, token, days, hours=0):
    """Hace que la sesión parezca abierta y pasada por el Authenticator hace tantos días."""
    run(
        api,
        "update sessions set created_at = now() - make_interval(days => %s, hours => %s + 1), "
        "second_factor_at = now() - make_interval(days => %s, hours => %s) where token_hash = %s",
        days, hours, days, hours, hash_session_token(token),
    )


def test_thirty_days_later_the_same_session_asks_again(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    assert verify(sf, token, sf.clock.code(secret)).status_code == 200

    age_verification(sf, token, 30)

    response = me(sf, token)
    assert response.status_code == 403
    assert response.json()["errors"] == [PENDING]
    sf.clock.advance()
    assert verify(sf, token, sf.clock.code(secret)).status_code == 200
    assert me(sf, token).status_code == 200


def test_at_twenty_nine_days_it_does_not_ask_yet(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    verify(sf, token, sf.clock.code(secret))

    age_verification(sf, token, 29, hours=23)

    assert me(sf, token).status_code == 200


def test_the_number_of_days_comes_from_the_configuration(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    verify(sf, token, sf.clock.code(secret))
    age_verification(sf, token, 8)
    assert me(sf, token).status_code == 200

    sf.client.app.state.settings = sf.settings.model_copy(update={"two_factor_reverify_days": 7})

    assert me(sf, token).status_code == 403


def test_every_new_sign_in_asks_even_if_another_session_passed_it_today(sf):
    form, secret = enrolled(sf)
    _, first = sign_in(sf, form)
    assert verify(sf, first, sf.clock.code(secret)).status_code == 200

    response, second = sign_in(sf, form)

    assert response.json()["second_factor_required"] is True
    assert me(sf, second).status_code == 403 and me(sf, first).status_code == 200


def test_a_session_that_already_passed_can_pass_again_and_the_date_moves(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    verify(sf, token, sf.clock.code(secret))
    age_verification(sf, token, 10)
    before = second_factor_at(sf, token)
    sf.clock.advance()

    assert verify(sf, token, sf.clock.code(secret)).status_code == 200
    assert second_factor_at(sf, token) > before


# --- Caso 6: cerrar sesión -------------------------------------------------------------------------------------------


def test_signing_out_works_while_the_session_is_waiting(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)

    response = sf.client.post(LOGOUT, headers=change(sf, token))

    assert response.status_code == 200
    assert response.json() == {"status": "signed_out"}
    assert me(sf, token).status_code == 401


# --- Caso 7: al activarlo --------------------------------------------------------------------------------------------


def test_the_session_that_activates_it_has_already_passed_and_the_other_sessions_wait(sf):
    form = register(sf)
    here = login(sf, form)
    _, elsewhere = sign_in(sf, form)
    sf.client.post(HOST_PROFILE, headers=change(sf, here))
    secret = secret_of(sf.client.post(SETUP, json={"password": PASSWORD}, headers=change(sf, here)))

    assert sf.client.post(CONFIRM, json={"code": sf.clock.code(secret)}, headers=change(sf, here)).status_code == 200

    assert second_factor_at(sf, here) is not None
    assert me(sf, here).status_code == 200
    assert second_factor_at(sf, elsewhere) is None
    assert me(sf, elsewhere).status_code == 403


# --- Las defensas y lo que falta -------------------------------------------------------------------------------------


def test_writing_the_code_needs_a_session_and_the_defenses(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    code = sf.clock.code(secret)

    assert sf.client.post(VERIFY, json={"code": code}, headers={"Origin": "http://testserver"}).status_code == 401
    assert errors_of(verify(sf, token, code, Origin=None)) == [("request", "origin_not_allowed")]
    assert errors_of(verify(sf, token, code, **{"X-CSRF-Token": None})) == [("request", "csrf_failed")]
    assert me(sf, token).status_code == 403
    # Ninguno de esos intentos gastó el código ni un intento.
    assert verify(sf, token, code).status_code == 200


def test_without_the_master_key_the_code_cannot_be_checked_and_the_session_keeps_waiting(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    sf.client.app.state.settings = sf.settings.model_copy(update={"data_encryption_key": None})

    response = verify(sf, token, sf.clock.code(secret))

    assert response.status_code == 503
    assert errors_of(response) == [("two_factor", "two_factor_unavailable")]
    assert me(sf, token).status_code == 403


def test_a_closed_session_cannot_be_completed(sf):
    form, secret = enrolled(sf)
    _, token = sign_in(sf, form)
    sf.client.post(LOGOUT, headers=change(sf, token))

    assert verify(sf, token, sf.clock.code(secret)).status_code == 401


def test_the_api_documentation_lists_the_new_route(sf):
    paths = sf.client.get("/openapi.json").json()["paths"]

    assert set(paths[VERIFY]) == {"post"}
    assert {"200", "400", "401", "403", "409", "422", "429", "503"} <= set(paths[VERIFY]["post"]["responses"])
