"""El paso del Authenticator en la ventana de iniciar sesión, con navegador, servidor y base de verdad.

Decisiones de Sophia del 25 de noviembre de 2026 (pieza 3.3, ADR 0018): quien tiene el Authenticator activo inicia
sesión con su contraseña, el código del correo y el código de su aplicación. La sesión se abre con el código del correo,
pero queda en espera hasta que escribe el de la aplicación.

     1. Después del código del correo la ventana no se cierra: pide el código del Authenticator. La cabecera sigue
        siendo la del visitante. Con el código correcto la ventana se cierra y aparece el nombre.
     2. Con un código incorrecto dice cuántos intentos quedan, no deja escrito el código y sigue en ese paso.
     3. Lo que no son 6 números se avisa sin llamar a la API. El código se acepta con el espacio de en medio.
     4. Si se recarga la página con la sesión en espera, «Iniciar sesión» abre la ventana directo en ese paso.
     5. «Cerrar sesión» en ese paso cierra la sesión que estaba en espera y vuelve al correo y la contraseña.
     6. Una página protegida no muestra nada mientras la sesión está en espera.
     7. Quien no tiene el Authenticator activo inicia sesión como siempre.

El reloj de los códigos lo controla la prueba, porque el servidor corre en el mismo proceso. La API se prueba en
tests/backend/test_second_factor_login.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e\\test_authenticator_e2e.py -v -rs
"""

import pytest
from e2e_support import browser, enroll_authenticator, make_account, make_host, page, sessions_of, site  # noqa: F401
from test_entrar_e2e import go, open_window, send_code, send_credentials, settle

from app.modules.accounts import two_factor
from app.modules.accounts.totp import code_at, step_at

FORM_1 = "#ventana-entrar form[data-paso=correo]"
FORM_3 = "#ventana-entrar form[data-paso=authenticator]"
WARNING = "(() => { const a = document.querySelector('#ventana-entrar [data-aviso]'); return a && !a.hidden ? a.textContent : null; })()"
SIGNED_IN = "document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1"


@pytest.fixture(autouse=True)
def tables_ready(site):
    from app.database.transaction import system_transaction

    with system_transaction(site.pool) as connection:
        ready = connection.execute(
            "select to_regclass('public.user_totp') is not null and exists (select 1 from pg_attribute "
            "where attrelid = to_regclass('public.sessions') and attname = 'second_factor_at' and not attisdropped)"
        ).fetchone()[0]
    if not ready:
        pytest.skip("Faltan en la base integro las migraciones 20261124000006_user_totp.sql y 20261125000007_session_second_factor.sql.")


class Clock:
    """El reloj del servidor para los códigos del Authenticator."""

    def __init__(self):
        self.now = 1_800_000_015.0

    def advance(self, periods: int = 1) -> None:
        self.now += 30 * periods

    def code(self, secret: bytes) -> str:
        return code_at(secret, step_at(self.now))


@pytest.fixture
def clock(monkeypatch):
    current = Clock()
    monkeypatch.setattr(two_factor, "current_time", lambda: current.now)
    return current


def enrolled(site, first_name="Ana"):
    """Una anfitriona con el Authenticator activo: (cuenta, clave)."""
    account = make_account(site, first_name=first_name)
    make_host(site, account["email"])
    return account, enroll_authenticator(site, account["email"])


def to_the_authenticator_step(page, site, account, path="index.html"):
    go(page, site, path)
    open_window(page)
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect(f"!document.querySelector('{FORM_3}').hidden")


def send_totp(page, code):
    page.type(f"{FORM_3} [name=totp]", code)
    before = page.requests()
    page.press("Enter")
    settle(page, before)


# --- Caso 1: el paso nuevo -------------------------------------------------------------------------------------------


def test_after_the_email_code_the_window_asks_for_the_authenticator_code(page, site, clock):
    account, secret = enrolled(site)

    to_the_authenticator_step(page, site, account)

    assert page.window_open() is True
    assert page.step() == "authenticator"
    assert page.text(f"{FORM_3} [data-texto-authenticator]") == "Escribe el código de 6 dígitos que muestra tu aplicación Authenticator."
    assert page.text(f"{FORM_3} label span") == "Código de Authenticator"
    assert page.js("document.activeElement.name") == "totp"
    assert page.js("document.querySelector('#ventana-entrar .ventana-pie').hidden") is True
    assert page.js(WARNING) is None
    # La sesión existe pero está en espera: la cabecera sigue siendo la del visitante.
    assert sessions_of(site, account["email"]) == (1, 1)
    assert page.js(SIGNED_IN) is False


def test_the_right_code_closes_the_window_and_the_name_appears(page, site, clock):
    account, secret = enrolled(site, first_name="Carla")
    to_the_authenticator_step(page, site, account)

    send_totp(page, clock.code(secret))
    page.expect(SIGNED_IN)

    assert page.window_open() is False
    assert page.covers_the_page() is False
    assert page.header() == ["Carla"]
    assert page.js("document.querySelector('[data-aviso-de-sesion]').textContent") == "Iniciaste sesión como Carla."


def test_the_code_may_be_typed_with_the_space_the_app_shows(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)
    code = clock.code(secret)

    send_totp(page, f"{code[:3]} {code[3:]}")
    page.expect(SIGNED_IN)

    assert page.header() == ["Ana"]


# --- Caso 2: códigos incorrectos -------------------------------------------------------------------------------------


def test_a_wrong_code_says_how_many_attempts_are_left_and_is_not_left_written(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)
    right = clock.code(secret)
    wrong = "000000" if right != "000000" else "111111"

    send_totp(page, wrong)

    assert page.js(WARNING) == "El código ingresado no es correcto. Te quedan 4 intentos."
    assert page.step() == "authenticator"
    assert page.value(f"{FORM_3} [name=totp]") == ""
    assert page.js("document.activeElement.name") == "totp"
    assert page.js(SIGNED_IN) is False

    send_totp(page, right)
    page.expect(SIGNED_IN)
    assert page.header() == ["Ana"]


def test_the_fifth_wrong_code_says_how_long_to_wait(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)
    right = clock.code(secret)
    wrong = "000000" if right != "000000" else "111111"

    for _ in range(5):
        send_totp(page, wrong)

    assert page.js(WARNING) == "Se escribieron demasiados códigos incorrectos. Inténtalo nuevamente en 15 minutos."
    assert page.step() == "authenticator"
    send_totp(page, right)
    assert page.js(WARNING).startswith("Se escribieron demasiados códigos incorrectos.")
    assert page.js(SIGNED_IN) is False


# --- Caso 3: lo que no son 6 números ---------------------------------------------------------------------------------


@pytest.mark.parametrize("written,warning", [
    ("", "Escribe el código de tu aplicación Authenticator."),
    ("12345", "El código debe constar de 6 dígitos."),
    ("abcdef", "El código debe constar de 6 dígitos."),
])
def test_what_is_not_six_numbers_is_warned_without_asking_the_api(page, site, clock, written, warning):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)
    if written:
        page.type(f"{FORM_3} [name=totp]", written)
    before = page.requests()

    page.press("Enter")

    page.expect(f"{WARNING} !== null")
    assert page.js(WARNING) == warning
    assert page.requests() == before
    assert page.step() == "authenticator"


# --- Caso 4: recargar con la sesión en espera ------------------------------------------------------------------------


def test_after_a_reload_iniciar_sesion_goes_straight_to_the_authenticator_step(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)

    go(page, site, "index.html")

    assert page.window_open() is False
    assert page.header() == ["Iniciar sesión", "Crear cuenta"]
    assert account["first_name"] not in page.js("document.querySelector('header').textContent")

    open_window(page)

    assert page.step() == "authenticator"
    assert page.js(f"document.querySelector('{FORM_1}').hidden") is True
    send_totp(page, clock.code(secret))
    page.expect(SIGNED_IN)
    assert page.header() == ["Ana"]


def test_closing_the_window_leaves_the_session_waiting_and_it_can_be_resumed(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)

    page.press("Escape")
    page.expect("document.getElementById('ventana-entrar').hidden")
    assert page.header() == ["Iniciar sesión", "Crear cuenta"]

    open_window(page)
    assert page.step() == "authenticator"
    assert page.value(f"{FORM_3} [name=totp]") == ""


# --- Caso 5: cerrar la sesión en espera ------------------------------------------------------------------------------


def test_cerrar_sesion_in_that_step_closes_the_waiting_session_and_goes_back_to_the_start(page, site, clock):
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)
    assert sessions_of(site, account["email"]) == (1, 1)

    before = page.requests()
    page.click(f"{FORM_3} [data-salir-de-espera]")
    page.expect(f"window.__net.started > {before}")
    page.expect(f"!document.querySelector('{FORM_1}').hidden")

    assert page.step() == "correo"
    assert page.js("document.querySelector('#ventana-entrar .ventana-pie').hidden") is False
    assert sessions_of(site, account["email"]) == (0, 1)
    assert page.header() == ["Iniciar sesión", "Crear cuenta"]


# --- Caso 6: una página protegida ------------------------------------------------------------------------------------


def test_a_protected_page_shows_nothing_while_the_session_is_waiting(page, site, clock):
    account, secret = enrolled(site, first_name="Elena")
    to_the_authenticator_step(page, site, account)

    go(page, site, "mi-cuenta.html")

    assert page.js("document.querySelector('[data-contenido]').hidden") is True
    assert page.text("[data-acceso-titulo]") == "Inicia sesión para continuar"
    assert page.js("document.body.textContent.indexOf('Elena')") == -1
    assert page.js(f"document.body.textContent.indexOf({account['email']!r})") == -1

    page.click("[data-acceso-enlace]")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    assert page.step() == "authenticator"
    send_totp(page, clock.code(secret))
    page.expect("!document.querySelector('[data-contenido]').hidden")
    assert page.text("[data-dato=nombre]") == "Elena Torres"


# --- Caso 7: sin el Authenticator ------------------------------------------------------------------------------------


def test_without_the_authenticator_the_window_closes_after_the_email_code_as_always(page, site, clock):
    account = make_account(site, first_name="Diana")
    go(page, site, "index.html")
    open_window(page)
    send_credentials(page, account["email"], account["password"])

    send_code(page, site.codes.code_for(account["email"], "login"))
    page.expect(SIGNED_IN)

    assert page.window_open() is False
    assert page.header() == ["Diana"]


# --- En el teléfono --------------------------------------------------------------------------------------------------


def test_the_authenticator_step_fits_and_works_on_a_phone(page, site, clock):
    page.send("Emulation.setDeviceMetricsOverride", width=360, height=740, deviceScaleFactor=2, mobile=True)
    account, secret = enrolled(site)
    to_the_authenticator_step(page, site, account)

    assert page.js("document.documentElement.scrollWidth <= window.innerWidth") is True
    assert page.is_clickable(f"{FORM_3} button[type=submit]") is True
    assert page.is_clickable(f"{FORM_3} [data-salir-de-espera]") is True

    send_totp(page, clock.code(secret))
    page.expect("document.getElementById('ventana-entrar').hidden")
