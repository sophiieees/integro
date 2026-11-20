"""Casos de la pieza "cabecera y pie armados con un script" que se comprueban sin navegador.

Decisión de Sophia del 20 de noviembre de 2026: «haz la cabecera y el pie con
un script». No puede haber copias de la cabecera ni del pie en las cuatro
páginas: viven en web/assets/js/estructura.js y cada página trae solo un
espacio vacío para cada uno.

Qué produce el script (idéntico a lo que las páginas traían escrito) se prueba
con node en estructura.test.js; este archivo la corre y revisa las páginas.
Cómo se ven y se comportan en un navegador está en tests/e2e.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
PAGES = sorted(WEB.glob("*.html"))
SCRIPT = (WEB / "assets" / "js" / "estructura.js").read_text(encoding="utf-8")
CSS = (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8")

VARIANT_OF = {
    "index.html": "portada",
    "propiedad.html": "interior",
    "como-funciona.html": "interior",
    "anfitriones.html": "anfitriones",
    "registro.html": "interior",
}


def test_the_pages_are_the_ones_we_know():
    assert sorted(page.name for page in PAGES) == sorted(VARIANT_OF)


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_the_header_and_the_footer_of_a_page_are_empty_spaces(page):
    text = page.read_text(encoding="utf-8")

    header = re.findall(r"<header[^>]*>.*?</header>", text, re.S)
    footer = re.findall(r"<footer[^>]*>.*?</footer>", text, re.S)
    assert header == [f'<header class="cabecera" data-cabecera="{VARIANT_OF[page.name]}"></header>']
    assert footer == ['<footer class="pie" data-pie></footer>']


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_no_copy_of_the_header_or_the_footer_is_left_in_a_page(page):
    text = page.read_text(encoding="utf-8")

    # Solo lo propio de la cabecera y del pie: el contenido de la página puede usar las mismas palabras
    # (por ejemplo, el botón «Publica tu propiedad» del cuerpo de anfitriones).
    for copied in ('class="marca"', "enlaces-cabecera", "cabecera-acciones", "pie-fila", "btn-reportar", "data-cuenta",
                   "cuenta-entrar", "Términos y condiciones", "Aviso de privacidad"):
        assert copied not in text, f"{page.name} todavía trae «{copied}»"


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_every_page_loads_the_script_that_builds_them(page):
    text = page.read_text(encoding="utf-8")

    assert text.count('<script src="assets/js/estructura.js"></script>') == 1


def test_each_text_of_the_header_and_the_footer_lives_once_in_the_script():
    # «Buscar hospedaje» y «Conviértete en anfitrión» se usan en varias cabeceras, pero se escriben una sola vez.
    for text in ("Buscar hospedaje", "Conviértete en anfitrión", "Publica tu propiedad", "Cómo funciona", "Anfitriones",
                 "Términos y condiciones", "Aviso de privacidad"):
        assert SCRIPT.count(f'texto: "{text}"') == 1, text
    assert SCRIPT.count("Reportar un problema</a>") == 1


def test_the_views_are_a_table_that_grows_without_touching_the_pages():
    assert "var VARIANTES = {" in SCRIPT
    for name in ("portada", "interior", "anfitriones"):
        assert re.search(rf"\b{name}:", SCRIPT), name


def test_the_script_works_in_the_browser_and_in_node():
    assert "module.exports = fabrica()" in SCRIPT
    assert "raiz.INTEGRO_ESTRUCTURA = fabrica()" in SCRIPT
    assert 'if (typeof document !== "undefined") montar(document);' in SCRIPT
    # No hace peticiones: solo arma la cabecera y el pie.
    assert "fetch(" not in SCRIPT and "XMLHttpRequest" not in SCRIPT


def test_the_header_space_has_its_height_before_the_script_fills_it():
    """Sin esto la página se correría hacia abajo al aparecer la cabecera."""
    assert ".cabecera[data-cabecera]:empty { min-height: 69px; }" in CSS
