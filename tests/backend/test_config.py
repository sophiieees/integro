"""Casos de la configuración: qué pasa si falta una variable o trae un valor malo."""

import pytest

from app.core.config import ConfigurationError, load_settings

VALID = {
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5433",
    "DATABASE_NAME": "integro",
    "DATABASE_USER": "integro_api",
    "DATABASE_PASSWORD": "clave-inventada-para-la-prueba",
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


def test_no_variables_at_all_names_the_five(clean_environment):
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
