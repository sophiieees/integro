"""Casos de la pieza "recuperar la contraseña con un código de 6 dígitos".

Decisiones de Sophia del 21 de noviembre de 2026: el código es de 6 dígitos y no un enlace, dura 30 minutos, y
solo una cuenta con el correo comprobado puede recuperar la contraseña.

    POST /api/v1/auth/password-reset/request   (correo)
     1. Cuenta comprobada: 200 y llega un código de 6 dígitos al correo, que vence a los 30 minutos. En la base solo
        queda su huella.
     2. Correo sin cuenta, o cuenta sin comprobar: 200 con exactamente la misma respuesta; no se envía nada.
     3. Antes de 60 segundos del envío anterior, o con 5 códigos en la última hora: 200 igual y no se envía otro
        (no se revela nada con un 429). Pasado el minuto, el código nuevo deja sin efecto al anterior.
     4. Sin correo: 422.

    POST /api/v1/auth/password-reset/confirm   (correo, código y contraseña nueva)
     5. Código correcto y contraseña buena: 200; la contraseña cambia (Argon2id), la vieja deja de servir y la
        nueva sirve para iniciar sesión (con su código, como siempre). El código queda gastado.
     6. Se cierran todas las sesiones de esa cuenta; las de otras cuentas no se tocan.
     7. Código incorrecto: 400 con los intentos que quedan; a los 5 intentos el código se bloquea aunque después
        se escriba el correcto. Código vencido: 400. Nada cambia.
     8. Contraseña débil (le faltan reglas, o cumple las reglas pero es fácil de adivinar, como en el registro): 422;
        no gasta el código ni cuenta intento.
     9. Correo sin cuenta, o sin comprobar: igual que un código incorrecto. Un código de otro propósito no sirve.
    10. Cada fallo cuenta para la espera por dispositivo (ADR 0014): a los 6 fallos ese dispositivo espera, para
        cualquier cuenta; otro dispositivo no.
    11. Faltan datos: 422.

Corren contra la base real con rollback_pool: todo se deshace al terminar cada prueba. Los códigos no se envían:
la prueba los lee de un anotador. Necesitan la migración 20261121000005_password_reset_code.sql; si no se ha
corrido en la base, se omiten y la salida lo dice.
"""

import pytest
from conftest import with_session
from test_accounts_login import (
    LOGIN,
    LOGIN_VERIFY,
    ME,
    PASSWORD,
    age_codes,
    errors_of,
    login,
    one,
    register,
    sessions_of,
)

REQUEST = "/api/v1/auth/password-reset/request"
CONFIRM = "/api/v1/auth/password-reset/confirm"
NEW_PASSWORD = "Nueva-2026!"
DAY_MINUTES = 30 * 60
OTHER_DEVICE = {"user-agent": "IntegroPruebas/otro-dispositivo"}


@pytest.fixture(autouse=True)
def migration_applied(api):
    definition = one(
        api, "select pg_get_constraintdef(oid) from pg_constraint where conname = 'one_time_codes_purpose_valid'"
    )
    if definition is None or "password_reset" not in definition[0]:
        pytest.skip("Falta correr database/migrations/20261121000005_password_reset_code.sql en la base integro.")


def ask(api, email, headers=None):
    return api.client.post(REQUEST, json={"email": email}, headers=headers)


def confirm(api, email, code, password=NEW_PASSWORD, headers=None):
    return api.client.post(CONFIRM, json={"email": email, "code": code, "new_password": password}, headers=headers)


def reset_codes(api, email, *, live_only=False):
    extra = " and used_at is null" if live_only else ""
    return one(
        api,
        "select count(*) from one_time_codes where purpose = 'password_reset' and "
        f"user_id = (select id from users where email = %s){extra}",
        email,
    )[0]


def password_hash(api, email):
    return one(
        api,
        "select password_hash from user_credentials where user_id = (select id from users where email = %s)",
        email,
    )[0]


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def start(api, **kwargs):
    """Una cuenta comprobada que ya pidió su código: devuelve el correo y el código."""
    form = register(api, **kwargs)
    assert ask(api, form["email"]).status_code == 200
    return form, api.sender.last_code


# --- Caso 1: pedir el código ---------------------------------------------------------------------


def test_a_verified_account_gets_a_six_digit_code_that_lasts_thirty_minutes(api):
    form = register(api)
    sent_before = len(api.sender.sent)

    response = ask(api, form["email"])

    assert response.status_code == 200
    assert response.json() == {"status": "code_requested"}
    assert len(api.sender.sent) == sent_before + 1
    message = api.sender.sent[-1]
    assert (message["channel"], message["destination"], message["purpose"], message["ttl_seconds"]) == (
        "email", form["email"], "password_reset", DAY_MINUTES,
    )
    assert len(message["code"]) == 6 and message["code"].isdigit()


def test_the_code_expires_in_thirty_minutes_and_only_its_fingerprint_is_stored(api):
    form, code = start(api)

    seconds, fingerprint = one(
        api,
        "select extract(epoch from expires_at - created_at), code_hash from one_time_codes "
        "where purpose = 'password_reset' and user_id = (select id from users where email = %s)",
        form["email"],
    )

    assert round(float(seconds)) == DAY_MINUTES
    assert fingerprint != code and code not in fingerprint


def test_the_email_may_be_written_in_any_case_and_with_spaces(api):
    form = register(api)

    response = ask(api, f"  {form['email'].upper()}  ")

    assert response.status_code == 200
    assert api.sender.sent[-1]["destination"] == form["email"]


# --- Caso 2: sin cuenta o sin comprobar ----------------------------------------------------------


def test_an_email_without_an_account_gets_exactly_the_same_answer_and_nothing_is_sent(api):
    real = register(api)
    real_response = ask(api, real["email"])
    sent = len(api.sender.sent)

    unknown = ask(api, "no.existe.ninguna@prueba.invalid")

    assert (unknown.status_code, unknown.json()) == (real_response.status_code, real_response.json())
    assert len(api.sender.sent) == sent
    assert dict(unknown.headers).keys() - {"content-length"} == dict(real_response.headers).keys() - {"content-length"}


def test_an_unverified_account_gets_the_same_answer_and_no_code(api):
    form = register(api, verified=False)
    sent = len(api.sender.sent)

    response = ask(api, form["email"])

    assert (response.status_code, response.json()) == (200, {"status": "code_requested"})
    assert len(api.sender.sent) == sent
    assert reset_codes(api, form["email"]) == 0


# --- Caso 3: límites --------------------------------------------------------------------------------


def test_asking_again_before_sixty_seconds_answers_the_same_and_sends_nothing_new(api):
    form, first_code = start(api)
    sent = len(api.sender.sent)

    again = ask(api, form["email"])

    assert (again.status_code, again.json()) == (200, {"status": "code_requested"})
    assert len(api.sender.sent) == sent
    assert reset_codes(api, form["email"]) == 1


def test_after_sixty_seconds_a_new_code_replaces_the_old_one(api):
    form, first_code = start(api)
    age_codes(api, form["email"], 61)

    assert ask(api, form["email"]).status_code == 200

    new_code = api.sender.last_code
    assert reset_codes(api, form["email"]) == 2 and reset_codes(api, form["email"], live_only=True) == 1
    if new_code != first_code:  # uno en un millón: salió el mismo
        old = confirm(api, form["email"], first_code)
        assert old.status_code == 400 and errors_of(old) == [("code", "invalid_code")]
    assert confirm(api, form["email"], new_code).status_code == 200


def test_more_than_five_codes_in_an_hour_are_not_sent_and_the_answer_does_not_change(api):
    form = register(api)
    for _ in range(5):
        age_codes(api, form["email"], 61)
        assert ask(api, form["email"]).status_code == 200
    sent = len(api.sender.sent)
    age_codes(api, form["email"], 61)

    sixth = ask(api, form["email"])

    assert (sixth.status_code, sixth.json()) == (200, {"status": "code_requested"})
    assert len(api.sender.sent) == sent
    assert reset_codes(api, form["email"]) == 5


# --- La regla de la base --------------------------------------------------------------------------


def insert_code(api, purpose, channel, destination):
    from app.database.transaction import system_transaction

    with system_transaction(api.pool) as connection:
        connection.execute(
            "insert into one_time_codes (user_id, purpose, channel, destination, code_hash, expires_at) "
            "select id, %s, %s, %s, repeat('a', 64), now() + interval '30 minutes' from users limit 1",
            (purpose, channel, destination),
        )


def test_the_table_accepts_the_new_purpose_by_email_only(api):
    import psycopg

    register(api)
    insert_code(api, "password_reset", "email", "ana@prueba.invalid")
    for channel, destination in (("sms", "+525512345678"), ("whatsapp", "+525512345678")):
        with pytest.raises(psycopg.errors.CheckViolation) as error:
            insert_code(api, "password_reset", channel, destination)
        assert error.value.diag.constraint_name == "one_time_codes_channel_matches_purpose"


def test_the_table_still_refuses_a_purpose_that_does_not_exist(api):
    import psycopg

    register(api)
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        insert_code(api, "otro_uso", "email", "ana@prueba.invalid")
    assert error.value.diag.constraint_name == "one_time_codes_purpose_valid"


# --- Caso 4 y 11: datos que faltan ------------------------------------------------------------------


@pytest.mark.parametrize("body", [{}, {"email": ""}, {"email": "   "}, {"email": None}, {"email": 7}])
def test_asking_without_an_email_is_rejected(api, body):
    response = api.client.post(REQUEST, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [("email", "required")]


@pytest.mark.parametrize(
    "body, fields",
    [
        ({}, ["email", "code", "new_password"]),
        ({"email": "a@b.co"}, ["code", "new_password"]),
        ({"email": "a@b.co", "code": "123456"}, ["new_password"]),
        ({"email": "", "code": " ", "new_password": ""}, ["email", "code", "new_password"]),
        ({"email": "a@b.co", "code": 123456, "new_password": NEW_PASSWORD}, ["code"]),
    ],
)
def test_confirming_without_its_data_is_rejected(api, body, fields):
    response = api.client.post(CONFIRM, json=body)

    assert response.status_code == 422
    assert [field for field, _ in errors_of(response)] == fields


# --- Caso 5: el cambio ------------------------------------------------------------------------------


def test_the_right_code_changes_the_password(api):
    form, code = start(api)
    before = password_hash(api, form["email"])

    response = confirm(api, form["email"], code)

    assert response.status_code == 200
    assert response.json() == {"status": "password_changed"}
    after = password_hash(api, form["email"])
    assert after != before and after.startswith("$argon2id$")
    assert NEW_PASSWORD not in after


def test_the_old_password_stops_working_and_the_new_one_logs_in_with_its_code(api):
    form, code = start(api)
    assert confirm(api, form["email"], code).status_code == 200
    age_codes(api, form["email"], 61)

    old = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    new = api.client.post(LOGIN, json={"email": form["email"], "password": NEW_PASSWORD})

    assert old.status_code == 401
    assert (new.status_code, new.json()) == (200, {"status": "code_required"})
    opened = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code})
    assert opened.status_code == 200


def test_the_code_is_spent_and_cannot_be_used_twice(api):
    form, code = start(api)
    assert confirm(api, form["email"], code).status_code == 200
    hash_after = password_hash(api, form["email"])

    again = confirm(api, form["email"], code, password="Otra-2026!x")

    assert again.status_code == 400 and errors_of(again) == [("code", "invalid_code")]
    assert password_hash(api, form["email"]) == hash_after
    assert reset_codes(api, form["email"], live_only=True) == 0


def test_the_email_may_be_written_in_any_case_when_confirming(api):
    form, code = start(api)

    assert confirm(api, f" {form['email'].upper()} ", f" {code} ").status_code == 200


def test_the_new_password_may_be_the_old_one(api):
    """No hay regla contra repetirla; solo cambia el estado de las sesiones. Queda dicho en una prueba."""
    form, code = start(api)

    assert confirm(api, form["email"], code, password=PASSWORD).status_code == 200


def test_the_password_change_does_not_touch_anything_else_of_the_account(api):
    form, code = start(api)
    before = one(
        api,
        "select u.first_name, u.last_name, u.email, u.country, u.birth_date, u.email_verified_at, "
        "(select phone from user_phones where user_id = u.id and is_primary) from users u where u.email = %s",
        form["email"],
    )

    assert confirm(api, form["email"], code).status_code == 200

    after = one(
        api,
        "select u.first_name, u.last_name, u.email, u.country, u.birth_date, u.email_verified_at, "
        "(select phone from user_phones where user_id = u.id and is_primary) from users u where u.email = %s",
        form["email"],
    )
    assert after == before


# --- Caso 6: las sesiones -------------------------------------------------------------------------


def test_every_open_session_of_the_account_is_closed(api):
    form = register(api)
    first = login(api, form)
    second = login(api, form)
    assert api.client.get(ME, headers=with_session(first)).status_code == 200
    assert api.client.get(ME, headers=with_session(second)).status_code == 200
    age_codes(api, form["email"], 61)
    assert ask(api, form["email"]).status_code == 200

    assert confirm(api, form["email"], api.sender.last_code).status_code == 200

    assert api.client.get(ME, headers=with_session(first)).status_code == 401
    assert api.client.get(ME, headers=with_session(second)).status_code == 401
    open_sessions = one(
        api,
        "select count(*) from sessions where revoked_at is null and "
        "user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert open_sessions == 0 and sessions_of(api, form["email"]) == 2


def test_the_sessions_of_other_accounts_are_not_touched(api):
    mine = register(api, first_name="Ana")
    other = register(api, first_name="Beto")
    other_session = login(api, other)
    age_codes(api, mine["email"], 61)
    assert ask(api, mine["email"]).status_code == 200

    assert confirm(api, mine["email"], api.sender.last_code).status_code == 200

    assert api.client.get(ME, headers=with_session(other_session)).status_code == 200


def test_the_reset_code_does_not_open_a_session(api):
    form, code = start(api)

    response = api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": code})

    assert response.status_code == 400 and errors_of(response) == [("code", "invalid_code")]
    assert sessions_of(api, form["email"]) == 0


# --- Caso 7: código incorrecto o vencido ---------------------------------------------------------


def test_a_wrong_code_says_how_many_attempts_are_left_and_changes_nothing(api):
    form, code = start(api)
    before = password_hash(api, form["email"])

    response = confirm(api, form["email"], wrong(code))

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert response.json()["attempts_left"] == 4
    assert response.json()["errors"][0]["message"] == "El código no es correcto."
    assert password_hash(api, form["email"]) == before
    # El código correcto sigue sirviendo.
    assert confirm(api, form["email"], code).status_code == 200


def test_after_five_wrong_codes_even_the_right_one_is_blocked(api):
    form, code = start(api)
    for left in (4, 3, 2, 1, 0):
        # Otro dispositivo cada vez: aquí se prueba el máximo del código, no la espera por dispositivo.
        response = confirm(api, form["email"], wrong(code), headers={"user-agent": f"IntegroPruebas/{left}"})
        assert response.json()["attempts_left"] == left
    before = password_hash(api, form["email"])

    blocked = confirm(api, form["email"], code, headers={"user-agent": "IntegroPruebas/final"})

    assert blocked.status_code == 400
    assert errors_of(blocked) == [("code", "too_many_attempts")]
    assert password_hash(api, form["email"]) == before


def test_an_expired_code_is_rejected_and_one_that_is_not_yet_still_works(api):
    form, code = start(api)
    age_codes(api, form["email"], DAY_MINUTES - 60)
    # A los 29 minutos todavía sirve (se prueba con un segundo código para no gastar este).
    form2, code2 = start(api)
    age_codes(api, form2["email"], DAY_MINUTES + 1)
    before = password_hash(api, form2["email"])

    expired = confirm(api, form2["email"], code2)

    assert expired.status_code == 400 and errors_of(expired) == [("code", "code_expired")]
    assert password_hash(api, form2["email"]) == before
    assert confirm(api, form["email"], code).status_code == 200


def test_a_wrong_code_costs_the_attempt_only_to_that_code(api):
    form, code = start(api)
    assert confirm(api, form["email"], wrong(code)).json()["attempts_left"] == 4
    age_codes(api, form["email"], 61)
    assert ask(api, form["email"]).status_code == 200

    fresh = confirm(api, form["email"], wrong(api.sender.last_code), headers=OTHER_DEVICE)

    assert fresh.json()["attempts_left"] == 4


# --- Caso 8: contraseña débil ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, code",
    [
        ("Corta-1!", "too_short"),
        ("Larguisima-2026-con-demasiados", "too_long"),
        ("Con espacios-2026!", "has_spaces"),
        ("sin-mayuscula-2026", "missing_uppercase"),
        ("SIN-MINUSCULA-2026", "missing_lowercase"),
        ("Sin-numero-aqui!!", "missing_digit"),
        ("SinSimbolo2026ab", "missing_symbol"),
    ],
)
def test_a_weak_password_is_rejected_without_spending_the_code(api, password, code):
    form, reset_code = start(api)
    before = password_hash(api, form["email"])

    response = confirm(api, form["email"], reset_code, password=password)

    assert response.status_code == 422
    assert ("new_password", code) in errors_of(response)
    assert {field for field, _ in errors_of(response)} == {"new_password"}
    assert password_hash(api, form["email"]) == before
    # El código no se gastó ni contó intento: sirve con una contraseña buena, y le quedaban sus 5 intentos.
    wrong_try = confirm(api, form["email"], wrong(reset_code), headers=OTHER_DEVICE)
    assert wrong_try.json()["attempts_left"] == 4
    assert confirm(api, form["email"], reset_code, headers=OTHER_DEVICE).status_code == 200


@pytest.mark.parametrize("password", ["Contrasena-1234", "Password-1234"])
def test_a_password_that_is_easy_to_guess_is_rejected_like_in_the_registration(api, password):
    from app.modules.accounts.password_strength import password_strength

    form, reset_code = start(api)
    before = password_hash(api, form["email"])
    assert not password_strength(password, first_name="Ana", last_name="Torres", email=form["email"]).is_enough

    response = confirm(api, form["email"], reset_code, password=password)

    assert response.status_code == 422
    assert errors_of(response) == [("new_password", "too_weak")]
    assert response.json()["errors"][0]["message"].startswith("La contraseña es muy fácil de adivinar.")
    assert password_hash(api, form["email"]) == before
    # No gastó el código ni contó intento.
    assert confirm(api, form["email"], wrong(reset_code), headers=OTHER_DEVICE).json()["attempts_left"] == 4
    assert confirm(api, form["email"], reset_code, headers=OTHER_DEVICE).status_code == 200


def test_the_registration_and_the_reset_judge_the_same_password_the_same_way(api):
    """Lo que el registro rechaza por fácil de adivinar, el cambio también; y al revés."""
    from test_accounts_login import REGISTER

    form = register(api, first_name="Beto")
    easy = "Contrasena-1234"
    signup = api.client.post(REGISTER, json={**form, "email": "otro.beto@prueba.invalid", "phone": "+525511112222", "password": easy})
    assert signup.status_code == 422 and ("password", "too_weak") in errors_of(signup)
    assert ask(api, form["email"]).status_code == 200

    reset = confirm(api, form["email"], api.sender.last_code, password=easy)

    assert reset.status_code == 422 and errors_of(reset) == [("new_password", "too_weak")]


def test_the_password_rules_are_the_ones_of_the_registration(api):
    from app.modules.accounts.validation import password_errors

    form, code = start(api)
    password = "sinreglas"

    response = confirm(api, form["email"], code, password=password)

    assert [c for _, c in errors_of(response)] == [error.code for error in password_errors(password)]


# --- Caso 9: sin cuenta, sin comprobar, otro propósito ------------------------------------------------


def test_an_email_without_an_account_answers_like_a_wrong_code(api):
    response = confirm(api, "no.existe.ninguna@prueba.invalid", "123456")

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert response.json()["errors"][0]["message"] == "El código no es correcto."


def test_an_unverified_account_cannot_recover_its_password_even_with_a_code(api):
    from app.database.transaction import system_transaction
    from app.modules.accounts.codes import create_code

    form = register(api, verified=False)
    user_id = one(api, "select id from users where email = %s", form["email"])[0]
    with system_transaction(api.pool) as connection:
        code = create_code(connection, user_id, "password_reset", form["email"], api.settings)
    before = password_hash(api, form["email"])

    response = confirm(api, form["email"], code)

    assert response.status_code == 400 and errors_of(response) == [("code", "invalid_code")]
    assert password_hash(api, form["email"]) == before


def test_a_login_code_does_not_recover_the_password(api):
    form = register(api)
    age_codes(api, form["email"], 61)
    api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})
    login_code = api.sender.last_code
    before = password_hash(api, form["email"])

    response = confirm(api, form["email"], login_code)

    assert response.status_code == 400 and errors_of(response) == [("code", "invalid_code")]
    assert password_hash(api, form["email"]) == before


def test_a_code_of_one_account_does_not_work_for_another(api):
    ana, ana_code = start(api)
    beto = register(api, first_name="Beto")
    assert ask(api, beto["email"]).status_code == 200
    before = password_hash(api, beto["email"])

    response = confirm(api, beto["email"], ana_code)

    if ana_code != api.sender.last_code:  # uno en un millón: salió el mismo
        assert response.status_code == 400
        assert password_hash(api, beto["email"]) == before


# --- Caso 10: espera por dispositivo ---------------------------------------------------------------


def test_six_failures_make_that_device_wait_for_any_account(api):
    form, code = start(api)
    for _ in range(6):
        assert confirm(api, "no.existe.ninguna@prueba.invalid", "123456").status_code == 400

    waiting = confirm(api, form["email"], code)

    assert waiting.status_code == 429
    assert errors_of(waiting) == [("credentials", "try_later")]
    assert int(waiting.headers["retry-after"]) > 0
    assert password_hash(api, form["email"]) == password_hash(api, form["email"])
    assert reset_codes(api, form["email"], live_only=True) == 1


def test_another_device_is_not_made_to_wait(api):
    form, code = start(api)
    for _ in range(6):
        confirm(api, "no.existe.ninguna@prueba.invalid", "123456")

    other = confirm(api, form["email"], code, headers=OTHER_DEVICE)

    assert other.status_code == 200


def test_failures_of_the_reset_count_with_the_failures_of_the_login(api):
    """Es la misma espera por dispositivo: tres fallos de contraseña y tres de código suman seis."""
    form, code = start(api)
    for _ in range(3):
        assert api.client.post(LOGIN, json={"email": form["email"], "password": "Mala-2026!x"}).status_code == 401
    for _ in range(3):
        assert confirm(api, "no.existe.ninguna@prueba.invalid", "123456").status_code == 400

    blocked = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert blocked.status_code == 429


def test_a_wrong_reset_code_is_noted_without_telling_the_owner_it_was_a_login_attempt(api):
    form, code = start(api)
    for _ in range(3):
        confirm(api, form["email"], wrong(code), headers={"user-agent": f"IntegroPruebas/{_}"})

    assert api.sender.notices == []
    noted = one(
        api,
        "select count(*) from login_attempts where not succeeded and "
        "user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert noted == 3


def test_a_good_reset_does_not_count_as_a_failure_nor_as_a_login(api):
    form, code = start(api)

    assert confirm(api, form["email"], code).status_code == 200

    total = one(
        api,
        "select count(*) from login_attempts where user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert total == 0


# --- El aviso al dueño de la cuenta ------------------------------------------------------------------
# Decisión de Sophia del 21 de noviembre de 2026: al cambiar la contraseña se le avisa por correo al dueño.


def password_notices(api):
    return [n for n in api.sender.notices if n["kind"] == "password_changed"]


def test_changing_the_password_sends_one_notice_to_the_owner(api):
    form, code = start(api)

    response = confirm(api, form["email"], code, headers={"user-agent": "IntegroPruebas/aviso"})

    assert response.status_code == 200
    notices = password_notices(api)
    assert len(notices) == 1 and len(api.sender.notices) == 1
    notice = notices[0]
    assert (notice["channel"], notice["destination"]) == ("email", form["email"])
    assert set(notice["details"]) == {"at", "ip_address", "user_agent"}
    assert notice["details"]["user_agent"] == "IntegroPruebas/aviso"
    from datetime import datetime, timezone

    assert abs((datetime.now(timezone.utc) - notice["details"]["at"]).total_seconds()) < 60


def test_the_notice_goes_to_the_address_of_the_account_even_if_it_was_written_differently(api):
    form, code = start(api)

    assert confirm(api, f"  {form['email'].upper()} ", code).status_code == 200

    assert password_notices(api)[0]["destination"] == form["email"]


def test_the_notice_carries_no_password_and_no_code(api):
    form, code = start(api)
    assert confirm(api, form["email"], code).status_code == 200

    text = str(password_notices(api)[0])

    assert NEW_PASSWORD not in text and PASSWORD not in text and code not in text


def test_asking_for_the_code_sends_no_notice(api):
    form, code = start(api)

    assert api.sender.notices == []


@pytest.mark.parametrize("case", ["wrong_code", "expired", "weak", "easy_to_guess", "attempts_exhausted", "unknown_email"])
def test_no_notice_is_sent_when_the_password_did_not_change(api, case):
    form, code = start(api)
    email, attempt, password = form["email"], code, NEW_PASSWORD
    if case == "wrong_code":
        attempt = wrong(code)
    elif case == "expired":
        age_codes(api, email, DAY_MINUTES + 1)
    elif case == "weak":
        password = "corta"
    elif case == "easy_to_guess":
        password = "Contrasena-1234"
    elif case == "attempts_exhausted":
        for number in range(5):
            confirm(api, email, wrong(code), headers={"user-agent": f"IntegroPruebas/{number}"})
    elif case == "unknown_email":
        email = "no.existe.ninguna@prueba.invalid"

    response = confirm(api, email, attempt, password=password, headers={"user-agent": "IntegroPruebas/final"})

    assert response.status_code in (400, 422)
    assert api.sender.notices == []


def test_no_notice_is_sent_to_a_device_that_has_to_wait(api):
    form, code = start(api)
    for _ in range(6):
        confirm(api, "no.existe.ninguna@prueba.invalid", "123456")

    assert confirm(api, form["email"], code).status_code == 429

    assert api.sender.notices == []


def test_the_notice_is_not_repeated_if_the_same_code_is_used_again(api):
    form, code = start(api)
    assert confirm(api, form["email"], code).status_code == 200

    assert confirm(api, form["email"], code, password="Otra-2026!x").status_code == 400

    assert len(password_notices(api)) == 1


def test_the_console_prints_the_notice_without_secrets(api, capsys):
    from datetime import datetime, timezone

    from app.notifications.console import ConsoleCodeSender

    ConsoleCodeSender().send_notice(
        channel="email",
        destination="ana@prueba.invalid",
        kind="password_changed",
        details={"at": datetime(2026, 11, 21, 12, 30, tzinfo=timezone.utc), "ip_address": "203.0.113.7", "user_agent": "Edge"},
    )

    printed = capsys.readouterr().out
    assert printed.startswith("[MODO DESARROLLO] Aviso para ana@prueba.invalid (email, password_changed): ")
    assert "La contraseña de tu cuenta de Íntegro se cambió el 2026-11-21 12:30:00 UTC." in printed
    assert "Navegador: Edge. Dirección: 203.0.113.7." in printed
    assert "Por seguridad cerramos todas tus sesiones." in printed
    assert "¿Olvidaste tu contraseña?" in printed
    assert "usted" not in printed.lower()


def test_the_console_says_unknown_when_there_is_no_browser_or_address(api, capsys):
    from datetime import datetime, timezone

    from app.notifications.console import ConsoleCodeSender

    ConsoleCodeSender().send_notice(
        channel="email",
        destination="ana@prueba.invalid",
        kind="password_changed",
        details={"at": datetime(2026, 11, 21, tzinfo=timezone.utc), "ip_address": None, "user_agent": None},
    )

    assert "Navegador: desconocido. Dirección: desconocida." in capsys.readouterr().out
