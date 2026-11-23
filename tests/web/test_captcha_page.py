"""Casos del CAPTCHA en las pantallas que se comprueban sin navegador.

Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016): Cloudflare Turnstile, siempre activo, en cinco acciones. Cada
zona del widget declara su acción en el HTML (data-captcha="register") y esa es la única fuente: el widget se la dice a
Cloudflare y la API espera la suya en cada ruta.

La lógica se prueba con node en captcha_logica.test.js y captcha.test.js. Cómo se ve y se comporta con navegador, servidor
y base está en tests/e2e/test_captcha_e2e.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
JS = WEB / "assets" / "js"
PAGES = sorted(path.name for path in WEB.glob("*.html"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


REGISTER = read(WEB / "registro.html")
RECOVER = read(WEB / "recuperar-contrasena.html")
ACCOUNT = read(JS / "cuenta.js")
REGISTER_JS = read(JS / "registro.js")
RECOVER_JS = read(JS / "recuperar.js")
CAPTCHA_JS = read(JS / "captcha.js")
CAPTCHA_LOGIC = read(JS / "captcha-logica.js")
CSS = read(WEB / "assets" / "css" / "estilos.css")
ROUTER = read(ROOT / "backend" / "app" / "modules" / "accounts" / "router.py")


def code_of(text: str) -> str:
    """El archivo sin sus comentarios: lo que de verdad se ejecuta."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def form_of(page: str, form_id: str) -> str:
    """El HTML de un formulario o bloque de la página, por su id."""
    start = page.index(f'id="{form_id}"')
    end = page.index("</form>", start) if "<form" in page[start - 30:start] else page.index("\n          </div>", start)
    return page[start:end]


def zones_in(block: str) -> list[str]:
    return re.findall(r'<div class="captcha" data-captcha="([a-z_]+)"></div>', block)


# --- Los scripts ------------------------------------------------------------------------------------------------------


def test_there_are_pages():
    assert len(PAGES) == 10


@pytest.mark.parametrize("name", PAGES)
def test_every_page_with_the_account_script_loads_the_captcha_scripts_before_it(name):
    text = read(WEB / name)
    order = [text.index(f'<script src="assets/js/{script}.js"></script>')
             for script in ("captcha-logica", "captcha", "cuenta-logica", "cuenta")]

    assert order == sorted(order), name


def test_the_script_of_cloudflare_is_only_named_in_one_place_and_never_written_in_a_page():
    for path in [*WEB.glob("*.html"), *JS.glob("*.js")]:
        text = read(path)
        if path.name == "captcha-logica.js":
            assert text.count("https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit") == 1
        else:
            assert "challenges.cloudflare.com" not in text, path.name


def test_no_key_is_written_in_the_web_folder():
    for path in [*WEB.glob("*.html"), *JS.glob("*.js"), WEB / "assets" / "css" / "estilos.css"]:
        text = read(path)
        assert not re.search(r"\b[0-3]x[A-Za-z0-9_-]{18,}", text), path.name
        assert "secret" not in code_of(text).lower(), path.name


# --- Las zonas --------------------------------------------------------------------------------------------------------


def test_the_registration_page_has_one_zone_in_each_form_that_asks_for_the_captcha_and_none_where_it_does_not():
    assert zones_in(form_of(REGISTER, "formulario-registro")) == ["register"]
    assert zones_in(form_of(REGISTER, "formulario-codigo")) == ["resend_code"]
    assert zones_in(form_of(REGISTER, "formulario-correccion")) == ["correct_email"]
    assert zones_in(form_of(REGISTER, "registro-listo")) == []
    assert REGISTER.count("data-captcha") == 3


def test_the_recovery_page_has_a_zone_in_each_of_its_two_forms_and_none_in_the_done_step():
    assert zones_in(form_of(RECOVER, "formulario-correo")) == ["password_reset"]
    assert zones_in(form_of(RECOVER, "formulario-cambio")) == ["password_reset"]
    assert zones_in(form_of(RECOVER, "recuperar-listo")) == []
    assert RECOVER.count("data-captcha") == 2


def test_the_sign_in_window_has_its_zone_in_the_first_step_only():
    first, second = ACCOUNT.index('data-paso=\\"correo\\"'), ACCOUNT.index('data-paso=\\"codigo\\"')

    assert ACCOUNT.count("data-captcha") == 2  # la zona y la búsqueda de la zona
    zone = ACCOUNT.index('<div class=\\"captcha\\" data-captcha=\\"login\\"></div>')
    assert first < zone < second


@pytest.mark.parametrize("page,form_id", [
    (REGISTER, "formulario-registro"), (REGISTER, "formulario-codigo"), (REGISTER, "formulario-correccion"),
    (RECOVER, "formulario-correo"), (RECOVER, "formulario-cambio"),
])
def test_the_zone_goes_right_before_the_buttons_of_its_form(page, form_id):
    block = form_of(page, form_id)

    assert re.search(r'<div class="captcha" data-captcha="[a-z_]+"></div>\s*<div class="formulario-acciones', block)


def test_the_actions_of_the_pages_are_exactly_the_five_the_api_asks_for():
    in_pages = set(zones_in(REGISTER)) | set(zones_in(RECOVER)) | {"login"}
    in_api = set(re.findall(r'require_captcha\("([a-z_]+)"\)', ROUTER))
    in_logic = set(re.findall(r'^\s+\w+: "([a-z_]+)",?$', CAPTCHA_LOGIC.split("var ACCIONES = {")[1].split("};")[0], re.M))

    assert in_pages == in_api == in_logic
    assert len(in_api) == 5


# --- Quién llama a qué ------------------------------------------------------------------------------------------------


def test_the_registration_page_never_calls_a_captcha_route_without_the_captcha():
    for route in ("/register", "/resend-code", "/correct-unverified-email"):
        assert f'peticion("{route}"' not in REGISTER_JS, route
        assert f'peticionConCaptcha("{route}"' in REGISTER_JS, route
    # Escribir el código de verificación no pide CAPTCHA.
    assert 'peticion("/verify-email"' in REGISTER_JS
    assert 'peticionConCaptcha("/verify-email"' not in REGISTER_JS


def test_the_recovery_page_never_calls_the_code_request_without_the_captcha():
    assert 'peticion("/password-reset/request"' not in RECOVER_JS
    assert RECOVER_JS.count('peticionConCaptcha("/password-reset/request"') == 2
    assert 'peticion("/password-reset/confirm"' in RECOVER_JS
    assert 'peticionConCaptcha("/password-reset/confirm"' not in RECOVER_JS


def test_the_sign_in_window_asks_for_the_captcha_in_the_first_step_only():
    assert 'peticion("POST", "/login",' not in ACCOUNT
    assert 'peticionConCaptcha("POST", "/login",' in ACCOUNT
    assert 'peticion("POST", "/login/verify"' in ACCOUNT
    assert 'peticionConCaptcha("POST", "/login/verify"' not in ACCOUNT


def test_the_result_travels_in_the_header_the_api_reads_and_only_when_there_is_one():
    assert 'X-Captcha-Token' in CAPTCHA_LOGIC and "CAPTCHA_HEADER = \"X-Captcha-Token\"" in read(ROOT / "backend" / "app" / "api" / "captcha.py")
    for text in (ACCOUNT, REGISTER_JS, RECOVER_JS):
        assert "if (captcha) cabeceras[CAPTCHA_LOGICA.ENCABEZADO] = captcha;" in text
        assert "X-Captcha-Token" not in code_of(text)


def test_a_request_that_has_no_result_is_never_sent():
    for text in (ACCOUNT, REGISTER_JS, RECOVER_JS):
        assert "if (!resultado.token) return CAPTCHA_LOGICA.respuestaSinResultado(resultado.aviso);" in text


def test_without_a_server_the_screens_say_what_they_always_say():
    """Si la API no contesta, la respuesta es la de «sin servidor» (status 0), no un aviso del CAPTCHA."""
    for text in (ACCOUNT, REGISTER_JS, RECOVER_JS):
        assert "if (resultado.sinServidor) return { status: 0, cuerpo: null };" in text
        assert text.index("resultado.sinServidor") < text.index("respuestaSinResultado(resultado.aviso)")


def test_every_captcha_answer_of_the_api_is_handled_before_the_normal_answer():
    for text, count in ((ACCOUNT, 1), (REGISTER_JS, 3), (RECOVER_JS, 2)):
        assert text.count("CAPTCHA_LOGICA.avisoDe(r.status, r.cuerpo)") == count


def test_the_widget_of_each_step_is_prepared_when_the_step_is_shown():
    assert 'if (paso === "codigo") CAPTCHA.preparar(zonaCodigo);' in REGISTER_JS
    assert 'if (paso === "correccion") CAPTCHA.preparar(zonaCorreccion);' in REGISTER_JS
    assert 'if (paso === "correo") CAPTCHA.preparar(zonaCorreo);' in RECOVER_JS
    assert 'if (paso === "codigo") CAPTCHA.preparar(zonaCodigo);' in RECOVER_JS
    assert "CAPTCHA.preparar(zonaDelCaptcha());" in ACCOUNT


def test_the_widget_is_prepared_only_for_people_without_a_session():
    assert "if (!form.hidden) CAPTCHA.preparar(zonaDatos);" in REGISTER_JS
    assert "if (!formCorreo.hidden) CAPTCHA.preparar(zonaCorreo);" in RECOVER_JS


# --- El módulo y los estilos ------------------------------------------------------------------------------------------


def test_the_widget_module_never_writes_html_and_only_asks_for_the_public_key():
    assert "innerHTML" not in CAPTCHA_JS
    assert CAPTCHA_JS.count("fetch(") == 1
    assert "LOGICA.RUTA_DE_LA_LLAVE" in CAPTCHA_JS


def test_the_widget_is_only_drawn_where_a_zone_declares_an_action_the_api_knows():
    assert 'zona.getAttribute("data-captcha")' in CAPTCHA_JS
    assert "LOGICA.esAccion(accion)" in CAPTCHA_JS


def test_the_zone_takes_no_room_while_empty():
    assert ".captcha { display: flex; justify-content: center; }" in CSS
    assert ".captcha:empty { display: none; }" in CSS


def test_the_texts_are_in_formal_tu_never_usted():
    assert not re.search(r"\busted(es)?\b", CAPTCHA_LOGIC, re.I)
