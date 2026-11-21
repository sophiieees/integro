"""Casos de la pieza "tablas de acceso a la cuenta".

Migración: database/migrations/20261117000003_sessions_codes_password_resets.sql

Especificación aceptada por Sophia el 17 de noviembre de 2026:

    sessions
     1. El sistema crea una sesión de Ana: aceptado.
     2. La misma huella dos veces: rechazado 23505.
     3. Huella con formato inválido: rechazado 23514.
     4. Vence antes de la fecha de creación: rechazado 23514.
     5. Ana lee sus sesiones: ve la suya y no la de Beto; leer la huella:
        rechazado 42501.
     6. Ana crea, cambia o borra una sesión: rechazado 42501.
     7. El sistema la revoca: aceptado. El sistema la borra: rechazado 42501.
    password_resets
     8. El sistema crea una y la marca usada: aceptado. Ana intenta leerla:
        rechazado 42501.
    one_time_codes
     9. El sistema crea un código por correo: aceptado. Propósito o canal fuera
        de la lista, canal sms con un correo como destino, intentos negativos:
        rechazado 23514.
    10. Ana intenta leer códigos: rechazado 42501.
    users.email_verified_at
    11. Nace vacía; el sistema la llena: aceptado. Ana la lee; Ana intenta
        cambiarla: rechazado 42501.
    Todas
    12. Fila para una persona que no existe: rechazado 23503.

Corren contra la base real, integro en el puerto 5433, con rollback_pool: todo
se deshace al terminar cada prueba y no queda ninguna fila.
"""

import hashlib
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest

from app.database.transaction import system_transaction, user_transaction
from people import create_person

# Códigos de PostgreSQL (tests/database/README.md).
NOT_NULL = "23502"
FOREIGN_KEY = "23503"
UNIQUE = "23505"
CHECK = "23514"
PERMISSION_DENIED = "42501"
INVALID_TEXT = "22P02"

MIGRATION = "20261117000003_sessions_codes_password_resets.sql"


@pytest.fixture(scope="module", autouse=True)
def migration_applied(real_pool):
    """Si la migración no se ha corrido en la base, las pruebas se omiten y lo dicen."""
    with real_pool.connection() as connection:
        ready = connection.execute(
            "select to_regclass('public.sessions') is not null "
            "and to_regclass('public.password_resets') is not null "
            "and to_regclass('public.one_time_codes') is not null"
        ).fetchone()[0]
    if not ready:
        pytest.skip(f"Falta correr en pgAdmin la migración {MIGRATION} sobre la base integro.")


def fingerprint(secret: str | None = None) -> str:
    """Huella SHA-256 en hexadecimal, como la que calculará la API."""
    return hashlib.sha256((secret or uuid4().hex).encode()).hexdigest()


@contextmanager
def rejected(code: str, constraint: str | None = None):
    """El bloque debe ser rechazado por la base con ese código y esa regla."""
    with pytest.raises(psycopg.Error) as raised:
        yield
    assert raised.value.sqlstate == code
    if constraint is not None:
        assert raised.value.diag.constraint_name == constraint


def create_session(pool, user_id, **columns):
    """El sistema crea una sesión. Devuelve su id."""
    values = {
        "user_id": user_id,
        "token_hash": fingerprint(),
        "expires_at": "2099-01-01T00:00:00Z",
        **columns,
    }
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    with system_transaction(pool) as connection:
        return connection.execute(
            f"insert into sessions ({names}) values ({marks}) returning id", list(values.values())
        ).fetchone()[0]


def create_password_reset(pool, user_id, **columns):
    values = {
        "user_id": user_id,
        "token_hash": fingerprint(),
        "expires_at": "2099-01-01T00:00:00Z",
        **columns,
    }
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    with system_transaction(pool) as connection:
        return connection.execute(
            f"insert into password_resets ({names}) values ({marks}) returning id",
            list(values.values()),
        ).fetchone()[0]


def create_code(pool, user_id, **columns):
    values = {
        "user_id": user_id,
        "purpose": "login",
        "channel": "email",
        "destination": "ana@prueba.invalid",
        "code_hash": fingerprint(),
        "expires_at": "2099-01-01T00:00:00Z",
        **columns,
    }
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    with system_transaction(pool) as connection:
        return connection.execute(
            f"insert into one_time_codes ({names}) values ({marks}) returning id",
            list(values.values()),
        ).fetchone()[0]


# ===========================================================================
# sessions
# ===========================================================================

# --- Caso 1 ----------------------------------------------------------------


def test_system_creates_a_session(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    session_id = create_session(rollback_pool, ana)

    with system_transaction(rollback_pool) as connection:
        row = connection.execute(
            "select user_id, revoked_at, ip_address, user_agent, "
            "last_used_at = created_at, updated_at = created_at "
            "from sessions where id = %s",
            (session_id,),
        ).fetchone()
    assert row == (ana, None, None, None, True, True)


def test_session_keeps_where_it_was_opened_from(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    ipv4 = create_session(rollback_pool, ana, ip_address="203.0.113.7", user_agent="Mozilla/5.0")
    ipv6 = create_session(rollback_pool, ana, ip_address="2001:db8::1", user_agent="x" * 500)

    with system_transaction(rollback_pool) as connection:
        rows = connection.execute(
            "select host(ip_address), char_length(user_agent) from sessions "
            "where id in (%s, %s) order by char_length(user_agent)",
            (ipv4, ipv6),
        ).fetchall()
    assert rows == [("203.0.113.7", 11), ("2001:db8::1", 500)]


def test_one_person_can_have_several_sessions(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    create_session(rollback_pool, ana)
    create_session(rollback_pool, ana)

    with system_transaction(rollback_pool) as connection:
        count = connection.execute(
            "select count(*) from sessions where user_id = %s", (ana,)
        ).fetchone()[0]
    assert count == 2


# --- Caso 2 ----------------------------------------------------------------


def test_same_session_fingerprint_twice_is_rejected(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")
    same = fingerprint("la misma llave")
    create_session(rollback_pool, ana, token_hash=same)

    with rejected(UNIQUE, "sessions_token_hash_unique"):
        create_session(rollback_pool, beto, token_hash=same)


# --- Caso 3 ----------------------------------------------------------------

INVALID_FINGERPRINTS = [
    "",
    "abc",
    "a" * 63,
    "a" * 65,
    "A" * 64,  # mayúsculas
    "g" * 64,  # no es hexadecimal
    "llave-sin-convertir-que-alguien-guardo-por-error",
]


@pytest.mark.parametrize("token_hash", INVALID_FINGERPRINTS)
def test_session_fingerprint_with_invalid_format_is_rejected(rollback_pool, token_hash):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "sessions_token_hash_sha256"):
        create_session(rollback_pool, ana, token_hash=token_hash)


# --- Caso 4 ----------------------------------------------------------------


@pytest.mark.parametrize("expires_at", ["2000-01-01T00:00:00Z", "2026-11-17T12:00:00Z"])
def test_session_that_expires_before_it_was_created_is_rejected(rollback_pool, expires_at):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "sessions_expires_after_created"):
        create_session(
            rollback_pool, ana, created_at="2026-11-17T12:00:00Z", expires_at=expires_at
        )


def test_session_dates_before_creation_are_rejected(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "sessions_revoked_after_created"):
        create_session(rollback_pool, ana, revoked_at="2000-01-01T00:00:00Z")
    with rejected(CHECK, "sessions_last_used_after_created"):
        create_session(rollback_pool, ana, last_used_at="2000-01-01T00:00:00Z")


def test_session_limits(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "sessions_user_agent_length"):
        create_session(rollback_pool, ana, user_agent="x" * 501)
    with rejected(INVALID_TEXT):
        create_session(rollback_pool, ana, ip_address="no-es-una-ip")


@pytest.mark.parametrize("column", ["user_id", "token_hash", "expires_at"])
def test_session_required_columns(rollback_pool, column):
    ana = create_person(rollback_pool, "Ana")
    values = {"user_id": ana, column: None}

    with rejected(NOT_NULL):
        create_session(rollback_pool, values.pop("user_id"), **values)


# --- Caso 5 ----------------------------------------------------------------

READABLE_SESSION_COLUMNS = (
    "id, user_id, expires_at, revoked_at, last_used_at, ip_address, user_agent, created_at"
)


def test_person_reads_only_own_sessions(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")
    ana_session = create_session(rollback_pool, ana, user_agent="Celular de Ana")
    beto_session = create_session(rollback_pool, beto, user_agent="Computadora de Beto")

    with user_transaction(rollback_pool, ana) as connection:
        ana_sees = connection.execute(
            f"select {READABLE_SESSION_COLUMNS} from sessions"
        ).fetchall()
    with user_transaction(rollback_pool, beto) as connection:
        beto_sees = connection.execute("select id, user_agent from sessions").fetchall()

    assert [(row[0], row[1], row[6]) for row in ana_sees] == [(ana_session, ana, "Celular de Ana")]
    assert beto_sees == [(beto_session, "Computadora de Beto")]


@pytest.mark.parametrize(
    "query",
    [
        "select token_hash from sessions",
        "select * from sessions",
        "select id from sessions where token_hash = 'x'",
        "select updated_at from sessions",
    ],
)
def test_person_cannot_read_the_session_fingerprint(rollback_pool, query):
    ana = create_person(rollback_pool, "Ana")
    create_session(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(query)


# --- Caso 6 ----------------------------------------------------------------


def test_person_cannot_create_change_or_delete_sessions(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    session_id = create_session(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(
                "insert into sessions (user_id, token_hash, expires_at) "
                "values (%s, %s, '2099-01-01T00:00:00Z')",
                (ana, fingerprint()),
            )
    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(
                "update sessions set expires_at = '2199-01-01T00:00:00Z' where id = %s",
                (session_id,),
            )
    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute("update sessions set revoked_at = now() where id = %s", (session_id,))
    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute("delete from sessions where id = %s", (session_id,))


# --- Caso 7 ----------------------------------------------------------------


def test_system_revokes_a_session_and_the_person_sees_it(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    session_id = create_session(rollback_pool, ana)

    with system_transaction(rollback_pool) as connection:
        changed = connection.execute(
            "update sessions set revoked_at = now() + interval '1 minute', "
            "last_used_at = now() + interval '1 minute' where id = %s",
            (session_id,),
        ).rowcount
    with user_transaction(rollback_pool, ana) as connection:
        revoked = connection.execute(
            "select revoked_at is not null from sessions where id = %s", (session_id,)
        ).fetchone()[0]

    assert changed == 1
    assert revoked is True


def test_system_cannot_delete_a_session(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    session_id = create_session(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with system_transaction(rollback_pool) as connection:
            connection.execute("delete from sessions where id = %s", (session_id,))


# ===========================================================================
# password_resets
# ===========================================================================

# --- Caso 8 ----------------------------------------------------------------


def test_system_creates_a_password_reset_and_marks_it_used(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    reset_id = create_password_reset(rollback_pool, ana)
    with system_transaction(rollback_pool) as connection:
        before = connection.execute(
            "select used_at from password_resets where id = %s", (reset_id,)
        ).fetchone()[0]
        changed = connection.execute(
            "update password_resets set used_at = now() + interval '1 minute' where id = %s",
            (reset_id,),
        ).rowcount
        after = connection.execute(
            "select used_at is not null from password_resets where id = %s", (reset_id,)
        ).fetchone()[0]

    assert before is None
    assert changed == 1
    assert after is True


@pytest.mark.parametrize(
    "query",
    [
        "select count(*) from password_resets",
        "select id from password_resets",
        "insert into password_resets (user_id, token_hash, expires_at) "
        "values ('{user}', '{hash}', '2099-01-01T00:00:00Z')",
        "update password_resets set used_at = now()",
        "delete from password_resets",
    ],
)
def test_person_cannot_touch_password_resets(rollback_pool, query):
    ana = create_person(rollback_pool, "Ana")
    create_password_reset(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(query.format(user=ana, hash=fingerprint()))


def test_password_reset_rules(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    same = fingerprint("el mismo enlace")
    create_password_reset(rollback_pool, ana, token_hash=same)

    with rejected(UNIQUE, "password_resets_token_hash_unique"):
        create_password_reset(rollback_pool, ana, token_hash=same)
    with rejected(CHECK, "password_resets_token_hash_sha256"):
        create_password_reset(rollback_pool, ana, token_hash="abc")
    with rejected(CHECK, "password_resets_expires_after_created"):
        create_password_reset(rollback_pool, ana, expires_at="2000-01-01T00:00:00Z")
    with rejected(CHECK, "password_resets_used_after_created"):
        create_password_reset(rollback_pool, ana, used_at="2000-01-01T00:00:00Z")


def test_system_cannot_delete_a_password_reset(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    reset_id = create_password_reset(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with system_transaction(rollback_pool) as connection:
            connection.execute("delete from password_resets where id = %s", (reset_id,))


# ===========================================================================
# one_time_codes
# ===========================================================================

# --- Caso 9 ----------------------------------------------------------------


def test_system_creates_a_code_sent_by_email(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    code_id = create_code(rollback_pool, ana)

    with system_transaction(rollback_pool) as connection:
        row = connection.execute(
            "select user_id, purpose, channel, destination, attempts, used_at "
            "from one_time_codes where id = %s",
            (code_id,),
        ).fetchone()
    assert row == (ana, "login", "email", "ana@prueba.invalid", 0, None)


VALID_CODES = [
    ("login", "email", "ana@prueba.invalid"),
    ("login", "sms", "+525512345678"),
    ("login", "whatsapp", "+525512345678"),
    ("verify_email", "email", "ana@prueba.invalid"),
    ("password_reset", "email", "ana@prueba.invalid"),  # desde la migración del 21 de noviembre
    ("verify_phone", "sms", "+14155550123"),
    ("verify_phone", "whatsapp", "+14155550123"),
]


@pytest.mark.parametrize("purpose, channel, destination", VALID_CODES)
def test_every_allowed_purpose_and_channel_is_accepted(rollback_pool, purpose, channel, destination):
    ana = create_person(rollback_pool, "Ana")

    code_id = create_code(
        rollback_pool, ana, purpose=purpose, channel=channel, destination=destination
    )

    assert code_id is not None


@pytest.mark.parametrize("purpose", ["", "reset", "LOGIN", "password-reset", "PASSWORD_RESET"])
def test_code_purpose_outside_the_list_is_rejected(rollback_pool, purpose):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_purpose_valid"):
        create_code(rollback_pool, ana, purpose=purpose)


@pytest.mark.parametrize("channel", ["", "telegram", "EMAIL", "phone"])
def test_code_channel_outside_the_list_is_rejected(rollback_pool, channel):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_channel_valid"):
        create_code(rollback_pool, ana, channel=channel)


WRONG_DESTINATIONS = [
    ("sms", "ana@prueba.invalid"),  # el caso de la especificación
    ("whatsapp", "ana@prueba.invalid"),
    ("email", "+525512345678"),
    ("email", "Ana@Prueba.invalid"),  # mayúsculas
    ("email", "sin-arroba"),
    ("email", ""),
    ("sms", "5512345678"),  # sin signo de más ni código de país
    ("sms", "+0525512345678"),
    ("sms", ""),
]


@pytest.mark.parametrize("channel, destination", WRONG_DESTINATIONS)
def test_code_destination_must_match_the_channel(rollback_pool, channel, destination):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_destination_matches_channel"):
        create_code(rollback_pool, ana, channel=channel, destination=destination)


@pytest.mark.parametrize(
    "purpose, channel, destination",
    [
        ("verify_email", "sms", "+525512345678"),
        ("verify_email", "whatsapp", "+525512345678"),
        ("verify_phone", "email", "ana@prueba.invalid"),
        ("password_reset", "sms", "+525512345678"),
        ("password_reset", "whatsapp", "+525512345678"),
    ],
)
def test_code_channel_must_match_the_purpose(rollback_pool, purpose, channel, destination):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_channel_matches_purpose"):
        create_code(rollback_pool, ana, purpose=purpose, channel=channel, destination=destination)


@pytest.mark.parametrize("attempts", [-1, -100])
def test_code_negative_attempts_are_rejected(rollback_pool, attempts):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_attempts_not_negative"):
        create_code(rollback_pool, ana, attempts=attempts)


def test_code_other_rules(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with rejected(CHECK, "one_time_codes_code_hash_sha256"):
        create_code(rollback_pool, ana, code_hash="123456")  # el código sin convertir
    with rejected(CHECK, "one_time_codes_expires_after_created"):
        create_code(rollback_pool, ana, expires_at="2000-01-01T00:00:00Z")
    with rejected(CHECK, "one_time_codes_used_after_created"):
        create_code(rollback_pool, ana, used_at="2000-01-01T00:00:00Z")
    with rejected(NOT_NULL):
        create_code(rollback_pool, ana, destination=None)


def test_system_counts_attempts_and_marks_the_code_used(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    code_id = create_code(rollback_pool, ana)

    with system_transaction(rollback_pool) as connection:
        connection.execute(
            "update one_time_codes set attempts = attempts + 1 where id = %s", (code_id,)
        )
        connection.execute(
            "update one_time_codes set used_at = now() + interval '1 minute' where id = %s",
            (code_id,),
        )
        row = connection.execute(
            "select attempts, used_at is not null from one_time_codes where id = %s", (code_id,)
        ).fetchone()

    assert row == (1, True)


def test_two_codes_can_share_the_same_fingerprint(rollback_pool):
    """Un código de seis dígitos se repite entre personas; no puede ser único."""
    ana = create_person(rollback_pool, "Ana")
    beto = create_person(rollback_pool, "Beto")
    same = fingerprint("123456")

    first = create_code(rollback_pool, ana, code_hash=same)
    second = create_code(rollback_pool, beto, code_hash=same)

    assert first != second


def test_system_cannot_delete_a_code(rollback_pool):
    ana = create_person(rollback_pool, "Ana")
    code_id = create_code(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with system_transaction(rollback_pool) as connection:
            connection.execute("delete from one_time_codes where id = %s", (code_id,))


# --- Caso 10 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "select count(*) from one_time_codes",
        "select code_hash from one_time_codes",
        "insert into one_time_codes (user_id, purpose, channel, destination, code_hash, expires_at) "
        "values ('{user}', 'login', 'email', 'ana@prueba.invalid', '{hash}', '2099-01-01T00:00:00Z')",
        "update one_time_codes set attempts = 0",
        "delete from one_time_codes",
    ],
)
def test_person_cannot_touch_codes(rollback_pool, query):
    ana = create_person(rollback_pool, "Ana")
    create_code(rollback_pool, ana)

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(query.format(user=ana, hash=fingerprint()))


# ===========================================================================
# users.email_verified_at
# ===========================================================================

# --- Caso 11 ---------------------------------------------------------------


def test_email_verified_at_starts_empty_and_the_system_fills_it(rollback_pool):
    ana = create_person(rollback_pool, "Ana")

    with system_transaction(rollback_pool) as connection:
        before = connection.execute(
            "select email_verified_at from users where id = %s", (ana,)
        ).fetchone()[0]
        changed = connection.execute(
            "update users set email_verified_at = now() where id = %s", (ana,)
        ).rowcount
    with user_transaction(rollback_pool, ana) as connection:
        seen_by_ana = connection.execute(
            "select email_verified_at is not null from users where id = %s", (ana,)
        ).fetchone()[0]

    assert before is None
    assert changed == 1
    assert seen_by_ana is True


@pytest.mark.parametrize("value", ["now()", "null"])
def test_person_cannot_change_email_verified_at(rollback_pool, value):
    ana = create_person(rollback_pool, "Ana")

    with rejected(PERMISSION_DENIED):
        with user_transaction(rollback_pool, ana) as connection:
            connection.execute(
                f"update users set email_verified_at = {value} where id = %s", (ana,)
            )


def test_person_can_still_change_own_name(rollback_pool):
    """La columna nueva no cambió lo que la persona ya podía corregir."""
    ana = create_person(rollback_pool, "Ana")

    with user_transaction(rollback_pool, ana) as connection:
        changed = connection.execute(
            "update users set first_name = 'Ana María' where id = %s", (ana,)
        ).rowcount

    assert changed == 1


# ===========================================================================
# Todas
# ===========================================================================

# --- Caso 12 ---------------------------------------------------------------


@pytest.mark.parametrize("create", [create_session, create_password_reset, create_code])
def test_row_for_a_person_that_does_not_exist_is_rejected(rollback_pool, create):
    with rejected(FOREIGN_KEY):
        create(rollback_pool, uuid4())


@pytest.mark.parametrize("table", ["sessions", "password_resets", "one_time_codes"])
def test_without_role_integro_api_cannot_read_the_new_tables(real_pool, table):
    with rejected(PERMISSION_DENIED):
        with real_pool.connection() as connection:
            connection.execute(f"select count(*) from {table}")
