"""Casos de «Reservar sin sesión», de principio a fin: navegador, servidor y base de verdad.

Decisión de Sophia del 20 de noviembre de 2026: un visitante que da clic en «Reservar» sin sesión ve el aviso de
iniciar sesión o crear su cuenta y, al terminar, vuelve a la misma propiedad con sus fechas y sus huéspedes, guardados
en la dirección de la página. Para quien ya tiene sesión, por ahora, las reservas «se abren pronto».

    1. La ficha toma de su dirección las fechas y los huéspedes; lo que no sirve se ignora.
    2. Sin sesión, «Reservar» muestra el aviso con «Iniciar sesión» y «Crear cuenta», y guarda lo elegido en la
       dirección sin recargar ni agregar pasos al historial. No se guarda nada en el navegador.
    3. Una salida igual o anterior a la llegada se avisa y no sigue.
    4. «Crear cuenta» lleva al registro con el regreso; al registrarse, comprobar el correo e iniciar sesión, la persona
       vuelve a la misma propiedad con sus fechas y sus huéspedes.
    5. Si inicia sesión en la misma página, no se va a ningún lado: sus fechas siguen ahí y el aviso cambia.
    6. Con sesión, «Reservar» dice que las reservas se abren pronto.
    7. Una dirección de regreso que apunta a otro sitio o a algo raro no se sigue nunca.
    8. En celular cabe y se puede usar.

Corren contra la base `integro` de backend/.env, dentro de una transacción que se deshace al terminar el archivo.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import urllib.parse

import pytest
from e2e_support import browser, make_account, page, site  # noqa: F401
from test_entrar_e2e import log_in, open_window, send_code, send_credentials
from test_registro_e2e import fill, person, step, submit, type_code

DATES = "llegada=2026-12-01&salida=2026-12-03&huespedes=3"
FICHA = f"propiedad.html?id=2&{DATES}"
NOTICE = "[data-reserva-aviso]"


def go(page, site, path):
    page.goto(f"{site.url}/{path}")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


def form_values(page):
    return page.js(
        "(() => { const f = document.querySelector('.caja-precio form'); "
        "return [f.elements.llegada.value, f.elements.salida.value, f.elements.huespedes.value]; })()"
    )


def reserve(page):
    page.click(".caja-precio form button.btn-primario")


def notice_text(page):
    return page.js(f"(() => {{ const a = document.querySelector('{NOTICE}'); return a && !a.hidden ? a.innerText : null; }})()")


# --- Caso 1: lo que trae la dirección ------------------------------------------------------------------


def test_the_page_takes_the_dates_and_the_guests_from_its_address(page, site):
    go(page, site, FICHA)

    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]


@pytest.mark.parametrize("query, expected", [
    ("llegada=2026-12-01", ["2026-12-01", "", "1"]),
    ("llegada=2026-02-31&salida=2026-12-03&huespedes=9", ["", "2026-12-03", "1"]),
    ("llegada=%3Cscript%3E&salida=26-12-03&huespedes=0", ["", "", "1"]),
    ("huespedes=1e1", ["", "", "1"]),
])
def test_what_does_not_work_in_the_address_is_ignored(page, site, query, expected):
    """Lo que se ignora queda como estaba: sin fechas y con el primer número de huéspedes de la lista (1)."""
    go(page, site, f"propiedad.html?id=2&{query}")

    assert form_values(page) == expected
    assert notice_text(page) is None
    assert page.text("h1")  # la ficha se pintó igual


def test_a_page_without_dates_starts_empty_as_before(page, site):
    go(page, site, "propiedad.html?id=2")

    assert form_values(page)[:2] == ["", ""]


# --- Caso 2: «Reservar» sin sesión --------------------------------------------------------------------------


def test_reserve_without_a_session_asks_to_sign_in_or_create_the_account(page, site):
    go(page, site, FICHA)

    reserve(page)

    text = notice_text(page)
    assert text.startswith("Para reservar necesitas una cuenta")
    assert "Inicia sesión o crea tu cuenta." in text
    assert "Volverás a esta propiedad con tus fechas y tus huéspedes." in text
    assert page.text(f"{NOTICE} [data-reserva-entrar]") == "Iniciar sesión"
    assert page.text(f"{NOTICE} [data-reserva-crear]") == "Crear cuenta"
    assert page.is_clickable(f"{NOTICE} [data-reserva-entrar]") is True


def test_what_was_chosen_is_saved_in_the_address_without_reloading_or_adding_history(page, site):
    go(page, site, "propiedad.html?id=2")
    page.set_value(".caja-precio [name=llegada]", "2026-12-10")
    page.set_value(".caja-precio [name=salida]", "2026-12-12")
    page.set_value(".caja-precio [name=huespedes]", "4")
    steps_before = page.js("history.length")
    requests_before = page.requests()

    reserve(page)

    assert page.location() == "/propiedad.html?id=2&llegada=2026-12-10&salida=2026-12-12&huespedes=4"
    assert page.js("history.length") == steps_before
    assert page.requests() == requests_before  # no se pidió nada: ni a la API ni se recargó
    # Recargar con esa dirección deja lo mismo.
    go(page, site, page.location().lstrip("/"))
    assert form_values(page) == ["2026-12-10", "2026-12-12", "4"]


def test_without_dates_the_notice_still_appears_and_only_the_property_is_saved(page, site):
    go(page, site, "propiedad.html?id=2")

    reserve(page)

    assert notice_text(page).startswith("Para reservar necesitas una cuenta")
    assert page.location() == "/propiedad.html?id=2&huespedes=1"


def test_nothing_is_kept_in_the_browser(page, site):
    go(page, site, FICHA)

    reserve(page)

    assert page.js("localStorage.length") == 0 and page.js("sessionStorage.length") == 0
    assert page.js("document.cookie") == ""


def test_the_sign_in_button_of_the_notice_opens_the_window(page, site):
    go(page, site, FICHA)
    reserve(page)

    page.click(f"{NOTICE} [data-reserva-entrar]")

    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    assert page.text("#ventana-entrar h2") == "Iniciar sesión"
    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]


# --- Caso 3: fechas que no pueden ser --------------------------------------------------------------------------


@pytest.mark.parametrize("arrival, departure", [("2026-12-05", "2026-12-03"), ("2026-12-05", "2026-12-05")])
def test_a_departure_that_is_not_after_the_arrival_is_warned_and_goes_no_further(page, site, arrival, departure):
    go(page, site, "propiedad.html?id=2")
    page.set_value(".caja-precio [name=llegada]", arrival)
    page.set_value(".caja-precio [name=salida]", departure)

    reserve(page)

    assert notice_text(page) == "La fecha de salida debe ser posterior a la de llegada."
    assert page.count(f"{NOTICE} [data-reserva-crear]") == 0
    assert page.location() == "/propiedad.html?id=2"


def test_fixing_the_dates_clears_the_warning_and_lets_it_go_on(page, site):
    go(page, site, "propiedad.html?id=2")
    page.set_value(".caja-precio [name=llegada]", "2026-12-05")
    page.set_value(".caja-precio [name=salida]", "2026-12-03")
    reserve(page)
    assert notice_text(page) is not None

    page.set_value(".caja-precio [name=salida]", "2026-12-07")

    assert notice_text(page) is None
    reserve(page)
    assert notice_text(page).startswith("Para reservar necesitas una cuenta")


# --- Caso 4: crear la cuenta y volver --------------------------------------------------------------------------------


def test_create_account_carries_the_way_back(page, site):
    go(page, site, FICHA)
    reserve(page)

    href = page.js(f"document.querySelector('{NOTICE} [data-reserva-crear]').getAttribute('href')")

    assert href == "registro.html?siguiente=" + urllib.parse.quote(FICHA, safe="")


def test_the_whole_trip_register_verify_sign_in_and_come_back_to_the_same_property(page, site):
    go(page, site, FICHA)
    reserve(page)
    page.click(f"{NOTICE} [data-reserva-crear]")
    page.expect("location.pathname === '/registro.html'")
    page.expect("document.documentElement.hasAttribute('data-registro-listo')")
    data = person(first_name="Valeria")

    fill(page, data)
    submit(page)
    assert step(page) == "codigo"
    type_code(page, site.codes.code_for(data["email"], "verify_email"))
    assert step(page) == "listo"
    assert "volverás a la página donde estabas" in page.text("[data-nota-siguiente]")
    assert page.js("document.querySelector('[data-nota-siguiente]').hidden") is False
    page.click("[data-iniciar-sesion]")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, data["email"], data["password"])
    send_code(page, site.codes.code_for(data["email"], "login"))

    page.expect("location.pathname === '/propiedad.html'")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    assert page.location() == "/" + FICHA
    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]
    assert page.header() == ["Valeria"]
    assert page.text("h1")


def test_an_existing_account_signs_in_from_the_registration_page_and_comes_back(page, site):
    account = make_account(site, first_name="Camila")
    go(page, site, "registro.html?siguiente=" + urllib.parse.quote(FICHA, safe=""))

    page.click(".cuenta-entrar")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect("location.pathname === '/propiedad.html'")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    assert page.location() == "/" + FICHA
    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]


def test_the_registration_page_says_nothing_about_going_back_if_it_was_not_asked(page, site):
    go(page, site, "registro.html")

    assert page.js("document.querySelector('[data-nota-siguiente]').hidden") is True


# --- Caso 5: iniciar sesión en la misma página ----------------------------------------------------------------------------


def test_signing_in_on_the_same_page_goes_nowhere_and_the_notice_changes(page, site):
    account = make_account(site, first_name="Diana")
    go(page, site, FICHA)
    reserve(page)
    page.click(f"{NOTICE} [data-reserva-entrar]")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")

    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect(f"document.querySelector('{NOTICE}').innerText.indexOf('Ya iniciaste sesión') === 0")
    assert page.location() == "/" + FICHA
    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]
    assert "Las reservas se abren pronto." in notice_text(page)
    assert page.count(f"{NOTICE} [data-reserva-entrar]") == 0
    assert page.header() == ["Diana"]


def test_signing_in_on_another_page_shows_a_brief_notice_and_keeps_what_was_typed(page, site):
    account = make_account(site, first_name="Diana")
    go(page, site, FICHA)
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    open_window(page)
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect("document.querySelector('[data-aviso-de-sesion]') !== null")
    assert page.js("document.querySelector('[data-aviso-de-sesion]').textContent") == "Iniciaste sesión como Diana."
    assert page.js("document.querySelector('[data-aviso-de-sesion]').getAttribute('role')") == "status"
    # No recibe clics, no tapa la página y no la recarga: la persona sigue donde estaba, con lo que había escrito.
    assert page.js("getComputedStyle(document.querySelector('[data-aviso-de-sesion]')).pointerEvents") == "none"
    assert page.location() == "/" + FICHA
    assert form_values(page) == ["2026-12-01", "2026-12-03", "3"]
    # Se quita solo.
    page.expect("document.querySelector('[data-aviso-de-sesion]') === null", seconds=8)


# --- Caso 6: con sesión ----------------------------------------------------------------------------------------------------


def test_with_a_session_reserve_says_the_reservations_open_soon(page, site):
    account = make_account(site)
    log_in(page, site, account, FICHA)

    reserve(page)

    text = notice_text(page)
    assert text.startswith("Las reservas se abren pronto")
    assert "Todavía no se puede reservar." in text
    assert page.count(f"{NOTICE} [data-reserva-crear]") == 0
    assert page.location() == "/" + FICHA


# --- Caso 7: una dirección de regreso que no se debe seguir ---------------------------------------------------------------------


@pytest.mark.parametrize("bad", [
    "https://evil.example/propiedad.html",
    "//evil.example",
    "javascript:alert(1)",
    "registro.html",
    "propiedad.html?x=<script>",
    "../propiedad.html",
])
def test_a_way_back_that_is_not_allowed_is_never_followed_and_the_registration_goes_to_the_home_page(page, site, bad):
    account = make_account(site, first_name="Elena")
    go(page, site, "registro.html?siguiente=" + urllib.parse.quote(bad, safe=""))
    assert page.js("document.querySelector('[data-nota-siguiente]').hidden") is True

    page.click(".cuenta-entrar")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect("location.pathname === '/index.html'")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    # Una dirección de regreso que no vale se ignora: se hace lo de siempre desde el registro, ir a la portada.
    assert page.js("location.origin") == site.url
    assert page.js("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1") is True


def test_a_safe_way_back_works_from_any_page_with_the_address_in_it(page, site):
    account = make_account(site)
    go(page, site, "index.html?siguiente=" + urllib.parse.quote("propiedad.html?id=3", safe=""))

    page.click(".cuenta-entrar")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect("location.pathname === '/propiedad.html'")
    assert page.location() == "/propiedad.html?id=3"


def test_a_failed_sign_in_does_not_go_anywhere(page, site):
    account = make_account(site)
    go(page, site, "registro.html?siguiente=" + urllib.parse.quote(FICHA, safe=""))
    page.click(".cuenta-entrar")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")

    send_credentials(page, account["email"], "Mala-2026!x")

    assert page.js("location.pathname") == "/registro.html"
    assert page.warning() == "El correo electrónico o la contraseña no son correctos."


# --- Caso 8: celular ----------------------------------------------------------------------------------------------------------


def test_on_a_phone_the_notice_fits_and_the_buttons_can_be_used(page, site):
    page.set_viewport(390, 844, mobile=True)
    go(page, site, FICHA)

    reserve(page)

    right = page.js(f"Math.max(...Array.from(document.querySelectorAll('{NOTICE} *')).map(e => e.getBoundingClientRect().right))")
    assert right <= 390
    assert page.js("document.documentElement.scrollWidth") <= 390
    assert page.is_clickable(f"{NOTICE} [data-reserva-entrar]") is True
    assert page.is_clickable(f"{NOTICE} [data-reserva-crear]") is True
