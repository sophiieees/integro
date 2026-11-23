"""El CAPTCHA en las pantallas, con navegador, servidor y base de verdad.

Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016): Cloudflare Turnstile, siempre activo, en cinco acciones:
registrar (register), iniciar sesión (login), pedir el código de recuperar la contraseña (password_reset), pedir otro
código de verificación (resend_code) y corregir el correo (correct_email).

Aquí no se toca internet. La página recibe un widget de Cloudflare de mentira (FAKE_TURNSTILE, en e2e_support.py) que se
porta como el de verdad: entrega un resultado nuevo cada vez, y la API de la prueba lo comprueba como Cloudflare, una sola
vez y para la acción de su pantalla (StubCaptcha). Lo que se prueba es la pantalla: que dibuje el widget donde toca, que
espere el resultado, que lo mande, que pida uno nuevo para cada petición y qué dice cuando algo falla.
El CAPTCHA de la API se prueba en tests/backend/test_captcha.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e\\test_captcha_e2e.py -v -rs
"""

import pytest
from e2e_support import age_codes, browser, make_account, page, site  # noqa: F401
from test_entrar_e2e import log_in, open_window, send_code, send_credentials
from test_recuperar_e2e import ask_for_the_code, migration_applied  # noqa: F401
from test_recuperar_e2e import go as go_recover
from test_registro_e2e import (
    CODE_FORM,
    CORRECTION,
    FORM,
    fill,
    go,
    notice,
    open_correction,
    person,
    register_up_to_the_code,
    send_correction,
    step,
    submit,
    user_row,
)

from app.api.captcha import CaptchaResult

NOTICE = "No pudimos comprobar que eres una persona. Inténtalo de nuevo."
NOT_LOADED = "No pudimos cargar la comprobación de que eres una persona. Revisa tu conexión e inténtalo de nuevo."


@pytest.fixture(autouse=True)
def fresh_captcha(site):
    """Cada prueba empieza sin historia y con el CAPTCHA comportándose normal."""
    site.captcha.seen.clear()
    site.captcha.force = None
    yield
    site.captcha.force = None


def screen_requests(site):
    """Lo que la API comprobó de la pantalla: sin las peticiones directas de los ayudantes que crean cuentas."""
    return [(token, action) for token, action in site.captcha.seen if not token.startswith("STUB-DIRECT-")]


def seen(site):
    return [token for token, _ in screen_requests(site)]


def actions(site):
    return [action for _, action in screen_requests(site)]


def renders(page):
    return page.js("window.__stub.renders")


def widget(page, selector):
    """Los datos del widget de esa zona, o None si todavía no se dibuja."""
    return page.js(
        f"(() => {{ const z = document.querySelector({selector!r}); "
        "return z && z.hasAttribute('data-stub-widget') ? { action: z.getAttribute('data-stub-action'), "
        "sitekey: z.getAttribute('data-stub-sitekey'), appearance: z.getAttribute('data-stub-appearance') } : null; })()"
    )


def stub_before_the_page(page, source):
    """Cambia el widget de mentira antes de que la página cargue."""
    page.send("Page.addScriptToEvaluateOnNewDocument", source=source)


def wait_for_widget(page, selector):
    page.expect(f"document.querySelector({selector!r}) && document.querySelector({selector!r}).hasAttribute('data-stub-widget')")


# --- El widget aparece donde toca ----------------------------------------------------------


def test_the_registration_page_draws_the_widget_of_the_form_with_its_action_and_the_key_of_the_api(page, site):
    go(page, site)
    wait_for_widget(page, f"{FORM} [data-captcha]")

    assert widget(page, f"{FORM} [data-captcha]") == {
        "action": "register", "sitekey": "1x00000000000000000000AA", "appearance": "interaction-only",
    }
    # Los otros pasos todavía no se ven: su widget se dibuja cuando se muestran.
    assert widget(page, f"{CODE_FORM} [data-captcha]") is None
    assert widget(page, f"{CORRECTION} [data-captcha]") is None


def test_the_code_step_and_the_correction_draw_their_own_widgets_when_they_are_shown(page, site):
    register_up_to_the_code(page, site)
    wait_for_widget(page, f"{CODE_FORM} [data-captcha]")
    assert widget(page, f"{CODE_FORM} [data-captcha]")["action"] == "resend_code"

    open_correction(page)
    wait_for_widget(page, f"{CORRECTION} [data-captcha]")
    assert widget(page, f"{CORRECTION} [data-captcha]")["action"] == "correct_email"


def test_the_recovery_page_draws_a_widget_for_each_of_its_two_steps(page, site):
    go_recover(page, site)
    wait_for_widget(page, "#formulario-correo [data-captcha]")
    assert widget(page, "#formulario-correo [data-captcha]")["action"] == "password_reset"
    assert widget(page, "#formulario-cambio [data-captcha]") is None

    account = make_account(site)
    ask_for_the_code(page, account["email"])
    wait_for_widget(page, "#formulario-cambio [data-captcha]")
    assert widget(page, "#formulario-cambio [data-captcha]")["action"] == "password_reset"


def test_the_sign_in_window_draws_its_widget_when_it_opens_and_not_before(page, site):
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")

    # Mirar la portada no pide nada a Cloudflare ni a la API del CAPTCHA.
    assert renders(page) == []
    assert page.js("performance.getEntriesByType('resource').some(r => r.name.includes('/auth/captcha'))") is False

    open_window(page)
    wait_for_widget(page, "#ventana-entrar [data-captcha]")

    assert widget(page, "#ventana-entrar [data-captcha]")["action"] == "login"
    assert page.js("performance.getEntriesByType('resource').some(r => r.name.includes('/auth/captcha'))") is True


def test_with_a_session_the_registration_page_draws_no_widget(page, site):
    log_in(page, site, make_account(site))

    go(page, site)

    assert renders(page) == []


def test_the_widget_zone_takes_no_room_while_it_is_empty_and_centers_the_widget_when_it_has_one(page, site):
    go(page, site)

    shown = page.js(
        "(() => { const vacia = document.createElement('div'); vacia.className = 'captcha'; document.body.appendChild(vacia); "
        "const llena = document.createElement('div'); llena.className = 'captcha'; llena.appendChild(document.createElement('iframe')); "
        "document.body.appendChild(llena); "
        "const r = [getComputedStyle(vacia).display, getComputedStyle(llena).display, getComputedStyle(llena).justifyContent]; "
        "vacia.remove(); llena.remove(); return r; })()"
    )
    assert shown == ["none", "flex", "center"]


# --- Cada acción manda su resultado, y uno nuevo cada vez ---------------------------------------


def test_registering_sends_a_result_made_for_register_and_the_account_is_created(page, site):
    data = register_up_to_the_code(page, site)

    assert actions(site) == ["register"]
    assert seen(site)[0].startswith("STUB-register-")
    assert user_row(site, data["email"]) is not None


def test_asking_for_another_code_and_correcting_the_email_each_send_a_new_result_for_their_action(page, site):
    data = register_up_to_the_code(page, site)
    age_codes(site, data["email"], 120)
    before = page.requests()
    page.click(f"{CODE_FORM} [data-reenviar]")
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")
    assert notice(page) is None

    open_correction(page)
    send_correction(page, "otro." + data["email"], data["password"])
    assert step(page) == "codigo"

    assert actions(site) == ["register", "resend_code", "correct_email"]
    # Cloudflare entrega un resultado nuevo para cada petición: ninguno se repitió, o la API lo habría rechazado.
    assert len(set(seen(site))) == 3
    assert page.js("window.__stub.resets") >= 3


def test_a_failed_password_and_then_the_right_one_each_carry_their_own_result(page, site):
    account = make_account(site)
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    open_window(page)

    send_credentials(page, account["email"], "Contrasena-equivocada-1!")
    assert page.text("#ventana-entrar [data-aviso]") == "El correo electrónico o la contraseña no son correctos."
    page.js("document.querySelector('#ventana-entrar form[data-paso=correo] [name=password]').value = ''")
    send_credentials(page, account["email"], account["password"])
    assert page.step() == "codigo", page.state()

    assert actions(site) == ["login", "login"]
    assert len(set(seen(site))) == 2


def test_signing_in_from_the_window_works_end_to_end_with_the_captcha(page, site):
    account = make_account(site, first_name="Carla")
    log_in(page, site, account)

    assert page.header() == ["Carla"]
    assert actions(site) == ["login"]


def test_recovering_the_password_asks_for_the_code_and_for_another_one_with_their_own_results(page, site):
    account = make_account(site)
    go_recover(page, site)
    ask_for_the_code(page, account["email"])
    assert page.js("(() => { const f = document.getElementById('formulario-cambio'); return !f.hidden; })()") is True

    age_codes(site, account["email"], 120)
    before = page.requests()
    page.click("#formulario-cambio [data-reenviar]")
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")

    assert actions(site) == ["password_reset", "password_reset"]
    assert len(set(seen(site))) == 2


def test_the_steps_that_write_a_code_send_no_captcha_result(page, site):
    data = register_up_to_the_code(page, site)
    page.type(f"{CODE_FORM} [name=code]", site.codes.code_for(data["email"], "verify_email"))
    page.press("Enter")
    page.expect("!document.getElementById('registro-listo').hidden")

    assert actions(site) == ["register"]


# --- Esperar el resultado ---------------------------------------------------------------------------


def test_the_form_waits_for_the_result_and_sends_nothing_until_it_arrives(page, site):
    stub_before_the_page(page, "window.__stub.mode = 'never'")
    data = person()
    go(page, site)
    wait_for_widget(page, f"{FORM} [data-captcha]")
    fill(page, data)
    before = page.requests()

    page.click(f"{FORM} button[type=submit]")
    page.expect(f"Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")

    # Está esperando el desafío: no hay petición, no se creó nada, el formulario está ocupado.
    assert page.requests() == before
    assert user_row(site, data["email"]) is None

    page.js("window.__stub.mode = 'ok'; window.turnstile.reset('stub-0')")
    page.expect(f"window.__net.started > {before}")
    page.expect("!document.getElementById('formulario-codigo').hidden")

    assert user_row(site, data["email"]) is not None
    assert actions(site) == ["register"]


def test_a_slow_challenge_only_delays_the_request(page, site):
    stub_before_the_page(page, "window.__stub.delay = 600")

    data = register_up_to_the_code(page, site)

    assert user_row(site, data["email"]) is not None


# --- Cuando algo falla -------------------------------------------------------------------------------


def test_if_the_challenge_fails_the_person_is_told_nothing_is_sent_and_can_try_again(page, site):
    stub_before_the_page(page, "window.__stub.mode = 'error'")
    data = person()
    go(page, site)
    wait_for_widget(page, f"{FORM} [data-captcha]")
    fill(page, data)
    before = page.requests()

    page.click(f"{FORM} button[type=submit]")
    page.expect("(() => { const a = document.querySelector('[data-aviso]'); return a && !a.hidden; })()")

    assert notice(page) == NOTICE
    assert step(page) == "datos"
    assert page.requests() == before
    assert user_row(site, data["email"]) is None
    assert page.js("Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)") is False
    assert page.value(f"{FORM} [name=first_name]") == "Ana"

    page.js("window.__stub.mode = 'ok'")
    submit(page)

    assert step(page) == "codigo", (page.state(), notice(page))
    assert user_row(site, data["email"]) is not None


@pytest.mark.parametrize("forced", [CaptchaResult.FAILED, CaptchaResult.UNAVAILABLE])
def test_if_the_api_refuses_the_captcha_the_form_says_so_and_a_new_try_works(page, site, forced):
    data = person()
    go(page, site)
    wait_for_widget(page, f"{FORM} [data-captcha]")
    fill(page, data)
    site.captcha.force = forced

    submit(page)

    assert notice(page) == NOTICE
    assert step(page) == "datos"
    assert user_row(site, data["email"]) is None
    assert page.value(f"{FORM} [name=email]") == data["email"]

    site.captcha.force = None
    submit(page)

    assert step(page) == "codigo", (page.state(), notice(page))
    assert user_row(site, data["email"]) is not None
    # El segundo intento usó un resultado nuevo, no el del que se rechazó.
    first, second = seen(site)
    assert first != second


def test_if_the_api_refuses_the_captcha_in_the_sign_in_window_it_says_so_and_keeps_what_was_typed(page, site):
    account = make_account(site)
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    open_window(page)
    wait_for_widget(page, "#ventana-entrar [data-captcha]")
    site.captcha.force = CaptchaResult.UNAVAILABLE

    send_credentials(page, account["email"], account["password"])

    assert page.text("#ventana-entrar [data-aviso]") == NOTICE
    assert page.step() == "correo"
    assert page.value("#ventana-entrar form[data-paso=correo] [name=email]") == account["email"]
    assert not [m for m in site.codes.sent if m["destination"] == account["email"] and m["purpose"] == "login"]

    site.captcha.force = None
    page.js("document.querySelector('#ventana-entrar form[data-paso=correo]').requestSubmit()")
    page.expect("!document.querySelector('#ventana-entrar form[data-paso=codigo]').hidden")


def test_if_the_api_refuses_the_captcha_when_asking_for_the_recovery_code_it_says_so_and_sends_nothing(page, site):
    account = make_account(site)
    go_recover(page, site)
    wait_for_widget(page, "#formulario-correo [data-captcha]")
    site.captcha.force = CaptchaResult.FAILED

    ask_for_the_code(page, account["email"])

    assert page.js("(() => { const a = document.querySelector('[data-aviso]'); return a && !a.hidden ? a.textContent : null; })()") == NOTICE
    assert page.js("document.getElementById('formulario-correo').hidden") is False
    assert not [m for m in site.codes.sent if m["destination"] == account["email"] and m["purpose"] == "password_reset"]


def test_a_refused_captcha_when_asking_for_another_code_keeps_the_person_in_the_code_step(page, site):
    data = register_up_to_the_code(page, site)
    wait_for_widget(page, f"{CODE_FORM} [data-captcha]")
    age_codes(site, data["email"], 120)
    sent_before = len([m for m in site.codes.sent if m["destination"] == data["email"]])
    site.captcha.force = CaptchaResult.FAILED

    before = page.requests()
    page.click(f"{CODE_FORM} [data-reenviar]")
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")

    assert notice(page) == NOTICE
    assert step(page) == "codigo"
    assert len([m for m in site.codes.sent if m["destination"] == data["email"]]) == sent_before


# --- En el teléfono ----------------------------------------------------------------------------------


def test_the_widget_zone_does_not_push_the_form_out_of_a_phone_screen(page, site):
    page.send("Emulation.setDeviceMetricsOverride", width=360, height=740, deviceScaleFactor=2, mobile=True)
    go(page, site)
    wait_for_widget(page, f"{FORM} [data-captcha]")

    assert page.js("document.documentElement.scrollWidth <= window.innerWidth") is True
