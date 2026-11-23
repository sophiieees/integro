"""Casos de la pantalla de recuperar la contraseña que se comprueban sin navegador.

Decisiones de Sophia del 21 de noviembre de 2026: recuperar la contraseña con un código de 6 dígitos que llega al
correo y dura 30 minutos, y solo con el correo comprobado. La pantalla es una página aparte, como el registro, y se
llega a ella desde «¿Olvidaste tu contraseña?» en la ventana de iniciar sesión.

La lógica (qué se dice con cada respuesta de la API) se prueba con node en recuperar_logica.test.js. Cómo se ve y
se comporta con navegador, servidor y base está en tests/e2e/test_recuperar_e2e.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"
PAGE = (WEB / "recuperar-contrasena.html").read_text(encoding="utf-8")
SCREEN = (WEB / "assets" / "js" / "recuperar.js").read_text(encoding="utf-8")
LOGIC = (WEB / "assets" / "js" / "recuperar-logica.js").read_text(encoding="utf-8")
ACCOUNT_SCREEN = (WEB / "assets" / "js" / "cuenta.js").read_text(encoding="utf-8")
CSS = (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8")


def test_the_page_has_the_three_steps_in_one_card():
    assert 'id="formulario-correo" data-paso="correo"' in PAGE
    assert 'id="formulario-cambio" data-paso="codigo"' in PAGE and 'id="formulario-cambio" data-paso="codigo" novalidate hidden' in PAGE
    assert 'id="recuperar-listo" data-paso="listo" hidden' in PAGE
    assert PAGE.count('class="formulario-tarjeta"') == 1


def test_the_fields_tell_the_browser_what_they_are():
    assert 'name="email" autocomplete="email"' in PAGE
    assert 'name="code" autocomplete="one-time-code" inputmode="numeric" maxlength="6"' in PAGE
    assert 'type="password" id="recuperar-contrasena" name="new_password" autocomplete="new-password"' in PAGE
    # Ni el código ni la contraseña se piden como si fueran de una cuenta que ya existe en el navegador.
    assert "current-password" not in PAGE


def test_every_field_has_its_label_and_its_place_for_the_warning():
    for name in ("email", "code", "new_password"):
        assert f'data-error-de="{name}" hidden' in PAGE, name
        assert f'id="recuperar-error-{name}"' in PAGE, name
    assert PAGE.count('class="campo-etiqueta"') == 3


def test_the_password_rules_and_the_indicator_are_the_same_as_in_the_registration():
    registration = (WEB / "registro.html").read_text(encoding="utf-8")
    rules = "De 10 a 20 caracteres, con mayúscula, minúscula, número y símbolo, sin espacios."
    assert rules in PAGE and rules in registration
    def indicator(html: str) -> str:
        # Sin las sangrías: la página del registro y esta no están a la misma altura.
        block = re.search(r'<div class="fortaleza".*?</ul>\s*</div>', html, re.S).group(0)
        return re.sub(r"\s+", " ", block)

    assert indicator(PAGE) == indicator(registration)


def test_the_page_loads_the_scripts_in_order():
    scripts = re.findall(r'<script src="assets/js/([a-z-]+)\.js"></script>', PAGE)

    assert scripts == [
        "estructura", "captcha-logica", "captcha", "cuenta-logica", "cuenta", "paises", "registro-logica",
        "recuperar-logica", "recuperar",
    ]


def test_the_page_header_and_footer_are_the_empty_spaces_the_script_fills():
    assert '<header class="cabecera" data-cabecera="interior"></header>' in PAGE
    assert '<footer class="pie" data-pie></footer>' in PAGE


def test_the_screen_talks_to_the_three_routes_and_only_to_them():
    assert 'var API = "/api/v1/auth"' in SCREEN
    for route in ('"/password-reset/request"', '"/password-reset/confirm"', '"/password-strength"', 'API + "/me"'):
        assert route in SCREEN, route
    assert 'credentials: "same-origin"' in SCREEN
    assert SCREEN.count("fetch(") == 2  # la ayuda de peticion() y la consulta de /me


def test_the_screen_keeps_nothing_in_the_browser_and_never_leaves_the_password_written():
    assert not re.search(r"localStorage|sessionStorage|document\\.cookie", SCREEN)
    assert not re.search(r"console\\.", SCREEN)
    # Cuando la contraseña ya se mandó con éxito, se borra de la página.
    after_success = SCREEN[SCREEN.index('if (siguiente.paso === "listo")'):]
    assert 'formCambio.elements.new_password.value = "";' in after_success[:300]
    # Y al pasar al paso del código, o volver al correo, empieza vacía.
    assert SCREEN.count('formCambio.elements.new_password.value = "";') >= 3


def test_what_comes_from_the_api_is_written_as_text_never_as_html():
    assert "linea.textContent = texto;" in SCREEN and "li.textContent = texto;" in SCREEN
    assert not re.search(r"innerHTML\s*=\s*[^\"'\s]", SCREEN)  # solo se vacía: innerHTML = ""
    assert "innerHTML" not in LOGIC


def test_the_logic_works_in_the_browser_and_in_node_and_does_not_touch_the_page():
    assert "module.exports = fabrica(require(\"./cuenta-logica.js\"), require(\"./registro-logica.js\"))" in LOGIC
    assert "raiz.INTEGRO_RECUPERAR = fabrica(raiz.INTEGRO_CUENTA, raiz.INTEGRO_REGISTRO)" in LOGIC
    code = re.sub(r"/\*.*?\*/", "", LOGIC, flags=re.S)  # sin los comentarios
    assert "document." not in code and "fetch(" not in code and "window." not in code.replace("typeof window", "")


def test_the_button_names_say_what_they_do():
    for text in ("Enviar código", "Cambiar contraseña", "Enviar otro código", "Usa otro correo", "Iniciar sesión"):
        assert text in PAGE, text


def test_the_login_window_links_to_the_page():
    assert 'class=\\"ventana-olvido\\"><a href=\\"recuperar-contrasena.html\\">¿Olvidaste tu contraseña?</a>' in ACCOUNT_SCREEN
    assert ".ventana-olvido a" in CSS


def test_with_a_session_open_the_form_is_hidden():
    assert "formCorreo.hidden = true;" in SCREEN and "avisoDeSesionIniciada(yo.first_name)" in SCREEN


def test_the_page_signals_when_it_is_ready_for_the_end_to_end_tests():
    assert 'document.documentElement.setAttribute("data-recuperar-listo", "")' in SCREEN


def test_the_done_step_counts_three_seconds_and_offers_to_go_now():
    listo = PAGE.split('id="recuperar-listo"')[1].split("</div>\n        </div>")[0]
    assert "<h2>Tu contraseña cambió</h2>" in listo
    assert 'data-espera role="status"' in listo
    assert 'href="index.html#entrar" data-ir-a-iniciar-sesion>Iniciar sesión ahora</a>' in listo
    assert "data-iniciar-sesion" not in PAGE
    # La pantalla ya no abre la ventana por su cuenta: lleva a la portada, que la abre con #entrar.

    assert "window.location.href = LOGICA.DESTINO_AL_TERMINAR" in SCREEN
    assert "SEGUNDOS_DE_ESPERA = 3" in LOGIC


def test_the_account_screen_shows_a_brief_notice_that_does_not_block_the_page():
    assert "pointer-events: none" in CSS.split(".aviso-de-sesion {")[1].split("}")[0]
    assert 'aviso.setAttribute("role", "status")' in ACCOUNT_SCREEN
    assert "aviso.textContent = LOGICA.avisoDeInicio(estado.nombre)" in ACCOUNT_SCREEN
