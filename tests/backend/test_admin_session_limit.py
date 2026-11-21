"""Casos de la pieza "tope de sesión del administrador".

Decisiones de Sophia del 21 de noviembre de 2026 (ADR 0014): quien es administrador (tabla admins) tiene una sesión
corta en TODO el sitio, no solo en las pantallas de administración; se cierra a los 30 minutos sin uso y, aunque se
use todo el tiempo, a las 12 horas de haber iniciado sesión.

     1. Al iniciar sesión, la sesión de un administrador vence a los 30 minutos y su cookie dura 30 minutos; la cookie
        se vuelve a entregar con lo que le queda en cada uso.
     2. Con 29 minutos sin uso la sesión sirve; con 31, no: la petición es 401 y la sesión queda cerrada en la base.
     3. Cada uso renueva los 30 minutos.
     4. A las 12 horas de haber iniciado sesión se cierra aunque se haya usado hace un minuto; poco antes, sirve, y
        el vencimiento no pasa del tope.
     5. Los demás no cambian: un huésped sigue en 30 días y un anfitrión en 7, y no se les aplica nada de esto.
     6. Se lee el papel en cada petición: quien se vuelve administrador pierde su sesión vieja si pasó el tiempo, y quien
        deja de serlo vuelve a las reglas normales. Si es anfitrión y administrador, gana el límite del administrador.
     7. Los tiempos salen de la configuración. Cada sesión es independiente de las otras de la misma persona.

El tiempo se simula moviendo hacia el pasado las fechas de la sesión en la base. Corren contra la base real con
rollback_pool: todo se deshace al terminar cada prueba. La tabla admins solo se llena en pgAdmin y las pruebas no
tienen permiso de escribir en ella: se usa la tabla temporal de test_view_roles.py.
"""

import pytest
from conftest import session_cookie, with_session
from test_accounts_login import ME, LOGIN, LOGIN_VERIFY, PASSWORD, age_codes, login, make_host, one, register, run
from test_session_cookie import use_settings, verify
from test_view_roles import make_admin, remove_admin

MINUTE = 60
HOUR = 60 * MINUTE


def admin_with_session(api, **kwargs):
    form = register(api, **kwargs)
    make_admin(api, form["email"])
    return form, login(api, form)


def session_row(api, email):
    """(cerrada, segundos de vida que le quedan, segundos desde que se abrió, segundos desde su último uso)."""
    return one(
        api,
        "select revoked_at is not null, extract(epoch from expires_at - now()), extract(epoch from now() - created_at), "
        "extract(epoch from now() - last_used_at) from sessions "
        "where user_id = (select id from users where email = %s) order by created_at desc limit 1",
        email,
    )


def age(api, email, *, idle_minutes=0, open_hours=0, token=None):
    """Hace que una sesión de esa persona parezca abierta hace `open_hours` y sin uso hace `idle_minutes`.

    Si hay varias, se dice cuál con su llave (en las pruebas, todas se abren en la misma transacción y quedan con la
    misma hora de creación, así que «la más reciente» no existe). Sin llave, la única que tenga.
    """
    from app.modules.accounts.security import hash_session_token

    open_seconds = open_hours * HOUR + idle_minutes * MINUTE + 1
    where = "token_hash = %s" if token else "user_id = (select id from users where email = %s)"
    run(
        api,
        "update sessions set created_at = now() - make_interval(secs => %s), "
        "last_used_at = now() - make_interval(secs => %s), expires_at = now() + interval '20 minutes' "
        f"where {where}",
        open_seconds,
        idle_minutes * MINUTE,
        hash_session_token(token) if token else email,
    )


def me(api, token):
    return api.client.get(ME, headers=with_session(token))


# --- Caso 1: al iniciar sesión ---------------------------------------------------------------------


def test_the_session_of_an_admin_opens_for_thirty_minutes(api):
    form = register(api)
    make_admin(api, form["email"])

    cookie = session_cookie(verify(api, form))

    closed, left, _, _ = session_row(api, form["email"])
    assert closed is False and 1795 <= float(left) <= 1800
    assert cookie["max-age"] == str(30 * MINUTE)
    api.client.cookies.clear()


def test_the_cookie_of_an_admin_is_renewed_with_what_is_left_of_the_session(api):
    form, token = admin_with_session(api)

    response = me(api, token)

    assert response.status_code == 200
    assert int(session_cookie(response)["max-age"]) in range(1797, 1801)


def test_what_me_says_about_the_expiry_is_thirty_minutes_away(api):
    form, token = admin_with_session(api)

    body = me(api, token).json()

    assert body["is_admin"] is True
    from datetime import datetime, timezone

    seconds = (datetime.fromisoformat(body["session_expires_at"]) - datetime.now(timezone.utc)).total_seconds()
    assert 1700 <= seconds <= 1801


def test_the_expiry_is_stored_as_thirty_minutes_not_thirty_days(api):
    form, token = admin_with_session(api)

    _, left, _, _ = session_row(api, form["email"])

    assert float(left) < 31 * MINUTE


# --- Caso 2: el tiempo sin uso ---------------------------------------------------------------------------


def test_twenty_nine_minutes_without_use_still_works(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=29)

    assert me(api, token).status_code == 200


def test_thirty_one_minutes_without_use_closes_the_session(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=31)

    response = me(api, token)

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "not_authenticated"
    closed, _, _, _ = session_row(api, form["email"])
    assert closed is True


def test_once_closed_it_does_not_come_back(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=31)
    assert me(api, token).status_code == 401

    assert me(api, token).status_code == 401
    # Tampoco aunque se lleven las fechas otra vez a un tiempo que sí serviría.
    age(api, form["email"], idle_minutes=1)
    assert me(api, token).status_code == 401


def test_an_expired_admin_session_does_not_show_in_the_list_of_open_sessions(api):
    form, token = admin_with_session(api)
    other = login(api, form)
    age(api, form["email"], idle_minutes=31, token=other)
    assert me(api, other).status_code == 401

    count = one(
        api,
        "select count(*) from sessions where revoked_at is null and user_id = (select id from users where email = %s)",
        form["email"],
    )[0]
    assert count == 1


# --- Caso 3: cada uso renueva ---------------------------------------------------------------------------


def test_every_use_renews_the_thirty_minutes(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=20)
    assert me(api, token).status_code == 200  # a los 20 minutos: se renueva
    run(
        api,
        "update sessions set created_at = created_at - interval '20 minutes', last_used_at = last_used_at - interval '20 minutes', "
        "expires_at = now() + interval '10 minutes' where user_id = (select id from users where email = %s)",
        form["email"],
    )

    assert me(api, token).status_code == 200  # otros 20 minutos después del último uso: sirve


def test_using_it_moves_the_last_use_to_now(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=25)

    assert me(api, token).status_code == 200

    _, _, _, since_use = session_row(api, form["email"])
    assert float(since_use) < 5


# --- Caso 4: el tope de 12 horas ---------------------------------------------------------------------------


def test_after_twelve_hours_it_closes_even_if_it_was_used_a_minute_ago(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=1, open_hours=12)

    response = me(api, token)

    assert response.status_code == 401
    assert session_row(api, form["email"])[0] is True


def test_shortly_before_twelve_hours_it_still_works_and_the_expiry_does_not_pass_the_cap(api):
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=1, open_hours=11)
    run(
        api,
        "update sessions set created_at = now() - interval '11 hours 59 minutes', last_used_at = now() - interval '1 minute' "
        "where user_id = (select id from users where email = %s)",
        form["email"],
    )

    response = me(api, token)

    assert response.status_code == 200
    _, left, _, _ = session_row(api, form["email"])
    # Le queda como mucho un minuto (hasta las 12 horas), no los 30 minutos de siempre.
    assert 0 < float(left) <= 62
    assert int(session_cookie(response)["max-age"]) <= 62


def test_a_session_that_is_used_all_the_time_still_ends_at_twelve_hours(api):
    form, token = admin_with_session(api)
    for _ in range(3):
        assert me(api, token).status_code == 200
    age(api, form["email"], idle_minutes=0, open_hours=12)

    assert me(api, token).status_code == 401


# --- Caso 5: los demás no cambian --------------------------------------------------------------------------------


def test_a_guest_session_is_still_thirty_days_and_is_not_limited(api):
    form = register(api)
    token = login(api, form)
    age(api, form["email"], idle_minutes=31, open_hours=13)

    response = me(api, token)

    assert response.status_code == 200
    assert response.json()["is_admin"] is False
    _, left, _, _ = session_row(api, form["email"])
    assert 29 * 24 * HOUR < float(left) <= 30 * 24 * HOUR
    assert session_cookie(response)["max-age"] == str(30 * 24 * HOUR)


def test_a_host_session_is_still_seven_days_and_is_not_limited(api):
    form = register(api)
    make_host(api, form["email"])
    token = login(api, form)
    age(api, form["email"], idle_minutes=31, open_hours=13)

    response = me(api, token)

    assert response.status_code == 200
    assert session_cookie(response)["max-age"] == str(7 * 24 * HOUR)


def test_the_session_of_another_person_is_not_touched_when_an_admin_expires(api):
    admin, admin_token = admin_with_session(api, first_name="Ana")
    guest = register(api, first_name="Beto")
    guest_token = login(api, guest)
    age(api, admin["email"], idle_minutes=31)

    assert me(api, admin_token).status_code == 401

    assert me(api, guest_token).status_code == 200


# --- Caso 6: el papel se lee en cada petición ---------------------------------------------------------------------------


def test_someone_who_becomes_admin_loses_an_old_session_if_the_time_has_passed(api):
    form = register(api)
    token = login(api, form)
    age(api, form["email"], idle_minutes=60)
    assert me(api, token).status_code == 200  # todavía no es administradora: la sesión sirve
    age(api, form["email"], idle_minutes=60)
    make_admin(api, form["email"])

    assert me(api, token).status_code == 401


def test_someone_who_becomes_admin_keeps_a_session_that_is_within_the_limit_and_it_gets_shorter(api):
    form = register(api)
    token = login(api, form)
    make_admin(api, form["email"])

    response = me(api, token)

    assert response.status_code == 200 and response.json()["is_admin"] is True
    assert int(session_cookie(response)["max-age"]) <= 30 * MINUTE
    assert float(session_row(api, form["email"])[1]) <= 30 * MINUTE + 1


def test_someone_who_stops_being_admin_goes_back_to_the_normal_rules(api):
    form, token = admin_with_session(api)
    remove_admin(api, form["email"])

    response = me(api, token)

    assert response.status_code == 200 and response.json()["is_admin"] is False
    assert session_cookie(response)["max-age"] == str(30 * 24 * HOUR)
    age(api, form["email"], idle_minutes=31, open_hours=13)
    assert me(api, token).status_code == 200


def test_an_admin_who_is_also_a_host_gets_the_admin_limit(api):
    form = register(api)
    make_host(api, form["email"])
    make_admin(api, form["email"])
    token = login(api, form)

    response = me(api, token)

    assert response.json()["is_host"] is True and response.json()["is_admin"] is True
    assert int(session_cookie(response)["max-age"]) <= 30 * MINUTE
    age(api, form["email"], idle_minutes=31)
    assert me(api, token).status_code == 401


# --- Caso 7: la configuración y la independencia ---------------------------------------------------------------------


def test_the_times_come_from_the_configuration(api):
    use_settings(api, session_idle_minutes_admin=5, session_max_hours_admin=1)
    form = register(api)
    make_admin(api, form["email"])
    cookie = session_cookie(verify(api, form))
    api.client.cookies.clear()
    token = cookie.value
    assert cookie["max-age"] == str(5 * MINUTE)

    age(api, form["email"], idle_minutes=4)
    assert me(api, token).status_code == 200
    age(api, form["email"], idle_minutes=6)
    assert me(api, token).status_code == 401


def test_the_cap_comes_from_the_configuration_too(api):
    use_settings(api, session_idle_minutes_admin=30, session_max_hours_admin=1)
    form, token = admin_with_session(api)
    age(api, form["email"], idle_minutes=1, open_hours=1)

    assert me(api, token).status_code == 401


def test_two_sessions_of_the_same_admin_expire_on_their_own(api):
    form, first = admin_with_session(api)
    second = login(api, form)
    age(api, form["email"], idle_minutes=31, token=second)

    assert me(api, second).status_code == 401
    assert me(api, first).status_code == 200


def test_the_configuration_has_the_decided_values(api):
    assert api.settings.session_idle_minutes_admin == 30
    assert api.settings.session_max_hours_admin == 12


def test_closing_an_admin_session_on_purpose_still_works(api):
    from test_accounts_logout import change

    form, token = admin_with_session(api)

    response = api.client.post("/api/v1/auth/logout", headers=change(api, token))

    assert response.status_code == 200
    assert me(api, token).status_code == 401
