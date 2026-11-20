"""Casos de la cabecera y el pie armados con un script, de principio a fin: navegador, servidor y base de verdad.

Decisión de Sophia del 20 de noviembre de 2026: «haz la cabecera y el pie con
un script». Las páginas traen solo un espacio vacío para cada uno y
web/assets/js/estructura.js los llena.

    1. Cada página muestra su cabecera y su pie, con los mismos enlaces que
       traían escritos a mano.
    2. La portada es solo para el huésped: su cabecera no ofrece «Buscar hospedaje».
    3. Los enlaces llevan a donde dicen.
    4. «Reportar un problema» se ve en dorado arena.
    5. La cabecera ocupa su lugar desde el principio y queda fija arriba.
    6. En celular, el botón «Publica tu propiedad» de la cabecera de anfitriones se oculta.
    7. Sin JavaScript, la página se ve sin cabecera ni pie (consecuencia aceptada, ADR 0008).

Corren contra la base `integro` de backend/.env, dentro de una transacción que
se deshace al terminar el archivo. Ver e2e_support.py y README.md.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import pytest
from e2e_support import browser, page, site  # noqa: F401

PAGES = {
    "index.html": ["Íntegro", "Conviértete en anfitrión", "Iniciar sesión"],
    "propiedad.html?id=2": ["Íntegro", "Buscar hospedaje", "Conviértete en anfitrión", "Iniciar sesión"],
    "como-funciona.html": ["Íntegro", "Buscar hospedaje", "Conviértete en anfitrión", "Iniciar sesión"],
    "anfitriones.html": ["Íntegro", "Buscar hospedaje", "Publica tu propiedad", "Iniciar sesión"],
}
FOOTER = ["Íntegro", "Reportar un problema", "Cómo funciona", "Anfitriones", "Términos y condiciones", "Aviso de privacidad"]

HEADER_LINKS = "Array.from(document.querySelectorAll('header.cabecera .marca, header.cabecera a, header.cabecera button')).map(e => e.textContent.trim())"
FOOTER_TEXTS = "Array.from(document.querySelectorAll('footer.pie strong, footer.pie a')).map(e => e.textContent.trim())"


def go(page, site, path):
    page.goto(f"{site.url}/{path}")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


# --- Caso 1 ------------------------------------------------------------------------


@pytest.mark.parametrize("path, header", PAGES.items())
def test_every_page_shows_its_header_and_its_footer(page, site, path, header):
    go(page, site, path)

    # La marca y los enlaces, en el orden en que se ven.
    assert page.js(HEADER_LINKS) == header
    assert page.js(FOOTER_TEXTS) == FOOTER


@pytest.mark.parametrize("path", PAGES)
def test_there_is_one_header_and_one_footer_per_page(page, site, path):
    go(page, site, path)

    assert page.js("document.querySelectorAll('header').length") == 1
    assert page.js("document.querySelectorAll('footer').length") == 1
    assert page.js("document.querySelectorAll('[data-cuenta]').length") == 1


@pytest.mark.parametrize("path", PAGES)
def test_the_brand_link_goes_to_the_home_page(page, site, path):
    go(page, site, path)

    assert page.js("document.querySelector('header .marca').getAttribute('href')") == "index.html"
    assert page.js("document.querySelector('header .marca').getAttribute('aria-label')") == "Íntegro, inicio"


# --- Caso 2 ------------------------------------------------------------------------


def test_the_home_page_header_does_not_offer_buscar_hospedaje(page, site):
    go(page, site, "index.html")

    assert "Buscar hospedaje" not in page.js(HEADER_LINKS)
    assert page.js("document.querySelectorAll('header .enlaces-cabecera a').length") == 1


def test_the_other_pages_headers_do_offer_it(page, site):
    for path in ("propiedad.html?id=2", "como-funciona.html", "anfitriones.html"):
        go(page, site, path)
        assert "Buscar hospedaje" in page.js(HEADER_LINKS), path


def test_the_host_page_has_the_publish_button_and_not_the_become_host_link(page, site):
    go(page, site, "anfitriones.html")

    links = page.js(HEADER_LINKS)
    assert "Publica tu propiedad" in links
    assert "Conviértete en anfitrión" not in links
    assert page.js("document.querySelector('header .btn-azul').getAttribute('href')") == "#publicar"


# --- Caso 3 ------------------------------------------------------------------------


def click_and_arrive(page, selector, pathname):
    page.click(selector)
    page.expect(f"location.pathname === '{pathname}'")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


def test_the_brand_goes_to_the_home_page(page, site):
    go(page, site, "como-funciona.html")

    click_and_arrive(page, "header .marca", "/index.html")

    assert page.header() == ["Iniciar sesión"]


def test_the_header_link_to_become_a_host_goes_to_the_host_page(page, site):
    go(page, site, "index.html")

    click_and_arrive(page, "header .enlaces-cabecera a", "/anfitriones.html")

    assert page.js("document.querySelector('header .btn-azul') !== null") is True


def test_buscar_hospedaje_goes_to_the_home_page(page, site):
    go(page, site, "anfitriones.html")

    click_and_arrive(page, "header .btn-enlace", "/index.html")


def test_the_footer_links_go_where_they_say(page, site):
    go(page, site, "index.html")
    click_and_arrive(page, "footer.pie nav a[href='como-funciona.html']", "/como-funciona.html")

    click_and_arrive(page, "footer.pie nav a[href='anfitriones.html']", "/anfitriones.html")

    assert page.js(FOOTER_TEXTS) == FOOTER


def test_the_account_zone_filled_by_the_other_script_is_inside_the_built_header(page, site):
    go(page, site, "propiedad.html?id=2")

    assert page.js("document.querySelector('header [data-cuenta] .cuenta-entrar').textContent") == "Iniciar sesión"
    assert page.is_clickable("header [data-cuenta] .cuenta-entrar") is True


# --- Caso 4 ------------------------------------------------------------------------


@pytest.mark.parametrize("path", PAGES)
def test_reportar_un_problema_is_gold_with_night_green_letter(page, site, path):
    go(page, site, path)

    colors = page.js(
        "(() => { const s = getComputedStyle(document.querySelector('footer .btn-reportar')); "
        "return [s.backgroundColor, s.color]; })()"
    )
    assert colors == ["rgb(201, 166, 107)", "rgb(20, 42, 33)"]


# --- Caso 5 ------------------------------------------------------------------------


@pytest.mark.parametrize("path", PAGES)
def test_the_header_keeps_its_place_and_stays_on_top(page, site, path):
    go(page, site, path)

    height = page.js("document.querySelector('header.cabecera').getBoundingClientRect().height")
    assert height == 69
    assert page.js("getComputedStyle(document.querySelector('header.cabecera')).position") == "sticky"
    # Al bajar, la cabecera sigue arriba.
    page.js("window.scrollTo(0, 600); 1")
    assert page.js("Math.round(document.querySelector('header.cabecera').getBoundingClientRect().top)") == 0


def test_the_header_is_built_before_the_page_is_shown_to_the_person(page, site):
    """Cuando termina de cargar, el espacio ya tiene su contenido: no queda un hueco vacío."""
    page.goto(f"{site.url}/index.html")

    assert page.js("document.querySelector('header.cabecera').children.length") > 0
    assert page.js("document.querySelector('footer.pie').children.length") > 0


# --- Caso 6 ------------------------------------------------------------------------


def test_on_a_phone_the_publish_button_of_the_header_is_hidden(page, site):
    page.set_viewport(390, 844, mobile=True)
    go(page, site, "anfitriones.html")

    assert page.js("getComputedStyle(document.querySelector('header .btn-azul')).display") == "none"
    assert page.js("document.querySelector('header .btn-enlace').getBoundingClientRect().width") > 0
    assert page.is_clickable("header [data-cuenta] .cuenta-entrar") is True


def test_on_a_phone_the_header_does_not_overflow_the_screen(page, site):
    page.set_viewport(390, 844, mobile=True)
    for path in PAGES:
        go(page, site, path)
        right = page.js("Math.max(...Array.from(document.querySelectorAll('header.cabecera *')).map(e => e.getBoundingClientRect().right))")
        assert right <= 390, (path, right)


# --- Caso 7 ------------------------------------------------------------------------


def test_without_javascript_the_page_has_no_header_and_no_footer(page, site):
    """Consecuencia aceptada por Sophia: sin script, la cabecera y el pie no existen; el contenido de la página sí."""
    page.send("Emulation.setScriptExecutionDisabled", value=True)

    page.goto(f"{site.url}/como-funciona.html")

    assert page.js("document.querySelector('header.cabecera').children.length") == 0
    assert page.js("document.querySelector('footer.pie').children.length") == 0
    assert page.js("document.querySelector('main') !== null && document.querySelector('main').textContent.length") > 100
    page.send("Emulation.setScriptExecutionDisabled", value=False)
