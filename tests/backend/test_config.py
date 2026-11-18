"""Casos de la configuración: qué pasa si falta una variable o trae un valor malo."""

import pytest

from app.core.config import ConfigurationError, load_settings

VALID = {
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5433",
    "DATABASE_NAME": "integro",
    "DATABASE_USER": "integro_api",
    "DATABASE_PASSWORD": "clave-inventada-para-la-prueba",
    "CODE_HASH_SECRET": "llave-inventada-para-las-pruebas-0123456789",
    "EMAIL_DELIVERY": "console",
}


def set_variables(monkeypatch, **changes):
    """Pone las variables válidas con los cambios pedidos. None quita la variable."""
    for variable, value in {**VALID, **changes}.items():
        if value is None:
            monkeypatch.delenv(variable, raising=False)
        else:
            monkeypatch.setenv(variable, value)


def test_complete_configuration_is_accepted(clean_environment):
    set_variables(clean_environment)

    settings = load_settings(env_file=None)

    assert settings.database_host == "localhost"
    assert settings.database_port == 5433
    assert settings.database_name == "integro"
    assert settings.database_user == "integro_api"
    assert settings.database_password.get_secret_value() == "clave-inventada-para-la-prueba"


def test_configuration_is_read_from_env_file(clean_environment, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{variable}={value}" for variable, value in VALID.items()),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.database_port == 5433
    assert settings.database_name == "integro"


def test_environment_variable_wins_over_env_file(clean_environment, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{variable}={value}" for variable, value in VALID.items()),
        encoding="utf-8",
    )
    clean_environment.setenv("DATABASE_NAME", "other_database")

    settings = load_settings(env_file=env_file)

    assert settings.database_name == "other_database"


@pytest.mark.parametrize("variable", sorted(VALID))
def test_each_missing_variable_is_named(clean_environment, variable):
    set_variables(clean_environment, **{variable: None})

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert f"{variable} (falta)" in str(raised.value)


def test_no_variables_at_all_names_every_required_one(clean_environment):
    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    for variable in VALID:
        assert f"{variable} (falta)" in str(raised.value)


@pytest.mark.parametrize("variable", sorted(set(VALID) - {"DATABASE_PORT"}))
def test_empty_value_is_rejected(clean_environment, variable):
    set_variables(clean_environment, **{variable: ""})

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert f"{variable} (valor no válido)" in str(raised.value)


@pytest.mark.parametrize("port", ["1", "5433", "65535"])
def test_port_inside_range_is_accepted(clean_environment, port):
    set_variables(clean_environment, DATABASE_PORT=port)

    assert load_settings(env_file=None).database_port == int(port)


@pytest.mark.parametrize("port", ["0", "65536", "-1", "", "abc", "54.33"])
def test_port_outside_range_is_rejected(clean_environment, port):
    set_variables(clean_environment, DATABASE_PORT=port)

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert "DATABASE_PORT (valor no válido)" in str(raised.value)


def test_error_never_shows_the_password(clean_environment):
    set_variables(clean_environment, DATABASE_HOST=None)

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert "clave-inventada-para-la-prueba" not in str(raised.value)
    # Tampoco queda escondida en el error original de validación.
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


def test_printing_the_settings_hides_the_password(clean_environment):
    set_variables(clean_environment)

    settings = load_settings(env_file=None)

    assert "clave-inventada-para-la-prueba" not in repr(settings)
    assert "clave-inventada-para-la-prueba" not in str(settings)


# ---------------------------------------------------------------------------
# Códigos de un solo uso (ADR 0014)
# ---------------------------------------------------------------------------


def test_code_limits_default_to_the_decided_values(clean_environment):
    set_variables(clean_environment)

    settings = load_settings(env_file=None)

    assert settings.code_length == 6
    assert settings.code_ttl_seconds == 300
    assert settings.code_max_attempts == 5
    assert settings.code_resend_wait_seconds == 60
    assert settings.code_max_per_hour == 5


def test_code_limits_can_be_changed_without_touching_the_code(clean_environment):
    set_variables(clean_environment, CODE_TTL_SECONDS="600", CODE_MAX_PER_HOUR="3")

    settings = load_settings(env_file=None)

    assert settings.code_ttl_seconds == 600
    assert settings.code_max_per_hour == 3


@pytest.mark.parametrize("secret", ["corta", "x" * 31])
def test_code_hash_secret_shorter_than_32_is_rejected(clean_environment, secret):
    set_variables(clean_environment, CODE_HASH_SECRET=secret)

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert "CODE_HASH_SECRET (valor no válido)" in str(raised.value)
    assert secret not in str(raised.value)


def test_code_hash_secret_of_32_is_accepted(clean_environment):
    set_variables(clean_environment, CODE_HASH_SECRET="x" * 32)

    assert load_settings(env_file=None).code_hash_secret.get_secret_value() == "x" * 32


@pytest.mark.parametrize("delivery", ["smtp", "CONSOLE", "sms", "whatsapp"])
def test_email_delivery_not_built_is_rejected(clean_environment, delivery):
    set_variables(clean_environment, EMAIL_DELIVERY=delivery)

    with pytest.raises(ConfigurationError) as raised:
        load_settings(env_file=None)

    assert "EMAIL_DELIVERY (valor no válido)" in str(raised.value)


def test_printing_the_settings_hides_the_code_hash_secret(clean_environment):
    set_variables(clean_environment)

    settings = load_settings(env_file=None)

    assert VALID["CODE_HASH_SECRET"] not in repr(settings)
    assert VALID["CODE_HASH_SECRET"] not in str(settings)
