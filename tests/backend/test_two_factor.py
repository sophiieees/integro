"""Casos de la pieza 3.2, "Authenticator: activarlo y comprobarlo" (las rutas).

Especificación confirmada por Sophia el 24 y 25 de noviembre de 2026 (bitácora 41.11 y 41.12):

    POST /api/v1/auth/2fa/setup
     1. Un anfitrión o un administrador, con su contraseña: 200 con la clave (base32) y su dirección otpauth://. Queda
        una fila en user_totp, pendiente, con la clave cifrada: en la base no está en claro.
     2. Un cliente (ni anfitrión ni administrador): 403. Sin sesión: 401. Sin las defensas: 403.
     3. Contraseña incorrecta: 403 y no se guarda nada; cuenta como intento fallido de entrar (a los 3, aviso al dueño;
        a los 6, ese dispositivo espera).
     4. Volver a empezar mientras está pendiente: la clave nueva reemplaza a la anterior, en la misma fila.
     5. Si ya está activo: 409.
    POST /api/v1/auth/2fa/confirm
     6. Con el código de la aplicación: 200, queda activo y se avisa por correo.
     7. Con un código incorrecto: 400 con los intentos que quedan; sigue pendiente. Al quinto: 429 y 15 minutos de
        espera, también para el código correcto. Pasada la espera, vuelve a tener sus intentos.
     8. Se aceptan el periodo anterior y el siguiente; uno más viejo o más adelantado, no.
     9. Sin haber empezado: 409. Ya activo: 409. Lo que no son 6 números: 422.
    GET /api/v1/auth/2fa
    10. inactive, pending o active (con su fecha). Nunca la clave.
    Lo demás
    11. Sin la llave de cifrado, setup y confirm contestan 503 y la API arranca; el estado sigue respondiendo.
    12. Una clave cifrada movida a la fila de otra persona no se puede comprobar.

No van aquí: pedir el Authenticator al iniciar sesión (3.3), las pantallas (3.4) ni recuperar el acceso (3.6).

Corren contra la base real con rollback_pool: todo se deshace al terminar cada prueba. La llave de cifrado de las
pruebas es inventada: no usan la de backend/.env.
"""

import re

import pytest
from conftest import with_session
from pydantic import SecretStr
from test_accounts_login import ME, PASSWORD, errors_of, login, one, register, run
from test_accounts_logout import OTHER_SITE, change
from test_view_roles import make_admin

from app.core.encryption import decrypt
from app.modules.accounts import two_factor
from app.modules.accounts.totp import code_at, step_at
from app.modules.accounts.two_factor import PURPOSE, associated

SETUP = "/api/v1/auth/2fa/setup"
CONFIRM = "/api/v1/auth/2fa/confirm"
STATUS = "/api/v1/auth/2fa"
HOST_PROFILE = "/api/v1/host-profile"
MIGRATION = "20261124000006_user_totp.sql"
TEST_KEY = "llave-maestra-inventada-para-las-pruebas-0123456789"
# Un instante fijo, a la mitad de un periodo de 30 segundos.
NOW = 1_800_000_015.0


@pytest.fixture(scope="module", autouse=True)
def migration_applied(real_pool):
    """Si la migración no se ha corrido en la base, las pruebas se omiten y lo dicen."""
    with real_pool.connection() as connection:
        ready = connection.execute("select to_regclass('public.user_totp') is not null").fetchone()[0]
    if not ready:
        pytest.skip(f"Falta correr en pgAdmin la migración {MIGRATION} sobre la base integro.")


@pytest.fixture
def tf(api, monkeypatch):
    """La API con una llave de cifrado inventada y el reloj detenido en NOW."""
    settings = api.settings.model_copy(update={"data_encryption_key": SecretStr(TEST_KEY)})
    api.client.app.state.settings = settings
    api.settings = settings
    monkeypatch.setattr(two_factor, "current_time", lambda: NOW)
    return api


def host(api, first_name="Ana"):
    """Una anfitriona con sesión: (formulario, llave de la sesión)."""
    form = register(api, first_name=first_name)
    token = login(api, form)
    assert api.client.post(HOST_PROFILE, headers=change(api, token)).status_code == 201
    api.sender.notices.clear()
    return form, token


def user_id_of(api, email):
    return one(api, "select id from users where email = %s", email)[0]


def row_of(api, email):
    """La fila de user_totp de esa persona, como la ve el sistema, o None."""
    return one(
        api,
        "select t.secret_ciphertext, t.confirmed_at, t.last_used_step, t.failed_attempts, t.locked_until, t.key_version "
        "from user_totp t join users u on u.id = t.user_id where u.email = %s",
        email,
    )


def start(api, token, password=PASSWORD, **extra):
    return api.client.post(SETUP, json={"password": password}, headers=change(api, token, **extra))


def confirm(api, token, code, **extra):
    return api.client.post(CONFIRM, json={"code": code}, headers=change(api, token, **extra))


def state(api, token):
    return api.client.get(STATUS, headers=with_session(token))


def secret_of(response) -> bytes:
    import base64

    return base64.b32decode(response.json()["secret"])


def code_now(secret: bytes, offset: int = 0) -> str:
    return code_at(secret, step_at(NOW) + offset)


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


# --- Caso 1: empezar la activación -----------------------------------------------------------------------------------


def test_a_host_starts_and_gets_the_key_once_in_base32_and_as_an_address(tf):
    form, token = host(tf)

    response = start(tf, token)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "secret", "otpauth_uri", "digits", "period"}
    assert (body["status"], body["digits"], body["period"]) == ("pending", 6, 30)
    assert re.fullmatch(r"[A-Z2-7]{32}", body["secret"])
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert f"secret={body['secret']}" in body["otpauth_uri"]
    assert form["email"].replace("@", "%40") in body["otpauth_uri"]
    assert response.headers["cache-control"] == "no-store"


def test_the_key_is_stored_encrypted_and_pending(tf):
    form, token = host(tf)

    response = start(tf, token)

    ciphertext, confirmed_at, last_used_step, failed_attempts, locked_until, key_version = row_of(tf, form["email"])
    assert (confirmed_at, last_used_step, failed_attempts, locked_until, key_version) == (None, None, 0, None, 1)
    # En la base no está la clave en claro, ni como texto ni como bytes.
    assert response.json()["secret"] not in ciphertext
    assert len(ciphertext) == 64
    stored = decrypt(TEST_KEY, PURPOSE, ciphertext, associated(user_id_of(tf, form["email"])))
    assert stored == secret_of(response)


def test_an_administrator_who_is_not_a_host_can_start_too(tf):
    form = register(tf)
    token = login(tf, form)
    make_admin(tf, form["email"])

    assert start(tf, token).status_code == 200


# --- Caso 2: quién no puede ------------------------------------------------------------------------------------------


def test_a_plain_client_is_refused_and_nothing_is_stored(tf):
    form = register(tf)
    token = login(tf, form)

    started = start(tf, token)
    confirmed = confirm(tf, token, "123456")

    assert started.status_code == 403 and confirmed.status_code == 403
    assert errors_of(started) == errors_of(confirmed) == [("request", "two_factor_not_allowed")]
    assert row_of(tf, form["email"]) is None


def test_without_a_session_the_three_routes_say_401(tf):
    origin = {"Origin": "http://testserver"}

    assert tf.client.post(SETUP, json={"password": PASSWORD}, headers=origin).status_code == 401
    assert tf.client.post(CONFIRM, json={"code": "123456"}, headers=origin).status_code == 401
    assert tf.client.get(STATUS).status_code == 401


@pytest.mark.parametrize(
    "extra,code",
    [({"Origin": None}, "origin_not_allowed"), ({"Origin": OTHER_SITE}, "origin_not_allowed"), ({"X-CSRF-Token": None}, "csrf_failed")],
)
def test_without_the_defenses_nothing_is_started_or_confirmed(tf, extra, code):
    form, token = host(tf)

    started = start(tf, token, **extra)

    assert started.status_code == 403
    assert errors_of(started) == [("request", code)]
    assert row_of(tf, form["email"]) is None

    secret = secret_of(start(tf, token))
    confirmed = confirm(tf, token, code_now(secret), **extra)
    assert confirmed.status_code == 403
    assert row_of(tf, form["email"])[1] is None


# --- Caso 3: la contraseña -------------------------------------------------------------------------------------------


def test_a_wrong_password_is_refused_and_nothing_is_stored(tf):
    form, token = host(tf)

    response = start(tf, token, password="Otra-contrasena-1!")

    assert response.status_code == 403
    assert response.json() == {"errors": [{"field": "password", "code": "invalid_password", "message": "La contraseña no es correcta."}]}
    assert row_of(tf, form["email"]) is None


@pytest.mark.parametrize("body", [{}, {"password": ""}, {"password": None}, {"password": 12345}])
def test_starting_without_a_password_is_rejected(tf, body):
    form, token = host(tf)

    response = tf.client.post(SETUP, json=body, headers=change(tf, token))

    assert response.status_code == 422
    assert errors_of(response) == [("password", "required")]
    assert row_of(tf, form["email"]) is None


def test_a_wrong_password_counts_as_a_failed_attempt_to_get_in(tf):
    form, token = host(tf)
    before = one(tf, "select count(*) from login_attempts where not succeeded and user_id = %s", user_id_of(tf, form["email"]))[0]

    start(tf, token, password="Otra-contrasena-1!")

    after = one(tf, "select count(*) from login_attempts where not succeeded and user_id = %s", user_id_of(tf, form["email"]))[0]
    assert after == before + 1


def test_three_wrong_passwords_warn_the_owner_by_email(tf):
    form, token = host(tf)

    for attempt in range(3):
        assert start(tf, token, password=f"Equivocada-{attempt}-clave!").status_code == 403

    assert [notice["kind"] for notice in tf.sender.notices] == ["failed_logins"]
    assert tf.sender.notices[0]["destination"] == form["email"]
    assert tf.sender.notices[0]["details"]["failures"] == 3


def test_six_wrong_passwords_make_that_device_wait_even_with_the_right_one(tf):
    form, token = host(tf)
    for attempt in range(6):
        assert start(tf, token, password=f"Equivocada-{attempt}-clave!").status_code == 403

    response = start(tf, token)

    assert response.status_code == 429
    assert errors_of(response) == [("credentials", "try_later")]
    assert int(response.headers["retry-after"]) > 0
    assert row_of(tf, form["email"]) is None


# --- Caso 4: volver a empezar ----------------------------------------------------------------------------------------


def test_starting_again_while_pending_replaces_the_key_in_the_same_row(tf):
    form, token = host(tf)
    first = secret_of(start(tf, token))

    second = secret_of(start(tf, token))

    assert second != first
    assert one(tf, "select count(*) from user_totp where user_id = %s", user_id_of(tf, form["email"]))[0] == 1
    # La clave anterior ya no sirve; la nueva sí.
    assert confirm(tf, token, code_now(first)).status_code == 400
    assert confirm(tf, token, code_now(second)).status_code == 200


def test_starting_again_gives_back_all_the_attempts(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    confirm(tf, token, wrong(code_now(secret)))
    assert row_of(tf, form["email"])[3] == 1

    start(tf, token)

    assert row_of(tf, form["email"])[3] == 0


# --- Casos 5 y 6: comprobar ------------------------------------------------------------------------------------------


def test_the_code_of_the_app_activates_it(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))

    response = confirm(tf, token, code_now(secret))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "activated_at"}
    assert body["status"] == "active"
    ciphertext, confirmed_at, last_used_step, failed_attempts, locked_until, _ = row_of(tf, form["email"])
    assert confirmed_at is not None
    assert last_used_step == step_at(NOW)
    assert (failed_attempts, locked_until) == (0, None)


def test_the_code_may_be_written_with_the_space_the_app_shows(tf):
    form, token = host(tf)
    code = code_now(secret_of(start(tf, token)))

    assert confirm(tf, token, f" {code[:3]} {code[3:]} ").status_code == 200


def test_activating_it_warns_the_owner_by_email_without_the_key_or_the_code(tf):
    form, token = host(tf)
    started = start(tf, token)
    code = code_now(secret_of(started))

    confirm(tf, token, code)

    assert [notice["kind"] for notice in tf.sender.notices] == ["two_factor_enabled"]
    notice = tf.sender.notices[0]
    assert (notice["channel"], notice["destination"]) == ("email", form["email"])
    assert set(notice["details"]) == {"at", "ip_address", "user_agent"}
    assert started.json()["secret"] not in str(notice) and code not in str(notice)
    assert tf.sender.sent[-1]["purpose"] != "two_factor"


def test_once_active_it_cannot_be_started_or_confirmed_again(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    confirm(tf, token, code_now(secret))
    stored = row_of(tf, form["email"])[0]

    started = start(tf, token)
    confirmed = confirm(tf, token, code_now(secret, 1))

    assert started.status_code == 409 and confirmed.status_code == 409
    assert errors_of(started) == errors_of(confirmed) == [("two_factor", "two_factor_already_active")]
    assert "secret" not in started.json()
    assert row_of(tf, form["email"])[0] == stored


def test_confirming_before_starting_says_so(tf):
    form, token = host(tf)

    response = confirm(tf, token, "123456")

    assert response.status_code == 409
    assert errors_of(response) == [("two_factor", "two_factor_not_started")]


@pytest.mark.parametrize("body,code", [
    ({}, "required"), ({"code": ""}, "required"), ({"code": "   "}, "required"), ({"code": None}, "required"),
    ({"code": 123456}, "required"), ({"code": "12345"}, "invalid_format"), ({"code": "1234567"}, "invalid_format"),
    ({"code": "abcdef"}, "invalid_format"), ({"code": "12-456"}, "invalid_format"),
])
def test_what_is_not_six_numbers_is_rejected_without_spending_an_attempt(tf, body, code):
    form, token = host(tf)
    start(tf, token)

    response = tf.client.post(CONFIRM, json=body, headers=change(tf, token))

    assert response.status_code == 422
    assert errors_of(response) == [("code", code)]
    assert row_of(tf, form["email"])[3] == 0


# --- Caso 7: códigos incorrectos -------------------------------------------------------------------------------------


def test_a_wrong_code_says_how_many_attempts_are_left_and_it_stays_pending(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))

    response = confirm(tf, token, wrong(code_now(secret)))

    assert response.status_code == 400
    assert response.json() == {
        "errors": [{"field": "code", "code": "invalid_code", "message": "El código no es correcto."}], "attempts_left": 4,
    }
    assert state(tf, token).json()["status"] == "pending"
    assert tf.sender.notices == []


def test_the_fifth_wrong_code_starts_a_fifteen_minute_wait_even_for_the_right_code(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    bad = wrong(code_now(secret))

    answers = [confirm(tf, token, bad) for _ in range(5)]

    assert [answer.status_code for answer in answers] == [400, 400, 400, 400, 429]
    assert [answer.json().get("attempts_left") for answer in answers[:4]] == [4, 3, 2, 1]
    assert errors_of(answers[4]) == [("credentials", "try_later")]
    assert answers[4].headers["retry-after"] == "900"

    waiting = confirm(tf, token, code_now(secret))
    assert waiting.status_code == 429
    assert 0 < int(waiting.headers["retry-after"]) <= 900
    assert state(tf, token).json()["status"] == "pending"


def test_after_the_wait_the_person_has_all_the_attempts_again(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    bad = wrong(code_now(secret))
    for _ in range(5):
        confirm(tf, token, bad)
    run(tf, "update user_totp set locked_until = now() - interval '1 second' where user_id = %s", user_id_of(tf, form["email"]))

    again = confirm(tf, token, bad)
    right = confirm(tf, token, code_now(secret))

    assert again.status_code == 400 and again.json()["attempts_left"] == 4
    assert right.status_code == 200


def test_a_right_code_after_some_wrong_ones_activates_it(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    for _ in range(4):
        confirm(tf, token, wrong(code_now(secret)))

    assert confirm(tf, token, code_now(secret)).status_code == 200
    assert row_of(tf, form["email"])[3] == 0


def test_the_attempts_and_the_wait_come_from_the_configuration(tf):
    settings = tf.settings.model_copy(update={"two_factor_max_attempts": 2, "two_factor_wait_minutes": 30})
    tf.client.app.state.settings = settings
    form, token = host(tf)
    bad = wrong(code_now(secret_of(start(tf, token))))

    answers = [confirm(tf, token, bad) for _ in range(2)]

    assert [answer.status_code for answer in answers] == [400, 429]
    assert answers[0].json()["attempts_left"] == 1
    assert answers[1].headers["retry-after"] == "1800"


# --- Caso 8: el reloj ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_previous_the_current_and_the_next_period_are_accepted(tf, offset):
    form, token = host(tf)
    secret = secret_of(start(tf, token))

    response = confirm(tf, token, code_now(secret, offset))

    assert response.status_code == 200
    assert row_of(tf, form["email"])[2] == step_at(NOW) + offset


@pytest.mark.parametrize("offset", [-2, 2, -10, 10])
def test_an_older_or_a_later_period_is_refused(tf, offset):
    form, token = host(tf)
    secret = secret_of(start(tf, token))

    assert confirm(tf, token, code_now(secret, offset)).status_code == 400


def test_the_code_of_someone_else_does_not_work(tf):
    form, token = host(tf)
    other_form, other_token = host(tf, first_name="Beatriz")
    start(tf, token)
    other_secret = secret_of(start(tf, other_token))

    assert confirm(tf, token, code_now(other_secret)).status_code == 400
    assert state(tf, token).json()["status"] == "pending"


# --- Caso 10: el estado ----------------------------------------------------------------------------------------------


def test_the_status_goes_from_inactive_to_pending_to_active_and_never_shows_the_key(tf):
    form, token = host(tf)
    first = state(tf, token)
    started = start(tf, token)
    second = state(tf, token)
    confirm(tf, token, code_now(secret_of(started)))
    third = state(tf, token)

    assert first.json() == {"status": "inactive", "activated_at": None}
    assert second.json() == {"status": "pending", "activated_at": None}
    assert third.json()["status"] == "active" and third.json()["activated_at"] is not None
    for response in (first, second, third):
        assert response.status_code == 200
        assert set(response.json()) == {"status", "activated_at"}
        assert started.json()["secret"] not in response.text


def test_a_client_can_ask_and_is_told_inactive(tf):
    form = register(tf)
    token = login(tf, form)

    response = state(tf, token)

    assert response.status_code == 200
    assert response.json() == {"status": "inactive", "activated_at": None}


def test_each_person_sees_only_their_own_status(tf):
    form, token = host(tf)
    other_form, other_token = host(tf, first_name="Beatriz")
    confirm(tf, token, code_now(secret_of(start(tf, token))))

    assert state(tf, token).json()["status"] == "active"
    assert state(tf, other_token).json()["status"] == "inactive"


def test_me_does_not_carry_the_key(tf):
    form, token = host(tf)
    started = start(tf, token)

    assert started.json()["secret"] not in tf.client.get(ME, headers=with_session(token)).text


# --- Caso 11: sin la llave de cifrado --------------------------------------------------------------------------------


def test_without_the_master_key_setup_and_confirm_say_503_and_the_status_still_answers(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    tf.client.app.state.settings = tf.settings.model_copy(update={"data_encryption_key": None})

    started = start(tf, token)
    confirmed = confirm(tf, token, code_now(secret))

    assert started.status_code == 503 and confirmed.status_code == 503
    assert errors_of(started) == errors_of(confirmed) == [("two_factor", "two_factor_unavailable")]
    assert state(tf, token).json()["status"] == "pending"
    assert tf.client.get("/api/v1/health").status_code == 200
    # Sin llave ni siquiera se revisa la contraseña ni se gasta un intento.
    assert row_of(tf, form["email"])[3] == 0


def test_without_the_master_key_nothing_is_ever_stored_in_clear(tf):
    form, token = host(tf)
    tf.client.app.state.settings = tf.settings.model_copy(update={"data_encryption_key": None})

    assert start(tf, token).status_code == 503
    assert row_of(tf, form["email"]) is None


def test_with_another_master_key_what_was_stored_cannot_be_confirmed(tf):
    form, token = host(tf)
    secret = secret_of(start(tf, token))
    other = SecretStr("otra-llave-maestra-inventada-para-pruebas-987654321")
    tf.client.app.state.settings = tf.settings.model_copy(update={"data_encryption_key": other})

    response = confirm(tf, token, code_now(secret))

    assert response.status_code == 503
    assert row_of(tf, form["email"])[1] is None


# --- Caso 12: una clave movida a otra persona ------------------------------------------------------------------------


def test_a_key_moved_to_the_row_of_another_person_cannot_be_confirmed(tf):
    form, token = host(tf)
    other_form, other_token = host(tf, first_name="Beatriz")
    secret = secret_of(start(tf, token))
    start(tf, other_token)
    # Alguien con acceso a la base copia la clave cifrada de Ana a la fila de Beatriz.
    run(
        tf,
        "update user_totp set secret_ciphertext = (select secret_ciphertext from user_totp where user_id = %s) where user_id = %s",
        user_id_of(tf, form["email"]), user_id_of(tf, other_form["email"]),
    )

    response = confirm(tf, other_token, code_now(secret))

    assert response.status_code == 503
    assert state(tf, other_token).json()["status"] == "pending"
    # La de Ana sigue sirviendo.
    assert confirm(tf, token, code_now(secret)).status_code == 200


# --- La documentación de la API --------------------------------------------------------------------------------------


def test_the_api_documentation_lists_the_three_routes(tf):
    paths = tf.client.get("/openapi.json").json()["paths"]

    assert set(paths[SETUP]) == {"post"} and set(paths[CONFIRM]) == {"post"} and set(paths[STATUS]) == {"get"}
    assert {"200", "401", "403", "409", "422", "429", "503"} <= set(paths[SETUP]["post"]["responses"])
    assert {"200", "400", "401", "403", "409", "422", "429", "503"} <= set(paths[CONFIRM]["post"]["responses"])
