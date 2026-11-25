"""Casos de la pieza "la vista en la API": quién es anfitrión y quién es administrador.

Decisión de Sophia del 20 de noviembre de 2026: crear las vistas en el frontend y en el backend. Del lado de la
API, la vista de una persona sale de dos cosas que ya existen: su perfil de anfitrión y su fila en `admins`.

    GET /auth/me
     1. Una persona con sesión: is_host false e is_admin false.
     2. Con perfil de anfitrión: is_host true. En la tabla admins: is_admin true. Las dos cosas son independientes.
     3. Se lee en cada petición: quien deja de ser administrador deja de serlo en su siguiente petición.
    Dependencias de las rutas (app/api/roles.py)
     4. require_host y require_admin: sin sesión 401; con sesión pero sin el papel 403, con host_only o admin_only;
        con el papel, 200.
     5. Las variantes _for_change piden además el origen y la clave de la página; sin ellas 403 y no cambia nada.
     6. Un administrador no es anfitrión por serlo, ni al revés.

La tabla admins solo se llena a mano en pgAdmin y las pruebas no tienen permiso de escribir en ella. Para probar con
administradores se crea, dentro de la transacción de la prueba, una tabla temporal con el mismo nombre: la base busca
primero entre las temporales, así que las consultas del código la leen en lugar de la verdadera, y todo se deshace
al terminar. La tabla verdadera no se toca.

Corren contra la base real con rollback_pool.
"""

import pytest
from conftest import with_session
from fastapi import APIRouter, Depends
from test_accounts_login import ME, errors_of, login, make_host, one, register, run
from test_accounts_logout import change

from app.api.roles import require_admin, require_admin_for_change, require_host, require_host_for_change
from app.modules.accounts.sessions import CurrentSession

PROBE = APIRouter(prefix="/api/v1/probe")


@PROBE.get("/host")
def host_only(session: CurrentSession = Depends(require_host)):
    return {"user": str(session.user_id), "is_host": session.is_host}


@PROBE.get("/admin")
def admin_only(session: CurrentSession = Depends(require_admin)):
    return {"user": str(session.user_id), "is_admin": session.is_admin}


CHANGES = []


@PROBE.post("/host")
def host_change(session: CurrentSession = Depends(require_host_for_change)):
    CHANGES.append("host")
    return {"changed": True}


@PROBE.post("/admin")
def admin_change(session: CurrentSession = Depends(require_admin_for_change)):
    CHANGES.append("admin")
    return {"changed": True}


@pytest.fixture
def roles_api(api):
    """La API con las cuatro rutas de prueba, en una aplicación nueva para cada prueba."""
    CHANGES.clear()
    api.client.app.include_router(PROBE)
    return api


def make_admin(api, email: str) -> None:
    """Pone a esa persona como administradora en una tabla temporal que tapa a la verdadera, solo en esta prueba."""
    with api.pool.connection() as connection:
        connection.execute("create temp table if not exists admins (user_id uuid primary key)")
        connection.execute("grant select, insert, delete on admins to integro_service, integro_app")
    run(api, "insert into admins (user_id) select id from users where email = %s", email)


def remove_admin(api, email: str) -> None:
    run(api, "delete from admins where user_id = (select id from users where email = %s)", email)


# Una clave cifrada con la forma que pide user_totp (valor ficticio: estas pruebas no comprueban códigos).
FAKE_CIPHERTEXT = "A" * 64


def activate_authenticator(api, email: str) -> None:
    """Deja activo el Authenticator de esa persona y da por pasadas sus sesiones abiertas, sin pasar por las rutas.

    Desde la pieza 3.3 las rutas de anfitrión y de administrador piden tenerlo activo."""
    run(
        api,
        "insert into user_totp (user_id, secret_ciphertext, confirmed_at, last_used_step) "
        "select id, %s, now(), 0 from users where email = %s "
        "on conflict (user_id) do update set confirmed_at = now(), last_used_step = 0",
        FAKE_CIPHERTEXT, email,
    )
    run(api, "update sessions set second_factor_at = now() where user_id = (select id from users where email = %s)", email)


def person(api, *, host=False, admin=False, first_name="Ana", authenticator=True):
    """Una persona con sesión. Si es anfitriona o administradora tiene su Authenticator activo, salvo que se pida que no."""
    form = register(api, first_name)
    if host:
        make_host(api, form["email"])
    if admin:
        make_admin(api, form["email"])
    token = login(api, form)
    if (host or admin) and authenticator:
        activate_authenticator(api, form["email"])
    return form, token


# --- Casos 1 a 3: /auth/me -------------------------------------------------------------------


def test_a_plain_person_is_neither_host_nor_admin(roles_api):
    _, token = person(roles_api)

    body = roles_api.client.get(ME, headers=with_session(token)).json()

    assert (body["is_host"], body["is_admin"]) == (False, False)


def test_me_now_carries_is_admin(roles_api):
    _, token = person(roles_api)

    body = roles_api.client.get(ME, headers=with_session(token)).json()

    assert set(body) == {
        "id", "first_name", "last_name", "email", "country", "preferred_language", "is_host", "is_admin",
        "session_expires_at", "csrf_token",
    }


def test_a_host_is_host_and_not_admin(roles_api):
    _, token = person(roles_api, host=True)

    body = roles_api.client.get(ME, headers=with_session(token)).json()

    assert (body["is_host"], body["is_admin"]) == (True, False)


def test_an_admin_is_admin_and_not_host(roles_api):
    _, token = person(roles_api, admin=True)

    body = roles_api.client.get(ME, headers=with_session(token)).json()

    assert (body["is_host"], body["is_admin"]) == (False, True)


def test_a_person_can_be_both(roles_api):
    _, token = person(roles_api, host=True, admin=True)

    body = roles_api.client.get(ME, headers=with_session(token)).json()

    assert (body["is_host"], body["is_admin"]) == (True, True)


def test_the_role_of_one_person_is_not_the_role_of_another(roles_api):
    _, admin_token = person(roles_api, admin=True, first_name="Ana")
    _, plain_token = person(roles_api, first_name="Beto")

    assert roles_api.client.get(ME, headers=with_session(admin_token)).json()["is_admin"] is True
    assert roles_api.client.get(ME, headers=with_session(plain_token)).json()["is_admin"] is False


def test_the_role_is_read_on_every_request(roles_api):
    form, token = person(roles_api)
    assert roles_api.client.get(ME, headers=with_session(token)).json()["is_admin"] is False

    make_admin(roles_api, form["email"])
    assert roles_api.client.get(ME, headers=with_session(token)).json()["is_admin"] is True

    remove_admin(roles_api, form["email"])
    assert roles_api.client.get(ME, headers=with_session(token)).json()["is_admin"] is False


def test_a_person_who_becomes_host_is_host_from_the_next_request(roles_api):
    form, token = person(roles_api)
    make_host(roles_api, form["email"])

    assert roles_api.client.get(ME, headers=with_session(token)).json()["is_host"] is True


# --- Caso 4: las rutas de lectura ---------------------------------------------------------------


@pytest.mark.parametrize("route", ["host", "admin"])
def test_without_a_session_the_role_routes_are_401(roles_api, route):
    response = roles_api.client.get(f"/api/v1/probe/{route}")

    assert response.status_code == 401
    assert errors_of(response) == [("authorization", "not_authenticated")]


def test_a_plain_person_is_refused_by_both(roles_api):
    _, token = person(roles_api)

    host = roles_api.client.get("/api/v1/probe/host", headers=with_session(token))
    admin = roles_api.client.get("/api/v1/probe/admin", headers=with_session(token))

    assert (host.status_code, admin.status_code) == (403, 403)
    assert errors_of(host) == [("request", "host_only")]
    assert errors_of(admin) == [("request", "admin_only")]
    assert host.json()["errors"][0]["message"] == "Esta función es solo para anfitriones."
    assert admin.json()["errors"][0]["message"] == "Esta función es solo para el equipo de Íntegro."


def test_a_host_gets_into_the_host_route_and_not_the_admin_one(roles_api):
    _, token = person(roles_api, host=True)

    host = roles_api.client.get("/api/v1/probe/host", headers=with_session(token))
    admin = roles_api.client.get("/api/v1/probe/admin", headers=with_session(token))

    assert host.status_code == 200 and host.json()["is_host"] is True
    assert admin.status_code == 403 and errors_of(admin) == [("request", "admin_only")]


def test_an_admin_gets_into_the_admin_route_and_not_the_host_one(roles_api):
    """Ver las vistas con su propia cuenta no la vuelve anfitriona: el permiso de anfitrión es el perfil."""
    _, token = person(roles_api, admin=True)

    admin = roles_api.client.get("/api/v1/probe/admin", headers=with_session(token))
    host = roles_api.client.get("/api/v1/probe/host", headers=with_session(token))

    assert admin.status_code == 200 and admin.json()["is_admin"] is True
    assert host.status_code == 403 and errors_of(host) == [("request", "host_only")]


def test_someone_who_is_both_gets_into_both(roles_api):
    _, token = person(roles_api, host=True, admin=True)

    assert roles_api.client.get("/api/v1/probe/host", headers=with_session(token)).status_code == 200
    assert roles_api.client.get("/api/v1/probe/admin", headers=with_session(token)).status_code == 200


def test_an_admin_who_is_removed_is_refused_on_the_next_request_with_the_session_still_open(roles_api):
    form, token = person(roles_api, admin=True)
    assert roles_api.client.get("/api/v1/probe/admin", headers=with_session(token)).status_code == 200

    remove_admin(roles_api, form["email"])

    assert roles_api.client.get("/api/v1/probe/admin", headers=with_session(token)).status_code == 403
    assert roles_api.client.get(ME, headers=with_session(token)).status_code == 200


def test_a_refused_request_does_not_leak_data_of_the_route(roles_api):
    _, token = person(roles_api)

    response = roles_api.client.get("/api/v1/probe/admin", headers=with_session(token))

    assert "user" not in response.text and "is_admin" not in response.text


# --- Caso 5: las rutas que cambian algo ---------------------------------------------------------------


def test_a_host_can_change_through_the_host_route_with_the_defenses(roles_api):
    _, token = person(roles_api, host=True)

    response = roles_api.client.post("/api/v1/probe/host", headers=change(roles_api, token))

    assert response.status_code == 200 and CHANGES == ["host"]


def test_an_admin_can_change_through_the_admin_route_with_the_defenses(roles_api):
    _, token = person(roles_api, admin=True)

    response = roles_api.client.post("/api/v1/probe/admin", headers=change(roles_api, token))

    assert response.status_code == 200 and CHANGES == ["admin"]


@pytest.mark.parametrize("route, kwargs", [("host", {"host": True}), ("admin", {"admin": True})])
def test_without_the_page_key_or_from_another_page_the_role_routes_change_nothing(roles_api, route, kwargs):
    _, token = person(roles_api, **kwargs)

    no_key = roles_api.client.post(f"/api/v1/probe/{route}", headers=change(roles_api, token, **{"X-CSRF-Token": None}))
    other_page = roles_api.client.post(
        f"/api/v1/probe/{route}", headers=change(roles_api, token, Origin="https://pagina-ajena.example")
    )

    assert (no_key.status_code, other_page.status_code) == (403, 403)
    assert errors_of(no_key) == [("request", "csrf_failed")]
    assert errors_of(other_page) == [("request", "origin_not_allowed")]
    assert CHANGES == []


@pytest.mark.parametrize("route, expected", [("host", "host_only"), ("admin", "admin_only")])
def test_a_plain_person_with_every_defense_is_still_refused_by_the_role(roles_api, route, expected):
    _, token = person(roles_api)

    response = roles_api.client.post(f"/api/v1/probe/{route}", headers=change(roles_api, token))

    assert response.status_code == 403
    assert errors_of(response) == [("request", expected)]
    assert CHANGES == []


@pytest.mark.parametrize("route", ["host", "admin"])
def test_without_a_session_the_change_routes_are_401(roles_api, route):
    response = roles_api.client.post(f"/api/v1/probe/{route}", headers={"Origin": "http://testserver"})

    assert response.status_code == 401


# --- La tabla verdadera no se toca ---------------------------------------------------------------------------


def test_without_the_temporary_table_the_code_reads_the_real_admins_table(api):
    """Una prueba nueva empieza sin tabla temporal: la consulta de la sesión lee public.admins, que solo se lee."""
    assert one(api, "select to_regclass('pg_temp.admins') is null")[0] is True
    form = register(api)
    token = login(api, form)

    assert api.client.get(ME, headers=with_session(token)).json()["is_admin"] is False


# --- Pieza 3.3: sin el Authenticator activo no se entra a las funciones de anfitrión ni a las del equipo ----------


@pytest.mark.parametrize("role,route", [("host", "/api/v1/probe/host"), ("admin", "/api/v1/probe/admin")])
def test_a_host_or_an_admin_without_the_authenticator_is_told_to_activate_it(roles_api, role, route):
    form, token = person(roles_api, host=role == "host", admin=role == "admin", authenticator=False)

    response = roles_api.client.get(route, headers=with_session(token))

    assert response.status_code == 403
    assert response.json() == {
        "errors": [{"field": "request", "code": "two_factor_setup_required", "message": "Activa tu Authenticator para usar esta función."}]
    }
    # Sigue pudiendo usar lo de cliente: su sesión sirve.
    assert roles_api.client.get(ME, headers=with_session(token)).status_code == 200


@pytest.mark.parametrize("role,route", [("host", "/api/v1/probe/host"), ("admin", "/api/v1/probe/admin")])
def test_without_the_authenticator_the_change_routes_change_nothing(roles_api, role, route):
    form, token = person(roles_api, host=role == "host", admin=role == "admin", authenticator=False)

    response = roles_api.client.post(route, headers=change(roles_api, token))

    assert response.status_code == 403
    assert errors_of(response) == [("request", "two_factor_setup_required")]
    assert CHANGES == []


def test_an_authenticator_that_is_only_pending_does_not_count(roles_api):
    form, token = person(roles_api, host=True, authenticator=False)
    run(
        roles_api,
        "insert into user_totp (user_id, secret_ciphertext) select id, %s from users where email = %s",
        FAKE_CIPHERTEXT, form["email"],
    )

    response = roles_api.client.get("/api/v1/probe/host", headers=with_session(token))

    assert errors_of(response) == [("request", "two_factor_setup_required")]


def test_once_the_authenticator_is_active_the_host_gets_in(roles_api):
    form, token = person(roles_api, host=True, authenticator=False)
    assert roles_api.client.get("/api/v1/probe/host", headers=with_session(token)).status_code == 403

    activate_authenticator(roles_api, form["email"])

    assert roles_api.client.get("/api/v1/probe/host", headers=with_session(token)).status_code == 200


def test_someone_who_is_not_a_host_is_told_host_only_not_to_activate_anything(roles_api):
    _, token = person(roles_api)

    response = roles_api.client.get("/api/v1/probe/host", headers=with_session(token))

    assert errors_of(response) == [("request", "host_only")]
