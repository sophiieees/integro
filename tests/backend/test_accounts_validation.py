"""Reglas del formulario de registro, sin base de datos.

Decisiones de Sophia del 17 de noviembre de 2026: todos los datos obligatorios,
18 años cumplidos, y contraseña de mínimo 8 caracteres con mayúscula,
minúscula, número y símbolo.
"""

from datetime import date, datetime, timezone

import pytest

from app.modules.accounts.security import generate_code, hash_code, hash_password, same_hash
from app.modules.accounts.validation import (
    is_adult,
    password_errors,
    time_zones_by_country,
    today_in_country,
    validate_registration,
)
from app.notifications.console import ConsoleCodeSender
from app.notifications.whatsapp import WhatsAppCodeSender

# El instante del registro en casi todas las pruebas: mediodía del 17 de
# noviembre de 2026 en la Ciudad de México. En todo México es 17 de noviembre.
NOW = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)

VALID_FORM = {
    "first_name": "Ana",
    "last_name": "Torres",
    "email": "ana@example.com",
    "password": "Ejemplo-2026",
    "phone": "+525512345678",
    "country": "MX",
    "birth_date": "1995-03-14",
    "preferred_language": "es",
}


def errors_for(**changes) -> list[tuple[str, str]]:
    """Avisos (campo, código) que da el formulario válido con esos cambios."""
    _, errors = validate_registration({**VALID_FORM, **changes}, NOW)
    return [(error.field, error.code) for error in errors]


# ---------------------------------------------------------------------------
# Formulario completo
# ---------------------------------------------------------------------------


def test_valid_form_is_accepted_as_written():
    data, errors = validate_registration(VALID_FORM, NOW)

    assert errors == []
    assert data.first_name == "Ana"
    assert data.last_name == "Torres"
    assert data.email == "ana@example.com"
    assert data.password == "Ejemplo-2026"
    assert data.phone == "+525512345678"
    assert data.country == "MX"
    assert data.birth_date == date(1995, 3, 14)
    assert data.preferred_language == "es"


def test_form_is_tidied_before_saving():
    data, errors = validate_registration(
        {
            **VALID_FORM,
            "first_name": "  Ana ",
            "email": "  Ana@Example.COM ",
            "country": "mx",
            "preferred_language": "EN",
        },
        NOW,
    )

    assert errors == []
    assert data.first_name == "Ana"
    assert data.email == "ana@example.com"
    assert data.country == "MX"
    assert data.preferred_language == "en"
    assert data.password == "Ejemplo-2026"


@pytest.mark.parametrize("language", [None, "", "   "])
def test_language_defaults_to_spanish(language):
    data, errors = validate_registration({**VALID_FORM, "preferred_language": language}, NOW)

    assert errors == []
    assert data.preferred_language == "es"


def test_language_missing_from_the_form_defaults_to_spanish():
    form = {key: value for key, value in VALID_FORM.items() if key != "preferred_language"}

    data, errors = validate_registration(form, NOW)

    assert errors == []
    assert data.preferred_language == "es"


# ---------------------------------------------------------------------------
# Caso 2. Datos obligatorios
# ---------------------------------------------------------------------------

REQUIRED = ["first_name", "last_name", "email", "password", "phone", "country", "birth_date"]


@pytest.mark.parametrize("field", REQUIRED)
@pytest.mark.parametrize("empty", [None, "", "   "])
def test_each_required_field_empty_is_reported(field, empty):
    assert errors_for(**{field: empty}) == [(field, "required")]


@pytest.mark.parametrize("field", REQUIRED)
def test_each_required_field_missing_is_reported(field):
    form = {key: value for key, value in VALID_FORM.items() if key != field}

    _, errors = validate_registration(form, NOW)

    assert [(error.field, error.code) for error in errors] == [(field, "required")]


def test_empty_form_reports_every_required_field():
    _, errors = validate_registration({}, NOW)

    assert [(error.field, error.code) for error in errors] == [
        (field, "required") for field in REQUIRED
    ]


@pytest.mark.parametrize("field", REQUIRED)
@pytest.mark.parametrize("value", [123, True, ["x"], {"a": 1}])
def test_field_that_is_not_text_is_reported(field, value):
    assert errors_for(**{field: value}) == [(field, "invalid")]


def test_several_wrong_fields_are_reported_together():
    assert errors_for(email="sin-arroba", phone="5512345678", country="México") == [
        ("email", "invalid"),
        ("phone", "invalid"),
        ("country", "invalid"),
    ]


# ---------------------------------------------------------------------------
# Caso 3. Edad mínima
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "birth_date, today, adult",
    [
        (date(2008, 11, 17), date(2026, 11, 17), True),  # cumple 18 hoy
        (date(2008, 11, 18), date(2026, 11, 17), False),  # cumple 18 mañana
        (date(2008, 11, 16), date(2026, 11, 17), True),  # cumplió 18 ayer
        (date(1950, 1, 1), date(2026, 11, 17), True),
        (date(2026, 11, 17), date(2026, 11, 17), False),  # nació hoy
        (date(2008, 2, 29), date(2026, 2, 28), False),  # nació un 29 de febrero
        (date(2008, 2, 29), date(2026, 3, 1), True),
        (date(2006, 2, 28), date(2024, 2, 28), True),
        (date(2006, 3, 1), date(2024, 2, 29), False),
    ],
)
def test_is_adult(birth_date, today, adult):
    assert is_adult(birth_date, today) is adult


def test_turns_18_tomorrow_is_rejected():
    assert errors_for(birth_date="2008-11-18") == [("birth_date", "under_age")]


def test_turns_18_today_is_accepted():
    assert errors_for(birth_date="2008-11-17") == []


@pytest.mark.parametrize(
    "birth_date",
    ["2026-11-18", "2999-01-01", "1899-12-31", "14/03/1995", "1995-02-30", "ayer", "1995-3-14"],
)
def test_birth_date_that_is_not_valid_is_reported(birth_date):
    assert errors_for(birth_date=birth_date) == [("birth_date", "invalid")]


def test_oldest_birth_date_allowed():
    assert errors_for(birth_date="1900-01-01") == []


# ---------------------------------------------------------------------------
# La edad se cuenta con la fecha del país de la persona
# (decisión de Sophia del 17 de noviembre de 2026, al revisar la pieza)
# ---------------------------------------------------------------------------

# 18 de noviembre a las 03:00 en hora universal: en la Ciudad de México y en
# Nueva York todavía es 17; en Madrid y en Tokio ya es 18.
LATE_IN_MEXICO = datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "country, today",
    [
        ("MX", date(2026, 11, 17)),
        ("US", date(2026, 11, 17)),
        ("ES", date(2026, 11, 18)),
        ("JP", date(2026, 11, 18)),
        ("ZZ", date(2026, 11, 18)),  # país que no está en la tabla
        (None, date(2026, 11, 18)),  # sin país
    ],
)
def test_today_depends_on_the_country(country, today):
    assert today_in_country(country, LATE_IN_MEXICO) == today


def test_country_with_several_time_zones_uses_the_most_advanced():
    # 05:30 en hora universal: en Cancún ya es 18 (00:30) y en la Ciudad de México sigue siendo 17 (23:30).
    assert today_in_country("MX", datetime(2026, 11, 18, 5, 30, tzinfo=timezone.utc)) == date(2026, 11, 18)
    # 13:00 en hora universal del 17: en Kamchatka ya es 18 (01:00); en Moscú sigue siendo 17.
    assert today_in_country("RU", datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc)) == date(2026, 11, 18)


def test_time_zone_table_covers_the_countries():
    table = time_zones_by_country()

    assert len(table) > 240
    assert "America/Mexico_City" in table["MX"]
    assert table["JP"] == ("Asia/Tokyo",)


def form_errors_at(now, **changes) -> list[tuple[str, str]]:
    _, errors = validate_registration({**VALID_FORM, **changes}, now)
    return [(error.field, error.code) for error in errors]


def test_same_birthday_is_rejected_in_mexico_and_accepted_in_spain():
    """Cumple 18 el 18 de noviembre. En México aún es 17; en España ya es 18."""
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2008-11-18", country="MX") == [
        ("birth_date", "under_age")
    ]
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2008-11-18", country="ES") == []
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2008-11-18", country="es") == []


def test_birth_date_in_the_future_depends_on_the_country_too():
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2026-11-18", country="MX") == [
        ("birth_date", "invalid")
    ]
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2026-11-18", country="JP") == [
        ("birth_date", "under_age")
    ]


def test_missing_country_does_not_add_a_wrong_age_warning():
    assert form_errors_at(LATE_IN_MEXICO, birth_date="2008-11-18", country=None) == [
        ("country", "required")
    ]


# ---------------------------------------------------------------------------
# Caso 4. Contraseña
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, codes",
    [
        ("Ejemplo-2026", []),
        ("Abcdef-1xy", []),  # justo 10
        ("Abcde-1xy", ["too_short"]),  # 9
        ("Abcde-1x", ["too_short"]),  # 8: desde el 19 de noviembre el mínimo es 10
        ("ejemplo-2026", ["missing_uppercase"]),
        ("EJEMPLO-2026", ["missing_lowercase"]),
        ("Ejemplo-dos", ["missing_digit"]),
        ("Ejemplo2026", ["missing_symbol"]),
        ("Ejemplo 2026", ["has_spaces", "missing_symbol"]),  # el espacio no cuenta como símbolo
        ("Ejem plo-26", ["has_spaces"]),  # espacio en medio
        (" Ejemplo-26", ["has_spaces"]),  # espacio al inicio
        ("Ejemplo-26 ", ["has_spaces"]),  # espacio al final
        ("Ejemplo-26\t", ["has_spaces"]),  # tabulador
        ("abcdefghij", ["missing_uppercase", "missing_digit", "missing_symbol"]),
        ("1234567890", ["missing_uppercase", "missing_lowercase", "missing_symbol"]),
        ("a", ["too_short", "missing_uppercase", "missing_digit", "missing_symbol"]),
        ("Aa1-" + "x" * 16, []),  # justo 20
        ("Aa1-" + "x" * 17, ["too_long"]),  # 21
        ("Ejemplo-2026-largo", []),  # 18: desde el 19 de noviembre cabe hasta 20
        ("Contraseña-1", []),  # letras con acento o eñe valen
    ],
)
def test_password_rules(password, codes):
    assert [error.code for error in password_errors(password)] == codes
    assert all(error.field == "password" for error in password_errors(password))


def test_weak_password_is_reported_in_the_form():
    assert errors_for(password="Ejemplo2026") == [("password", "missing_symbol")]


def test_password_with_spaces_is_rejected_not_trimmed():
    """Decisión de Sophia: una contraseña no lleva espacios; se avisa, no se le quitan."""
    assert errors_for(password=" Ejemplo-26") == [("password", "has_spaces")]
    assert errors_for(password="Ejem plo-26") == [("password", "has_spaces")]


# ---------------------------------------------------------------------------
# Caso 5. Formatos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email",
    ["sin-arroba", "ana@", "@example.com", "ana@example", "ana maria@example.com", "ana@@example.com", "a" * 250 + "@x.mx"],
)
def test_email_with_invalid_format_is_reported(email):
    assert errors_for(email=email) == [("email", "invalid")]


@pytest.mark.parametrize(
    "phone",
    ["5512345678", "+0525512345678", "+52 55 1234 5678", "+52-55-1234-5678", "+1234567", "+1234567890123456", "telefono"],
)
def test_phone_with_invalid_format_is_reported(phone):
    assert errors_for(phone=phone) == [("phone", "invalid")]


@pytest.mark.parametrize("phone", ["+12345678", "+123456789012345", "+14155550123"])
def test_phone_on_the_limits_is_accepted(phone):
    assert errors_for(phone=phone) == []


@pytest.mark.parametrize("country", ["México", "MEX", "M", "M1", "52"])
def test_country_with_invalid_format_is_reported(country):
    assert errors_for(country=country) == [("country", "invalid")]


@pytest.mark.parametrize("language", ["fr", "español", 5])
def test_language_outside_the_list_is_reported(language):
    assert errors_for(preferred_language=language) == [("preferred_language", "invalid")]


def test_name_length_limits():
    assert errors_for(first_name="x" * 80, last_name="y" * 80) == []
    assert errors_for(first_name="x" * 81) == [("first_name", "too_long")]
    assert errors_for(last_name="y" * 81) == [("last_name", "too_long")]


# ---------------------------------------------------------------------------
# Contraseñas y códigos: lo que se guarda
# ---------------------------------------------------------------------------


def test_password_is_converted_with_argon2id():
    converted = hash_password("Ejemplo-2026")

    assert converted.startswith("$argon2id$")
    assert "Ejemplo-2026" not in converted
    # Dos conversiones de la misma contraseña no dan el mismo texto.
    assert hash_password("Ejemplo-2026") != converted


@pytest.mark.parametrize("length", [4, 6, 10])
def test_code_has_only_digits_and_the_asked_length(length):
    for _ in range(50):
        code = generate_code(length)
        assert len(code) == length
        assert code.isdigit()


def test_codes_are_not_always_the_same():
    assert len({generate_code(6) for _ in range(50)}) > 40


def test_code_fingerprint_has_the_format_the_database_expects():
    fingerprint = hash_code("123456", secret="s" * 32, purpose="verify_email", destination="ana@example.com")

    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
    assert "123456" not in fingerprint


def test_code_fingerprint_depends_on_code_secret_purpose_and_destination():
    base = dict(secret="s" * 32, purpose="verify_email", destination="ana@example.com")
    original = hash_code("123456", **base)

    assert hash_code("123456", **base) == original
    assert hash_code("123457", **base) != original
    assert hash_code("123456", **{**base, "secret": "t" * 32}) != original
    assert hash_code("123456", **{**base, "purpose": "login"}) != original
    assert hash_code("123456", **{**base, "destination": "beto@example.com"}) != original


def test_same_hash():
    assert same_hash("a" * 64, "a" * 64) is True
    assert same_hash("a" * 64, "b" * 64) is False


# ---------------------------------------------------------------------------
# Envío de códigos
# ---------------------------------------------------------------------------


def test_development_mode_writes_the_code_in_the_server_window(capsys):
    ConsoleCodeSender().send_code(
        channel="email", destination="ana@example.com", code="123456", purpose="verify_email", ttl_seconds=300
    )

    written = capsys.readouterr().out
    assert "MODO DESARROLLO" in written
    assert "ana@example.com" in written
    assert "123456" in written
    assert "5 minutos" in written


def test_whatsapp_is_still_pending():
    with pytest.raises(NotImplementedError):
        WhatsAppCodeSender().send_code(
            channel="whatsapp", destination="+525512345678", code="123456", purpose="login", ttl_seconds=300
        )
