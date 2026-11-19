"""Casos de la pieza "contraseña de hasta 20 caracteres con indicador de cuatro niveles".

Decisiones de Sophia del 19 de noviembre de 2026:

    - La contraseña mide de 10 a 20 caracteres (antes, de 8 a 12).
    - Niveles: bajo, medio, confiable y muy confiable. El largo da el nivel
      base (10 a 12 medio, 13 a 15 confiable, 16 a 20 muy confiable), dos
      símbolos distintos lo suben un nivel y cada debilidad lo baja un nivel:
      tres caracteres iguales seguidos, cuatro seguidos en orden (también
      símbolos en fila en el teclado), su nombre o su correo en palabras de
      cuatro letras o más, o una palabra de la lista de palabras comunes.
    - Para registrarse hace falta al menos el nivel medio.
    - El cálculo vive en la API, con una ruta que no guarda nada.

Ejemplos que Sophia aprobó:

    Abcde-1x             bajo       (desde la revisión, además no cumple el mínimo de 10)
    Ejemplo-2026         medio
    Lluvia-Verde-26      confiable
    Mi-Casa-Verde-2026   muy confiable
    Aaaa-1111-Bbbb       medio      (14, con repetición)
    Ana-Torres-2026!     confiable  (16, trae su nombre)

Ninguna de estas pruebas usa la base de datos.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.accounts.password_strength import (
    COMMON_WORDS,
    COMMON_WORDS_FROM_AI,
    COMMON_WORDS_FROM_SOPHIA,
    distinct_symbols,
    has_repeated_characters,
    has_sequence,
    password_strength,
    personal_words,
    plain,
    stands_alone,
)
from app.modules.accounts.validation import validate_registration

STRENGTH = "/api/v1/auth/password-strength"
NOW = datetime(2026, 11, 19, 18, 0, tzinfo=timezone.utc)
ANA = {"first_name": "Ana", "last_name": "Torres", "email": "ana.torres@example.com"}


def level_of(password: str, **person) -> tuple[str, tuple[str, ...]]:
    result = password_strength(password, **person)
    return result.level, result.weaknesses


# ---------------------------------------------------------------------------
# Los ejemplos aprobados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, person, level, label",
    [
        ("Abcde-1x", {}, "low", "Bajo"),
        ("Ejemplo-2026", {}, "medium", "Medio"),
        ("Lluvia-Verde-26", {}, "reliable", "Confiable"),
        ("Mi-Casa-Verde-2026", {}, "very_reliable", "Muy confiable"),
        ("Aaaa-1111-Bbbb", {}, "medium", "Medio"),
        ("Ana-Torres-2026!", ANA, "reliable", "Confiable"),
    ],
)
def test_approved_examples(password, person, level, label):
    result = password_strength(password, **person)

    assert (result.level, result.label) == (level, label)


# ---------------------------------------------------------------------------
# El largo da el nivel base
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length, level",
    [(8, "low"), (9, "low"), (10, "medium"), (12, "medium"), (13, "reliable"), (15, "reliable"),
     (16, "very_reliable"), (20, "very_reliable")],
)
def test_base_level_by_length(length, level):
    # Letras y cifras que no forman repeticiones, secuencias ni palabras comunes.
    password = ("Kz7-Pm4-Xv9-Tb2-Rg6-")[:length]

    assert len(password) == length
    assert password_strength(password).level == level


def test_short_is_reported_as_the_reason_for_low():
    assert level_of("Kz7-Pm4-") == ("low", ("short",))
    assert level_of("Kz7-Pm4-Xv") == ("medium", ())


# ---------------------------------------------------------------------------
# Cada debilidad baja un nivel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, person, level, weaknesses",
    [
        # 16 caracteres: sin debilidades es muy confiable.
        ("Kz7-Pm4-Xv9-Tb2-", {}, "very_reliable", ()),
        ("Kzzz-Pm4-Xv9-Tb2", {}, "reliable", ("repeated_characters",)),
        ("Kz7-5678-Xv9-Tb2", {}, "reliable", ("sequence",)),
        # "1234" es secuencia y además está en la lista de palabras comunes: baja dos.
        ("Kz7-1234-Xv9-Tb2", {}, "medium", ("sequence", "common_word")),
        ("Kz7-Torres-Xv9-2", ANA, "reliable", ("personal_data",)),
        ("Kz7-Qwerty-Xv9-2", {}, "medium", ("sequence", "common_word")),
        ("Kz7-Admin-Xv9-22", {}, "reliable", ("common_word",)),
        ("Password-1234-aaa", {}, "low", ("repeated_characters", "sequence", "common_word")),
        ("Torres-1234-aaa-Password", ANA, "low", ("repeated_characters", "sequence", "personal_data", "common_word")),
    ],
)
def test_each_weakness_lowers_one_level(password, person, level, weaknesses):
    assert level_of(password, **person) == (level, weaknesses)


def test_level_never_goes_below_low():
    assert password_strength("aaa-1234-Password").level == "low"


def test_the_same_kind_of_weakness_counts_once():
    """Tres repeticiones distintas siguen siendo una sola debilidad."""
    assert level_of("Aaaa-1111-Bbbb") == ("medium", ("repeated_characters",))


@pytest.mark.parametrize(
    "text, found",
    [("aaa", True), ("xx111yy", True), ("aabbcc", False), ("a-a-a", False), ("---", True), ("", False)],
)
def test_repeated_characters(text, found):
    assert has_repeated_characters(text) is found


@pytest.mark.parametrize(
    "text, found",
    [
        ("1234", True), ("x4321x", True), ("abcd", True), ("dcba", True), ("qwer", True), ("asdf", True),
        ("zxcv", True), ("123", False), ("abc", False), ("1357", False), ("a1b2c3d4", False), ("2026", False),
        # Símbolos en fila en el teclado: español de Latinoamérica e inglés, en los dos sentidos.
        ('!"#$', True), ("$%&/", True), ("/()=", True), ("=)(/", True), ("!@#$", True), ("%^&*", True),
        (")(*&", True), ('!"#', False), ("#-$-%-&", False), ("!#%/", False), ("-_.,", False),
    ],
)
def test_sequences(text, found):
    assert has_sequence(text) is found


# ---------------------------------------------------------------------------
# Dos símbolos distintos suben un nivel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, symbols",
    [("Kz7-Pm4-Xv", {"-"}), ("Kz7-Pm4_Xv", {"-", "_"}), ("Kz7Pm4Xv9T", set()), ("Añ7-Pm4!Xv", {"-", "!"}),
     ("#$%&![{", {"#", "$", "%", "&", "!", "[", "{"})],
)
def test_distinct_symbols(password, symbols):
    assert distinct_symbols(password) == symbols


@pytest.mark.parametrize(
    "password, level",
    [
        ("Kz7-Pm4-Xv", "medium"),  # 10, el mismo símbolo dos veces: no sube
        ("Kz7-Pm4_Xv", "reliable"),  # 10, dos símbolos distintos
        ("Kz7Pm4Xv9Tb", "medium"),  # 11, sin símbolos
        ("Kz7-Pm4-Xv9-T", "reliable"),  # 13, un símbolo
        ("Kz7-Pm4_Xv9-T", "very_reliable"),  # 13, dos símbolos distintos
        ("Kz7-Pm4_Xv9!Tb2#", "very_reliable"),  # 16: ya estaba en el más alto, no hay otro nivel
        ("Kz7-Pm4_", "low"),  # 8: una contraseña corta no sube
        ("Kz7-Pm4_X", "low"),  # 9
    ],
)
def test_two_distinct_symbols_raise_one_level(password, level):
    assert password_strength(password).level == level


def test_more_than_two_symbols_still_raise_only_one_level():
    assert level_of("Kz7-Pm4_X!") == ("reliable", ())


def test_the_raise_is_counted_before_the_weaknesses():
    """Primero sube, con tope en muy confiable, y después bajan las debilidades.

    Por eso el ejemplo aprobado Ana-Torres-2026! sigue en confiable: 16
    caracteres ya es el nivel más alto y su apellido lo baja uno."""
    assert level_of("Ana-Torres-2026!", **ANA) == ("reliable", ("personal_data",))
    # 13 caracteres: confiable, sube a muy confiable y la repetición la deja en confiable.
    assert level_of("Kzzz-Pm4_Xv9T") == ("reliable", ("repeated_characters",))
    # La misma con un solo símbolo: confiable menos uno.
    assert level_of("Kzzz-Pm4-Xv9T") == ("medium", ("repeated_characters",))


RAISE_HINT = "Usa dos símbolos distintos para subir un nivel."


@pytest.mark.parametrize(
    "password, strengths, raise_hints",
    [
        ("Kz7-Pm4-Xv", (), (RAISE_HINT,)),  # 10, un símbolo: puede subir
        ("Kz7Pm4Xv9Tb", (), (RAISE_HINT,)),  # 11, sin símbolos
        ("Kz7-Pm4_Xv", ("varied_symbols",), ()),  # 10, dos distintos: ya subió
        ("Kz7-Pm4-Xv9-T", (), (RAISE_HINT,)),  # 13, un símbolo
        ("Kz7-Pm4_Xv9-T", ("varied_symbols",), ()),  # 13, dos distintos
        ("Kz7-Pm4-Xv9-Tb2-", (), ()),  # 16: ya está en el más alto, nada que subir
        ("Kz7-Pm4_Xv9!Tb2#", (), ()),  # 16 con cuatro símbolos: tampoco subió nada
        ("Kz7-Pm4_", (), ()),  # 8: una contraseña corta no sube; su consejo es el largo
    ],
)
def test_what_adds_to_the_level(password, strengths, raise_hints):
    """Decisión de Sophia del 19 de noviembre: que también se diga lo que suma."""
    result = password_strength(password)

    assert (result.strengths, result.raise_hints) == (strengths, raise_hints)


def test_what_adds_is_told_together_with_what_lowers():
    """Una contraseña con una debilidad sigue recibiendo el consejo de los símbolos."""
    result = password_strength("Kzzz-Pm4-Xv9T")

    assert (result.level, result.weaknesses) == ("medium", ("repeated_characters",))
    assert result.hints == ("Evita repetir el mismo carácter tres veces seguidas.",)
    assert result.raise_hints == (RAISE_HINT,)


def test_symbols_in_a_row_raise_and_lower():
    """Cuatro símbolos en fila son dos símbolos distintos (sube) y una secuencia (baja)."""
    assert level_of('Kz7!"#$Pm4xT') == ("medium", ("sequence",))
    assert level_of("Kz7$%&/Pm4xT") == ("medium", ("sequence",))
    # Los mismos símbolos separados no son secuencia.
    assert level_of("K$z7%P&m4/xT") == ("reliable", ())


def test_capitals_and_accents_do_not_hide_a_weakness():
    assert "common_word" in password_strength("Mi-CONTRASEÑA-9x").weaknesses
    assert "common_word" in password_strength("Mi-Íntegro-2026x").weaknesses
    assert "sequence" in password_strength("Kz7-AbCd-Xv9-Tb2").weaknesses
    assert "repeated_characters" in password_strength("KzZz-Pm4-Xv9-Tb2").weaknesses
    assert plain("ÍNTEGRO Contraseña") == "integro contrasena"


# ---------------------------------------------------------------------------
# La lista de palabras comunes: la de la IA más la que dio Sophia
# ---------------------------------------------------------------------------


def test_the_list_is_the_one_of_the_ai_plus_the_one_sophia_gave():
    """«Complementa tu lista con la mía» (Sophia, 19 de noviembre de 2026)."""
    assert COMMON_WORDS_FROM_AI == (
        "password", "contraseña", "íntegro", "qwerty", "admin", "bienvenido", "welcome", "letmein",
    )
    assert COMMON_WORDS_FROM_SOPHIA == (
        "1234", "gato", "yo", "perro", "cuenta2026", "123456", "111111", "000000", "123123",
        "123456789", "admin", "password", "contraseña", "Pass@123", "1234567890", "abcd1234", "ADMIN",
    )
    # Para comparar: sin mayúsculas ni acentos, y las que están en las dos cuentan una vez.
    assert COMMON_WORDS == (
        "password", "contrasena", "integro", "qwerty", "admin", "bienvenido", "welcome", "letmein",
        "1234", "gato", "yo", "perro", "cuenta2026", "123456", "111111", "000000", "123123",
        "123456789", "pass@123", "1234567890", "abcd1234",
    )


@pytest.mark.parametrize("word", (*COMMON_WORDS_FROM_AI, *COMMON_WORDS_FROM_SOPHIA))
def test_every_word_of_the_list_is_found(word):
    assert "common_word" in password_strength(f"Kz7-{word}-Xv").weaknesses
    assert "common_word" in password_strength(f"Kz7-{word.upper()}-Xv").weaknesses


@pytest.mark.parametrize(
    "password, level",
    [("Mi-Integro-Kz7-Xv", "reliable"), ("Kz7-Bienvenido-9x", "reliable"), ("Kz7-Welcome-Xv9", "medium"),
     ("Kz7-Letmein-Xv9", "medium")],
)
def test_the_words_of_the_first_list_count_again(password, level):
    """Habían salido al tomar la lista de Sophia como la lista completa; ella pidió sumarlas."""
    assert level_of(password) == (level, ("common_word",))


@pytest.mark.parametrize(
    "password",
    ["Mayo-Kz7-Xv9-Tb2", "Apoyo-Kz7-Xv9-Tb", "Rayo-Kz7-Xv9-Tb2", "Yoga-Kz7-Xv9-Tb2", "Kz7-Xv9-Tb2-Joya", "Yoyo-Kz7-Xv9-Tb2"],
)
def test_yo_inside_a_longer_word_does_not_count(password):
    """Decisión de Sophia del 19 de noviembre: «yo» solo como palabra suelta, para que no castigue «mayo»."""
    assert level_of(password) == ("very_reliable", ())


@pytest.mark.parametrize(
    "password",
    [
        "Yo-Kz7-Xv9-Tb2-R",  # al principio
        "Kz7-Xv9-Tb2-R-yo",  # al final
        "Kz7-YO-Xv9-Tb2-R",  # en medio y en mayúsculas
        "Kz7-yo2026-Xv9-T",  # un número pegado no la esconde
        "Kz7yo-Xv9-Tb2-Rg",  # tampoco un número antes
    ],
)
def test_yo_as_a_word_on_its_own_counts(password):
    assert level_of(password) == ("reliable", ("common_word",))


@pytest.mark.parametrize(
    "word, text, alone",
    [("yo", "yo", True), ("yo", "mayo", False), ("yo", "yoga", False), ("yo", "mayo-yo", True),
     ("yo", "7yo7", True), ("yo", "-yo-", True), ("yo", "", False), ("yo", "kz7-xv9", False)],
)
def test_stands_alone(word, text, alone):
    assert stands_alone(word, text) is alone


@pytest.mark.parametrize("password", ["Kz7-Gatos-Xv9-Tb", "Kz7-Perros-Xv9-T", "Administrador-9x"])
def test_the_other_words_are_still_found_anywhere(password):
    """Solo «yo» pide ir suelta; gato, perro o admin cuentan también dentro de otra palabra."""
    assert "common_word" in password_strength(password).weaknesses


def test_a_number_of_the_list_is_also_a_sequence():
    assert level_of("Kz7-123456-Xv9-T") == ("medium", ("sequence", "common_word"))
    # Sin secuencia ni repetición de tres, solo cuenta como palabra común.
    assert level_of("Kz7-123123-Xv9-T") == ("reliable", ("common_word",))


def test_personal_data_comes_from_name_surname_and_email():
    assert personal_words("Ana María", "Torres-López", "anita.t_99@example.com") == {
        "maria", "torres", "lopez", "anita",
    }
    # Lo que va después de la arroba no cuenta, ni las palabras de menos de cuatro letras.
    assert personal_words("Ana", "Luz", "eva@example.com") == set()
    assert personal_words(None, None, None) == set()


@pytest.mark.parametrize(
    "password, weak",
    [("Kz7-TORRES-Xv9-2", True), ("Kz7-Torres-Xv9-2", True), ("Kz7-Pm4-Xv9-Tb2x", False),
     ("Manzana-Roja-9x", False)],  # trae «ana», pero un nombre de tres letras ya no cuenta
)
def test_personal_data_in_any_case(password, weak):
    assert ("personal_data" in password_strength(password, **ANA).weaknesses) is weak


def test_without_personal_data_nothing_is_assumed():
    assert password_strength("Kz7-Torres-Xv9-2").weaknesses == ()


# ---------------------------------------------------------------------------
# El registro: de 10 a 20 y al menos nivel medio
# ---------------------------------------------------------------------------

FORM = {
    "first_name": "Ana",
    "last_name": "Torres",
    "email": "ana.torres@example.com",
    "phone": "+525512345678",
    "country": "MX",
    "birth_date": "1995-03-14",
}


def register_errors(password: str) -> list[tuple[str, str]]:
    _, errors = validate_registration({**FORM, "password": password}, NOW)
    return [(error.field, error.code) for error in errors]


@pytest.mark.parametrize(
    "password",
    ["Ejemplo-2026", "Kz7-Pm4-Xv", "Lluvia-Verde-26", "Mi-Casa-Verde-2026", "Kz7-Pm4-Xv9-Tb2-Rg6-"],
)
def test_registration_accepts_medium_or_better(password):
    assert register_errors(password) == []


def test_registration_accepts_exactly_20_and_rejects_21():
    assert len("Kz7-Pm4-Xv9-Tb2-Rg6-") == 20
    assert register_errors("Kz7-Pm4-Xv9-Tb2-Rg6-") == []
    assert register_errors("Kz7-Pm4-Xv9-Tb2-Rg6-N") == [("password", "too_long")]


@pytest.mark.parametrize(
    "password",
    [
        "Kzzz-Pm4-Xv",  # 11, con repetición
        "Torres-26-xY",  # 12, con su apellido
        "Kz7-1234-xY",  # 11, con secuencia
    ],
)
def test_registration_rejects_a_low_password(password):
    assert register_errors(password) == [("password", "too_weak")]


def test_two_symbols_make_up_for_one_weakness_at_registration():
    """11 caracteres con repetición: con un símbolo sale baja; con dos distintos, media."""
    assert register_errors("Kzzz-Pm4-Xv") == [("password", "too_weak")]
    assert register_errors("Kzzz-Pm4_Xv") == []
    # Con dos debilidades no alcanza.
    assert register_errors("Kz7-1234_xY") == [("password", "too_weak")]


def test_the_too_weak_message_says_how_to_fix_it():
    _, errors = validate_registration({**FORM, "password": "Torres-5678-xY"}, NOW)

    assert len(errors) == 1
    assert errors[0].message == (
        "La contraseña es muy fácil de adivinar. Evita secuencias como 1234 o abcd. "
        "No uses tu nombre ni tu correo."
    )


@pytest.mark.parametrize("password", ["Abcde-1x", "Kz7-Pm4-X"])
def test_registration_rejects_fewer_than_10_characters(password):
    """Con 8 o 9 caracteres ya no cumple la regla del largo."""
    assert register_errors(password) == [("password", "too_short")]


def test_rule_errors_come_before_the_strength_check():
    """Si no cumple las reglas se avisan las reglas, no la fuerza."""
    assert register_errors("abcdef-1xy") == [("password", "missing_uppercase")]
    assert register_errors("Abc-1x") == [("password", "too_short")]


def test_a_long_password_with_her_name_is_still_accepted():
    """Trae su nombre, pero con 16 caracteres queda en confiable."""
    assert register_errors("Ana-Torres-2026!") == []


# ---------------------------------------------------------------------------
# La ruta POST /auth/password-strength
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """La API sin base de datos: esta ruta no la usa."""
    from conftest import TEST_CODE_HASH_SECRET
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        database_host="127.0.0.1",
        database_port=1,
        database_name="integro",
        database_user="integro_api",
        database_password="clave-inventada-para-la-prueba",
        code_hash_secret=TEST_CODE_HASH_SECRET,
        email_delivery="console",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_route_rates_a_password(client):
    response = client.post(STRENGTH, json={"password": "Lluvia-Verde-26"})

    assert response.status_code == 200
    assert response.json() == {
        "level": "reliable",
        "label": "Confiable",
        "weaknesses": [],
        "hints": [],
        "strengths": [],
        "raise_hints": ["Usa dos símbolos distintos para subir un nivel."],
        "meets_rules": True,
        "accepted": True,
        "errors": [],
    }


def test_route_raises_the_level_with_two_distinct_symbols(client):
    one = client.post(STRENGTH, json={"password": "Kz7-Pm4-Xv"}).json()
    two = client.post(STRENGTH, json={"password": "Kz7-Pm4_Xv"}).json()

    assert (one["level"], one["label"]) == ("medium", "Medio")
    assert (one["strengths"], one["raise_hints"]) == ([], ["Usa dos símbolos distintos para subir un nivel."])
    assert (two["level"], two["label"], two["weaknesses"], two["accepted"]) == ("reliable", "Confiable", [], True)
    assert (two["strengths"], two["raise_hints"]) == (["varied_symbols"], [])


def test_route_says_nothing_adds_when_the_rules_are_broken(client):
    """Sin cumplir las reglas sale baja y no se dan consejos para subir: primero van las reglas."""
    body = client.post(STRENGTH, json={"password": "lluvia verde"}).json()

    assert (body["meets_rules"], body["strengths"], body["raise_hints"]) == (False, [], [])


def test_route_reports_symbols_in_a_row_as_a_sequence(client):
    body = client.post(STRENGTH, json={"password": "Kz7$%&/Pm4xT"}).json()

    assert (body["level"], body["weaknesses"]) == ("medium", ["sequence"])
    assert body["hints"] == ["Evita secuencias como 1234 o abcd."]


def test_route_uses_the_personal_data_when_it_is_given(client):
    alone = client.post(STRENGTH, json={"password": "Ana-Torres-2026!"}).json()
    with_person = client.post(STRENGTH, json={"password": "Ana-Torres-2026!", **ANA}).json()

    assert alone["level"] == "very_reliable"
    assert (with_person["level"], with_person["weaknesses"]) == ("reliable", ["personal_data"])
    assert with_person["hints"] == ["No uses tu nombre ni tu correo."]


def test_route_says_a_low_password_would_not_be_accepted(client):
    body = client.post(STRENGTH, json={"password": "Kz7-1234-xY"}).json()

    assert (body["level"], body["label"], body["meets_rules"], body["accepted"]) == ("low", "Bajo", True, False)
    assert body["weaknesses"] == ["sequence", "common_word"]
    assert body["hints"] == ["Evita secuencias como 1234 o abcd.", "Evita palabras muy comunes."]


def test_route_says_which_rule_a_short_password_breaks(client):
    body = client.post(STRENGTH, json={"password": "Abcde-1x"}).json()

    assert (body["level"], body["meets_rules"], body["accepted"]) == ("low", False, False)
    assert [error["code"] for error in body["errors"]] == ["too_short"]


def test_route_reports_broken_rules_and_rates_it_low(client):
    body = client.post(STRENGTH, json={"password": "lluvia verde"}).json()

    assert (body["level"], body["meets_rules"], body["accepted"]) == ("low", False, False)
    assert [error["code"] for error in body["errors"]] == [
        "has_spaces", "missing_uppercase", "missing_digit", "missing_symbol",
    ]


def test_route_rates_low_a_password_longer_than_20(client):
    body = client.post(STRENGTH, json={"password": "Kz7-Pm4-Xv9-Tb2-Rg6-N"}).json()

    assert (body["level"], body["accepted"]) == ("low", False)
    assert [error["code"] for error in body["errors"]] == ["too_long"]


@pytest.mark.parametrize("body", [{}, {"password": ""}, {"password": None}, {"password": 12345678}])
def test_route_without_a_password_is_rejected(client, body):
    response = client.post(STRENGTH, json=body)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "password"


def test_route_ignores_personal_data_that_is_not_text(client):
    response = client.post(STRENGTH, json={"password": "Lluvia-Verde-26", "first_name": 5, "email": ["x"]})

    assert response.status_code == 200
    assert response.json()["level"] == "reliable"


def test_route_never_echoes_the_password(client):
    response = client.post(STRENGTH, json={"password": "Lluvia-Verde-26"})

    assert "Lluvia-Verde-26" not in response.text


def test_route_only_accepts_post_and_is_documented(client):
    assert client.get(STRENGTH).status_code == 405
    assert STRENGTH in client.get("/openapi.json").json()["paths"]
