"""Casos de la pieza "ventana de «Iniciar sesión»" que se comprueban sin navegador.

Decisiones de Sophia del 19 de noviembre de 2026: «Iniciar sesión» como texto sin
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
        [node, "--test", "--test-reporter=tap", str(Path(__file__).with_name("cuenta_logica.test.js")),
         str(Path(__file__).with_name("estructura.test.js")), str(Path(__file__).with_name("registro_logica.test.js"))],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"^# fail 0$", result.stdout, re.M), result.stdout
    # 20 de la cuenta, 14 de la cabecera y el pie y 36 del registro.
    assert int(re.search(r"^# pass (\d+)$", result.stdout, re.M).group(1)) >= 70


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_every_page_loads_the_structure_then_the_logic_then_the_screen(page):
    """La cuenta se pinta en un espacio que arma estructura.js: tiene que cargarse antes."""
    text = page.read_text(encoding="utf-8")
    # app.js solo está en las páginas que pintan propiedades; el registro no lo necesita.
    names = [name for name in ("app", "estructura", "cuenta-logica", "cuenta") if f'src="assets/js/{name}.js"' in text]
    order = [text.index(f'src="assets/js/{name}.js"') for name in names]

    assert names[-3:] == ["estructura", "cuenta-logica", "cuenta"]
    assert order == sorted(order)


def test_the_account_is_painted_by_the_screen_script_as_text_without_a_border():
    """«Iniciar sesión» es un enlace de texto, no un botón; lo pinta cuenta.js en el espacio que deja la cabecera."""
    assert 'entrar.className = "cuenta-entrar";' in SCREEN
    assert 'entrar.textContent = "Iniciar sesión";' in SCREEN
    assert 'btn btn-primario" href="#entrar"' not in SCREEN


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
    assert "document.cookie" not in SCREEN and "localStorage" not in SCREEN


def test_the_only_thing_kept_in_the_browser_is_which_view_an_admin_chose_to_look_at():
    """sessionStorage solo guarda eso, solo en esa pestaña: nunca la llave de sesión ni la clave de la página."""
    assert 'var VER_COMO = "integro_view_as";' in SCREEN
    uses = re.findall(r"sessionStorage\.(\w+)\(([^)]*)\)", SCREEN)
    assert uses, "debería usarlo para recordar la vista elegida"
    assert {method for method, _ in uses} <= {"getItem", "setItem", "removeItem"}
    assert all(args.startswith("VER_COMO") for _, args in uses)
    # Y solo vale para quien es administrador: si deja de serlo, se olvida.
    assert "if (!estado.esAdmin && leerVerComo()) guardarVerComo(null);" in SCREEN
    assert 'if (vista === "cliente" || vista === "anfitrion")' in SCREEN


def test_the_name_and_the_email_are_written_as_text_never_as_html():
    """Lo que viene de la API (nombre, apellidos, correo) entra con textContent: ahí no se interpreta HTML."""
    assert not re.search(r"innerHTML\s*=[^;]*estado\.", SCREEN)
    assert "nombre.textContent = estado.nombre;" in SCREEN
    assert 'if (typeof valor === "string") el.textContent = valor;' in SCREEN
    # Sin permiso se borran: no quedan escondidos en la página.
    assert "llenarDatos(true);" in SCREEN


def test_the_window_has_the_two_steps_and_the_register_link():
    assert 'data-paso=\\"correo\\"' in SCREEN and 'data-paso=\\"codigo\\"' in SCREEN
    assert 'name=\\"email\\"' in SCREEN and 'name=\\"password\\"' in SCREEN and 'name=\\"code\\"' in SCREEN
    assert 'autocomplete=\\"current-password\\"' in SCREEN and 'autocomplete=\\"one-time-code\\"' in SCREEN
    assert 'maxlength=\\"6\\"' in SCREEN and 'inputmode=\\"numeric\\"' in SCREEN
    assert '<a href=\\"registro.html\\">Regístrate</a>' in SCREEN
    assert 'role=\\"dialog\\"' in SCREEN and 'aria-modal=\\"true\\"' in SCREEN


def test_the_window_has_a_third_step_for_the_authenticator_code():
    """Pieza 3.3: quien tiene el Authenticator activo escribe el código de su aplicación después del código del correo."""
    assert 'data-paso=\\"authenticator\\"' in SCREEN
    assert 'name=\\"totp\\" autocomplete=\\"one-time-code\\" inputmode=\\"numeric\\" maxlength=\\"7\\"' in SCREEN
    # El texto del paso se escribe como texto, no como HTML, y sale de la lógica.
    assert 'querySelector("[data-texto-authenticator]").textContent = LOGICA.TEXTO_DEL_AUTHENTICATOR' in SCREEN
    # El paso tiene su propia salida: cerrar la sesión que quedó en espera.
    assert "data-salir-de-espera>Cerrar sesión</button>" in SCREEN
    order = [SCREEN.index(f'data-paso=\\"{step}\\"') for step in ("correo", "codigo", "authenticator")]
    assert order == sorted(order)


def test_the_authenticator_code_goes_to_its_own_route_with_the_page_key_and_without_captcha():
    assert 'peticion("POST", "/2fa/verify", datos, estado.clave)' in SCREEN
    assert 'peticionConCaptcha("POST", "/2fa/verify"' not in SCREEN
    assert "var datos = { code: LOGICA.limpiarCodigoDeAuthenticator(form.totp.value) };" in SCREEN


def test_a_waiting_session_opens_the_window_straight_at_the_authenticator_step():
    assert 'if (estado.enEspera) { mostrarPaso("authenticator", null, "totp"); return; }' in SCREEN
    assert "estado.enEspera = cabecera.enEspera;" in SCREEN
    # Al salir de la espera, por cerrar sesión o porque venció, se olvida.
    assert "estado.esAnfitrion = false; estado.esAdmin = false; estado.enEspera = false;" in SCREEN


def test_a_code_that_did_not_work_is_not_left_written():
    assert 'form.totp.value = "";' in SCREEN
    assert 'formulario("authenticator").reset();' in SCREEN


def test_the_register_invitation_is_hidden_in_the_authenticator_step():
    assert 'ventana.querySelector(".ventana-pie").hidden = paso === "authenticator";' in SCREEN


def test_escape_backdrop_and_cancel_close_the_window_and_clear_it():
    assert 'e.key === "Escape"' in SCREEN
    assert "if (e.target === fondo) cerrarVentana();" in SCREEN
    assert "[data-cancelar]" in SCREEN
    body = SCREEN[SCREEN.index("function cerrarVentana"):SCREEN.index("function enviarCorreo")]
    # Los tres formularios se limpian: correo y contraseña, código del correo y código del Authenticator.
    assert body.count(".reset()") == 3


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
