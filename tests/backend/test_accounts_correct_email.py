"""Casos de la pieza "corregir el correo de una cuenta sin comprobar".

Decisión de Sophia del 20 de noviembre de 2026: quien se equivoca de correo al registrarse puede corregirlo.

    POST /api/v1/auth/correct-unverified-email   (correo, contraseña y correo nuevo)
     1. Contraseña correcta y correo nuevo libre: 200; la cuenta cambia de correo (la misma persona, su teléfono
        y su contraseña no cambian), el código anterior deja de servir y llega uno nuevo al correo nuevo.
     2. Con el código nuevo el correo nuevo se comprueba y la cuenta puede iniciar sesión con él.
     3. Contraseña incorrecta, o correo sin cuenta: 401, la misma respuesta; no cambia nada y no se envía código.
        El intento se anota y cuenta para la espera por dispositivo.
     4. Cuenta ya comprobada: 409; el correo no se toca. (Solo se sabe con la contraseña correcta.)
     5. Correo nuevo que ya es de otra cuenta: 409; no cambia nada.
     6. El mismo correo, o uno mal escrito, o datos que faltan: 422.
     7. Máximo de códigos por hora: 429. La espera de un minuto no cuenta: el código anterior fue a un correo
        equivocado.

Corren contra la base real con rollback_pool: todo se deshace al terminar cada prueba. Los códigos no se
envían: la prueba los lee de un anotador.
"""

from uuid import uuid4

import pytest
from test_accounts_login import LOGIN, LOGIN_VERIFY, PASSWORD, VERIFY_EMAIL, errors_of, login, one, register, run

from app.database.transaction import system_transaction
from app.modules.accounts.codes import create_code

CORRECT = "/api/v1/auth/correct-unverified-email"
CORRECT_MESSAGES = {
    "invalid_credentials": "El correo o la contraseña no son correctos.",
}


def new_address() -> str:
    return f"correcta.{uuid4().hex[:10]}@prueba.invalid"


def correct(api, form, new_email, *, password=PASSWORD, email=None, headers=None):
    body = {"email": email if email is not None else form["email"], "password": password, "new_email": new_email}
    return api.client.post(CORRECT, json=body, headers=headers)


def user_by_email(api, email):
    return one(api, "select id, email_verified_at is not null from users where email = %s", email)


def state_of(api, user_id):
    """Lo que no debe cambiar al corregir el correo."""
    return one(
        api,
        "select u.first_name, u.last_name, u.country, u.birth_date, "
        "(select phone from user_phones where user_id = u.id and is_primary), "
        "(select password_hash from user_credentials where user_id = u.id) from users u where u.id = %s",
        user_id,
    )


# --- Caso 1 -----------------------------------------------------------------------------------


def test_a_good_correction_changes_the_email_and_sends_the_code_to_the_new_one(api):
    form = register(api, verified=False)
    new = new_address()

    response = correct(api, form, new)

    assert response.status_code == 200
    assert response.json() == {"status": "verification_required", "email": new}
    assert user_by_email(api, form["email"]) is None
    assert user_by_email(api, new) is not None
    message = api.sender.sent[-1]
    assert (message["channel"], message["destination"], message["purpose"], message["ttl_seconds"]) == (
        "email", new, "verify_email", 300,
    )
    assert len(message["code"]) == 6 and message["code"].isdigit()


def test_the_same_person_keeps_everything_else(api):
    form = register(api, verified=False)
    user_id = user_by_email(api, form["email"])[0]
    before = state_of(api, user_id)

    assert correct(api, form, new_address()).status_code == 200

    assert state_of(api, user_id) == before
    assert user_by_email(api, form["email"]) is None


def test_the_email_is_saved_in_lowercase_and_without_spaces(api):
    form = register(api, verified=False)
    new = new_address()

    response = correct(api, form, f"  {new.upper()}  ", email=f"  {form['email'].upper()} ")

    assert response.status_code == 200
    assert response.json()["email"] == new
    assert user_by_email(api, new) is not None


def test_the_old_code_stops_working_and_only_one_new_code_is_live(api):
    form = register(api, verified=False)
    old_code = api.sender.last_code
    new = new_address()

    assert correct(api, form, new).status_code == 200

    new_code = api.sender.last_code
    if old_code != new_code:  # uno en un millón: salió el mismo
        old = api.client.post(VERIFY_EMAIL, json={"email": new, "code": old_code})
        assert old.status_code == 400
    live = one(
        api,
        "select count(*) from one_time_codes where user_id = (select id from users where email = %s) "
        "and purpose = 'verify_email' and used_at is null",
        new,
    )[0]
    assert live == 1


def test_the_new_code_is_tied_to_the_new_email(api):
    """Un código de la dirección anterior no sirve para la nueva, aunque sea el mismo número."""
    form = register(api, verified=False)
    new = new_address()
    correct(api, form, new)

    row = one(
        api,
        "select destination from one_time_codes where user_id = (select id from users where email = %s) "
        "and purpose = 'verify_email' and used_at is null",
        new,
    )

    assert row[0] == new


def test_the_wait_of_a_minute_does_not_apply_because_the_first_code_went_to_a_wrong_email(api):
    form = register(api, verified=False)  # el código acaba de enviarse: hace menos de un minuto

    response = correct(api, form, new_address())

    assert response.status_code == 200


def test_it_can_be_corrected_more_than_once(api):
    form = register(api, verified=False)
    first, second = new_address(), new_address()

    assert correct(api, form, first).status_code == 200
    assert correct(api, form, second, email=first).status_code == 200

    assert user_by_email(api, first) is None
    assert user_by_email(api, second) is not None
    assert api.sender.sent[-1]["destination"] == second


# --- Caso 2 -----------------------------------------------------------------------------------


def test_with_the_new_code_the_email_is_checked_and_the_person_can_log_in_with_it(api):
    form = register(api, verified=False)
    new = new_address()
    correct(api, form, new)

    verified = api.client.post(VERIFY_EMAIL, json={"email": new, "code": api.sender.last_code})

    assert verified.status_code == 200
    assert user_by_email(api, new)[1] is True
    token = login(api, {**form, "email": new})
    assert len(token) >= 40


def test_the_old_email_no_longer_has_an_account_to_verify_or_log_into(api):
    form = register(api, verified=False)
    new = new_address()
    correct(api, form, new)

    verify_old = api.client.post(VERIFY_EMAIL, json={"email": form["email"], "code": api.sender.last_code})
    login_old = api.client.post(LOGIN, json={"email": form["email"], "password": PASSWORD})

    assert verify_old.status_code == 400
    assert login_old.status_code == 401


def test_the_old_email_can_be_registered_again_by_someone_else(api):
    form = register(api, verified=False)
    correct(api, form, new_address())

    other = api.client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Beto", "last_name": "Pérez", "email": form["email"], "password": PASSWORD,
            "phone": "+5255" + str(uuid4().int)[:8], "country": "MX", "birth_date": "1990-01-01",
        },
    )

    assert other.status_code == 201


# --- Caso 3 -----------------------------------------------------------------------------------


def test_a_wrong_password_is_refused_and_changes_nothing(api):
    form = register(api, verified=False)
    sent = len(api.sender.sent)

    response = correct(api, form, new_address(), password="Ejemplo-2027")

    assert response.status_code == 401
    assert errors_of(response) == [("credentials", "invalid_credentials")]
    assert response.json()["errors"][0]["message"] == CORRECT_MESSAGES["invalid_credentials"]
    assert user_by_email(api, form["email"]) is not None
    assert len(api.sender.sent) == sent


@pytest.mark.parametrize("password", ["Ejemplo-2027", "ejemplo-2026", "Ejemplo-2026 ", "x"])
def test_any_wrong_password_is_the_same_answer(api, password):
    form = register(api, verified=False)

    assert correct(api, form, new_address(), password=password).status_code == 401


def test_an_email_without_account_answers_exactly_the_same(api):
    form = register(api, verified=False)
    wrong_password = correct(api, form, new_address(), password="Ejemplo-2027")

    no_account = correct(api, form, new_address(), email=f"nadie.{uuid4().hex[:8]}@prueba.invalid")

    assert no_account.status_code == wrong_password.status_code == 401
    assert no_account.json() == wrong_password.json()


def test_the_attempts_are_noted_the_failed_one_and_the_good_one(api):
    form = register(api, verified=False)
    user_id = user_by_email(api, form["email"])[0]

    correct(api, form, new_address(), password="Ejemplo-2027")
    failed = one(api, "select count(*) from login_attempts where user_id = %s and not succeeded", user_id)[0]
    correct(api, form, new_address())
    succeeded = one(api, "select count(*) from login_attempts where user_id = %s and succeeded", user_id)[0]

    assert (failed, succeeded) == (1, 1)


def test_six_wrong_passwords_make_the_device_wait_even_with_the_right_one(api):
    form = register(api, verified=False)
    for _ in range(6):
        assert correct(api, form, new_address(), password="Ejemplo-2027").status_code == 401

    response = correct(api, form, new_address())

    assert response.status_code == 429
    assert errors_of(response) == [("credentials", "try_later")]
    assert response.json()["retry_after"] == 900
    assert response.headers["retry-after"] == "900"
    assert user_by_email(api, form["email"]) is not None
    # Otro dispositivo, otro navegador, entra normal: la cuenta no se bloquea.
    other = correct(api, form, new_address(), headers={"User-Agent": "Otro navegador"})
    assert other.status_code == 200


def test_the_wait_of_a_device_that_failed_logging_in_also_applies_here(api):
    """Es la misma espera por dispositivo del inicio de sesión (ADR 0014)."""
    form = register(api, verified=False)
    for _ in range(6):
        api.client.post(LOGIN, json={"email": form["email"], "password": "Ejemplo-2027"})

    assert correct(api, form, new_address()).status_code == 429


# --- Caso 4 -----------------------------------------------------------------------------------


def test_a_verified_account_cannot_be_corrected_here(api):
    form = register(api, verified=True)
    new = new_address()

    response = correct(api, form, new)

    assert response.status_code == 409
    assert errors_of(response) == [("email", "already_verified")]
    assert user_by_email(api, form["email"]) is not None
    assert user_by_email(api, new) is None


def test_a_verified_account_with_a_wrong_password_looks_like_any_wrong_password(api):
    """Que la cuenta esté comprobada solo se dice a quien tiene su contraseña."""
    form = register(api, verified=True)

    response = correct(api, form, new_address(), password="Ejemplo-2027")

    assert response.status_code == 401


# --- Caso 5 -----------------------------------------------------------------------------------


def test_an_email_that_belongs_to_another_account_is_refused_and_nothing_changes(api):
    mine = register(api, "Ana", verified=False)
    other = register(api, "Beto", verified=True)
    sent = len(api.sender.sent)

    response = correct(api, mine, other["email"])

    assert response.status_code == 409
    assert errors_of(response) == [("new_email", "already_registered")]
    assert response.json()["errors"][0]["message"] == "Ya existe una cuenta con este correo."
    assert user_by_email(api, mine["email"]) is not None
    assert user_by_email(api, other["email"])[1] is True
    assert len(api.sender.sent) == sent


def test_an_email_of_another_account_in_other_case_is_refused_too(api):
    mine = register(api, "Ana", verified=False)
    other = register(api, "Beto", verified=False)

    assert correct(api, mine, other["email"].upper()).status_code == 409


# --- Caso 6 -----------------------------------------------------------------------------------


def test_the_same_email_is_refused(api):
    form = register(api, verified=False)
    sent = len(api.sender.sent)

    response = correct(api, form, f"  {form['email'].upper()} ")

    assert response.status_code == 422
    assert errors_of(response) == [("new_email", "same_email")]
    assert len(api.sender.sent) == sent


@pytest.mark.parametrize("bad", ["ana", "ana@", "@x.com", "ana@x", "ana @x.com", "a" * 250 + "@x.com"])
def test_a_badly_written_new_email_is_refused(api, bad):
    form = register(api, verified=False)

    response = correct(api, form, bad)

    assert response.status_code == 422
    assert errors_of(response) == [("new_email", "invalid")]
    assert user_by_email(api, form["email"]) is not None


@pytest.mark.parametrize(
    "body, fields",
    [
        ({}, ["email", "password", "new_email"]),
        ({"email": "a@b.co"}, ["password", "new_email"]),
        ({"password": PASSWORD}, ["email", "new_email"]),
        ({"email": "", "password": "", "new_email": ""}, ["email", "password", "new_email"]),
        ({"email": 5, "password": None, "new_email": ["x"]}, ["email", "password", "new_email"]),
    ],
)
def test_missing_data_is_refused_field_by_field(api, body, fields):
    response = api.client.post(CORRECT, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required") for field in fields]


# --- Caso 7 -----------------------------------------------------------------------------------


def test_the_hourly_limit_of_codes_applies(api):
    form = register(api, verified=False)
    user_id = user_by_email(api, form["email"])[0]
    with system_transaction(api.pool) as connection:
        for _ in range(4):  # con el del registro, cinco en la última hora
            create_code(connection, user_id, "verify_email", form["email"], api.settings)

    response = correct(api, form, new_address())

    assert response.status_code == 429
    assert errors_of(response) == [("email", "hourly_limit")]
    assert user_by_email(api, form["email"]) is not None


def test_four_codes_in_the_hour_still_allow_one_more(api):
    form = register(api, verified=False)
    user_id = user_by_email(api, form["email"])[0]
    with system_transaction(api.pool) as connection:
        for _ in range(3):
            create_code(connection, user_id, "verify_email", form["email"], api.settings)

    assert correct(api, form, new_address()).status_code == 200


# --- La ruta ----------------------------------------------------------------------------------


def test_the_route_is_documented_and_only_accepts_post(api):
    assert CORRECT in api.client.get("/openapi.json").json()["paths"]
    assert api.client.get(CORRECT).status_code == 405


def test_the_answers_never_show_the_password_or_the_old_email_of_another_person(api):
    form = register(api, verified=False)
    other = register(api, "Beto", verified=True)

    for response in (
        correct(api, form, other["email"]),
        correct(api, form, new_address(), password="Ejemplo-2027"),
        correct(api, form, new_address()),
    ):
        assert PASSWORD not in response.text and "argon2" not in response.text
        assert other["email"] not in response.text or response.status_code == 409


def test_the_messages_are_formal_but_of_tu(api):
    form = register(api, verified=False)
    mine = correct(api, form, form["email"])
    taken = correct(api, form, register(api, "Beto", verified=True)["email"])

    for response in (mine, taken):
        message = response.json()["errors"][0]["message"]
        assert not any(word in message for word in ("Escriba", "Intente ", "Revise", "su correo"))
