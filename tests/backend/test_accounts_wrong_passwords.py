"""Casos de la pieza "contraseñas incorrectas".

Especificación aceptada por Sophia el 18 de noviembre de 2026 (ADR 0014). El
aviso se cuenta por cuenta y la espera por dispositivo (dirección y navegador):

     1. Primer y segundo fallo: 401 como hoy; se anotan; no hay aviso.
     2. Tercer fallo seguido en la cuenta: 401 y se envía un aviso al correo
        del dueño, una sola vez.
     3. Cuarto y quinto fallo: 401, sin más avisos.
     4. Sexto fallo desde el mismo dispositivo: 401. Desde ahí ese dispositivo
        recibe 429 "intenta más tarde" con los segundos que faltan, aunque
        escriba la contraseña correcta.
     5. Durante esa espera, otra persona entra a la misma cuenta desde otro
        dispositivo: 200. La cuenta no está bloqueada.
     6. Pasados 15 minutos, el dispositivo que esperaba escribe la contraseña
        correcta: 200.
     7. Entrar bien reinicia la cuenta de fallos: 2 fallos, 1 acierto,
        2 fallos: sin aviso.
     8. Los fallos de hace más de 15 minutos no cuentan.
     9. Correo sin cuenta: los fallos se anotan y cuentan para la espera del
        dispositivo; no hay a quién avisar.
    10. Nada cambia en la cuenta: sigue con su contraseña y sus sesiones
        abiertas.

Corren contra la base real con rollback_pool: todo se deshace al terminar.
Los avisos y los códigos no se envían: la prueba los lee de un anotador.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from conftest import session_cookie, with_session

from app.database.transaction import system_transaction
from app.modules.accounts.attempts import clean_user_agent, email_for_record
from app.notifications.console import ConsoleCodeSender

REGISTER = "/api/v1/auth/register"
VERIFY_EMAIL = "/api/v1/auth/verify-email"
LOGIN = "/api/v1/auth/login"
LOGIN_VERIFY = "/api/v1/auth/login/verify"
ME = "/api/v1/auth/me"

PASSWORD = "Ejemplo-2026"
WRONG = "Ejemplo-2027"
PHONE = {"User-Agent": "Celular de prueba"}
COMPUTER = {"User-Agent": "Computadora de prueba"}


def errors_of(response) -> list[tuple[str, str]]:
    return [(error["field"], error["code"]) for error in response.json()["errors"]]


def one(api, query: str, *parameters):
    with system_transaction(api.pool) as connection:
        return connection.execute(query, parameters).fetchone()


def register(api, first_name: str = "Ana", verified: bool = True) -> dict:
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
        assert api.client.post(
            VERIFY_EMAIL, json={"email": form["email"], "code": api.sender.last_code}
        ).status_code == 200
    return form


def try_login(api, email: str, password: str, device: dict = PHONE):
    return api.client.post(LOGIN, json={"email": email, "password": password}, headers=device)


def fail(api, email: str, times: int, device: dict = PHONE) -> list:
    """Escribe una contraseña incorrecta tantas veces. Devuelve las respuestas."""
    return [try_login(api, email, WRONG, device) for _ in range(times)]


def old_failures(api, email: str, times: int, minutes_ago: int, device: dict = PHONE) -> None:
    """Anota fallos como si hubieran ocurrido hace tantos minutos (los intentos no se pueden cambiar)."""
    with system_transaction(api.pool) as connection:
        for _ in range(times):
            connection.execute(
                "insert into login_attempts (email, user_id, succeeded, user_agent, created_at) "
                "values (%s, (select id from users where email = %s), false, %s, "
                "clock_timestamp() - make_interval(mins => %s))",
                (email, email, device["User-Agent"], minutes_ago),
            )


def attempts(api, email: str) -> list[tuple]:
    """Intentos anotados para ese correo, del más viejo al más nuevo."""
    with system_transaction(api.pool) as connection:
        return connection.execute(
            "select succeeded, user_id is not null, user_agent, host(ip_address) from login_attempts "
            "where email = %s order by created_at",
            (email,),
        ).fetchall()


def age_codes(api, email: str, seconds: int) -> None:
    with system_transaction(api.pool) as connection:
        connection.execute(
            "update one_time_codes set created_at = created_at - make_interval(secs => %s), "
            "expires_at = expires_at - make_interval(secs => %s) "
            "where user_id = (select id from users where email = %s)",
            (seconds, seconds, email),
        )


# --- Caso 1 ----------------------------------------------------------------


def test_first_and_second_failure_are_noted_and_send_no_notice(api):
    form = register(api)

    responses = fail(api, form["email"], 2)

    assert [response.status_code for response in responses] == [401, 401]
    assert errors_of(responses[-1]) == [("credentials", "invalid_credentials")]
    assert attempts(api, form["email"]) == [(False, True, "Celular de prueba", None)] * 2
    assert api.sender.notices == []


def test_a_right_password_is_noted_as_a_success(api):
    form = register(api)

    assert try_login(api, form["email"], PASSWORD).status_code == 200

    assert attempts(api, form["email"]) == [(True, True, "Celular de prueba", None)]


# --- Caso 2 ----------------------------------------------------------------


def test_third_failure_in_a_row_sends_one_notice_to_the_owner(api):
    form = register(api)

    responses = fail(api, form["email"], 3)

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert len(api.sender.notices) == 1
    notice = api.sender.notices[0]
    assert (notice["channel"], notice["destination"], notice["kind"]) == ("email", form["email"], "failed_logins")
    details = notice["details"]
    assert details["failures"] == 3
    assert details["user_agent"] == "Celular de prueba"
    assert details["ip_address"] is None  # el cliente de pruebas no tiene dirección
    assert abs((datetime.now(timezone.utc) - details["at"]).total_seconds()) < 60


def test_the_notice_never_carries_a_password(api):
    form = register(api)

    fail(api, form["email"], 3)

    assert WRONG not in repr(api.sender.notices) and PASSWORD not in repr(api.sender.notices)


def test_the_third_failure_answers_like_any_other(api):
    """Quien intenta no se entera de que se avisó al dueño."""
    form = register(api)

    first, _, third = fail(api, form["email"], 3)

    assert third.status_code == first.status_code == 401
    assert third.json() == first.json()


def test_failures_from_two_devices_add_up_for_the_notice_but_nobody_waits(api):
    form = register(api)

    fail(api, form["email"], 2, PHONE)
    fail(api, form["email"], 1, COMPUTER)

    assert len(api.sender.notices) == 1
    assert try_login(api, form["email"], PASSWORD, PHONE).status_code == 200


# --- Caso 3 ----------------------------------------------------------------


def test_fourth_and_fifth_failure_send_no_more_notices(api):
    form = register(api)

    responses = fail(api, form["email"], 5)

    assert [response.status_code for response in responses] == [401] * 5
    assert len(api.sender.notices) == 1


# --- Caso 4 ----------------------------------------------------------------


def test_after_the_sixth_failure_that_device_must_wait_even_with_the_right_password(api):
    form = register(api)
    responses = fail(api, form["email"], 6)
    assert [response.status_code for response in responses] == [401] * 6
    codes_before = len(api.sender.sent)

    response = try_login(api, form["email"], PASSWORD)

    assert response.status_code == 429
    assert errors_of(response) == [("credentials", "try_later")]
    retry_after = response.json()["retry_after"]
    assert 890 <= retry_after <= 900
    assert response.headers["retry-after"] == str(retry_after)
    assert "15 minutos" in response.json()["errors"][0]["message"]
    assert len(api.sender.sent) == codes_before


def test_while_waiting_attempts_are_not_noted_so_the_wait_does_not_grow(api):
    form = register(api)
    fail(api, form["email"], 6)

    waiting = [try_login(api, form["email"], WRONG), try_login(api, form["email"], PASSWORD)]

    assert [response.status_code for response in waiting] == [429, 429]
    assert len(attempts(api, form["email"])) == 6
    assert len(api.sender.notices) == 1


def test_five_failures_do_not_make_the_device_wait(api):
    form = register(api)
    fail(api, form["email"], 5)

    assert try_login(api, form["email"], PASSWORD).status_code == 200


def test_the_wait_is_for_the_device_against_any_account(api):
    ana = register(api, "Ana")
    beto = register(api, "Beto")
    fail(api, ana["email"], 3)
    fail(api, beto["email"], 3)

    response = try_login(api, beto["email"], PASSWORD)

    assert response.status_code == 429
    # Cada cuenta llegó a 3 fallos: se avisó a los dos dueños.
    assert sorted(notice["destination"] for notice in api.sender.notices) == sorted([ana["email"], beto["email"]])


# --- Caso 5 ----------------------------------------------------------------


def test_while_one_device_waits_another_device_enters_the_same_account(api):
    form = register(api)
    fail(api, form["email"], 6, PHONE)
    assert try_login(api, form["email"], PASSWORD, PHONE).status_code == 429

    response = try_login(api, form["email"], PASSWORD, COMPUTER)

    assert response.status_code == 200
    assert response.json() == {"status": "code_required"}


# --- Caso 6 ----------------------------------------------------------------


def test_after_15_minutes_the_device_can_enter_again(api):
    form = register(api)
    old_failures(api, form["email"], 6, minutes_ago=16)

    response = try_login(api, form["email"], PASSWORD)

    assert response.status_code == 200


def test_one_minute_before_the_15_the_device_still_waits(api):
    form = register(api)
    old_failures(api, form["email"], 6, minutes_ago=14)

    response = try_login(api, form["email"], PASSWORD)

    assert response.status_code == 429
    assert 50 <= response.json()["retry_after"] <= 60
    assert response.json()["errors"][0]["message"].endswith("en 1 minuto.")


def test_after_the_wait_the_count_starts_again(api):
    form = register(api)
    old_failures(api, form["email"], 6, minutes_ago=16)

    responses = fail(api, form["email"], 5)

    assert [response.status_code for response in responses] == [401] * 5
    assert try_login(api, form["email"], PASSWORD).status_code == 200


# --- Caso 7 ----------------------------------------------------------------


def test_entering_right_restarts_the_count_of_the_account(api):
    form = register(api)
    fail(api, form["email"], 2)
    assert try_login(api, form["email"], PASSWORD).status_code == 200

    fail(api, form["email"], 2)

    assert api.sender.notices == []


def test_after_a_success_three_new_failures_send_the_notice(api):
    form = register(api)
    fail(api, form["email"], 2)
    try_login(api, form["email"], PASSWORD)

    fail(api, form["email"], 3)

    assert len(api.sender.notices) == 1
    assert api.sender.notices[0]["details"]["failures"] == 3


# --- Caso 8 ----------------------------------------------------------------


def test_failures_older_than_15_minutes_do_not_count_for_the_notice(api):
    form = register(api)
    old_failures(api, form["email"], 2, minutes_ago=16)

    fail(api, form["email"], 1)

    assert api.sender.notices == []


def test_failures_older_than_15_minutes_do_not_count_for_the_wait(api):
    form = register(api)
    old_failures(api, form["email"], 5, minutes_ago=16)

    fail(api, form["email"], 1)

    assert try_login(api, form["email"], PASSWORD).status_code == 200


def test_recent_failures_do_count(api):
    form = register(api)
    old_failures(api, form["email"], 2, minutes_ago=14)

    fail(api, form["email"], 1)

    assert len(api.sender.notices) == 1


# --- Caso 9 ----------------------------------------------------------------


def test_failures_for_an_email_without_account_are_noted_and_make_the_device_wait(api):
    email = f"nadie.{uuid4().hex[:8]}@prueba.invalid"

    responses = fail(api, email, 6)

    assert [response.status_code for response in responses] == [401] * 6
    assert attempts(api, email) == [(False, False, "Celular de prueba", None)] * 6
    assert api.sender.notices == []
    assert try_login(api, email, WRONG).status_code == 429


def test_what_was_written_instead_of_an_email_is_not_stored(api):
    before = one(api, "select count(*) from login_attempts where email is null")[0]

    response = try_login(api, "no es un correo'; drop table users; --", WRONG)

    assert response.status_code == 401
    assert one(api, "select count(*) from login_attempts where email is null")[0] == before + 1


def test_unverified_account_gets_no_notice(api):
    """Solo se avisa a un correo que ya se comprobó que es de la persona."""
    form = register(api, verified=False)

    responses = fail(api, form["email"], 3)

    assert [response.status_code for response in responses] == [401] * 3
    assert api.sender.notices == []
    assert len(attempts(api, form["email"])) == 3


# --- Caso 10 ---------------------------------------------------------------


def test_nothing_changes_in_the_account(api):
    form = register(api)
    age_codes(api, form["email"], 61)
    try_login(api, form["email"], PASSWORD, COMPUTER)
    token = session_cookie(
        api.client.post(LOGIN_VERIFY, json={"email": form["email"], "code": api.sender.last_code}, headers=COMPUTER)
    ).value
    api.client.cookies.clear()
    before = one(
        api,
        "select c.password_hash, c.updated_at, u.updated_at, u.email_verified_at from users u "
        "join user_credentials c on c.user_id = u.id where u.email = %s",
        form["email"],
    )

    fail(api, form["email"], 6, PHONE)

    after = one(
        api,
        "select c.password_hash, c.updated_at, u.updated_at, u.email_verified_at from users u "
        "join user_credentials c on c.user_id = u.id where u.email = %s",
        form["email"],
    )
    assert after == before
    # La sesión que ya estaba abierta sigue sirviendo.
    assert api.client.get(ME, headers={**with_session(token), **COMPUTER}).status_code == 200
    open_sessions = one(
        api,
        "select count(*) from sessions where revoked_at is null "
        "and user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert open_sessions == 1


# --- Límites y piezas sueltas ----------------------------------------------


def test_the_numbers_come_from_the_settings(api):
    form = register(api)
    api.client.app.state.settings = api.settings.model_copy(
        update={"login_notice_after_failures": 2, "login_wait_after_failures": 3, "login_wait_minutes": 5}
    )

    responses = fail(api, form["email"], 3)
    waiting = try_login(api, form["email"], PASSWORD)

    assert [response.status_code for response in responses] == [401] * 3
    assert len(api.sender.notices) == 1 and api.sender.notices[0]["details"]["failures"] == 2
    assert waiting.status_code == 429
    assert 290 <= waiting.json()["retry_after"] <= 300


def test_the_same_browser_from_another_address_is_another_device(api):
    """Seis fallos anotados con una dirección no hacen esperar al mismo navegador sin esa dirección."""
    form = register(api)
    with system_transaction(api.pool) as connection:
        for _ in range(6):
            connection.execute(
                "insert into login_attempts (email, succeeded, ip_address, user_agent, created_at) "
                "values (%s, false, '203.0.113.7', %s, clock_timestamp())",
                (form["email"], PHONE["User-Agent"]),
            )

    assert try_login(api, form["email"], PASSWORD, PHONE).status_code == 200


@pytest.mark.parametrize(
    "written, stored",
    [
        ("ana@prueba.invalid", "ana@prueba.invalid"),
        ("  Ana@Prueba.INVALID ", "ana@prueba.invalid"),
        ("sin-arroba", None),
        ("", None),
        ("a" * 250 + "@x.mx", None),
        ("ana maria@prueba.invalid", None),
    ],
)
def test_email_as_it_is_noted(written, stored):
    assert email_for_record(written) == stored


@pytest.mark.parametrize("user_agent, stored", [("Firefox", "Firefox"), ("x" * 900, "x" * 500), ("", None), (None, None)])
def test_browser_name_as_it_is_noted(user_agent, stored):
    assert clean_user_agent(user_agent) == stored


def test_development_mode_writes_the_notice_in_the_server_window(capsys):
    ConsoleCodeSender().send_notice(
        channel="email",
        destination="ana@prueba.invalid",
        kind="failed_logins",
        details={
            "failures": 3,
            "at": datetime(2026, 11, 18, 12, 30, tzinfo=timezone.utc),
            "ip_address": "203.0.113.7",
            "user_agent": "Firefox",
        },
    )

    written = capsys.readouterr().out
    assert "MODO DESARROLLO" in written and "Aviso para ana@prueba.invalid" in written
    assert "Hubo 3 intentos fallidos" in written
    assert "2026-11-18 12:30:00" in written and "Firefox" in written and "203.0.113.7" in written
