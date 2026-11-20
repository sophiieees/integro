"""Casos de la ventana de «Iniciar sesión», de principio a fin: navegador, servidor y base de verdad.

Especificación aceptada por Sophia el 19 de noviembre de 2026:

     1. Correo y contraseña correctos: pasa al paso del código y dice a qué correo se envió.
     2. Contraseña incorrecta: aviso, se queda en el paso 1.
     3. Correo sin comprobar: aviso de comprobar el correo.
     4. Demasiados intentos (429): aviso con los minutos.
     5. Código correcto: ventana cerrada, nombre y «Cerrar sesión» en la cabecera, misma página.
     6. Código incorrecto: aviso con los intentos que quedan; vencido o agotado:
        aviso y vuelve al paso 1.
     7. «Cerrar sesión»: sesión cerrada en la API, vuelve «Iniciar sesión».
     8. Al recargar o cambiar de página con sesión, la cabecera muestra el nombre
        sin volver a entrar.
     9. Sin API (archivo abierto con doble clic): «Iniciar sesión» avisa que hace falta el servidor.
    10. Escape, clic fuera o «Cancelar» cierran la ventana; los campos quedan
        vacíos; funciona en celular.

Corren contra la base `integro` de backend/.env, dentro de una transacción que
se deshace al terminar el archivo. Ver e2e_support.py y README.md.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import re
from pathlib import Path

import pytest
from e2e_support import age_codes, browser, make_account, page, sessions_of, site  # noqa: F401

PASSWORD = "Ejemplo-2026"
WEB = Path(__file__).resolve().parents[2] / "web"
PAGES = ["index.html", "propiedad.html?id=2", "anfitriones.html", "como-funciona.html"]
FORM_1 = "#ventana-entrar form[data-paso=correo]"
FORM_2 = "#ventana-entrar form[data-paso=codigo]"

WRONG_PASSWORD = "El correo electrónico o la contraseña no son correctos."


# --- Lo que hace una persona ------------------------------------------------


def go(page, site, path="index.html"):
    """Abre una página del sitio y espera a que la cabecera sepa si hay sesión."""
    page.goto(f"{site.url}/{path}")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


def open_window(page):
    page.click(".cuenta-entrar")
    page.expect("!document.getElementById('ventana-entrar').hidden")


def settle(page, before):
    """Espera a que la petición que empezó después de `before` termine y la ventana vuelva a estar libre."""
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('#ventana-entrar input')).some(i => i.disabled)")


def send_credentials(page, email, password):
    page.type(f"{FORM_1} [name=email]", email)
    page.type(f"{FORM_1} [name=password]", password)
    before = page.requests()
    page.press("Enter")
    settle(page, before)


def send_code(page, code):
    page.type(f"{FORM_2} [name=code]", code)
    before = page.requests()
    page.press("Enter")
    settle(page, before)


def wrong_code(code):
    return "000000" if code != "000000" else "111111"


def login_up_to_the_code(page, site, account):
    go(page, site)
    open_window(page)
    send_credentials(page, account["email"], account["password"])
    assert page.step() == "codigo", page.state()
    return site.codes.code_for(account["email"], "login")


def log_in(page, site, account, path="index.html"):
    go(page, site, path)
    open_window(page)
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect(f"document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")


# --- La cabecera y la ventana en las cuatro páginas ----------------------------


@pytest.mark.parametrize("path", PAGES)
def test_every_page_shows_entrar_and_opens_the_window(page, site, path):
    go(page, site, path)

    assert page.header() == ["Iniciar sesión"]
    assert page.window_open() is False
    open_window(page)

    assert page.window_open() is True
    assert page.step() == "correo"
    assert page.text("#ventana-entrar h2") == "Iniciar sesión"
    assert page.js("document.activeElement.name") == "email"
    assert page.js("document.body.classList.contains('con-ventana')") is True


def test_the_hash_entrar_opens_the_window_when_there_is_no_session(page, site):
    page.goto(f"{site.url}/index.html#entrar")

    page.expect("!document.getElementById('ventana-entrar') === false && !document.getElementById('ventana-entrar').hidden")
    assert page.step() == "correo"


def test_the_window_links_to_registro_html(page, site):
    go(page, site)
    open_window(page)

    link = page.js("document.querySelector('#ventana-entrar .ventana-pie a').getAttribute('href')")
    assert link == "registro.html"
    assert page.text("#ventana-entrar .ventana-pie").strip() == "¿Aún no tienes una cuenta? Regístrate"


# --- Caso 1 ------------------------------------------------------------------------


def test_right_email_and_password_go_to_the_code_step_and_send_the_code(page, site):
    account = make_account(site)
    go(page, site)
    open_window(page)

    send_credentials(page, account["email"], account["password"])

    assert page.step() == "codigo"
    assert page.warning() is None
    assert page.text(f"{FORM_2} [data-texto]") == f"Te enviamos un código de 6 dígitos a {account['email']}. Su vigencia es de 5 minutos."
    assert page.js("document.activeElement.name") == "code"
    # La contraseña ya no queda escrita en la página.
    assert page.value(f"{FORM_1} [name=password]") == ""
    code = site.codes.code_for(account["email"], "login")
    assert re.fullmatch(r"[0-9]{6}", code)
    # Todavía no hay sesión.
    assert sessions_of(site, account["email"]) == (0, 0)
    assert page.header() == ["Iniciar sesión"]


def test_the_email_is_accepted_with_capitals_and_spaces(page, site):
    account = make_account(site)
    go(page, site)
    open_window(page)

    send_credentials(page, f"  {account['email'].upper()} ", account["password"])

    assert page.step() == "codigo"


def test_going_back_and_asking_again_within_a_minute_asks_for_the_same_code(page, site):
    """Si ya se envió un código hace menos de un minuto, la ventana pide ese en lugar de fallar."""
    account = make_account(site)
    login_up_to_the_code(page, site, account)
    page.click("#ventana-entrar [data-volver]")
    assert page.step() == "correo"

    send_credentials(page, account["email"], account["password"])

    assert page.step() == "codigo"
    assert page.warning() is None
    assert "hace menos de un minuto" in page.text(f"{FORM_2} [data-texto]")


def test_empty_or_badly_written_fields_are_warned_without_asking_the_api(page, site):
    go(page, site)
    open_window(page)
    before = page.requests()

    page.press("Enter")
    assert page.warning() == "Escribe tu correo electrónico."
    page.type(f"{FORM_1} [name=email]", "ana")
    page.press("Enter")
    assert page.warning() == "El correo electrónico no tiene un formato válido."
    page.type(f"{FORM_1} [name=email]", "ana@prueba.invalid")
    page.press("Enter")
    assert page.warning() == "Escribe tu contraseña."

    assert page.requests() == before
    assert page.step() == "correo"


# --- Caso 2 ------------------------------------------------------------------------


def test_wrong_password_warns_and_stays_in_step_one(page, site):
    account = make_account(site)
    go(page, site)
    open_window(page)

    send_credentials(page, account["email"], "Ejemplo-2027")

    assert page.step() == "correo"
    assert page.warning() == WRONG_PASSWORD
    assert page.window_open() is True
    assert page.js("document.activeElement.name") == "password"
    assert page.header() == ["Iniciar sesión"]
    assert sessions_of(site, account["email"]) == (0, 0)


def test_an_email_without_account_gets_the_same_warning(page, site):
    go(page, site)
    open_window(page)

    send_credentials(page, "nadie.123456@prueba.invalid", PASSWORD)

    assert page.step() == "correo"
    assert page.warning() == WRONG_PASSWORD


# --- Caso 3 ------------------------------------------------------------------------


def test_an_unverified_email_is_told_to_verify_it(page, site):
    account = make_account(site, verified=False)
    go(page, site)
    open_window(page)

    send_credentials(page, account["email"], account["password"])

    assert page.step() == "correo"
    assert page.warning() == "Aún no has comprobado tu correo electrónico. Revisa el código que te enviamos al registrarte."


# --- Caso 4 ------------------------------------------------------------------------


def test_six_wrong_passwords_make_the_device_wait_and_the_window_says_how_long(page, site):
    account = make_account(site)
    go(page, site)
    open_window(page)

    for _ in range(6):
        send_credentials(page, account["email"], "Ejemplo-2027")
        assert page.warning() == WRONG_PASSWORD

    # Con la contraseña correcta, ese dispositivo ya no pasa.
    send_credentials(page, account["email"], account["password"])

    assert page.step() == "correo"
    assert page.warning() == "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en 15 minutos."
    assert sessions_of(site, account["email"]) == (0, 0)
    # La cuenta no se bloqueó: otro dispositivo (otro navegador) entra normal.
    other = page.browser.new_page()
    try:
        other.set_user_agent("IntegroE2E/otro-dispositivo")
        go(other, site)
        open_window(other)
        send_credentials(other, account["email"], account["password"])
        assert other.step() == "codigo"
    finally:
        other.close()


# --- Caso 5 ------------------------------------------------------------------------


def test_right_code_closes_the_window_and_shows_the_name_on_the_same_page(page, site):
    account = make_account(site, first_name="Beatriz")
    go(page, site, "propiedad.html?id=2")
    open_window(page)
    send_credentials(page, account["email"], account["password"])
    code = site.codes.code_for(account["email"], "login")

    send_code(page, code)
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")

    assert page.header() == ["Beatriz", "Cerrar sesión"]
    assert page.window_open() is False
    assert page.js("document.body.classList.contains('con-ventana')") is False
    # La ventana cerrada ya no tapa la página: se puede dar clic en «Cerrar sesión» y en la ficha.
    assert page.covers_the_page() is False
    assert page.is_clickable(".cuenta-salir") is True
    assert page.is_clickable(".marca") is True
    assert page.location() == "/propiedad.html?id=2"
    assert sessions_of(site, account["email"]) == (1, 1)
    # La llave de sesión viaja en una cookie que la página no puede leer.
    assert page.js("document.cookie") == ""


def test_the_window_can_be_closed_and_opened_again_after_logging_in_from_the_code_step(page, site):
    account = make_account(site)
    login_up_to_the_code(page, site, account)
    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")

    assert page.header() == ["Ana", "Cerrar sesión"]
    assert page.js("document.querySelector('.cuenta-entrar')") is None


# --- Caso 6 ------------------------------------------------------------------------


def test_wrong_code_says_how_many_attempts_are_left(page, site):
    account = make_account(site)
    code = login_up_to_the_code(page, site, account)

    send_code(page, wrong_code(code))

    assert page.step() == "codigo"
    assert page.warning() == "El código ingresado no es correcto. Te quedan 4 intentos."
    assert page.header() == ["Iniciar sesión"]
    assert sessions_of(site, account["email"]) == (0, 0)
    # Sigue sirviendo el código correcto.
    send_code(page, code)
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")


def test_five_wrong_codes_send_the_person_back_to_step_one(page, site):
    account = make_account(site)
    code = login_up_to_the_code(page, site, account)

    for expected in ("Te quedan 4 intentos.", "Te quedan 3 intentos.", "Te quedan 2 intentos.", "Te queda 1 intento."):
        send_code(page, wrong_code(code))
        assert page.warning() == f"El código ingresado no es correcto. {expected}"
        assert page.step() == "codigo"
    send_code(page, wrong_code(code))

    assert page.step() == "correo"
    assert page.warning() == "El código ingresado no es correcto. Ya no te quedan intentos."
    assert page.header() == ["Iniciar sesión"]
    assert sessions_of(site, account["email"]) == (0, 0)


def test_an_expired_code_sends_the_person_back_to_step_one(page, site):
    account = make_account(site)
    code = login_up_to_the_code(page, site, account)
    age_codes(site, account["email"], 301)

    send_code(page, code)

    assert page.step() == "correo"
    assert page.warning() == "El código venció. Vuelve a escribir tu correo electrónico y tu contraseña para recibir uno nuevo."
    assert sessions_of(site, account["email"]) == (0, 0)


def test_a_code_that_is_not_six_numbers_is_warned_without_asking_the_api(page, site):
    account = make_account(site)
    login_up_to_the_code(page, site, account)
    before = page.requests()

    page.press("Enter")
    assert page.warning() == "Escribe el código que recibiste."
    page.type(f"{FORM_2} [name=code]", "12ab")
    page.press("Enter")
    assert page.warning() == "El código debe constar de 6 dígitos."

    assert page.requests() == before


# --- Caso 7 ------------------------------------------------------------------------


def test_salir_closes_the_session_in_the_api_and_entrar_comes_back(page, site):
    account = make_account(site)
    log_in(page, site, account)
    assert sessions_of(site, account["email"]) == (1, 1)

    page.click(".cuenta-salir")
    page.expect("document.querySelector('[data-cuenta]').textContent.trim() === 'Iniciar sesión'")

    assert page.header() == ["Iniciar sesión"]
    assert sessions_of(site, account["email"]) == (0, 1)
    # La cookie se borró: la API ya no reconoce a nadie.
    assert page.js("fetch('/api/v1/auth/me').then(r => r.status)") == 401
    # Y al recargar sigue sin sesión.
    go(page, site)
    assert page.header() == ["Iniciar sesión"]


def test_after_salir_the_same_person_can_enter_again(page, site):
    account = make_account(site)
    log_in(page, site, account)
    page.click(".cuenta-salir")
    page.expect("document.querySelector('[data-cuenta]').textContent.trim() === 'Iniciar sesión'")
    age_codes(site, account["email"], 61)  # para no chocar con la espera de un minuto entre códigos

    open_window(page)
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")

    assert page.header() == ["Ana", "Cerrar sesión"]
    assert sessions_of(site, account["email"]) == (1, 2)


# --- Caso 8 ------------------------------------------------------------------------


def test_the_name_stays_on_reload_and_on_every_page(page, site):
    account = make_account(site, first_name="Carolina")
    log_in(page, site, account, "propiedad.html?id=2")

    go(page, site, "propiedad.html?id=2")
    assert page.header() == ["Carolina", "Cerrar sesión"]
    for path in PAGES:
        go(page, site, path)
        assert page.header() == ["Carolina", "Cerrar sesión"], path
        assert page.js("document.querySelector('.cuenta-entrar')") is None, path


def test_the_hash_entrar_does_not_open_the_window_when_there_is_already_a_session(page, site):
    account = make_account(site)
    log_in(page, site, account, "propiedad.html?id=2")

    # Desde otra página, para que sea una carga completa y no solo un cambio del ancla.
    page.goto(f"{site.url}/index.html#entrar")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")

    assert page.header() == ["Ana", "Cerrar sesión"]
    assert page.window_open() is False


def test_a_person_without_session_in_a_clean_browser_sees_entrar(page, site):
    account = make_account(site)
    log_in(page, site, account)
    # Otro contexto del navegador no comparte cookies: es otra persona en otra computadora.
    other = page.browser.new_page()
    try:
        go(other, site)
        assert other.header() == ["Iniciar sesión"]
    finally:
        other.close()


# --- Caso 9 ------------------------------------------------------------------------


def test_without_the_server_entrar_says_the_server_is_needed(page, site):
    """La página abierta con doble clic, sin la API: el archivo se ve, pero no se puede entrar."""
    page.goto((WEB / "index.html").as_uri())
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")

    assert page.header() == ["Iniciar sesión"]
    open_window(page)

    assert page.step() == "correo"
    assert page.warning() == (
        "No fue posible comunicarse con el servidor de Íntegro. Inícialo y abre la página desde http://127.0.0.1:8000/."
    )


# --- Caso 10 -----------------------------------------------------------------------


def test_a_closed_window_does_not_cover_the_page(page, site):
    """Cerrada no es solo «con el atributo hidden»: la página tiene que poder recibir clics otra vez."""
    go(page, site)
    assert page.covers_the_page() is False
    open_window(page)
    assert page.covers_the_page() is True

    page.press("Escape")

    assert page.window_open() is False
    assert page.covers_the_page() is False
    assert page.is_clickable(".cuenta-entrar") is True
    assert page.is_clickable(".marca") is True


def test_escape_closes_the_window_and_clears_the_fields(page, site):
    go(page, site)
    open_window(page)
    page.type(f"{FORM_1} [name=email]", "ana@prueba.invalid")
    page.type(f"{FORM_1} [name=password]", "algo")

    page.press("Escape")

    assert page.window_open() is False
    open_window(page)
    assert page.value(f"{FORM_1} [name=email]") == ""
    assert page.value(f"{FORM_1} [name=password]") == ""
    assert page.warning() is None


def test_clicking_outside_the_window_closes_it(page, site):
    go(page, site)
    open_window(page)
    page.type(f"{FORM_1} [name=email]", "ana@prueba.invalid")

    # Un punto de la esquina: está sobre el fondo oscuro, fuera de la ventana.
    page.click_at(8, 8)

    assert page.window_open() is False
    open_window(page)
    assert page.value(f"{FORM_1} [name=email]") == ""


def test_clicking_inside_the_window_does_not_close_it(page, site):
    go(page, site)
    open_window(page)

    page.click("#ventana-entrar h2")
    page.click(f"{FORM_1} [name=email]")

    assert page.window_open() is True


def test_cancelar_closes_the_window_and_clears_it(page, site):
    go(page, site)
    open_window(page)
    page.type(f"{FORM_1} [name=email]", "ana@prueba.invalid")

    page.click("#ventana-entrar [data-cancelar]")

    assert page.window_open() is False
    assert page.js("document.body.classList.contains('con-ventana')") is False
    open_window(page)
    assert page.value(f"{FORM_1} [name=email]") == ""


def test_closing_the_code_step_starts_again_from_step_one(page, site):
    account = make_account(site)
    login_up_to_the_code(page, site, account)

    page.press("Escape")
    assert page.window_open() is False
    open_window(page)

    assert page.step() == "correo"
    assert page.warning() is None


def test_the_window_fits_on_a_phone(page, site):
    page.set_viewport(390, 844, mobile=True)
    go(page, site)
    open_window(page)

    box = page.js(
        "(() => { const r = document.querySelector('#ventana-entrar .ventana').getBoundingClientRect(); "
        "return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, ancho: innerWidth, alto: innerHeight }; })()"
    )
    assert box["left"] >= 0 and box["right"] <= box["ancho"], box
    assert box["top"] >= 0 and box["bottom"] <= box["alto"], box
    for selector in (f"{FORM_1} [name=email]", f"{FORM_1} [name=password]", f"{FORM_1} button[type=submit]", "#ventana-entrar [data-cancelar]"):
        inside = page.js(
            "(() => { const r = document.querySelector(" + repr(selector) + ").getBoundingClientRect(); "
            "return r.left >= 0 && r.right <= innerWidth && r.width > 0; })()"
        )
        assert inside, selector


def test_the_whole_flow_works_on_a_phone(page, site):
    page.set_viewport(390, 844, mobile=True)
    account = make_account(site, first_name="Diana")

    log_in(page, site, account, "propiedad.html?id=2")

    assert page.header() == ["Diana", "Cerrar sesión"]
    assert page.location() == "/propiedad.html?id=2"
