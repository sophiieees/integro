"""Casos de las páginas de las vistas que se comprueban sin navegador.

Decisión de Sophia del 20 de noviembre de 2026: crear las vistas en el frontend y en el backend (docs/diseno/vistas.md).
Cada vista tiene su página de inicio:

    mi-cuenta.html       cliente: sus datos, reservas, mensajes, reseñas y comentarios
    anfitrion.html       anfitrión: propiedades, reservas, reseñas, comentarios, chats y publicaciones
    administracion.html  administrador: verificaciones, casos, cargos y bitácora
    proximamente.html    Experiencias y Servicios de la barra de navegación

Lo que cada una muestra a cada persona se prueba con node (cuenta_logica.test.js) y, con navegador, servidor y base,
en tests/e2e/test_vistas_e2e.py. Este archivo revisa lo que las páginas traen escrito.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"

PROTECTED = {
    "mi-cuenta.html": ("sesion", ["datos", "reservas", "mensajes", "resenas", "comentarios"]),
    "anfitrion.html": ("anfitrion", ["propiedades", "reservas", "resenas", "comentarios", "chats", "publicar"]),
    "administracion.html": ("administrador", ["verificaciones", "casos", "cargos", "bitacora"]),
}


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name, spec", PROTECTED.items())
def test_a_protected_page_says_who_can_see_it(name, spec):
    text = read(name)

    assert re.search(rf'<body data-requiere="{spec[0]}">', text)


@pytest.mark.parametrize("name", PROTECTED)
def test_the_content_is_hidden_until_the_script_knows_who_is_looking(name):
    """Sin script, o antes de saber quién mira, no hay contenido: solo «Comprobando tu sesión»."""
    text = read(name)

    assert "<div data-contenido hidden>" in text
    assert '<h1 data-acceso-titulo>Comprobando tu sesión</h1>' in text
    assert 'data-acceso-enlace href="#entrar" hidden' in text


@pytest.mark.parametrize("name, spec", PROTECTED.items())
def test_every_section_the_header_points_to_exists(name, spec):
    text = read(name)

    for section in spec[1]:
        assert f'<section class="vista-seccion" id="{section}">' in text, section
    assert len(re.findall(r'class="vista-seccion"', text)) == len(spec[1])


@pytest.mark.parametrize("name", PROTECTED)
def test_nothing_personal_is_written_in_the_page(name):
    """Los datos de la persona los pone cuenta.js, con lo que contesta la API, no vienen en el archivo."""
    text = read(name)

    assert not re.search(r"@[a-z0-9-]+\.[a-z]{2,}", text, re.I)
    for node in re.findall(r'<(?:dd|span|p)[^>]*data-dato="[a-z]+"[^>]*>(.*?)</(?:dd|span|p)>', text):
        assert node == ""


def test_my_account_has_the_two_data_it_shows():
    text = read("mi-cuenta.html")

    assert '<dd data-dato="nombre"></dd>' in text and '<dd data-dato="correo"></dd>' in text


@pytest.mark.parametrize("name", [*PROTECTED, "proximamente.html"])
def test_each_page_loads_the_scripts_in_order(name):
    text = read(name)
    scripts = re.findall(r'<script src="assets/js/([a-z-]+)\.js"></script>', text)

    assert scripts[:3] == ["estructura", "cuenta-logica", "cuenta"]
    assert scripts[3:] == (["proximamente"] if name == "proximamente.html" else [])


def test_proximamente_is_public_and_its_title_comes_from_the_address():
    text = read("proximamente.html")

    assert "data-requiere" not in text
    assert "<h1 data-titulo-de-seccion>Próximamente</h1>" in text
    assert 'href="index.html#resultados">Ver alojamientos</a>' in text
    script = (WEB / "assets" / "js" / "proximamente.js").read_text(encoding="utf-8")
    assert "tituloDeSeccion(window.location.search)" in script
    assert "textContent = titulo" in script and "innerHTML" not in script


def test_the_pages_of_each_view_do_not_promise_what_does_not_exist():
    """Cada sección dice «Próximamente»: ninguna pretende funcionar todavía."""
    for name, spec in PROTECTED.items():
        text = read(name)
        sections = re.findall(r'<section class="vista-seccion" id="([a-z]+)">(.*?)</section>', text, re.S)
        for section, body in sections:
            if section == "datos":
                continue
            assert "Próximamente" in body, f"{name}#{section}"
            assert "<form" not in body and "<button" not in body, f"{name}#{section}"


def test_the_reseñas_of_the_host_use_the_words_sophia_gave():
    text = read("anfitrion.html")

    assert "responder con un agradecimiento o una disculpa" in text
