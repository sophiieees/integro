"""Casos de la pantalla de recuperar la contraseña, de principio a fin: navegador, servidor y base de verdad.

Decisiones de Sophia del 21 de noviembre de 2026: recuperar la contraseña con un código de 6 dígitos al correo que
dura 30 minutos, y solo con el correo comprobado.

    1. Se llega desde «¿Olvidaste tu contraseña?» en la ventana de iniciar sesión.
    2. Correo vacío o mal escrito: aviso en el campo, sin llamar a la API.
    3. Pedir el código: pasa al paso del código con el mismo texto tenga o no cuenta ese correo; el código llega
       solo a una cuenta con el correo comprobado, y vence a los 30 minutos.
    4. Código y contraseña nueva: la contraseña cambia, todas las sesiones se cierran, la vieja deja de servir y la
       nueva sirve para iniciar sesión (con su código, como siempre).
    5. Código incorrecto: dice cuántos intentos quedan y la contraseña escrita se queda. Vencido, o con los intentos
       agotados: se ofrece pedir otro.
    6. Contraseña débil: el indicador y una línea en el campo; el código no se gasta. Fácil de adivinar: una línea
       que remite a los consejos del indicador, sin repetirlos.
    7. «Enviar otro código» y «Usa otro correo».
    8. Con sesión iniciada no hay nada que recuperar.
    9. En celular cabe en la pantalla.

Corren contra la base `integro` de backend/.env, dentro de una transacción que se deshace al terminar el archivo.
Necesitan la migración 20261121000005_password_reset_code.sql en esa base.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import pytest
from e2e_support import age_codes, browser, make_account, page, sessions_of, site  # noqa: F401
from test_entrar_e2e import log_in, open_window, send_code, send_credentials

NEW_PASSWORD = "Nueva-2026!"
WEAK = "Contrasena-1234"
UNKNOWN = "no.existe.ninguna@prueba.invalid"
TEXT_START = "Si {email} tiene una cuenta con el correo electrónico comprobado, te enviamos un código de 6 dígitos."
FORM_1 = "#formulario-correo"
FORM_2 = "#formulario-cambio"


@pytest.fixture(autouse=True)
def migration_applied(site):
    from app.database.transaction import system_transaction

    with system_transaction(site.pool) as connection:
        definition = connection.execute(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = 'one_time_codes_purpose_valid'"
        ).fetchone()
    if definition is None or "password_reset" not in definition[0]:
        pytest.skip("Falta correr database/migrations/20261121000005_password_reset_code.sql en la base integro.")


def go(page, site, path="recuperar-contrasena.html"):
    page.goto(f"{site.url}/{path}")
    page.expect("document.documentElement.hasAttribute('data-recuperar-listo')")


def step(page):
    return page.js(
        "(() => { const v = (s) => document.querySelector(s) && !document.querySelector(s).hidden; "
        "return v('#formulario-correo') ? 'correo' : v('#formulario-cambio') ? 'codigo' : v('#recuperar-listo') ? 'listo' : null; })()"
    )


def warning(page):
    return page.js("(() => { const a = document.querySelector('[data-aviso]'); return a && !a.hidden ? a.textContent : null; })()")


def field_errors(page):
    return page.js(
        "Object.fromEntries(Array.from(document.querySelectorAll('[data-error-de]')).filter(e => !e.hidden)"
        ".map(e => [e.getAttribute('data-error-de'), Array.from(e.children).map(c => c.textContent)]))"
    )


def settle(page, before):
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")


def ask_for_the_code(page, email):
    page.type(f"{FORM_1} [name=email]", email)
    before = page.requests()
    page.press("Enter")
    settle(page, before)


def sent(site, email):
    return [m for m in site.codes.sent if m["destination"] == email and m["purpose"] == "password_reset"]


def fill_change(page, code, password):
    page.type(f"{FORM_2} [name=code]", code)
    page.type(f"{FORM_2} [name=new_password]", password)


def submit_change(page):
    before = page.requests()
    page.press("Enter")
    settle(page, before)


def started(page, site, **kwargs):
    """Una cuenta comprobada que ya pidió su código y está en el paso del código: (cuenta, código)."""
    account = make_account(site, **kwargs)
    go(page, site)
    ask_for_the_code(page, account["email"])
    assert step(page) == "codigo", page.state()
    return account, sent(site, account["email"])[-1]["code"]


# --- Caso 1: cómo se llega ------------------------------------------------------------------------


def test_the_login_window_links_to_the_page(page, site):
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    open_window(page)

    assert page.text("#ventana-entrar .ventana-olvido a") == "¿Olvidaste tu contraseña?"
    page.click("#ventana-entrar .ventana-olvido a")

    page.expect("location.pathname === '/recuperar-contrasena.html'")
    page.expect("document.documentElement.hasAttribute('data-recuperar-listo')")
    assert step(page) == "correo"


def test_the_page_starts_at_the_email_step_with_its_introduction(page, site):
    go(page, site)

    assert page.text("h1") == "Recupera tu contraseña"
    assert step(page) == "correo"
    assert page.js("document.querySelector('[data-intro]').hidden") is False
    assert page.js("document.activeElement === document.body || document.activeElement.tagName !== 'INPUT'") is True
    assert warning(page) is None


# --- Caso 2: lo escrito -----------------------------------------------------------------------------


@pytest.mark.parametrize("text, message", [
    ("", "Escribe tu correo electrónico."),
    ("ana", "El correo electrónico no tiene un formato válido."),
    ("ana@", "El correo electrónico no tiene un formato válido."),
])
def test_an_empty_or_badly_written_email_is_warned_without_asking_the_api(page, site, text, message):
    go(page, site)
    before = page.requests()
    if text:
        page.type(f"{FORM_1} [name=email]", text)

    page.press("Enter") if text else page.click(f"{FORM_1} button[type=submit]")

    assert field_errors(page) == {"email": [message]}
    assert step(page) == "correo"
    assert page.requests() == before


# --- Caso 3: pedir el código -----------------------------------------------------------------------------


def test_asking_for_the_code_moves_to_the_code_step_and_the_code_goes_to_the_email(page, site):
    account = make_account(site)
    go(page, site)

    ask_for_the_code(page, account["email"])

    assert step(page) == "codigo"
    assert page.js("document.querySelector('[data-intro]').hidden") is True
    text = page.text(f"{FORM_2} [data-texto]")
    assert text.startswith(TEXT_START.format(email=account["email"]))
    assert "30 minutos" in text
    message = sent(site, account["email"])[-1]
    assert (message["channel"], message["ttl_seconds"], len(message["code"])) == ("email", 1800, 6)
    assert page.js("document.activeElement.name") == "code"


def test_an_email_without_an_account_gets_the_same_screen_and_nothing_is_sent(page, site):
    real = make_account(site)
    go(page, site)
    ask_for_the_code(page, real["email"])
    real_text = page.text(f"{FORM_2} [data-texto]").replace(real["email"], "{email}")
    page.click(f"{FORM_2} [data-otro-correo]")
    page.clear(f"{FORM_1} [name=email]")
    total_before = len(site.codes.sent)

    ask_for_the_code(page, UNKNOWN)

    assert step(page) == "codigo"
    assert page.text(f"{FORM_2} [data-texto]").replace(UNKNOWN, "{email}") == real_text
    assert len(site.codes.sent) == total_before
    assert sent(site, UNKNOWN) == []


def test_an_unverified_account_gets_the_same_screen_and_no_code(page, site):
    account = make_account(site, verified=False)
    go(page, site)
    total_before = len(site.codes.sent)

    ask_for_the_code(page, account["email"])

    assert step(page) == "codigo"
    assert len(site.codes.sent) == total_before
    assert sent(site, account["email"]) == []
    # Con cualquier código, lo mismo que un código incorrecto: no se revela nada.
    fill_change(page, "123456", NEW_PASSWORD)
    submit_change(page)
    assert field_errors(page) == {"code": ["El código ingresado no es correcto."]}


# --- Caso 4: cambiar la contraseña -------------------------------------------------------------------------


def test_the_right_code_and_a_good_password_change_it_and_the_new_one_logs_in(page, site):
    account, code = started(page, site)
    fill_change(page, code, NEW_PASSWORD)
    page.expect("document.querySelector('.fortaleza-nivel').textContent !== ''")

    submit_change(page)

    assert step(page) == "listo"
    assert page.text("#recuperar-listo h2") == "Tu contraseña cambió"
    assert "cerramos todas las sesiones" in page.text("#recuperar-listo")
    # La contraseña no queda escrita en la página.
    assert page.value(f"{FORM_2} [name=new_password]") == ""
    assert NEW_PASSWORD not in page.js("document.body.innerHTML")
    # A los 3 segundos se va a la portada con la ventana de iniciar sesión abierta.
    page.expect("location.pathname === '/index.html'", seconds=10)
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, account["email"], NEW_PASSWORD)
    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")
    assert page.header() == [account["first_name"]]


def test_the_old_password_no_longer_works(page, site):
    from test_entrar_e2e import send_credentials

    account, code = started(page, site)
    fill_change(page, code, NEW_PASSWORD)
    submit_change(page)
    assert step(page) == "listo"
    page.click("#recuperar-listo [data-ir-a-iniciar-sesion]")
    page.expect("location.pathname === '/index.html'")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")

    send_credentials(page, account["email"], account["password"])

    assert page.step() == "correo"
    assert page.warning() == "El correo electrónico o la contraseña no son correctos."


def test_every_open_session_is_closed(page, site):
    account = make_account(site)
    log_in(page, site, account)
    assert sessions_of(site, account["email"]) == (1, 1)
    other = page.browser.new_page()
    try:
        # Otra computadora: no comparte cookies, y pide el código por su cuenta.
        go(other, site)
        ask_for_the_code(other, account["email"])
        code = sent(site, account["email"])[-1]["code"]
        fill_change(other, code, NEW_PASSWORD)
        submit_change(other)
        assert step(other) == "listo"
    finally:
        other.close()

    assert sessions_of(site, account["email"]) == (0, 1)
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    assert page.js("document.querySelector('.cuenta-entrar') !== null") is True


def test_the_indicator_fills_while_the_new_password_is_typed(page, site):
    account, code = started(page, site)

    page.type(f"{FORM_2} [name=new_password]", NEW_PASSWORD)

    page.expect("document.querySelector('.fortaleza-nivel').textContent !== ''")
    assert page.js("document.querySelectorAll('.fortaleza-barra .lleno').length") >= 3
    assert page.js("document.querySelector('[data-fortaleza]').getAttribute('data-nivel')") in ("confiable", "muy-confiable")


# --- Caso 5: el código ------------------------------------------------------------------------------------------


def wrong_code(code):
    return "000000" if code != "000000" else "111111"


def test_a_wrong_code_says_how_many_attempts_are_left_and_keeps_the_password(page, site):
    account, code = started(page, site)
    fill_change(page, wrong_code(code), NEW_PASSWORD)

    submit_change(page)

    assert step(page) == "codigo"
    assert field_errors(page) == {"code": ["El código ingresado no es correcto. Te quedan 4 intentos."]}
    assert page.value(f"{FORM_2} [name=new_password]") == NEW_PASSWORD
    assert page.js("document.activeElement.name") == "code"
    # Con el código correcto sirve.
    page.clear(f"{FORM_2} [name=code]")
    page.type(f"{FORM_2} [name=code]", code)
    submit_change(page)
    assert step(page) == "listo"


def test_an_expired_code_offers_to_ask_for_another(page, site):
    account, code = started(page, site)
    age_codes(site, account["email"], 1801)
    fill_change(page, code, NEW_PASSWORD)

    submit_change(page)

    assert step(page) == "codigo"
    assert field_errors(page) == {"code": ["El código venció. Pide uno nuevo."]}
    assert page.js("document.activeElement.hasAttribute('data-reenviar')") is True


def test_a_code_that_is_not_six_numbers_is_warned_without_asking_the_api(page, site):
    started(page, site)
    before = page.requests()

    page.press("Enter")
    assert field_errors(page) == {"code": ["Escribe el código que recibiste."], "new_password": ["Escribe tu contraseña nueva."]}
    page.type(f"{FORM_2} [name=code]", "12ab")
    page.press("Enter")
    assert field_errors(page)["code"] == ["El código debe constar de 6 dígitos."]

    assert page.requests() == before


# --- Caso 6: la contraseña -------------------------------------------------------------------------------------------


def test_a_password_that_breaks_the_rules_gets_one_line_and_the_code_is_not_spent(page, site):
    account, code = started(page, site)
    fill_change(page, code, "corta")

    submit_change(page)

    assert step(page) == "codigo"
    assert field_errors(page) == {"new_password": ["Tu contraseña aún no cumple lo que se indica abajo."]}
    page.expect("document.querySelectorAll('[data-fortaleza-consejos] li').length > 0")
    # El código sigue sirviendo, con sus cinco intentos.
    page.clear(f"{FORM_2} [name=new_password]")
    page.type(f"{FORM_2} [name=new_password]", NEW_PASSWORD)
    submit_change(page)
    assert step(page) == "listo"


def test_a_password_that_is_easy_to_guess_points_to_the_advice_of_the_indicator_without_repeating_it(page, site):
    account, code = started(page, site)
    fill_change(page, code, WEAK)

    submit_change(page)

    assert step(page) == "codigo"
    assert field_errors(page) == {"new_password": ["Tu contraseña es muy fácil de adivinar. Revisa los consejos de abajo."]}
    # Los consejos están una sola vez: en el indicador.
    page.expect("document.querySelectorAll('[data-fortaleza-consejos] li').length > 0")
    advice = page.js("Array.from(document.querySelectorAll('[data-fortaleza-consejos] li')).map(li => li.textContent)")
    assert any("secuencias" in text for text in advice)
    assert "secuencias" not in page.text("[data-error-de=new_password]")


# --- Caso 7: otro código y otro correo -----------------------------------------------------------------------------------


def test_asking_for_another_code_says_so_and_the_old_one_stops_working(page, site):
    account, first_code = started(page, site)
    age_codes(site, account["email"], 61)
    before = page.requests()

    page.click(f"{FORM_2} [data-reenviar]")
    settle(page, before)

    assert len(sent(site, account["email"])) == 2
    note = page.text(f"{FORM_2} [data-nota]")
    assert note.startswith("Si la cuenta existe, enviamos otro código.")
    assert page.js("document.querySelector('[data-nota]').hidden") is False
    second = sent(site, account["email"])[-1]["code"]
    if second != first_code:  # uno en un millón: salió el mismo
        fill_change(page, first_code, NEW_PASSWORD)
        submit_change(page)
        assert field_errors(page)["code"][0].startswith("El código ingresado no es correcto.")
        page.clear(f"{FORM_2} [name=code]")
    page.type(f"{FORM_2} [name=code]", second)
    if not page.value(f"{FORM_2} [name=new_password]"):
        page.type(f"{FORM_2} [name=new_password]", NEW_PASSWORD)
    submit_change(page)
    assert step(page) == "listo"


def test_asking_again_before_a_minute_says_the_same_and_sends_nothing_new(page, site):
    account, code = started(page, site)
    before = page.requests()

    page.click(f"{FORM_2} [data-reenviar]")
    settle(page, before)

    assert len(sent(site, account["email"])) == 1
    assert "Debes esperar un minuto" in page.text(f"{FORM_2} [data-nota]")


def test_use_another_email_goes_back_to_the_first_step_without_the_typed_password(page, site):
    account, code = started(page, site)
    page.type(f"{FORM_2} [name=new_password]", NEW_PASSWORD)

    page.click(f"{FORM_2} [data-otro-correo]")

    assert step(page) == "correo"
    assert page.value(f"{FORM_2} [name=new_password]") == ""
    assert page.js("document.querySelector('[data-intro]').hidden") is False
    assert page.js("document.activeElement.name") == "email"


# --- Caso 8: con sesión ------------------------------------------------------------------------------------------------------


def test_with_a_session_open_there_is_nothing_to_recover(page, site):
    account = make_account(site, first_name="Beatriz")
    log_in(page, site, account)

    go(page, site)

    assert page.text("[data-ya-con-sesion]") == "Ya iniciaste sesión como Beatriz. Para recuperar tu contraseña, primero cierra sesión."
    assert step(page) is None
    assert page.js("document.querySelector('[data-intro]').hidden") is True


# --- Caso 9: celular -----------------------------------------------------------------------------------------------------------


def test_on_a_phone_every_step_fits_the_screen(page, site):
    page.set_viewport(390, 844, mobile=True)
    account = make_account(site)
    go(page, site)
    widest = "Math.max(...Array.from(document.querySelectorAll('main *')).map(e => e.getBoundingClientRect().right))"

    assert page.js(widest) <= 390
    ask_for_the_code(page, account["email"])
    assert step(page) == "codigo"
    fill_change(page, "123456", NEW_PASSWORD)
    page.expect("document.querySelector('.fortaleza-nivel').textContent !== ''")

    assert page.js(widest) <= 390
    assert page.is_clickable(f"{FORM_2} button[type=submit]") is True
