"""Casos de la pieza "tablas de intentos de inicio de sesión y de administradores".

Migración: database/migrations/20261118000004_login_attempts_admins.sql

Especificación aceptada por Sophia el 18 de noviembre de 2026:

    login_attempts  (solo se agregan filas)
     1. El sistema anota un intento fallido con correo, IP y navegador:
        aceptado. Con un correo que no tiene cuenta: aceptado.
     2. El sistema anota un intento correcto: aceptado.
     3. Correo con formato inválido o en mayúsculas, o navegador de más de
        500 letras: rechazado 23514.
     4. El sistema cambia o borra un intento: rechazado 42501.
     5. Ana lee o escribe intentos: rechazado 42501.
     6. Intento de una persona que no existe: rechazado 23503.
    admins
     7. El sistema lee la tabla: aceptado. El sistema crea, cambia o borra un
        administrador: rechazado 42501.
     8. Ana intenta hacerse administradora: rechazado 42501. Ana lee la tabla:
        solo vería su propia fila.
     9. Dar de alta a un administrador: solo el dueño de la base, a mano.
    10. La misma persona dos veces: rechazado 23505.

Los casos 9 y 10 no se pueden probar aquí, justo porque la API no tiene
permiso de escribir en admins: los comprobó la IA en un PostgreSQL temporal y
los comprueba Sophia al darse de alta en pgAdmin.

Corren contra la base real con rollback_pool: todo se deshace al terminar.
"""

from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest

from app.database.transaction import system_transaction, user_transaction
from people import create_person

NOT_NULL = "23502"
FOREIGN_KEY = "23503"
CHECK = "23514"
PERMISSION_DENIED = "42501"
INVALID_TEXT = "22P02"

MIGRATION = "20261118000004_login_attempts_admins.sql"


@pytest.fixture(scope="module", autouse=True)
def migration_applied(real_pool):
    """Si la migración no se ha corrido en la base, las pruebas se omiten y lo dicen."""
    with real_pool.connection() as connection:
        ready = connection.execute(
            "select to_regclass('public.login_attempts') is not null "
            "and to_regclass('public.admins') is not null"
        ).fetchone()[0]
    if not ready:
        pytest.skip(f"Falta correr en pgAdmin la migración {MIGRATION} sobre la base integro.")


@contextmanager
def rejected(code: str, constraint: str | None = None):
    """El bloque debe ser rechazado por la base con ese código y esa regla."""
    with pytest.raises(psycopg.Error) as raised:
        yield
    assert raised.value.sqlstate == code
    if constraint is not None:
        assert raised.value.diag.constraint_name == constraint


def note_attempt(pool, **columns):
    """El sistema anota un intento. Devuelve su id."""
    values = {"email": "ana@prueba.invalid", "succeeded": False, **columns}
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    with system_transaction(pool) as connection:
        return connection.execute(
            f"insert into login_attempts ({names}) values ({marks}) returning id", list(values.values())
        ).fetchone()[0]


def email_of(pool, user_id) -> str:
    with system_transaction(pool) as connection:
        return connection.execute("select email from users where id = %s", (user_id,)).fetchone()[0]


# ===========================================================================
# login_attempts
# ===========================================================================

# --- Caso 1 ----------------------------------------------------------------


def test_system_notes_a_failed_attempt(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    email = email_of(rollback_pool, ana)

    attempt = note_attempt(
        rollback_pool, email=email, user_id=ana, ip_address="203.0.113.7", user_agent="Navegador de prueba"
    )

    with system_transaction(rollback_pool) as connection:
        row = connection.execute(
            "select email, user_id, succeeded, host(ip_address), user_agent, created_at is not null "
            "from login_attempts where id = %s",
            (attempt,),
        ).fetchone()
    assert row == (email, ana, False, "203.0.113.7", "Navegador de prueba", True)


def test_failed_attempt_for_an_email_without_account_is_noted_too(rollback_pool):
    attempt = note_attempt(rollback_pool, email=f"nadie.{uuid4().hex[:8]}@prueba.invalid", ip_address="2001:db8::1")

    with system_transaction(rollback_pool) as connection:
        row = connection.execute(
            "select user_id, succeeded, host(ip_address) from login_attempts where id = %s", (attempt,)
        ).fetchone()
    assert row == (None, False, "2001:db8::1")


def test_attempt_with_nothing_known_about_who_tried_is_noted_too(rollback_pool):
    """Lo escrito no tenía forma de correo y no se conoce la dirección: el intento cuenta igual."""
    attempt = note_attempt(rollback_pool, email=None, ip_address=None, user_agent=None)

    assert attempt is not None


# --- Caso 2 ----------------------------------------------------------------


def test_system_notes_a_successful_attempt(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    attempt = note_attempt(rollback_pool, email=email_of(rollback_pool, ana), user_id=ana, succeeded=True)

    with system_transaction(rollback_pool) as connection:
        succeeded = connection.execute(
            "select succeeded from login_attempts where id = %s", (attempt,)
        ).fetchone()[0]
    assert succeeded is True


def test_successful_attempt_without_a_person_is_rejected(rollback_pool):
    with rejected(CHECK, "login_attempts_success_has_user"):
        note_attempt(rollback_pool, succeeded=True)


def test_attempts_of_one_person_can_be_counted_in_order(rollback_pool):
    """Lo que necesitará la pieza siguiente: fallos seguidos desde el último acierto."""
    ana = create_person(rollback_pool, "Ana")
    email = email_of(rollback_pool, ana)
    moments = [
        ("10 minutes", False), ("9 minutes", True), ("8 minutes", False), ("7 minutes", False), ("6 minutes", False),
    ]
    with system_transaction(rollback_pool) as connection:
        for ago, succeeded in moments:
            connection.execute(
                "insert into login_attempts (email, user_id, succeeded, created_at) "
                "values (%s, %s, %s, now() - %s::interval)",
                (email, ana, succeeded, ago),
            )
        failures_since_last_success = connection.execute(
            "select count(*) from login_attempts where user_id = %s and not succeeded and created_at > "
            "coalesce((select max(created_at) from login_attempts where user_id = %s and succeeded), '-infinity')",
            (ana, ana),
        ).fetchone()[0]

    assert failures_since_last_success == 3


# --- Caso 3 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "email", ["sin-arroba", "Ana@Prueba.invalid", "ana@prueba", "ana maria@prueba.invalid", "", "a" * 250 + "@x.mx"]
)
def test_attempt_with_invalid_email_is_rejected(rollback_pool, email):
    with rejected(CHECK, "login_attempts_email_format"):
        note_attempt(rollback_pool, email=email)


def test_attempt_browser_name_limits(rollback_pool):
    assert note_attempt(rollback_pool, user_agent="x" * 500) is not None
    with rejected(CHECK, "login_attempts_user_agent_length"):
        note_attempt(rollback_pool, user_agent="x" * 501)


def test_attempt_with_invalid_ip_is_rejected(rollback_pool):
    with rejected(INVALID_TEXT):
        note_attempt(rollback_pool, ip_address="no-es-una-ip")


def test_attempt_must_say_if_it_succeeded(rollback_pool):
    with rejected(NOT_NULL):
        note_attempt(rollback_pool, succeeded=None)


# --- Caso 4 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "update login_attempts set succeeded = true where id = %s",
        "update login_attempts set created_at = now() - interval '1 day' where id = %s",
        "delete from login_attempts where id = %s",
    ],
)
def test_system_cannot_change_or_delete_an_attempt(rollback_pool, statement):
    attempt = note_attempt(rollback_pool)

    with rejected(PERMISSION_DENIED):
        with system_transaction(rollback_pool) as connection:
            connection.execute(statement, (attempt,))


# --- Caso 5 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from login_attempts",
        "select email from login_attempts",
        "insert into login_attempts (email, succeeded) values ('ana@prueba.invalid', false)",
        "update login_attempts set succeeded = true",
        "delete from login_attempts",
    ],
)
def test_person_cannot_touch_login_attempts(rollback_pool, statement):
    ana = create_person(rollback_pool, "Ana")
    note_attempt(rollback_pool, email=email_of(rollback_pool, ana), user_id=ana)

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(statement)


# --- Caso 6 ----------------------------------------------------------------


def test_attempt_of_a_person_that_does_not_exist_is_rejected(rollback_pool):
    with rejected(FOREIGN_KEY):
        note_attempt(rollback_pool, user_id=uuid4())


# ===========================================================================
# admins
# ===========================================================================

# --- Caso 7 ----------------------------------------------------------------


def test_system_can_read_admins(rollback_pool):
    with system_transaction(rollback_pool) as connection:
        count = connection.execute("select count(*) from admins").fetchone()[0]

    assert count >= 0


@pytest.mark.parametrize(
    "statement",
    [
        "insert into admins (user_id) values (%s)",
        "update admins set user_id = %s",
        "delete from admins where user_id = %s",
    ],
)
def test_system_cannot_create_change_or_delete_admins(rollback_pool, statement):
    ana = create_person(rollback_pool, "Ana")

    with rejected(PERMISSION_DENIED):
        with system_transaction(rollback_pool) as connection:
            connection.execute(statement, (ana,))


# --- Caso 8 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "insert into admins (user_id) values (%s)",
        "update admins set user_id = %s",
        "delete from admins where user_id = %s",
    ],
)
def test_person_cannot_make_herself_admin(rollback_pool, statement):
    ana = create_person(rollback_pool, "Ana")

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(statement, (ana,))


def test_person_who_is_not_admin_sees_no_admin_rows(rollback_pool):
    """La persona puede leer la tabla, pero solo vería su propia fila; Ana no es administradora."""
    ana = create_person(rollback_pool, "Ana")

    with user_transaction(rollback_pool, ana) as connection:
        rows = connection.execute("select user_id from admins").fetchall()

    assert rows == []


# ===========================================================================
# Las dos
# ===========================================================================


@pytest.mark.parametrize("table", ["login_attempts", "admins"])
def test_without_role_integro_api_cannot_read_the_new_tables(real_pool, table):
    with rejected(PERMISSION_DENIED):
        with real_pool.connection() as connection:
            connection.execute(f"select count(*) from {table}")
