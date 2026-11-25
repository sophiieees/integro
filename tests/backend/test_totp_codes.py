"""Casos de los códigos del Authenticator y del cifrado de su clave (pieza 3.2), sin base de datos.

Especificación confirmada por Sophia el 24 y 25 de noviembre de 2026:

    Los códigos (app/modules/accounts/totp.py)
     1. Los vectores de prueba oficiales del estándar (RFC 6238 y RFC 4226) dan los códigos esperados.
     2. Se aceptan el código del periodo actual, el del anterior y el del siguiente; uno más viejo o más adelantado, no.
     3. Un código ya usado no se acepta dos veces: ni ese periodo ni uno anterior.
     4. Lo que no son 6 números no es un código.
     5. La clave se entrega en base32 y como dirección otpauth://, con el nombre de Íntegro y el correo de la cuenta.
    El cifrado (app/core/encryption.py)
     6. Lo cifrado se descifra con la misma llave, el mismo uso y la misma persona, y solo así: con otra llave, otro uso
        u otra persona, o si se alteró, falla.
     7. Dos cifrados del mismo dato nunca salen iguales, y lo cifrado tiene la forma que pide la tabla user_totp.
     8. Sin llave no se cifra ni se descifra.
    La configuración
     9. DATA_ENCRYPTION_KEY se lee del entorno y no se imprime. Con menos de 43 caracteres el backend no arranca y lo
        dice. Sin ella sí arranca.
"""

import base64
import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from app.core.config import ConfigurationError, load_settings
from app.core.encryption import (
    CURRENT_KEY_VERSION,
    DecryptionFailed,
    EncryptionUnavailable,
    decrypt,
    derive_key,
    encrypt,
)
from app.modules.accounts.totp import (
    DIGITS,
    PERIOD_SECONDS,
    SECRET_BYTES,
    code_at,
    generate_secret,
    matching_step,
    provisioning_uri,
    step_at,
    to_base32,
)

# La clave de los ejemplos del estándar: el texto «12345678901234567890».
RFC_SECRET = b"12345678901234567890"
MASTER = "llave-maestra-inventada-para-las-pruebas-0123456789"
OTHER_MASTER = "otra-llave-maestra-inventada-para-pruebas-987654321"
ANA = b"11111111-1111-4111-8111-111111111111"
JOHN = b"22222222-2222-4222-8222-222222222222"
PURPOSE = "totp-secret"


# --- Caso 1: los vectores oficiales ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "timestamp,eight_digits",
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_the_official_time_examples_give_the_expected_codes(timestamp, eight_digits):
    """RFC 6238, apéndice B (SHA-1). El estándar los da con 8 dígitos; con 6 son los últimos 6."""
    step = step_at(timestamp)

    assert code_at(RFC_SECRET, step, digits=8) == eight_digits
    assert code_at(RFC_SECRET, step) == eight_digits[-6:]


def test_the_official_counter_examples_give_the_expected_codes():
    """RFC 4226, apéndice D: los códigos de los contadores 0 a 9."""
    expected = ["755224", "287082", "359152", "969429", "338314", "254676", "287922", "162583", "399871", "520489"]

    assert [code_at(RFC_SECRET, counter) for counter in range(10)] == expected


def test_a_period_is_thirty_seconds():
    assert PERIOD_SECONDS == 30 and DIGITS == 6
    assert step_at(0) == 0 and step_at(29.999) == 0 and step_at(30) == 1 and step_at(59) == 1 and step_at(60) == 2


def test_a_code_keeps_its_leading_zeros():
    assert code_at(RFC_SECRET, step_at(1111111109)) == "081804"
    assert code_at(RFC_SECRET, step_at(1234567890)) == "005924"


# --- Casos 2 y 3: qué periodos valen ---------------------------------------------------------------------------------

NOW = 1_800_000_015.0  # a la mitad de un periodo
STEP = step_at(NOW)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_current_the_previous_and_the_next_period_are_accepted(offset):
    code = code_at(RFC_SECRET, STEP + offset)

    assert matching_step(RFC_SECRET, code, NOW) == STEP + offset


@pytest.mark.parametrize("offset", [-3, -2, 2, 3, 100, -100])
def test_an_older_or_a_later_period_is_not_accepted(offset):
    code = code_at(RFC_SECRET, STEP + offset)

    assert matching_step(RFC_SECRET, code, NOW) is None


def test_the_edges_of_a_period_follow_the_clock():
    code = code_at(RFC_SECRET, STEP)
    start, end = STEP * 30, STEP * 30 + 29.999

    # El código de un periodo vale desde 30 segundos antes de que empiece hasta 30 segundos después de que termina.
    assert matching_step(RFC_SECRET, code, start) == STEP and matching_step(RFC_SECRET, code, end) == STEP
    assert matching_step(RFC_SECRET, code, start - 30) == STEP and matching_step(RFC_SECRET, code, end + 30) == STEP
    assert matching_step(RFC_SECRET, code, start - 30.001) is None and matching_step(RFC_SECRET, code, end + 30.002) is None


def test_a_code_is_not_accepted_twice():
    code = code_at(RFC_SECRET, STEP)

    assert matching_step(RFC_SECRET, code, NOW, last_used_step=None) == STEP
    assert matching_step(RFC_SECRET, code, NOW, last_used_step=STEP) is None


def test_after_a_code_only_later_periods_are_accepted():
    previous, following = code_at(RFC_SECRET, STEP - 1), code_at(RFC_SECRET, STEP + 1)

    assert matching_step(RFC_SECRET, previous, NOW, last_used_step=STEP) is None
    assert matching_step(RFC_SECRET, previous, NOW, last_used_step=STEP - 1) is None
    assert matching_step(RFC_SECRET, following, NOW, last_used_step=STEP) == STEP + 1
    assert matching_step(RFC_SECRET, previous, NOW, last_used_step=STEP - 2) == STEP - 1


def test_the_code_of_another_key_is_not_accepted():
    other = bytes(range(20))

    assert matching_step(RFC_SECRET, code_at(other, STEP), NOW) is None


# --- Caso 4: lo que no es un código ------------------------------------------------------------------------------------


@pytest.mark.parametrize("written", ["", "12345", "1234567", "abcdef", "12 456", "１２３４５６", " 23456", "-12345", "12345a"])
def test_what_is_not_six_numbers_is_not_a_code(written):
    assert matching_step(RFC_SECRET, written, NOW) is None


# --- Caso 5: cómo se entrega la clave ----------------------------------------------------------------------------------


def test_a_new_key_is_random_and_twenty_bytes_long():
    keys = {generate_secret() for _ in range(50)}

    assert len(keys) == 50
    assert all(len(key) == SECRET_BYTES == 20 for key in keys)


def test_the_key_is_written_in_base32_without_padding():
    assert to_base32(RFC_SECRET) == "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    for _ in range(20):
        written = to_base32(generate_secret())
        assert re.fullmatch(r"[A-Z2-7]{32}", written)
        assert base64.b32decode(written) != b""


def test_the_address_for_the_app_carries_the_name_the_account_and_the_standard_settings():
    uri = provisioning_uri(RFC_SECRET, "ana.torres@prueba.invalid")
    parts = urlsplit(uri)
    query = parse_qs(parts.query)

    assert parts.scheme == "otpauth" and parts.netloc == "totp"
    assert unquote(parts.path) == "/Íntegro:ana.torres@prueba.invalid"
    assert query == {
        "secret": ["GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"], "issuer": ["Íntegro"], "algorithm": ["SHA1"],
        "digits": ["6"], "period": ["30"],
    }


def test_an_odd_account_name_cannot_break_the_address():
    uri = provisioning_uri(RFC_SECRET, "ana+otra&secret=AAAA?x=1#y@prueba.invalid")
    query = parse_qs(urlsplit(uri).query)

    assert query["secret"] == ["GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"]
    assert set(query) == {"secret", "issuer", "algorithm", "digits", "period"}
    assert unquote(urlsplit(uri).path) == "/Íntegro:ana+otra&secret=AAAA?x=1#y@prueba.invalid"


# --- Casos 6 a 8: el cifrado -------------------------------------------------------------------------------------------


def test_what_is_encrypted_comes_back_with_the_same_key_purpose_and_person():
    secret = generate_secret()

    sealed = encrypt(MASTER, PURPOSE, secret, ANA)

    assert decrypt(MASTER, PURPOSE, sealed, ANA) == secret


def test_the_key_is_not_readable_in_what_is_stored():
    sealed = encrypt(MASTER, PURPOSE, RFC_SECRET, ANA)
    raw = base64.b64decode(sealed)

    assert RFC_SECRET not in raw
    assert to_base32(RFC_SECRET) not in sealed
    assert MASTER not in sealed


def test_two_encryptions_of_the_same_key_are_never_equal():
    sealed = {encrypt(MASTER, PURPOSE, RFC_SECRET, ANA) for _ in range(50)}

    assert len(sealed) == 50


def test_what_is_stored_has_the_shape_the_table_asks_for():
    sealed = encrypt(MASTER, PURPOSE, generate_secret(), ANA)

    # 12 bytes + 20 de la clave + 16 = 48 bytes, que en base64 son 64 caracteres (regla de user_totp).
    assert len(sealed) == 64
    assert re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", sealed)
    assert len(base64.b64decode(sealed)) == 12 + 20 + 16


def test_with_another_master_key_it_does_not_decrypt():
    sealed = encrypt(MASTER, PURPOSE, RFC_SECRET, ANA)

    with pytest.raises(DecryptionFailed):
        decrypt(OTHER_MASTER, PURPOSE, sealed, ANA)


def test_moved_to_another_person_it_does_not_decrypt():
    sealed = encrypt(MASTER, PURPOSE, RFC_SECRET, ANA)

    with pytest.raises(DecryptionFailed):
        decrypt(MASTER, PURPOSE, sealed, JOHN)


def test_for_another_purpose_it_does_not_decrypt():
    sealed = encrypt(MASTER, PURPOSE, RFC_SECRET, ANA)

    with pytest.raises(DecryptionFailed):
        decrypt(MASTER, "otro-uso", sealed, ANA)
    assert derive_key(MASTER, PURPOSE) != derive_key(MASTER, "otro-uso")


@pytest.mark.parametrize("position", [0, 5, 12, 20, 40, 47])
def test_any_change_in_what_is_stored_is_noticed(position):
    raw = bytearray(base64.b64decode(encrypt(MASTER, PURPOSE, RFC_SECRET, ANA)))
    raw[position] ^= 0x01
    altered = base64.b64encode(bytes(raw)).decode("ascii")

    with pytest.raises(DecryptionFailed):
        decrypt(MASTER, PURPOSE, altered, ANA)


@pytest.mark.parametrize("stored", ["", "no es base64", "AAAA", "A" * 64, "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"])
def test_what_was_never_encrypted_here_does_not_decrypt(stored):
    with pytest.raises(DecryptionFailed):
        decrypt(MASTER, PURPOSE, stored, ANA)


@pytest.mark.parametrize("missing", [None, ""])
def test_without_the_master_key_nothing_is_encrypted_or_decrypted(missing):
    with pytest.raises(EncryptionUnavailable):
        encrypt(missing, PURPOSE, RFC_SECRET, ANA)
    with pytest.raises(EncryptionUnavailable):
        decrypt(missing, PURPOSE, "A" * 64, ANA)


def test_the_derived_key_is_256_bits_and_is_not_the_master_key():
    key = derive_key(MASTER, PURPOSE)

    assert len(key) == 32
    assert key != MASTER.encode()[:32]
    assert derive_key(MASTER, PURPOSE) == key
    assert CURRENT_KEY_VERSION == 1


# --- Caso 9: la configuración ------------------------------------------------------------------------------------------

BASE = {
    "DATABASE_HOST": "127.0.0.1", "DATABASE_PORT": "5433", "DATABASE_NAME": "integro",
    "DATABASE_USER": "integro_api", "DATABASE_PASSWORD": "clave-inventada", "CODE_HASH_SECRET": "x" * 32,
    "EMAIL_DELIVERY": "console",
}


def environment(clean_environment, **extra):
    for name, value in {**BASE, **extra}.items():
        clean_environment.setenv(name, value)


def test_the_master_key_is_read_from_the_environment_and_is_not_printed(clean_environment):
    environment(clean_environment, DATA_ENCRYPTION_KEY=MASTER)

    settings = load_settings(None)

    assert settings.data_encryption_key.get_secret_value() == MASTER
    assert MASTER not in repr(settings) and MASTER not in str(settings)


def test_without_the_master_key_the_backend_still_starts(clean_environment):
    environment(clean_environment)

    settings = load_settings(None)

    assert settings.data_encryption_key is None
    assert (settings.two_factor_max_attempts, settings.two_factor_wait_minutes) == (5, 15)


@pytest.mark.parametrize("short", ["", "corta", "x" * 42])
def test_a_master_key_that_is_too_short_stops_the_backend_and_says_which_variable(clean_environment, short):
    environment(clean_environment, DATA_ENCRYPTION_KEY=short)

    with pytest.raises(ConfigurationError, match=r"DATA_ENCRYPTION_KEY \(valor no válido\)") as raised:
        load_settings(None)

    assert short == "" or short not in str(raised.value)


def test_forty_three_characters_are_enough(clean_environment):
    environment(clean_environment, DATA_ENCRYPTION_KEY="x" * 43)

    assert load_settings(None).data_encryption_key is not None


def test_the_attempts_and_the_wait_can_be_changed_without_touching_the_code(clean_environment):
    environment(clean_environment, TWO_FACTOR_MAX_ATTEMPTS="3", TWO_FACTOR_WAIT_MINUTES="30")

    settings = load_settings(None)

    assert (settings.two_factor_max_attempts, settings.two_factor_wait_minutes) == (3, 30)
