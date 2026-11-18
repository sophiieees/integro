"""Casos de la pieza "cambio de papel por transacción".

Especificación aceptada por Sophia el 17 de noviembre de 2026:

    1. Como el sistema: la base dice integro_service y ve a Ana y a Beto.
    2. Como Ana: la base dice integro_app y el id de Ana; ve su fila y no la
       de Beto.
    3. Como Ana, leer user_credentials: rechazado, código 42501.
    4. Al terminar la transacción la conexión vuelve a ser integro_api, sin
       persona anotada.
    5. Si el código falla a la mitad se deshace todo y la conexión queda limpia.
    6. Id que no es un UUID: rechazado antes de tocar la base.
    7. Sin elegir papel (integro_api solo), leer users: rechazado, código 42501.

Corren contra la base real, integro en el puerto 5433. Las que escriben usan
rollback_pool: todo se deshace al terminar la prueba y no queda ninguna fila.
"""

from uuid import UUID, uuid4

import psycopg
import pytest

from app.database.transaction import (
    InvalidUserIdError,
    parse_user_id,
    system_transaction,
    user_transaction,
)

PERMISSION_DENIED = "42501"


def create_person(pool, first_name: str) -> UUID:
    """Crea una persona de prueba como el sistema: fila en users y su teléfono."""
    tag = uuid4().hex[:12]
    with system_transaction(pool) as connection:
        user_id = connection.execute(
            "insert into users (first_name, last_name, email, country, birth_date) "
            "values (%s, 'Prueba', %s, 'MX', date '1990-01-01') returning id",
            (first_name, f"{first_name.lower()}.{tag}@prueba.invalid"),
        ).fetchone()[0]
        connection.execute(
            "insert into user_phones (user_id, phone, is_primary) values (%s, %s, true)",
            (user_id, "+52" + str(int(tag, 16))[:10].rjust(10, "5")),
        )
    return user_id


def who_am_i(connection) -> tuple:
    """Papel con el que se está actuando y persona anotada, según la base."""
    return connection.execute(
        "select session_user, current_user, public.current_user_id()"
    ).fetchone()


# ---------------------------------------------------------------------------
# Caso 1. Como el sistema
# ---------------------------------------------------------------------------


def test_system_acts_as_integro_service_and_sees_everyone(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")

    with system_transaction(rollback_pool) as connection:
        identity = who_am_i(connection)
        seen = connection.execute(
            "select count(*) from users where id in (%s, %s)", (ana, beto)
        ).fetchone()[0]

    assert identity == ("integro_api", "integro_service", None)
    assert seen == 2


# ---------------------------------------------------------------------------
# Caso 2. Como Ana
# ---------------------------------------------------------------------------


def test_user_acts_as_integro_app_and_sees_only_own_row(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")

    with user_transaction(rollback_pool, ana) as connection:
        identity = who_am_i(connection)
        all_visible = connection.execute("select id from users").fetchall()
        beto_visible = connection.execute(
            "select count(*) from users where id = %s", (beto,)
        ).fetchone()[0]
        own_phones = connection.execute("select user_id from user_phones").fetchall()

    assert identity == ("integro_api", "integro_app", ana)
    assert all_visible == [(ana,)]
    assert beto_visible == 0
    assert own_phones == [(ana,)]


def test_each_person_sees_only_themselves(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")

    with user_transaction(rollback_pool, beto) as connection:
        beto_sees = connection.execute("select id from users").fetchall()
    with user_transaction(rollback_pool, ana) as connection:
        ana_sees = connection.execute("select id from users").fetchall()

    assert beto_sees == [(beto,)]
    assert ana_sees == [(ana,)]


def test_person_without_account_sees_nothing(rollback_pool):
    create_person(rollback_pool, "Ana")

    with user_transaction(rollback_pool, uuid4()) as connection:
        visible = connection.execute("select count(*) from users").fetchone()[0]

    assert visible == 0


def test_system_after_user_no_longer_carries_the_person(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with user_transaction(rollback_pool, ana):
        pass
    with system_transaction(rollback_pool) as connection:
        identity = who_am_i(connection)

    assert identity == ("integro_api", "integro_service", None)


# ---------------------------------------------------------------------------
# Caso 3. Como Ana, lo que no le toca
# ---------------------------------------------------------------------------


def test_user_cannot_read_credentials(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with pytest.raises(psycopg.errors.InsufficientPrivilege) as raised:
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute("select count(*) from user_credentials")

    assert raised.value.sqlstate == PERMISSION_DENIED


def test_user_cannot_change_own_email(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with pytest.raises(psycopg.errors.InsufficientPrivilege) as raised:
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(
                "update users set email = 'otra@prueba.invalid' where id = %s", (ana,)
            )

    assert raised.value.sqlstate == PERMISSION_DENIED


# ---------------------------------------------------------------------------
# Caso 4. Al terminar, la conexión vuelve limpia
# ---------------------------------------------------------------------------


def connection_state(pool) -> tuple:
    """Proceso de la conexión, papel y persona anotada, fuera de toda transacción con papel."""
    with pool.connection() as connection:
        return connection.execute(
            "select pg_backend_pid(), current_user, "
            "coalesce(current_setting('app.user_id', true), '')"
        ).fetchone()


def test_connection_is_clean_after_user_transaction(real_pool):
    person = uuid4()

    with user_transaction(real_pool, person) as connection:
        inside = connection.execute(
            "select pg_backend_pid(), current_user, public.current_user_id()"
        ).fetchone()
    after = connection_state(real_pool)

    assert inside[1:] == ("integro_app", person)
    # Es la misma conexión, ya devuelta al grupo.
    assert after == (inside[0], "integro_api", "")


def test_connection_is_clean_after_system_transaction(real_pool):
    with system_transaction(real_pool) as connection:
        inside = connection.execute("select pg_backend_pid(), current_user").fetchone()
    after = connection_state(real_pool)

    assert inside[1] == "integro_service"
    assert after == (inside[0], "integro_api", "")


# ---------------------------------------------------------------------------
# Caso 5. Si el código falla a la mitad
# ---------------------------------------------------------------------------


class FailureInTheMiddle(Exception):
    pass


def test_failure_undoes_everything_and_leaves_connection_clean(real_pool):
    email = f"falla.{uuid4().hex[:12]}@prueba.invalid"

    with pytest.raises(FailureInTheMiddle):
        with system_transaction(real_pool) as connection:
            pid = connection.execute("select pg_backend_pid()").fetchone()[0]
            connection.execute(
                "insert into users (first_name, last_name, email, country, birth_date) "
                "values ('Falla', 'Prueba', %s, 'MX', date '1990-01-01')",
                (email,),
            )
            raise FailureInTheMiddle()

    after = connection_state(real_pool)
    with system_transaction(real_pool) as connection:
        saved = connection.execute(
            "select count(*) from users where email = %s", (email,)
        ).fetchone()[0]

    assert saved == 0, f"La fila con el correo {email} se guardó y hay que borrarla."
    assert after == (pid, "integro_api", "")


def test_failure_as_user_leaves_connection_clean(real_pool):
    with pytest.raises(FailureInTheMiddle):
        with user_transaction(real_pool, uuid4()) as connection:
            pid = connection.execute("select pg_backend_pid()").fetchone()[0]
            raise FailureInTheMiddle()

    assert connection_state(real_pool) == (pid, "integro_api", "")


def test_database_error_leaves_connection_clean(real_pool):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_transaction(real_pool, uuid4()) as connection:
            pid = connection.execute("select pg_backend_pid()").fetchone()[0]
            connection.execute("select count(*) from user_credentials")

    assert connection_state(real_pool) == (pid, "integro_api", "")


# ---------------------------------------------------------------------------
# Caso 6. Id que no es un UUID
# ---------------------------------------------------------------------------

INVALID_USER_IDS = [
    None,
    "",
    "   ",
    "ana",
    "'; reset role; --",
    "00000000-0000-0000-0000-00000000000",  # le falta un carácter
    "00000000-0000-0000-0000-0000000000000",  # le sobra un carácter
    "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
    123,
    0,
    True,
    b"00000000-0000-0000-0000-000000000000",
    ["00000000-0000-0000-0000-000000000000"],
]


class PoolThatMustNotBeUsed:
    def connection(self, timeout=None):
        raise AssertionError("Se pidió una conexión con un id que no es válido.")


@pytest.mark.parametrize("user_id", INVALID_USER_IDS, ids=repr)
def test_invalid_user_id_is_rejected_before_touching_the_database(user_id):
    with pytest.raises(InvalidUserIdError):
        with user_transaction(PoolThatMustNotBeUsed(), user_id):
            pytest.fail("El bloque no debió ejecutarse.")


@pytest.mark.parametrize("user_id", INVALID_USER_IDS, ids=repr)
def test_parse_user_id_rejects(user_id):
    with pytest.raises(InvalidUserIdError):
        parse_user_id(user_id)


def test_parse_user_id_accepts_uuid_and_its_text():
    value = uuid4()

    assert parse_user_id(value) == value
    assert parse_user_id(str(value)) == value
    assert parse_user_id(str(value).upper()) == value


def test_user_id_as_text_works_like_uuid(real_pool):
    person = uuid4()

    with user_transaction(real_pool, str(person)) as connection:
        noted = connection.execute("select public.current_user_id()").fetchone()[0]

    assert noted == person


# ---------------------------------------------------------------------------
# Caso 7. Sin elegir papel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "table", ["users", "user_credentials", "user_phones", "host_profiles", "verifications"]
)
def test_without_role_integro_api_cannot_read(real_pool, table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as raised:
        with real_pool.connection() as connection:
            connection.execute(f"select count(*) from {table}")

    assert raised.value.sqlstate == PERMISSION_DENIED
