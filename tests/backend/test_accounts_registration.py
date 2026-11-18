"""Casos de la pieza "registro con comprobación de correo".

Especificación aceptada por Sophia el 17 de noviembre de 2026:

    POST /api/v1/auth/register
     1. Datos completos y válidos: 201. Se guardan la persona (correo en
        minúsculas), el teléfono principal, la contraseña convertida con
        Argon2id y un código de 6 dígitos que vence en 5 minutos.
     2. Falta un dato o viene vacío: 422, dice qué campo; no se guarda nada.
     3. Cumple 18 mañana: 422. Cumple 18 hoy: 201.
     4. Contraseña de 7 caracteres, o sin mayúscula, sin minúscula, sin
        número o sin símbolo: 422.
     5. Correo o teléfono con formato inválido: 422.
     6. Correo ya registrado (aunque cambien las mayúsculas) o teléfono ya
        registrado: 409, dice qué campo; no se guarda nada.
    POST /api/v1/auth/verify-email
     7. Código correcto: 200. El correo queda comprobado; el código no sirve
        dos veces.
     8. Código incorrecto: 400. Al quinto fallo el código se bloquea, aunque
        después se escriba el correcto.
     9. Código vencido (más de 5 minutos): 400.
    POST /api/v1/auth/resend-code
    10. Pedir otro antes de 60 segundos: 429. Después de 60 segundos: 200,
        llega uno nuevo y el anterior deja de servir.
    11. Más de 5 códigos en una hora: 429.

Corren contra la base real con rollback_pool: todo se deshace al terminar
cada prueba. Los códigos no se envían: la prueba los lee de un anotador.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.database.transaction import system_transaction
from app.modules.accounts.security import hash_code
from app.modules.accounts.validation import today_in_country

REGISTER = "/api/v1/auth/register"
VERIFY = "/api/v1/auth/verify-email"
RESEND = "/api/v1/auth/resend-code"

PASSWORD = "Ejemplo-2026"


def new_form(**changes) -> dict:
    """Formulario válido con correo y teléfono que no existen en la base."""
    tag = uuid4().hex[:12]
    return {
        "first_name": "Ana",
        "last_name": "Torres",
        "email": f"ana.{tag}@prueba.invalid",
        "password": PASSWORD,
        "phone": "+52" + str(int(tag, 16))[:10].rjust(10, "5"),
        "country": "MX",
        "birth_date": "1995-03-14",
        "preferred_language": "es",
        **changes,
    }


def errors_of(response) -> list[tuple[str, str]]:
    return [(error["field"], error["code"]) for error in response.json()["errors"]]


def one(api, query: str, *parameters):
    """Lee una fila como el sistema."""
    with system_transaction(api.pool) as connection:
        return connection.execute(query, parameters).fetchone()


def count_users(api, email: str) -> int:
    return one(api, "select count(*) from users where email = %s", email.lower())[0]


def age_codes(api, email: str, seconds: int) -> None:
    """Hace que los códigos de esa persona parezcan creados hace tantos segundos."""
    with system_transaction(api.pool) as connection:
        connection.execute(
            "update one_time_codes set created_at = created_at - make_interval(secs => %s), "
            "expires_at = expires_at - make_interval(secs => %s) "
            "where user_id = (select id from users where email = %s)",
            (seconds, seconds, email),
        )


def register(api, **changes) -> dict:
    """Registra a una persona y devuelve su formulario. Deja el código en api.sender."""
    form = new_form(**changes)
    response = api.client.post(REGISTER, json=form)
    assert response.status_code == 201, response.text
    return form


# ===========================================================================
# POST /auth/register
# ===========================================================================

# --- Caso 1 ----------------------------------------------------------------


def test_register_with_valid_data_creates_the_account(api):
    form = new_form(email="Ana.Torres.%s@Prueba.INVALID" % uuid4().hex[:8])
    email = form["email"].lower()

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 201
    assert response.json() == {"status": "verification_required", "email": email}

    user = one(
        api,
        "select id, first_name, last_name, country, birth_date::text, preferred_language, "
        "email_verified_at, identity_status from users where email = %s",
        email,
    )
    assert user[1:] == ("Ana", "Torres", "MX", "1995-03-14", "es", None, "unverified")
    user_id = user[0]

    phones = one(
        api,
        "select phone, is_primary, verified_at from user_phones where user_id = %s",
        user_id,
    )
    assert phones == (form["phone"], True, None)

    password_hash = one(
        api, "select password_hash from user_credentials where user_id = %s", user_id
    )[0]
    assert password_hash.startswith("$argon2id$")
    assert PASSWORD not in password_hash


def test_register_sends_a_six_digit_code_that_expires_in_five_minutes(api):
    form = register(api)

    assert len(api.sender.sent) == 1
    message = api.sender.sent[0]
    assert message["channel"] == "email"
    assert message["destination"] == form["email"]
    assert message["purpose"] == "verify_email"
    assert message["ttl_seconds"] == 300
    assert len(message["code"]) == 6 and message["code"].isdigit()

    code = one(
        api,
        "select purpose, channel, destination, attempts, used_at, "
        "extract(epoch from expires_at - created_at)::int, code_hash "
        "from one_time_codes where user_id = (select id from users where email = %s)",
        form["email"],
    )
    assert code[:6] == ("verify_email", "email", form["email"], 0, None, 300)
    # En la base está la huella, no el código.
    assert code[6] != message["code"]
    assert code[6] == hash_code(
        message["code"],
        secret=api.settings.code_hash_secret.get_secret_value(),
        purpose="verify_email",
        destination=form["email"],
    )


def test_register_response_never_carries_the_password_or_the_code(api):
    form = new_form()

    response = api.client.post(REGISTER, json=form)

    assert PASSWORD not in response.text
    assert api.sender.last_code not in response.text


def test_register_keeps_odd_text_as_text(api):
    name = "Robert'); drop table users; --"

    form = register(api, first_name=name)

    assert one(api, "select first_name from users where email = %s", form["email"])[0] == name


# --- Caso 2 ----------------------------------------------------------------

REQUIRED = ["first_name", "last_name", "email", "password", "phone", "country", "birth_date"]


@pytest.mark.parametrize("field", REQUIRED)
@pytest.mark.parametrize("how", ["missing", "empty", "null"])
def test_register_without_a_required_field_saves_nothing(api, field, how):
    form = new_form()
    email = form["email"]
    if how == "missing":
        del form[field]
    else:
        form[field] = "" if how == "empty" else None

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required")]
    assert count_users(api, email) == 0
    assert api.sender.sent == []


def test_register_with_empty_body_reports_every_field(api):
    response = api.client.post(REGISTER, json={})

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required") for field in REQUIRED]


# --- Caso 3 ----------------------------------------------------------------


def years_ago(years: int):
    """La fecha de hace tantos años, contada con la fecha de hoy en México."""
    today = today_in_country("MX", datetime.now(timezone.utc))
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # hoy es 29 de febrero
        return today.replace(year=today.year - years, day=28)


def test_register_turning_18_tomorrow_is_rejected(api):
    form = new_form(birth_date=(years_ago(18) + timedelta(days=1)).isoformat())

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 422
    assert errors_of(response) == [("birth_date", "under_age")]
    assert count_users(api, form["email"]) == 0


def test_register_turning_18_today_is_accepted(api):
    form = new_form(birth_date=years_ago(18).isoformat())

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 201
    assert count_users(api, form["email"]) == 1


def test_register_accepts_a_guest_from_another_country(api):
    form = register(api, country="us", preferred_language="en", phone=new_form()["phone"].replace("+52", "+1"))

    saved = one(api, "select country, preferred_language from users where email = %s", form["email"])
    assert saved == ("US", "en")


# --- Caso 4 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "password, code",
    [
        ("Abcd-1x", "too_short"),
        ("ejemplo-2026", "missing_uppercase"),
        ("EJEMPLO-2026", "missing_lowercase"),
        ("Ejemplo-dosmil", "missing_digit"),
        ("Ejemplo2026", "missing_symbol"),
    ],
)
def test_register_with_weak_password_is_rejected(api, password, code):
    form = new_form(password=password)

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 422
    assert errors_of(response) == [("password", code)]
    assert count_users(api, form["email"]) == 0


def test_register_with_password_of_exactly_8_is_accepted(api):
    register(api, password="Abcde-1x")


# --- Caso 5 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("email", "sin-arroba"),
        ("email", "ana@example"),
        ("phone", "5512345678"),
        ("phone", "+52 55 1234 5678"),
        ("country", "México"),
        ("birth_date", "14/03/1995"),
        ("preferred_language", "fr"),
    ],
)
def test_register_with_invalid_format_is_rejected(api, field, value):
    form = new_form(**{field: value})

    response = api.client.post(REGISTER, json=form)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "invalid")]
    assert api.sender.sent == []


# --- Caso 6 ----------------------------------------------------------------


def test_register_with_an_email_already_registered_is_rejected(api):
    first = register(api)
    second = new_form(email=first["email"].upper(), first_name="Otra")

    response = api.client.post(REGISTER, json=second)

    assert response.status_code == 409
    assert errors_of(response) == [("email", "already_registered")]
    assert count_users(api, first["email"]) == 1
    assert one(api, "select first_name from users where email = %s", first["email"])[0] == "Ana"
    # No se guardó el teléfono de la segunda ni se le envió código.
    assert one(api, "select count(*) from user_phones where phone = %s", second["phone"])[0] == 0
    assert len(api.sender.sent) == 1


def test_register_with_a_phone_already_registered_is_rejected(api):
    first = register(api)
    second = new_form(phone=first["phone"])

    response = api.client.post(REGISTER, json=second)

    assert response.status_code == 409
    assert errors_of(response) == [("phone", "already_registered")]
    assert count_users(api, second["email"]) == 0
    assert len(api.sender.sent) == 1


# ===========================================================================
# POST /auth/verify-email
# ===========================================================================

# --- Caso 7 ----------------------------------------------------------------


def test_verify_with_the_right_code_marks_the_email_verified(api):
    form = register(api)
    code = api.sender.last_code

    response = api.client.post(VERIFY, json={"email": form["email"], "code": code})

    assert response.status_code == 200
    assert response.json() == {"status": "verified"}
    verified, used = one(
        api,
        "select u.email_verified_at is not null, c.used_at is not null "
        "from users u join one_time_codes c on c.user_id = u.id where u.email = %s",
        form["email"],
    )
    assert (verified, used) == (True, True)


def test_verify_accepts_the_email_in_any_case_and_spaces_around_the_code(api):
    form = register(api)

    response = api.client.post(
        VERIFY, json={"email": form["email"].upper(), "code": f" {api.sender.last_code} "}
    )

    assert response.status_code == 200


def test_the_same_code_does_not_work_twice(api):
    form = register(api)
    body = {"email": form["email"], "code": api.sender.last_code}
    assert api.client.post(VERIFY, json=body).status_code == 200

    response = api.client.post(VERIFY, json=body)

    assert response.status_code == 409
    assert errors_of(response) == [("email", "already_verified")]


# --- Caso 8 ----------------------------------------------------------------


def wrong_code(code: str) -> str:
    """Un código de seis dígitos distinto al correcto."""
    return "000000" if code != "000000" else "111111"


def test_verify_with_a_wrong_code_counts_the_attempt(api):
    form = register(api)
    wrong = wrong_code(api.sender.last_code)

    response = api.client.post(VERIFY, json={"email": form["email"], "code": wrong})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert response.json()["attempts_left"] == 4
    attempts, verified = one(
        api,
        "select c.attempts, u.email_verified_at from users u "
        "join one_time_codes c on c.user_id = u.id where u.email = %s",
        form["email"],
    )
    assert (attempts, verified) == (1, None)


def test_after_four_wrong_attempts_the_right_code_still_works(api):
    form = register(api)
    code = api.sender.last_code
    for expected_left in (4, 3, 2, 1):
        response = api.client.post(VERIFY, json={"email": form["email"], "code": wrong_code(code)})
        assert response.json()["attempts_left"] == expected_left

    response = api.client.post(VERIFY, json={"email": form["email"], "code": code})

    assert response.status_code == 200


def test_after_five_wrong_attempts_the_code_is_blocked_even_with_the_right_one(api):
    form = register(api)
    code = api.sender.last_code
    for expected_left in (4, 3, 2, 1, 0):
        response = api.client.post(VERIFY, json={"email": form["email"], "code": wrong_code(code)})
        assert response.status_code == 400
        assert response.json()["attempts_left"] == expected_left

    response = api.client.post(VERIFY, json={"email": form["email"], "code": code})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "too_many_attempts")]
    assert one(api, "select email_verified_at from users where email = %s", form["email"])[0] is None


def test_verify_for_an_email_without_account_looks_like_a_wrong_code(api):
    response = api.client.post(
        VERIFY, json={"email": f"nadie.{uuid4().hex[:8]}@prueba.invalid", "code": "123456"}
    )

    assert response.status_code == 400
    assert errors_of(response) == [("code", "invalid_code")]
    assert "attempts_left" not in response.json()


@pytest.mark.parametrize(
    "body, fields",
    [
        ({}, ["email", "code"]),
        ({"email": "ana@prueba.invalid"}, ["code"]),
        ({"code": "123456"}, ["email"]),
        ({"email": "", "code": "  "}, ["email", "code"]),
        ({"email": 5, "code": 123456}, ["email", "code"]),
    ],
)
def test_verify_without_its_data_is_rejected(api, body, fields):
    response = api.client.post(VERIFY, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [(field, "required") for field in fields]


# --- Caso 9 ----------------------------------------------------------------


def test_verify_with_an_expired_code_is_rejected(api):
    form = register(api)
    age_codes(api, form["email"], 301)

    response = api.client.post(VERIFY, json={"email": form["email"], "code": api.sender.last_code})

    assert response.status_code == 400
    assert errors_of(response) == [("code", "code_expired")]
    assert one(api, "select email_verified_at from users where email = %s", form["email"])[0] is None


def test_verify_one_second_before_expiring_still_works(api):
    form = register(api)
    age_codes(api, form["email"], 299)

    response = api.client.post(VERIFY, json={"email": form["email"], "code": api.sender.last_code})

    assert response.status_code == 200


# ===========================================================================
# POST /auth/resend-code
# ===========================================================================

# --- Caso 10 ---------------------------------------------------------------


def test_resend_before_60_seconds_is_rejected(api):
    form = register(api)

    response = api.client.post(RESEND, json={"email": form["email"]})

    assert response.status_code == 429
    assert errors_of(response) == [("email", "wait")]
    assert response.json()["retry_after"] == 60
    assert response.headers["retry-after"] == "60"
    assert len(api.sender.sent) == 1


def test_resend_at_59_seconds_is_still_rejected(api):
    form = register(api)
    age_codes(api, form["email"], 59)

    response = api.client.post(RESEND, json={"email": form["email"]})

    assert response.status_code == 429
    assert response.json()["retry_after"] == 1


def test_resend_after_60_seconds_sends_a_new_code_and_the_old_one_stops_working(api):
    form = register(api)
    old_code = api.sender.last_code
    age_codes(api, form["email"], 61)

    response = api.client.post(RESEND, json={"email": form["email"]})

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    assert len(api.sender.sent) == 2
    new_code = api.sender.last_code
    unused = one(
        api,
        "select count(*) from one_time_codes where used_at is null "
        "and user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert unused == 1

    if old_code != new_code:  # uno en un millón: el código nuevo salió igual al viejo
        old = api.client.post(VERIFY, json={"email": form["email"], "code": old_code})
        assert old.status_code == 400
        assert errors_of(old) == [("code", "invalid_code")]
    new = api.client.post(VERIFY, json={"email": form["email"], "code": new_code})
    assert new.status_code == 200


# --- Caso 11 ---------------------------------------------------------------


def test_more_than_five_codes_in_an_hour_is_rejected(api):
    form = register(api)  # código 1
    for _ in range(4):  # códigos 2 a 5
        age_codes(api, form["email"], 61)
        assert api.client.post(RESEND, json={"email": form["email"]}).status_code == 200
    age_codes(api, form["email"], 61)

    response = api.client.post(RESEND, json={"email": form["email"]})  # sería el sexto

    assert response.status_code == 429
    assert errors_of(response) == [("email", "hourly_limit")]
    assert len(api.sender.sent) == 5


def test_after_the_hour_passes_codes_can_be_requested_again(api):
    form = register(api)
    for _ in range(4):
        age_codes(api, form["email"], 61)
        api.client.post(RESEND, json={"email": form["email"]})
    age_codes(api, form["email"], 3601)

    response = api.client.post(RESEND, json={"email": form["email"]})

    assert response.status_code == 200
    assert len(api.sender.sent) == 6


# --- Límites ---------------------------------------------------------------


def test_resend_for_an_email_without_account_answers_the_same_and_sends_nothing(api):
    response = api.client.post(RESEND, json={"email": f"nadie.{uuid4().hex[:8]}@prueba.invalid"})

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    assert api.sender.sent == []


def test_resend_for_a_verified_email_sends_nothing(api):
    form = register(api)
    api.client.post(VERIFY, json={"email": form["email"], "code": api.sender.last_code})
    age_codes(api, form["email"], 61)

    response = api.client.post(RESEND, json={"email": form["email"]})

    assert response.status_code == 200
    assert len(api.sender.sent) == 1


@pytest.mark.parametrize("body", [{}, {"email": ""}, {"email": None}, {"email": 5}])
def test_resend_without_email_is_rejected(api, body):
    response = api.client.post(RESEND, json=body)

    assert response.status_code == 422
    assert errors_of(response) == [("email", "required")]


@pytest.mark.parametrize("path", [REGISTER, VERIFY, RESEND])
def test_account_routes_only_accept_post(api, path):
    assert api.client.get(path).status_code == 405


def test_openapi_lists_the_account_routes(api):
    paths = api.client.get("/openapi.json").json()["paths"]

    assert {REGISTER, VERIFY, RESEND} <= set(paths)
