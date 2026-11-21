"""Casos de la pantalla de registro que se comprueban sin navegador.

Decisiones de Sophia del 20 de noviembre de 2026: página aparte (registro.html), todos los datos obligatorios,
teléfono con selector de código y número, todos los países con México primero e indicador de cuatro cuadros.

La lógica (qué se manda, qué pasa con cada respuesta de la API) se prueba con node en registro_logica.test.js;
este archivo revisa la página y los scripts. Cómo se ve y se comporta en un navegador, con el servidor y la base,
está en tests/e2e/test_registro_e2e.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import importlib.resources as resources
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
PAGE = (WEB / "registro.html").read_text(encoding="utf-8")
SCREEN = (WEB / "assets" / "js" / "registro.js").read_text(encoding="utf-8")
LOGIC = (WEB / "assets" / "js" / "registro-logica.js").read_text(encoding="utf-8")
COUNTRIES = (WEB / "assets" / "js" / "paises.js").read_text(encoding="utf-8")
CSS = (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8")

FIELDS = {
    # nombre del campo: (tipo de etiqueta, autocomplete)
    "first_name": ("input", "given-name"),
    "last_name": ("input", "family-name"),
    "email": ("input", "email"),
    "password": ("input", "new-password"),
    "numero": ("input", "tel-national"),
    "country": ("select", "country"),
    "birth_date": ("input", "bday"),
}


def tag(name: str) -> str:
    """La etiqueta de apertura del campo con ese nombre."""
    found = re.search(rf'<(?:input|select)\b[^>]*\bname="{name}"[^>]*>', PAGE)
    assert found, name
    return found.group(0)


# --- La página --------------------------------------------------------------------


def test_the_page_has_its_title_description_and_browser_bar_colour():
    assert "<title>Crea tu cuenta | Íntegro</title>" in PAGE
    assert '<meta name="description" content="Crea tu cuenta en Íntegro' in PAGE
    assert '<meta name="theme-color" content="#1F4D3A">' in PAGE
    assert '<html lang="es-MX">' in PAGE


def test_the_header_and_the_footer_are_the_empty_spaces_of_the_structure_script():
    assert PAGE.count('<header class="cabecera" data-cabecera="interior"></header>') == 1
    assert PAGE.count('<footer class="pie" data-pie></footer>') == 1
    for copied in ('class="marca"', "enlaces-cabecera", "pie-fila", "btn-reportar", "data-cuenta"):
        assert copied not in PAGE


def test_the_scripts_load_in_the_order_they_need():
    order = [PAGE.index(f'src="assets/js/{name}.js"') for name in ("estructura", "cuenta-logica", "cuenta", "paises", "registro-logica", "registro")]

    assert order == sorted(order)


def test_every_required_field_is_there_with_its_autocomplete():
    for name, (kind, autocomplete) in FIELDS.items():
        assert tag(name).startswith(f"<{kind}"), name
        assert f'autocomplete="{autocomplete}"' in tag(name), name
    assert 'type="password"' in tag("password")
    assert 'type="email"' in tag("email")
    assert 'type="date"' in tag("birth_date") and 'min="1900-01-01"' in tag("birth_date")
    assert 'type="tel"' in tag("numero")
    # La lista del código de marcación del teléfono.
    assert re.search(r'<select name="marcacion"[^>]*aria-label="Código de marcación del país"', PAGE)


def test_the_password_has_no_length_limit_in_the_browser_because_the_api_explains_the_limits():
    assert "maxlength" not in tag("password")
    assert "De 10 a 20 caracteres, con mayúscula, minúscula, número y símbolo, sin espacios." in PAGE


def test_the_form_checks_nothing_by_itself_because_the_script_gives_the_warnings():
    assert '<form id="formulario-registro" data-paso="datos" novalidate>' in PAGE
    assert "required" not in re.sub(r"<!--.*?-->", "", PAGE, flags=re.S).replace("data-required", "")


@pytest.mark.parametrize("name", ["first_name", "last_name", "email", "password", "country", "birth_date"])
def test_every_field_has_a_label_that_points_at_it(name):
    field_id = re.search(r'\bid="([^"]+)"', tag(name)).group(1)

    assert f'<label class="campo-etiqueta" for="{field_id}">' in PAGE


def test_the_phone_has_a_group_label_and_each_part_has_a_name_for_screen_readers():
    assert 'id="registro-etiqueta-telefono"' in PAGE
    assert 'role="group" aria-labelledby="registro-etiqueta-telefono"' in PAGE
    assert 'aria-label="Número de teléfono"' in tag("numero")


@pytest.mark.parametrize(
    "api_field, input_name",
    [("first_name", "first_name"), ("last_name", "last_name"), ("email", "email"), ("password", "password"),
     ("phone", "numero"), ("country", "country"), ("birth_date", "birth_date")],
)
def test_every_field_has_its_place_for_the_notice_and_the_input_points_at_it(api_field, input_name):
    assert f'id="registro-error-{api_field}" data-error-de="{api_field}" hidden' in PAGE
    assert f"registro-error-{api_field}" in tag(input_name)


def test_the_terms_checkbox_is_there_with_no_links_and_nothing_to_unfold():
    """Decisión de Sophia del 20 de noviembre de 2026: la casilla, sin desplegar nada porque no hay texto legal."""
    label = re.search(r'<label class="casilla" for="registro-terminos">.*?</label>', PAGE, re.S).group(0)

    assert 'type="checkbox"' in label and 'name="terminos"' in label
    assert "Acepto los términos y condiciones y el aviso de privacidad." in label
    assert "<a " not in label and "href" not in label
    assert 'id="registro-error-terms" data-error-de="terms" hidden' in PAGE
    # Sin enlaces a textos legales: ni en el formulario ni en una ventana.
    form = re.search(r'<form id="formulario-registro".*?</form>', PAGE, re.S).group(0)
    assert re.findall(r'<a [^>]*href="([^"]+)"', form) == ["#entrar"]
    assert "required" not in tag("terminos")


def test_the_three_steps_are_there_and_only_the_data_is_shown():
    assert '<form id="formulario-registro" data-paso="datos" novalidate>' in PAGE
    assert '<form id="formulario-codigo" data-paso="codigo" novalidate hidden>' in PAGE
    assert '<div id="registro-listo" data-paso="listo" hidden>' in PAGE
    assert 'autocomplete="one-time-code"' in PAGE and 'maxlength="6"' in PAGE and 'inputmode="numeric"' in PAGE
    assert "data-reenviar" in PAGE and ">Enviar otro código</button>" in PAGE
    assert 'data-iniciar-sesion>Iniciar sesión</button>' in PAGE


def test_the_page_offers_to_sign_in_and_the_notices_are_announced():
    assert '¿Ya tienes una cuenta? <a href="#entrar" data-abrir-sesion>Inicia sesión</a>' in PAGE
    assert 'data-aviso role="alert" hidden' in PAGE
    assert 'data-ya-con-sesion role="status" hidden' in PAGE


# --- El indicador de la contraseña ---------------------------------------------------


def test_the_indicator_has_four_squares_and_is_announced_while_it_changes():
    block = re.search(r'<div class="fortaleza".*?</ul>\s*</div>', PAGE, re.S).group(0)

    assert 'aria-live="polite"' in block
    assert block.count("<span></span>") == 4
    assert "data-fortaleza-nivel" in block and "data-fortaleza-consejos" in block


@pytest.mark.parametrize(
    "level, token",
    [("bajo", "--color-alerta"), ("medio", "--color-acento"), ("confiable", "--color-primario"), ("muy-confiable", "--color-primario")],
)
def test_each_level_has_its_colour_of_the_palette(level, token):
    rule = re.search(rf'\.fortaleza\[data-nivel="{level}"\][^{{]*\{{([^}}]*)\}}', CSS)

    assert rule is not None, level
    assert f"background: var({token})" in rule.group(1)


def test_the_gold_of_the_indicator_is_a_fill_and_never_a_text_colour():
    assert not re.search(r"(?<![\w-])color:\s*var\(--color-acento\)", CSS)


# --- Los países ------------------------------------------------------------------------


def test_the_countries_are_the_ones_the_api_knows():
    table = resources.files("tzdata").joinpath("zoneinfo", "zone.tab").read_text(encoding="utf-8")
    api = sorted({line.split("\t")[0] for line in table.splitlines() if line and not line.startswith("#")})
    listed = re.findall(r'\["([A-Z]{2})", (\d+)\]', COUNTRIES)

    assert [code for code, _ in listed] == api
    assert len(listed) == 247


def test_the_dial_codes_of_the_main_countries():
    codes = {code: int(dial) for code, dial in re.findall(r'\["([A-Z]{2})", (\d+)\]', COUNTRIES)}

    assert {k: codes[k] for k in ("MX", "US", "CA", "ES", "CO", "AR", "GB", "DE")} == {
        "MX": 52, "US": 1, "CA": 1, "ES": 34, "CO": 57, "AR": 54, "GB": 44, "DE": 49,
    }


def test_the_countries_file_says_it_is_generated_and_how():
    assert "Archivo generado por tools/countries/generate_countries.py" in COUNTRIES
    assert (REPO / "tools" / "countries" / "generate_countries.py").is_file()
    assert 'PRIMERO: "MX"' in COUNTRIES


# --- Lo que hacen los scripts ------------------------------------------------------------


def test_the_script_only_talks_to_the_own_api_with_the_cookie_the_page_cannot_read():
    assert 'var API = "/api/v1/auth";' in SCREEN
    assert 'credentials: "same-origin"' in SCREEN
    for route in ('"/password-strength"', '"/register"', '"/verify-email"', '"/resend-code"', 'API + "/me"'):
        assert route in SCREEN, route
    assert "http://" not in SCREEN and "https://" not in SCREEN


def test_the_password_is_never_kept_in_the_browser():
    assert "localStorage" not in SCREEN and "sessionStorage" not in SCREEN and "document.cookie" not in SCREEN
    # Al crearse la cuenta, el campo se vacía.
    assert 'campo("password").value = "";' in SCREEN


def test_a_late_answer_of_the_indicator_is_ignored():
    assert "if (numero !== estado.secuencia) return;" in SCREEN
    assert "estado.temporizador = setTimeout(calificar, 300);" in SCREEN


def test_the_logic_works_in_the_browser_and_in_node_and_does_not_touch_the_page():
    assert "module.exports = fabrica(require(\"./cuenta-logica.js\"), require(\"./paises.js\"));" in LOGIC
    assert "raiz.INTEGRO_REGISTRO = fabrica(raiz.INTEGRO_CUENTA, raiz.INTEGRO_PAISES);" in LOGIC
    assert "document." not in LOGIC and "fetch(" not in LOGIC


def test_the_page_tells_the_registration_script_is_ready():
    """Las pruebas de principio a fin esperan esta marca."""
    assert 'document.documentElement.setAttribute("data-registro-listo", "");' in SCREEN


def test_the_texts_are_formal_but_of_tu():
    for usted in ("Escriba", "Intente", "Revise", "Vuelva", "tiene una cuenta"):
        assert usted not in LOGIC and usted not in SCREEN and usted not in PAGE, usted
    assert "Te enviamos un código de 6 dígitos a " in LOGIC
