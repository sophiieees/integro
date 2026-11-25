"""Casos de la pieza 3.1, "perfil de anfitrión".

Especificación confirmada por Sophia el 24 de noviembre de 2026 (bitácora 42.2):

    POST /api/v1/host-profile
     1. Con sesión y correo verificado, sin perfil: 201. Queda una fila en host_profiles con su user_id, nivel «new» y
        sin datos de Stripe ni de la CLABE. Después /auth/me dice is_host: true.
     2. Sin sesión: 401.
     3. Sin las defensas de origen y clave anti-falsificación: 403 y no se crea nada.
     4. Sesión abierta pero correo sin verificar: 403 y no se crea nada.
     6. Mandar el user_id de otra persona en el cuerpo no crea nada para ella: solo cuenta la sesión.
     7. Si ya tiene perfil y lo vuelve a pedir: 200 con el que tiene. Un perfil «verified» o «suspended» nunca vuelve a
        «new» por pedirlo otra vez.
     8. Dos peticiones no dejan dos filas.
    GET /api/v1/host-profile
     5. Con perfil: 200 con su nivel y la fecha en que se creó. Sin perfil: 404. Sin sesión: 401.
     6. Con dos personas, cada una ve solo el suyo.
     9. La respuesta nunca incluye la cuenta de Stripe.
    Lo que se activa solo, y ya existía
    10. La sesión de quien se vuelve anfitriona pasa de 30 a 7 días sin uso (ADR 0014).
    11. Un administrador también puede pedirlo: son dos permisos distintos.

No van aquí: el Authenticator (pieza 3.3), la verificación de identidad (pieza 3.5) ni las pantallas (pieza 3.4).

Corren contra la base real con rollback_pool: todo se deshace al terminar cada prueba.
"""

from datetime import datetime
from uuid import uuid4

import psycopg
import pytest
from conftest import session_cookie, with_session
from test_accounts_login import ME, errors_of, login, one, register, run
from test_accounts_logout import LOGOUT, OTHER_SITE, OWN_ORIGIN, change
from test_view_roles import make_admin

from app.api.captcha import CAPTCHA_HEADER
from app.database.transaction import system_transaction, user_transaction
from app.modules.hosts.profile import RequestOutcome, read_host_profile, request_host_profile

HOST_PROFILE = "/api/v1/host-profile"
DAY = 24 * 60 * 60


def person(api, first_name="Ana"):
    """Una persona con el correo comprobado y una sesión abierta: (formulario, llave de la sesión)."""
    form = register(api, first_name=first_name)
    return form, login(api, form)


def user_id_of(api, email):
    return one(api, "select id from users where email = %s", email)[0]


def profiles_of(api, email):
    """Las filas de host_profiles de esa persona, como las ve el sistema."""
    with system_transaction(api.pool) as connection:
        return connection.execute(
            "select h.level, h.stripe_account_id, h.clabe_last4, h.user_id from host_profiles h "
            "join users u on u.id = h.user_id where u.email = %s",
            (email,),
        ).fetchall()


def ask(api, token, **kwargs):
    return api.client.post(HOST_PROFILE, headers=change(api, token), **kwargs)


def see(api, token):
    return api.client.get(HOST_PROFILE, headers=with_session(token))


# --- Caso 1: pedirlo ------------------------------------------------------------------------------------------------


def test_a_person_with_a_session_asks_and_gets_a_profile_of_level_new(api):
    form, token = person(api)

    response = ask(api, token)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"level", "created_at"}
    assert body["level"] == "new"
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert profiles_of(api, form["email"]) == [("new", None, None, user_id_of(api, form["email"]))]


def test_before_asking_me_says_not_host_and_right_after_it_says_host(api):
    form, token = person(api)
    assert api.client.get(ME, headers=with_session(token)).json()["is_host"] is False

    assert ask(api, token).status_code == 201

    assert api.client.get(ME, headers=with_session(token)).json()["is_host"] is True


def test_the_request_needs_no_body(api):
    form, token = person(api)

    response = api.client.post(HOST_PROFILE, headers=change(api, token))

    assert response.status_code == 201
    assert response.request.content == b""


def test_asking_does_not_go_through_the_captcha(api):
    form, token = person(api)
    # Registrarse e iniciar sesión sí pasan por el CAPTCHA: aquí solo cuenta lo que pase desde ahora.
    api.captcha.seen.clear()
    api.client.headers.pop(CAPTCHA_HEADER, None)

    assert ask(api, token).status_code == 201
    assert api.captcha.seen == []


# --- Caso 2: sin sesión ----------------------------------------------------------------------------------------------


def test_without_a_session_both_routes_say_401(api):
    asked = api.client.post(HOST_PROFILE, headers={"Origin": OWN_ORIGIN})
    seen = api.client.get(HOST_PROFILE)

    assert asked.status_code == 401 and seen.status_code == 401
    assert errors_of(asked) == errors_of(seen) == [("authorization", "not_authenticated")]


def test_a_made_up_session_key_is_401(api):
    assert see(api, "llave-inventada").status_code == 401
    assert api.client.post(HOST_PROFILE, headers={**with_session("llave-inventada"), "Origin": OWN_ORIGIN}).status_code == 401


def test_a_closed_session_cannot_ask_or_see(api):
    form, token = person(api)
    assert api.client.post(LOGOUT, headers=change(api, token)).status_code == 200

    assert ask(api, token).status_code == 401
    assert see(api, token).status_code == 401
    assert profiles_of(api, form["email"]) == []


# --- Caso 3: las defensas de una ruta que cambia algo ---------------------------------------------------------------


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"Origin": None}, "origin_not_allowed"),
        ({"Origin": OTHER_SITE}, "origin_not_allowed"),
        ({"Origin": "null"}, "origin_not_allowed"),
        ({"X-CSRF-Token": None}, "csrf_failed"),
        ({"X-CSRF-Token": "clave-inventada"}, "csrf_failed"),
    ],
)
def test_without_the_defenses_nothing_is_created(api, extra, code):
    form, token = person(api)

    response = api.client.post(HOST_PROFILE, headers=change(api, token, **extra))

    assert response.status_code == 403
    assert errors_of(response) == [("request", code)]
    assert profiles_of(api, form["email"]) == []


def test_the_key_of_another_session_does_not_work(api):
    form, token = person(api)
    other_form, other_token = person(api, first_name="Beatriz")
    from app.api.protection import CSRF_HEADER, csrf_token

    response = api.client.post(HOST_PROFILE, headers=change(api, token, **{CSRF_HEADER: csrf_token(other_token, api.settings)}))

    assert response.status_code == 403
    assert profiles_of(api, form["email"]) == [] and profiles_of(api, other_form["email"]) == []


def test_seeing_the_profile_only_reads_so_it_needs_only_the_session(api):
    form, token = person(api)
    ask(api, token)

    assert api.client.get(HOST_PROFILE, headers=with_session(token)).status_code == 200


# --- Caso 4: el correo sin verificar ---------------------------------------------------------------------------------


def test_a_session_whose_email_is_no_longer_verified_is_refused_and_nothing_is_created(api):
    form, token = person(api)
    run(api, "update users set email_verified_at = null where email = %s", form["email"])

    response = ask(api, token)

    assert response.status_code == 403
    assert response.json() == {
        "errors": [
            {"field": "email", "code": "email_not_verified", "message": "Comprueba tu correo antes de pedir tu perfil de anfitrión."}
        ]
    }
    assert profiles_of(api, form["email"]) == []


def test_a_person_that_does_not_exist_gets_no_profile(api):
    result = request_host_profile(api.pool, uuid4())

    assert result.outcome is RequestOutcome.EMAIL_NOT_VERIFIED
    assert result.profile is None


# --- Caso 5: verlo ---------------------------------------------------------------------------------------------------


def test_seeing_the_profile_gives_the_level_and_the_date_it_was_created(api):
    form, token = person(api)
    asked = ask(api, token)

    response = see(api, token)

    assert response.status_code == 200
    assert response.json() == asked.json()
    assert set(response.json()) == {"level", "created_at"}


def test_without_a_profile_seeing_it_says_404(api):
    form, token = person(api)

    response = see(api, token)

    assert response.status_code == 404
    assert response.json() == {
        "errors": [{"field": "host_profile", "code": "no_host_profile", "message": "Todavía no tienes perfil de anfitrión."}]
    }


# --- Caso 6: cada quien lo suyo --------------------------------------------------------------------------------------


def test_the_user_id_of_someone_else_in_the_body_creates_nothing_for_them(api):
    form, token = person(api)
    other_form, other_token = person(api, first_name="Beatriz")
    other_id = str(user_id_of(api, other_form["email"]))

    response = ask(api, token, json={"user_id": other_id, "level": "verified", "stripe_account_id": "acct_ajena"})

    assert response.status_code == 201
    assert response.json()["level"] == "new"
    assert profiles_of(api, form["email"]) == [("new", None, None, user_id_of(api, form["email"]))]
    assert profiles_of(api, other_form["email"]) == []


def test_the_address_takes_no_user_id(api):
    form, token = person(api)
    other_form, _ = person(api, first_name="Beatriz")
    other_id = user_id_of(api, other_form["email"])

    assert api.client.post(f"{HOST_PROFILE}/{other_id}", headers=change(api, token)).status_code == 404
    assert api.client.get(f"{HOST_PROFILE}/{other_id}", headers=with_session(token)).status_code == 404
    assert api.client.get(f"{HOST_PROFILE}?user_id={other_id}", headers=with_session(token)).status_code == 404
    assert profiles_of(api, other_form["email"]) == []


def test_each_of_two_people_sees_only_their_own_profile(api):
    form, token = person(api)
    other_form, other_token = person(api, first_name="Beatriz")
    ask(api, token)
    assert see(api, other_token).status_code == 404

    run(api, "update host_profiles set level = 'verified' where user_id = %s", user_id_of(api, form["email"]))
    ask(api, other_token)

    assert see(api, token).json()["level"] == "verified"
    assert see(api, other_token).json()["level"] == "new"


def test_the_database_itself_only_hands_a_person_their_own_row(api):
    form, token = person(api)
    other_form, other_token = person(api, first_name="Beatriz")
    ask(api, token)
    ask(api, other_token)
    mine, theirs = user_id_of(api, form["email"]), user_id_of(api, other_form["email"])

    with user_transaction(api.pool, mine) as connection:
        rows = connection.execute("select user_id from host_profiles").fetchall()
        asking_for_theirs = connection.execute("select user_id from host_profiles where user_id = %s", (theirs,)).fetchall()

    assert rows == [(mine,)]
    assert asking_for_theirs == []
    assert read_host_profile(api.pool, mine).level == "new"


def test_a_person_cannot_write_their_own_profile_in_the_database(api):
    form, token = person(api)
    mine = user_id_of(api, form["email"])

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_transaction(api.pool, mine) as connection:
            connection.execute("insert into host_profiles (user_id, level) values (%s, 'verified')", (mine,))


# --- Caso 7: volver a pedirlo ----------------------------------------------------------------------------------------


def test_asking_again_gives_the_same_profile_with_200_and_no_second_row(api):
    form, token = person(api)
    first = ask(api, token)

    second = ask(api, token)
    third = ask(api, token)

    assert (first.status_code, second.status_code, third.status_code) == (201, 200, 200)
    assert second.json() == first.json() == third.json()
    assert len(profiles_of(api, form["email"])) == 1


@pytest.mark.parametrize("level", ["verified", "suspended"])
def test_a_profile_that_moved_on_never_goes_back_to_new_by_asking_again(api, level):
    form, token = person(api)
    ask(api, token)
    run(api, "update host_profiles set level = %s where user_id = %s", level, user_id_of(api, form["email"]))

    response = ask(api, token)

    assert response.status_code == 200
    assert response.json()["level"] == level
    assert [row[0] for row in profiles_of(api, form["email"])] == [level]
    assert see(api, token).json()["level"] == level


# --- Caso 8: nunca dos filas -----------------------------------------------------------------------------------------


def test_the_function_twice_gives_created_and_then_existing(api):
    form, _ = person(api)
    mine = user_id_of(api, form["email"])

    first = request_host_profile(api.pool, mine)
    second = request_host_profile(api.pool, mine)

    assert (first.outcome, second.outcome) == (RequestOutcome.CREATED, RequestOutcome.EXISTING)
    assert second.profile == first.profile
    assert len(profiles_of(api, form["email"])) == 1


def test_the_database_refuses_a_second_profile_for_the_same_person(api):
    """La regla de único es la que sostiene «una sola fila» cuando dos peticiones llegan a la vez."""
    form, token = person(api)
    ask(api, token)
    mine = user_id_of(api, form["email"])

    with pytest.raises(psycopg.errors.UniqueViolation):
        with system_transaction(api.pool) as connection:
            connection.execute("insert into host_profiles (user_id) values (%s)", (mine,))


# --- Caso 9: lo que nunca sale ---------------------------------------------------------------------------------------


def test_the_stripe_account_and_the_clabe_never_leave(api):
    form, token = person(api)
    ask(api, token)
    run(
        api,
        "update host_profiles set stripe_account_id = 'acct_SecretoDeStripe9', clabe_last4 = '9876' where user_id = %s",
        user_id_of(api, form["email"]),
    )

    for response in (see(api, token), ask(api, token)):
        assert set(response.json()) == {"level", "created_at"}
        assert "acct_" not in response.text and "stripe" not in response.text.lower()


def test_the_profile_cannot_be_changed_or_deleted_through_the_api(api):
    form, token = person(api)
    ask(api, token)

    for method in ("PUT", "PATCH", "DELETE"):
        assert api.client.request(method, HOST_PROFILE, headers=change(api, token)).status_code == 405
    assert [row[0] for row in profiles_of(api, form["email"])] == ["new"]


# --- Caso 10: la sesión de quien se vuelve anfitriona ----------------------------------------------------------------


def test_the_session_goes_from_thirty_to_seven_days_without_use_once_the_person_is_a_host(api):
    form, token = person(api)
    before = session_cookie(api.client.get(ME, headers=with_session(token)))
    assert before["max-age"] == str(30 * DAY)

    ask(api, token)

    after = session_cookie(api.client.get(ME, headers=with_session(token)))
    assert after["max-age"] == str(7 * DAY)


# --- Caso 11: un administrador ---------------------------------------------------------------------------------------


def test_an_administrator_can_ask_too_and_is_both_things(api):
    form, token = person(api)
    make_admin(api, form["email"])
    assert api.client.get(ME, headers=with_session(token)).json()["is_admin"] is True

    response = ask(api, token)

    assert response.status_code == 201
    me = api.client.get(ME, headers=with_session(token)).json()
    assert (me["is_admin"], me["is_host"]) == (True, True)


# --- La documentación de la API --------------------------------------------------------------------------------------


def test_the_api_documentation_lists_both_routes_and_their_answers(api):
    path = api.client.get("/openapi.json").json()["paths"][HOST_PROFILE]

    assert set(path) == {"post", "get"}
    assert {"200", "201", "401", "403"} <= set(path["post"]["responses"])
    assert {"200", "401", "404"} <= set(path["get"]["responses"])
    assert "requestBody" not in path["post"]
