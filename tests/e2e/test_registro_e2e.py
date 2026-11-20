"""Casos de la pantalla de registro, de principio a fin: navegador, servidor y base de verdad.

Especificación de la pieza (decisiones de Sophia del 20 de noviembre de 2026: página aparte, teléfono con
selector de código y número, todos los países con México primero, indicador de cuatro cuadros):

     1. registro.html muestra el formulario con todos los datos obligatorios; México ya elegido.
     2. El indicador de la contraseña sigue lo que se escribe: nivel, cuadros y consejos que contesta la API.
     3. Con datos vacíos o mal escritos avisa en cada campo y no le pregunta nada a la API.
     4. Con datos que la API rechaza (contraseña débil, menor de edad) avisa en su campo y no crea la cuenta.
     5. Con datos buenos crea la cuenta y pasa al código; el correo se comprueba con el código que llegó.
     6. Un código incorrecto dice cuántos intentos quedan; «Enviar otro código» respeta la espera de un minuto.
     7. Correo o teléfono que ya tienen cuenta: aviso en su campo; con el correo, ofrece iniciar sesión.
     8. El teléfono se guarda con el código elegido y sigue al país de residencia mientras no se cambie a mano.
     9. Con la cuenta lista, «Iniciar sesión» lleva a entrar con ella.
    10. Sin API, con sesión iniciada y en celular, la pantalla se porta bien.

Corren contra la base `integro` de backend/.env, dentro de una transacción que se deshace al terminar el archivo.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import re
import uuid
from datetime import date
from pathlib import Path

from e2e_support import age_codes, browser, make_account, page, sessions_of, site  # noqa: F401

from app.database.transaction import system_transaction

PASSWORD = "Ejemplo-2026"
WEB = Path(__file__).resolve().parents[2] / "web"
FORM = "#formulario-registro"
CODE_FORM = "#formulario-codigo"
LEVEL = "document.querySelector('[data-fortaleza-nivel]').textContent"
FILLED = "document.querySelectorAll('.fortaleza-barra span.lleno').length"
TIPS = "Array.from(document.querySelectorAll('[data-fortaleza-consejos] li')).map(li => li.textContent)"


# --- Lo que hace una persona --------------------------------------------------------


def go(page, site):
    page.goto(f"{site.url}/registro.html")
    page.expect("document.documentElement.hasAttribute('data-registro-listo')")


def person(**changes):
    """Una persona nueva: correo y teléfono que no existen."""
    tag = uuid.uuid4().hex[:12]
    data = {
        "first_name": "Ana", "last_name": "Torres López", "email": f"ana.{tag}@prueba.invalid", "password": PASSWORD,
        "number": "55" + str(int(tag, 16) % 10**8).zfill(8), "country": "MX", "birth_date": "1995-03-14",
    }
    data.update(changes)
    return data


def fill(page, data):
    page.type(f"{FORM} [name=first_name]", data["first_name"])
    page.type(f"{FORM} [name=last_name]", data["last_name"])
    page.type(f"{FORM} [name=email]", data["email"])
    page.type(f"{FORM} [name=password]", data["password"])
    page.type(f"{FORM} [name=numero]", data["number"])
    page.set_value(f"{FORM} [name=country]", data["country"])
    page.set_value(f"{FORM} [name=birth_date]", data["birth_date"])


def submit(page):
    """Da clic en «Crear cuenta» y espera a que la API conteste."""
    before = page.requests()
    page.click(f"{FORM} button[type=submit]")
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")


def field_errors(page):
    return page.js(
        "Object.fromEntries(Array.from(document.querySelectorAll('[data-error-de]')).filter(e => !e.hidden)"
        ".map(e => [e.getAttribute('data-error-de'), Array.from(e.children).filter(c => c.tagName === 'SPAN').map(c => c.textContent)]))"
    )


def notice(page):
    return page.js("(() => { const a = document.querySelector('[data-aviso]'); return a && !a.hidden ? a.textContent : null; })()")


def step(page):
    return page.js(
        "(() => { for (const [id, name] of [['formulario-registro', 'datos'], ['formulario-codigo', 'codigo'], ['registro-listo', 'listo']]) "
        "{ const e = document.getElementById(id); if (e && !e.hidden) return name; } return null; })()"
    )


def user_row(site, email):
    with system_transaction(site.pool) as connection:
        return connection.execute(
            "select u.email_verified_at is not null, u.country, "
            "(select phone from user_phones p where p.user_id = u.id and p.is_primary), "
            "(select password_hash from user_credentials c where c.user_id = u.id) from users u where u.email = %s",
            (email,),
        ).fetchone()


def register_up_to_the_code(page, site, **changes):
    data = person(**changes)
    go(page, site)
    fill(page, data)
    submit(page)
    assert step(page) == "codigo", (page.state(), field_errors(page), notice(page))
    return data


def type_code(page, code):
    page.type(f"{CODE_FORM} [name=code]", code)
    before = page.requests()
    page.press("Enter")
    page.expect(f"window.__net.started > {before}")
    page.expect("!Array.from(document.querySelectorAll('.formulario-tarjeta input')).some(i => i.disabled)")


# --- Caso 1 ------------------------------------------------------------------------


def test_the_page_shows_the_form_with_every_required_field_and_mexico_chosen(page, site):
    go(page, site)

    assert page.text("h1") == "Crea tu cuenta"
    assert page.header() == ["Iniciar sesión"]
    assert page.js("Array.from(document.querySelectorAll('header.cabecera .enlaces-cabecera a')).map(a => a.textContent)") == [
        "Buscar hospedaje", "Conviértete en anfitrión",
    ]
    assert step(page) == "datos"
    labels = page.js("Array.from(document.querySelectorAll('#formulario-registro .campo-etiqueta')).map(e => e.textContent.trim())")
    assert labels == ["Nombre", "Apellidos", "Correo electrónico", "Contraseña", "Teléfono", "País de residencia", "Fecha de nacimiento"]
    assert page.value(f"{FORM} [name=country]") == "MX"
    assert page.value(f"{FORM} [name=marcacion]") == "MX"
    assert page.js(f"document.querySelector('{FORM} [name=marcacion]').selectedOptions[0].textContent") == "+52 México"
    assert page.js("document.querySelector('footer.pie') && document.querySelector('footer.pie').children.length > 0") is True


def test_the_country_list_has_every_country_with_mexico_first_and_in_spanish(page, site):
    go(page, site)

    names = page.js(f"Array.from(document.querySelectorAll('{FORM} [name=country] option')).map(o => o.textContent)")
    assert len(names) == 247
    assert names[0] == "México"
    assert "Estados Unidos" in names and "España" in names and "Alemania" in names
    # Los demás, en orden alfabético del español, como lo ordena el propio navegador.
    assert page.js(
        f"(() => {{ const n = Array.from(document.querySelectorAll('{FORM} [name=country] option')).slice(1).map(o => o.textContent); "
        "return JSON.stringify(n) === JSON.stringify([...n].sort((a, b) => a.localeCompare(b, 'es'))); })()"
    ) is True


def test_the_phone_code_list_has_the_countries_with_a_dial_code(page, site):
    go(page, site)

    options = page.js(f"Array.from(document.querySelectorAll('{FORM} [name=marcacion] option')).map(o => o.textContent)")
    assert len(options) == 242
    assert options[0] == "+52 México"
    assert "+1 Estados Unidos" in options and "+34 España" in options and "+57 Colombia" in options
    assert not any("Antártida" in option for option in options)


def test_every_field_has_a_visible_label_and_the_password_rules_are_written(page, site):
    go(page, site)

    unlabeled = page.js(
        "Array.from(document.querySelectorAll('#formulario-registro input, #formulario-registro select'))"
        ".filter(e => !(e.labels && e.labels.length) && !e.getAttribute('aria-label')).map(e => e.name)"
    )
    assert unlabeled == []
    assert page.text("#registro-ayuda-contrasena") == "De 10 a 20 caracteres, con mayúscula, minúscula, número y símbolo, sin espacios."


def test_the_birth_date_cannot_be_in_the_future(page, site):
    go(page, site)

    assert page.js(f"document.querySelector('{FORM} [name=birth_date]').max") == date.today().isoformat()
    assert page.js(f"document.querySelector('{FORM} [name=birth_date]').min") == "1900-01-01"


# --- Caso 2 ------------------------------------------------------------------------


def test_the_indicator_follows_what_is_typed(page, site):
    go(page, site)
    assert page.js(LEVEL) == "" and page.js(FILLED) == 0

    page.type(f"{FORM} [name=password]", "abc")
    page.expect(f"{LEVEL} === 'Bajo'")
    assert page.js(FILLED) == 1
    assert page.js("document.querySelector('[data-fortaleza]').getAttribute('data-nivel')") == "bajo"
    assert "La contraseña debe tener al menos 10 caracteres." in page.js(TIPS)

    page.type(f"{FORM} [name=password]", "Ejemplo-2026")
    page.expect(f"{LEVEL} === 'Medio'")
    assert page.js(FILLED) == 2
    assert page.js(TIPS) == ["Usa dos símbolos distintos para subir un nivel."]

    page.type(f"{FORM} [name=password]", "Lluvia-Verde-26")
    page.expect(f"{LEVEL} === 'Confiable'")
    assert page.js(FILLED) == 3

    page.type(f"{FORM} [name=password]", "Lluvia#Verde!26")
    page.expect(f"{LEVEL} === 'Muy confiable'")
    assert page.js(FILLED) == 4
    assert page.js(TIPS) == []
    assert page.js("document.querySelector('[data-fortaleza]').getAttribute('data-nivel')") == "muy-confiable"


def test_the_indicator_goes_blank_when_the_password_is_erased(page, site):
    go(page, site)
    page.type(f"{FORM} [name=password]", "Ejemplo-2026")
    page.expect(f"{LEVEL} === 'Medio'")

    page.clear(f"{FORM} [name=password]")
    page.expect(f"{LEVEL} === ''")

    assert page.js(FILLED) == 0
    assert page.js(TIPS) == []


def test_the_indicator_uses_the_name_and_the_email_to_warn_about_personal_data(page, site):
    go(page, site)
    page.type(f"{FORM} [name=first_name]", "Ana")
    page.type(f"{FORM} [name=last_name]", "Torres")

    page.type(f"{FORM} [name=password]", "Ana-Torres-2026!")
    page.expect(f"{LEVEL} === 'Confiable'")

    assert "No uses tu nombre ni tu correo." in page.js(TIPS)


def test_the_indicator_ignores_a_late_answer(page, site):
    """Escribir rápido no deja un indicador de una contraseña anterior."""
    go(page, site)
    page.type(f"{FORM} [name=password]", "abc")
    page.type(f"{FORM} [name=password]", "Lluvia#Verde!26")

    page.expect(f"{LEVEL} === 'Muy confiable'")
    page.js("new Promise(r => setTimeout(() => r(1), 800))")

    assert page.js(LEVEL) == "Muy confiable"


# --- Caso 3 ------------------------------------------------------------------------


def test_an_empty_form_warns_in_every_field_and_asks_nothing_from_the_api(page, site):
    go(page, site)
    before = page.requests()

    page.click(f"{FORM} button[type=submit]")

    assert field_errors(page) == {
        "first_name": ["Escribe tu nombre."],
        "last_name": ["Escribe tus apellidos."],
        "email": ["Escribe tu correo electrónico."],
        "password": ["Escribe tu contraseña."],
        "phone": ["Escribe tu número de teléfono."],
        "birth_date": ["Escribe tu fecha de nacimiento."],
    }
    assert page.requests() == before
    assert step(page) == "datos"
    assert page.js("document.activeElement.name") == "first_name"
    assert page.js(f"document.querySelectorAll('{FORM} .campo.con-error').length") == 6


def test_a_badly_written_email_and_phone_are_warned_before_asking_the_api(page, site):
    go(page, site)
    data = person(email="ana-sin-arroba", number="55 abcd 5678")
    fill(page, data)
    before = page.requests()

    page.click(f"{FORM} button[type=submit]")

    assert field_errors(page) == {
        "email": ["El correo electrónico no tiene un formato válido."],
        "phone": ["El teléfono solo puede llevar números, espacios, guiones y paréntesis."],
    }
    assert page.requests() == before
    assert page.js("document.activeElement.name") == "email"


def test_a_phone_with_the_plus_sign_is_told_to_use_the_list(page, site):
    go(page, site)
    fill(page, person(number="+52 55 1234 5678"))

    page.click(f"{FORM} button[type=submit]")

    assert field_errors(page) == {"phone": ["Escribe el número sin el código del país; el código se elige en la lista."]}


def test_the_notices_go_away_when_the_form_is_sent_again(page, site):
    go(page, site)
    page.click(f"{FORM} button[type=submit]")
    assert field_errors(page)

    fill(page, person(password="abc"))
    submit(page)

    assert "first_name" not in field_errors(page) and "email" not in field_errors(page)


# --- Caso 4 ------------------------------------------------------------------------


def test_a_password_that_breaks_the_rules_is_refused_with_each_rule_and_creates_nothing(page, site):
    go(page, site)
    data = person(password="abc")
    fill(page, data)

    submit(page)

    # En el campo, una sola línea; lo que falta lo dice el indicador de debajo, ya actualizado.
    assert field_errors(page)["password"] == ["Tu contraseña aún no cumple lo que se indica abajo."]
    page.expect("document.querySelectorAll('[data-fortaleza-consejos] li').length === 4")
    tips = page.js(TIPS)
    assert "La contraseña debe tener al menos 10 caracteres." in tips
    assert "La contraseña debe tener al menos una mayúscula." in tips
    assert "La contraseña debe tener al menos un número." in tips
    assert "La contraseña debe tener al menos un símbolo." in tips
    assert step(page) == "datos"
    assert user_row(site, data["email"]) is None
    # Lo escrito se conserva: nadie vuelve a empezar por un error.
    assert page.value(f"{FORM} [name=first_name]") == "Ana"
    assert page.value(f"{FORM} [name=email]") == data["email"]
    assert page.value(f"{FORM} [name=password]") == "abc"
    assert page.js("document.activeElement.name") == "password"


def test_a_password_that_is_too_easy_to_guess_is_refused_and_says_how_to_fix_it(page, site):
    go(page, site)
    data = person(password="Kz7-1234-xY")
    fill(page, data)

    submit(page)

    assert field_errors(page)["password"] == ["Tu contraseña aún no cumple lo que se indica abajo."]
    page.expect(f"{LEVEL} === 'Bajo'")
    assert "Evita secuencias como 1234, abcd o símbolos en fila del teclado." in page.js(TIPS)
    assert user_row(site, data["email"]) is None


def test_someone_under_18_is_refused_with_the_date_of_their_country(page, site):
    today = date.today()
    seventeen = today.replace(year=today.year - 17).isoformat()
    go(page, site)
    data = person(birth_date=seventeen)
    fill(page, data)

    submit(page)

    assert field_errors(page) == {"birth_date": ["Hay que tener 18 años cumplidos para crear una cuenta."]}
    assert user_row(site, data["email"]) is None


# --- Caso 5 ------------------------------------------------------------------------


def test_good_data_creates_the_account_and_goes_to_the_code_step(page, site):
    go(page, site)
    data = person()
    fill(page, data)

    submit(page)

    assert step(page) == "codigo"
    assert notice(page) is None
    assert page.text(f"{CODE_FORM} [data-texto]") == (
        f"Te enviamos un código de 6 dígitos a {data['email']}. Escríbelo aquí para comprobar tu correo electrónico. "
        "Su vigencia es de 5 minutos."
    )
    assert page.js("document.activeElement.name") == "code"
    verified, country, phone, password_hash = user_row(site, data["email"])
    assert verified is False
    assert country == "MX"
    assert phone == "+52" + data["number"]
    # La contraseña se guardó convertida con Argon2id, nunca tal cual.
    assert password_hash.startswith("$argon2id$") and PASSWORD not in password_hash
    assert re.fullmatch(r"[0-9]{6}", site.codes.code_for(data["email"], "verify_email"))
    # La contraseña ya no queda escrita en la página, ni el indicador.
    assert page.value(f"{FORM} [name=password]") == ""
    assert page.js(LEVEL) == ""


def test_the_email_is_saved_in_lowercase_and_without_spaces(page, site):
    data = person()
    go(page, site)
    fill(page, {**data, "email": f"  {data['email'].upper()}  "})

    submit(page)

    assert step(page) == "codigo"
    assert user_row(site, data["email"]) is not None


def test_the_right_code_checks_the_email_and_leaves_the_account_ready(page, site):
    data = register_up_to_the_code(page, site)

    type_code(page, site.codes.code_for(data["email"], "verify_email"))

    assert step(page) == "listo"
    assert page.text("#registro-listo h2") == "Tu cuenta está lista"
    assert user_row(site, data["email"])[0] is True
    assert page.js("document.activeElement.hasAttribute('data-iniciar-sesion')") is True


def test_the_intro_is_only_for_the_data_step(page, site):
    data = register_up_to_the_code(page, site)

    assert page.js("document.querySelector('[data-intro]').hidden") is True
    assert page.js("getComputedStyle(document.querySelector('[data-intro]')).display") == "none"
    type_code(page, site.codes.code_for(data["email"], "verify_email"))
    assert page.js("document.querySelector('[data-intro]').hidden") is True


# --- Caso 6 ------------------------------------------------------------------------


def test_a_wrong_code_says_how_many_attempts_are_left_and_keeps_the_step(page, site):
    data = register_up_to_the_code(page, site)
    code = site.codes.code_for(data["email"], "verify_email")

    type_code(page, "000000" if code != "000000" else "111111")

    assert step(page) == "codigo"
    assert notice(page) == "El código ingresado no es correcto. Te quedan 4 intentos."
    assert user_row(site, data["email"])[0] is False
    type_code(page, code)
    assert step(page) == "listo"


def test_a_code_that_is_not_six_numbers_is_warned_without_asking_the_api(page, site):
    register_up_to_the_code(page, site)
    before = page.requests()

    page.press("Enter")
    assert notice(page) == "Escribe el código que recibiste."
    page.type(f"{CODE_FORM} [name=code]", "12ab")
    page.press("Enter")
    assert notice(page) == "El código debe constar de 6 dígitos."

    assert page.requests() == before


def test_an_expired_code_asks_for_a_new_one(page, site):
    data = register_up_to_the_code(page, site)
    code = site.codes.code_for(data["email"], "verify_email")
    age_codes(site, data["email"], 301)

    type_code(page, code)

    assert step(page) == "codigo"
    assert notice(page) == "El código venció. Solicita uno nuevo con «Enviar otro código»."


def test_asking_for_another_code_within_a_minute_says_to_wait(page, site):
    data = register_up_to_the_code(page, site)
    sent = len(site.codes.sent)

    page.click(f"{CODE_FORM} [data-reenviar]")
    page.expect("document.querySelector('[data-aviso]') && !document.querySelector('[data-aviso]').hidden")

    assert re.fullmatch(r"Espera [0-9]+ segundos? para solicitar otro código\.", notice(page))
    assert len(site.codes.sent) == sent


def test_another_code_after_a_minute_is_sent_and_works(page, site):
    data = register_up_to_the_code(page, site)
    age_codes(site, data["email"], 61)

    page.click(f"{CODE_FORM} [data-reenviar]")
    page.expect("!document.querySelector('[data-nota]').hidden")

    assert page.text(f"{CODE_FORM} [data-nota]") == f"Te enviamos un código nuevo a {data['email']}."
    assert notice(page) is None
    type_code(page, site.codes.code_for(data["email"], "verify_email"))
    assert step(page) == "listo"


# --- Caso 7 ------------------------------------------------------------------------


def test_an_email_that_already_has_an_account_is_warned_and_offers_to_sign_in(page, site):
    existing = make_account(site)
    go(page, site)
    fill(page, person(email=existing["email"]))

    submit(page)

    assert field_errors(page)["email"][0] == "Ya existe una cuenta con este correo."
    assert step(page) == "datos"
    assert page.count(f"{FORM} [data-enlace-sesion]") == 1
    page.click(f"{FORM} [data-enlace-sesion]")
    page.expect("!document.getElementById('ventana-entrar').hidden")
    assert page.text("#ventana-entrar h2") == "Iniciar sesión"


def test_a_phone_that_already_has_an_account_is_warned_in_its_field(page, site):
    existing = make_account(site)
    go(page, site)
    fill(page, person(number=existing["phone"][3:]))

    submit(page)

    assert field_errors(page) == {"phone": ["Ya existe una cuenta con este teléfono."]}
    assert page.count(f"{FORM} [data-enlace-sesion]") == 0


def test_the_sign_in_offer_goes_away_when_the_email_is_fixed(page, site):
    existing = make_account(site)
    go(page, site)
    fill(page, person(email=existing["email"]))
    submit(page)
    assert page.count(f"{FORM} [data-enlace-sesion]") == 1

    page.type(f"{FORM} [name=email]", person()["email"])
    submit(page)

    assert page.count(f"{FORM} [data-enlace-sesion]") == 0
    assert step(page) == "codigo"


# --- Caso 8 ------------------------------------------------------------------------


def test_the_phone_is_saved_with_the_chosen_code(page, site):
    go(page, site)
    data = person(country="US", number="212555" + str(int(uuid.uuid4().hex[:6], 16) % 10**4).zfill(4))
    fill(page, data)
    # Al elegir Estados Unidos como país, el código del teléfono pasó a ser el suyo.
    assert page.value(f"{FORM} [name=marcacion]") == "US"

    submit(page)

    assert step(page) == "codigo", (field_errors(page), notice(page))
    verified, country, phone, _ = user_row(site, data["email"])
    assert (country, phone) == ("US", "+1" + data["number"])


def test_the_phone_code_follows_the_country_until_it_is_changed_by_hand(page, site):
    go(page, site)

    page.set_value(f"{FORM} [name=country]", "ES")
    assert page.value(f"{FORM} [name=marcacion]") == "ES"
    page.set_value(f"{FORM} [name=country]", "CO")
    assert page.value(f"{FORM} [name=marcacion]") == "CO"
    # Una persona de Colombia que usa un teléfono de México lo cambia a mano.
    page.set_value(f"{FORM} [name=marcacion]", "MX")
    page.set_value(f"{FORM} [name=country]", "ES")

    assert page.value(f"{FORM} [name=marcacion]") == "MX"


def test_a_country_without_a_dial_code_leaves_the_phone_code_as_it_was(page, site):
    go(page, site)

    page.set_value(f"{FORM} [name=country]", "AQ")

    assert page.value(f"{FORM} [name=marcacion]") == "MX"


def test_a_foreign_phone_with_a_different_country_code_is_saved_as_chosen(page, site):
    """Alguien que vive en México pero tiene teléfono de España."""
    go(page, site)
    data = person(number="6" + str(int(uuid.uuid4().hex[:8], 16) % 10**8).zfill(8))
    fill(page, data)
    page.set_value(f"{FORM} [name=marcacion]", "ES")

    submit(page)

    assert step(page) == "codigo", (field_errors(page), notice(page))
    verified, country, phone, _ = user_row(site, data["email"])
    assert (country, phone) == ("MX", "+34" + data["number"])


# --- Caso 9 ------------------------------------------------------------------------


def test_with_the_account_ready_iniciar_sesion_opens_the_window_and_the_person_gets_in(page, site):
    data = register_up_to_the_code(page, site)
    type_code(page, site.codes.code_for(data["email"], "verify_email"))
    assert step(page) == "listo"

    page.click("#registro-listo [data-iniciar-sesion]")
    page.expect("!document.getElementById('ventana-entrar').hidden")
    page.type("#ventana-entrar form[data-paso=correo] [name=email]", data["email"])
    page.type("#ventana-entrar form[data-paso=correo] [name=password]", PASSWORD)
    before = page.requests()
    page.press("Enter")
    page.expect(f"window.__net.started > {before}")
    page.expect("!document.querySelector('#ventana-entrar form[data-paso=codigo]').hidden")
    page.type("#ventana-entrar form[data-paso=codigo] [name=code]", site.codes.code_for(data["email"], "login"))
    page.press("Enter")
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")

    assert page.header() == ["Ana", "Cerrar sesión"]
    assert page.location() == "/registro.html"
    assert sessions_of(site, data["email"]) == (1, 1)


def test_the_link_of_the_window_goes_to_the_register_page(page, site):
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    page.click(".cuenta-entrar")
    page.expect("!document.getElementById('ventana-entrar').hidden")

    page.click("#ventana-entrar .ventana-pie a")
    page.expect("location.pathname === '/registro.html'")
    page.expect("document.documentElement.hasAttribute('data-registro-listo')")

    assert step(page) == "datos"


def test_the_link_below_the_form_opens_the_window(page, site):
    go(page, site)

    page.click(f"{FORM} [data-abrir-sesion]")
    page.expect("!document.getElementById('ventana-entrar').hidden")

    assert page.location() == "/registro.html"


# --- Caso 10 ------------------------------------------------------------------------


def test_with_a_session_the_form_is_replaced_by_a_notice(page, site):
    account = make_account(site, first_name="Beatriz")
    page.goto(f"{site.url}/index.html")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")
    page.click(".cuenta-entrar")
    page.expect("!document.getElementById('ventana-entrar').hidden")
    page.type("#ventana-entrar form[data-paso=correo] [name=email]", account["email"])
    page.type("#ventana-entrar form[data-paso=correo] [name=password]", PASSWORD)
    before = page.requests()
    page.press("Enter")
    page.expect(f"window.__net.started > {before}")
    page.expect("!document.querySelector('#ventana-entrar form[data-paso=codigo]').hidden")
    page.type("#ventana-entrar form[data-paso=codigo] [name=code]", site.codes.code_for(account["email"], "login"))
    page.press("Enter")
    page.expect("document.querySelector('[data-cuenta]').textContent.indexOf('Cerrar sesión') !== -1")

    go(page, site)

    assert page.js("document.querySelector('[data-ya-con-sesion]').textContent") == (
        "Ya iniciaste sesión como Beatriz. Para crear otra cuenta, primero cierra sesión."
    )
    assert step(page) is None
    assert page.js("document.getElementById('formulario-registro').hidden") is True


def test_without_the_server_the_form_says_so(page, site):
    """La página abierta con doble clic, sin la API."""
    page.goto((WEB / "registro.html").as_uri())
    page.expect("document.documentElement.hasAttribute('data-registro-listo')")
    fill(page, person())

    page.click(f"{FORM} button[type=submit]")
    page.expect("document.querySelector('[data-aviso]') && !document.querySelector('[data-aviso]').hidden")

    assert notice(page) == (
        "No fue posible comunicarse con el servidor de Íntegro. Inícialo y abre la página desde http://127.0.0.1:8000/."
    )
    assert step(page) == "datos"
    assert page.value(f"{FORM} [name=first_name]") == "Ana"


def test_the_form_fits_on_a_phone(page, site):
    page.set_viewport(390, 844, mobile=True)
    go(page, site)

    box = page.js(
        "(() => { const r = document.querySelector('.formulario-tarjeta').getBoundingClientRect(); return { left: r.left, right: r.right, ancho: innerWidth }; })()"
    )
    assert box["left"] >= 0 and box["right"] <= box["ancho"], box
    for selector in (f"{FORM} [name=first_name]", f"{FORM} [name=last_name]", f"{FORM} [name=numero]", f"{FORM} [name=marcacion]",
                     f"{FORM} [name=country]", f"{FORM} [name=birth_date]", f"{FORM} button[type=submit]"):
        inside = page.js(
            "(() => { const r = document.querySelector(" + repr(selector) + ").getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.width > 0; })()"
        )
        assert inside, selector
    # En celular cada campo ocupa su renglón: nombre y apellidos ya no van lado a lado.
    first, last = page.js(
        f"[document.querySelector('{FORM} [name=first_name]').getBoundingClientRect().top, document.querySelector('{FORM} [name=last_name]').getBoundingClientRect().top]"
    )
    assert last > first


def test_the_whole_registration_works_on_a_phone(page, site):
    page.set_viewport(390, 844, mobile=True)

    data = register_up_to_the_code(page, site, first_name="Diana")
    type_code(page, site.codes.code_for(data["email"], "verify_email"))

    assert step(page) == "listo"
    assert user_row(site, data["email"])[0] is True


def test_the_page_has_no_leftovers_in_the_browser_storage(page, site):
    """La contraseña no se guarda en el navegador."""
    data = register_up_to_the_code(page, site)

    assert page.js("localStorage.length") == 0 and page.js("sessionStorage.length") == 0
    assert page.js("document.cookie") == ""
    assert data["password"] not in page.js("document.documentElement.outerHTML")
