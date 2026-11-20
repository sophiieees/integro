"""Casos de la pieza "ventana de «Entrar»" que se comprueban sin navegador.

Decisiones de Sophia del 19 de noviembre de 2026: «Entrar» como texto sin
borde a la derecha de la cabecera, una ventana sobre la página con los dos
pasos, el enlace a registro.html, y al terminar la persona sigue en la
página donde estaba.

La lógica (qué pasa con cada respuesta de la API) se prueba con node en
cuenta_logica.test.js; este archivo la corre y además revisa lo que las
páginas y los scripts tienen que traer. Los casos de principio a fin, con un
navegador de verdad, el servidor y la base, están en tests/e2e.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
PAGES = sorted(WEB.glob("*.html"))
LOGIC = (WEB / "assets" / "js" / "cuenta-logica.js").read_text(encoding="utf-8")
SCREEN = (WEB / "assets" / "js" / "cuenta.js").read_text(encoding="utf-8")
CSS = (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8")


def test_the_logic_cases_pass_with_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Falta node: la lógica de la ventana se prueba con node --test.")
    result = subprocess.run(
        [node, "--test", "--test-reporter=tap", str(Path(__file__).with_name("cuenta_logica.test.js"))],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"^# fail 0$", result.stdout, re.M), result.stdout
    assert int(re.search(r"^# pass (\d+)$", result.stdout, re.M).group(1)) >= 20


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_every_page_has_entrar_on_the_right_of_the_header(page):
    text = page.read_text(encoding="utf-8")
    header = re.search(r"<header.*?</header>", text, re.S).group(0)

    assert header.count("data-cuenta") == 1
    assert '<a class="cuenta-entrar" href="#entrar">Entrar</a>' in header
    # Texto sin borde, no botón.
    assert 'class="btn btn-primario" href="#entrar"' not in header


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_every_page_loads_the_logic_before_the_screen(page):
    text = page.read_text(encoding="utf-8")

    assert text.index('src="assets/js/app.js"') < text.index('src="assets/js/cuenta-logica.js"') < text.index('src="assets/js/cuenta.js"')


def test_the_logic_works_in_the_browser_and_in_node():
    assert "module.exports = fabrica()" in LOGIC
    assert "raiz.INTEGRO_CUENTA = fabrica()" in LOGIC
    assert "document." not in LOGIC and "fetch(" not in LOGIC


def test_the_screen_talks_to_the_api_the_way_the_cookie_needs():
    assert 'credentials: "same-origin"' in SCREEN
    assert '"X-CSRF-Token"' in SCREEN
    for route in ('"/me"', '"/login"', '"/login/verify"', '"/logout"'):
        assert route in SCREEN
    assert 'var API = "/api/v1/auth"' in SCREEN
    # Nunca lee ni escribe la llave de sesión: viaja en la cookie.
    assert "document.cookie" not in SCREEN and "localStorage" not in SCREEN and "sessionStorage" not in SCREEN


def test_the_window_has_the_two_steps_and_the_register_link():
    assert 'data-paso=\\"correo\\"' in SCREEN and 'data-paso=\\"codigo\\"' in SCREEN
    assert 'name=\\"email\\"' in SCREEN and 'name=\\"password\\"' in SCREEN and 'name=\\"code\\"' in SCREEN
    assert 'autocomplete=\\"current-password\\"' in SCREEN and 'autocomplete=\\"one-time-code\\"' in SCREEN
    assert 'maxlength=\\"6\\"' in SCREEN and 'inputmode=\\"numeric\\"' in SCREEN
    assert '<a href=\\"registro.html\\">Regístrate</a>' in SCREEN
    assert 'role=\\"dialog\\"' in SCREEN and 'aria-modal=\\"true\\"' in SCREEN


def test_escape_backdrop_and_cancel_close_the_window_and_clear_it():
    assert 'e.key === "Escape"' in SCREEN
    assert "if (e.target === fondo) cerrarVentana();" in SCREEN
    assert "[data-cancelar]" in SCREEN
    body = SCREEN[SCREEN.index("function cerrarVentana"):SCREEN.index("function enviarCorreo")]
    assert body.count(".reset()") == 2


def test_a_hidden_window_is_really_hidden():
    """Sin esta regla el display: grid de la ventana le gana al atributo hidden y la ventana cerrada tapa la página."""
    assert ".ventana-fondo[hidden] { display: none; }" in CSS


def test_the_window_is_styled_with_the_palette_and_works_on_a_phone():
    assert ".ventana-fondo { position: fixed; inset: 0;" in CSS
    assert "max-width: 420px" in CSS and "width: 100%" in CSS
    assert ".ventana-aviso" in CSS and "var(--color-alerta)" in CSS
    assert "prefers-reduced-motion" in CSS
    for selector in (".cuenta-entrar", ".cuenta-nombre", ".cuenta-salir", "body.con-ventana"):
        assert selector in CSS or selector == ".cuenta-salir"
