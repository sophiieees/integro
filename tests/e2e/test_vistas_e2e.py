"""Casos de las vistas, de principio a fin: navegador, servidor y base de verdad.

Decisión de Sophia del 20 de noviembre de 2026: crear las vistas en el frontend y en el backend. Una vista es lo que
ve cada tipo de persona (docs/diseno/vistas.md): visitante, cliente, anfitrión y administrador. La cabecera cambia con
la vista, pero la cabecera es comodidad, no seguridad: el permiso lo da la API (tests/backend/test_view_roles.py).

    1. Visitante: barra «Todo, Alojamientos, Experiencias, Servicios», «Conviértete en anfitrión», «Iniciar sesión»
       y «Crear cuenta».
    2. Experiencias y Servicios llevan a «Próximamente», con su nombre y su pestaña marcada.
    3. Cliente: su nombre con un menú de texto (Mi cuenta, Mis reservas, Mensajes, Reseñas, Comentarios, Cerrar sesión)
       que se abre con clic y se cierra con Escape o con un clic en otra parte.
    4. «Mi cuenta» muestra los datos que la API contesta; sin sesión pide iniciar sesión y, al hacerlo, muestra el contenido.
    5. Un cliente no entra al espacio del anfitrión ni a la administración: la página lo explica y le dice a dónde ir.
    6. Anfitrión: sus funciones en la cabecera; ya no ve «Conviértete en anfitrión» ni la barra.
    7. Administrador: sus cuatro secciones; ve las vistas de cliente y de anfitrión con su propia cuenta,
       sin ser anfitrión por eso, y lo elegido se recuerda solo en esa pestaña.
    8. Cerrar sesión borra lo elegido y vuelve a la vista del visitante.

Corren contra la base `integro` de backend/.env, dentro de una transacción que se deshace al terminar el archivo.
Se corren desde backend/ con:  python -m pytest ..\\tests\\e2e -v -rs
"""

import pytest
from e2e_support import browser, make_account, make_admin, make_host, page, site  # noqa: F401
from test_entrar_e2e import log_in, open_window, send_code, send_credentials

TABS = ["Todo", "Alojamientos", "Experiencias", "Servicios"]
CLIENT_MENU = ["Mi cuenta", "Mis reservas", "Mensajes", "Reseñas", "Comentarios", "Cerrar sesión"]
HOST_BAR = ["Mis propiedades", "Reservas", "Reseñas", "Comentarios", "Chats con clientes", "Subir publicación"]
ADMIN_BAR = ["Verificaciones", "Casos", "Cargos", "Bitácora"]
VIEW_AS = ["Vista de administrador", "Ver como cliente", "Ver como anfitrión"]


def go(page, site, path="index.html"):
    page.goto(f"{site.url}/{path}")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


def arrive(page, pathname):
    page.expect(f"location.pathname === '{pathname}'")
    page.expect("document.documentElement.hasAttribute('data-cuenta-lista')")


def session(page, site, *, first_name="Ana", host=False, admin=False, path="index.html"):
    """Una persona con sesión abierta de verdad, con el inicio de sesión de dos pasos."""
    account = make_account(site, first_name=first_name)
    if host:
        make_host(site, account["email"])
    if admin:
        make_admin(site, account["email"])
    log_in(page, site, account, path)
    return account


def menu_texts(page):
    return page.js("Array.from(document.querySelectorAll('.cuenta-lista a, .cuenta-lista button')).map(e => e.textContent.trim())")


def title(page):
    """El título que se ve en la página: el primer h1 con lugar en la pantalla."""
    return page.js(
        "(() => { const h = Array.from(document.querySelectorAll('main h1')).find(h => h.getClientRects().length > 0); "
        "return h ? h.textContent : null; })()"
    )


# --- Caso 1: el visitante ---------------------------------------------------------------


def test_the_visitor_sees_the_bar_become_a_host_and_both_account_links(page, site):
    go(page, site)

    assert page.nav() == TABS
    assert page.js("document.querySelector('header .cabecera-acciones a').textContent") == "Conviértete en anfitrión"
    assert page.header() == ["Iniciar sesión", "Crear cuenta"]
    assert page.js("document.querySelector('.cuenta-menu')") is None


def test_create_account_goes_to_the_registration_page(page, site):
    go(page, site)

    page.click(".cuenta-crear")

    page.expect("location.pathname === '/registro.html'")


def test_the_alojamientos_tab_goes_to_the_results_and_gets_marked(page, site):
    go(page, site)
    assert page.current_tab() == ["Todo"]

    page.click("header [data-pestana=alojamientos]")

    page.expect("location.hash === '#resultados'")
    assert page.current_tab() == ["Alojamientos"]
    assert page.js("document.querySelector('header [data-pestana=todo]').hasAttribute('aria-current')") is False


# --- Caso 2: Próximamente ----------------------------------------------------------------


@pytest.mark.parametrize("tab, name", [("experiencias", "Experiencias"), ("servicios", "Servicios")])
def test_experiencias_and_servicios_go_to_a_coming_soon_page_with_their_name(page, site, tab, name):
    go(page, site)

    page.click(f"header [data-pestana={tab}]")

    arrive(page, "/proximamente.html")
    assert page.text("main h1") == name
    assert page.js("document.title") == f"{name} | Íntegro"
    assert page.current_tab() == [name]
    assert "todavía no está disponible" in page.text("main")
    page.click("main .btn-primario")
    page.expect("location.pathname === '/index.html' && location.hash === '#resultados'")


@pytest.mark.parametrize("query", ["", "?seccion=otra", "?seccion=%3Cb%3E", "?seccion=experiencias2"])
def test_coming_soon_with_an_unknown_section_says_proximamente_and_marks_no_tab(page, site, query):
    go(page, site, "proximamente.html" + query)

    assert page.text("main h1") == "Próximamente"
    assert page.current_tab() == []
    assert page.js("document.querySelector('main b')") is None


# --- Caso 3: el cliente y su menú -----------------------------------------------------------


def test_after_logging_in_the_header_shows_the_name_with_a_closed_menu(page, site):
    session(page, site, first_name="Beatriz")

    assert page.header() == ["Beatriz"]
    assert page.nav() == TABS
    assert page.js("document.querySelector('header .cabecera-acciones a').textContent") == "Conviértete en anfitrión"
    assert page.menu_is_open() is False
    assert page.js("document.querySelector('.cuenta-nombre').getAttribute('aria-expanded')") == "false"


def test_the_menu_opens_with_a_click_and_lists_the_client_options_ending_in_cerrar_sesion(page, site):
    session(page, site)

    page.open_menu()

    assert menu_texts(page) == CLIENT_MENU
    assert page.js("document.querySelector('.cuenta-nombre').getAttribute('aria-expanded')") == "true"
    assert page.header()[0] == "Ana" and page.header()[-1] == "Cerrar sesión"
    assert page.is_clickable(".cuenta-lista a") is True


def test_the_menu_closes_with_a_second_click_on_the_name(page, site):
    session(page, site)
    page.open_menu()

    page.click(".cuenta-nombre")

    assert page.menu_is_open() is False
    assert page.js("document.querySelector('.cuenta-nombre').getAttribute('aria-expanded')") == "false"


def test_the_menu_closes_with_escape_and_the_focus_goes_back_to_the_name(page, site):
    session(page, site)
    page.open_menu()

    page.press("Escape")

    assert page.menu_is_open() is False
    assert page.js("document.activeElement.classList.contains('cuenta-nombre')") is True


def test_the_menu_closes_with_a_click_anywhere_else(page, site):
    session(page, site)
    page.open_menu()

    page.click("main h2")

    assert page.menu_is_open() is False


def test_the_menu_stays_inside_the_screen_on_a_phone(page, site):
    page.set_viewport(390, 844, mobile=True)
    session(page, site)

    page.open_menu()

    box = page.js(
        "(() => { const r = document.querySelector('.cuenta-lista').getBoundingClientRect(); return [r.left, r.right]; })()"
    )
    assert box[0] >= 0 and box[1] <= 390
    assert page.is_clickable(".cuenta-salir") is True


def test_a_client_header_does_not_overflow_a_phone_screen(page, site):
    page.set_viewport(390, 844, mobile=True)
    session(page, site, first_name="Maria-Fernanda")

    right = page.js("Math.max(...Array.from(document.querySelectorAll('header.cabecera *')).map(e => e.getBoundingClientRect().right))")

    assert right <= 390


# --- Caso 4: Mi cuenta -----------------------------------------------------------------------


def test_my_account_shows_the_data_the_api_gives_and_the_sections_that_are_coming(page, site):
    account = session(page, site, first_name="Carolina")

    page.open_menu()
    page.click(".cuenta-lista a[href='mi-cuenta.html']")
    arrive(page, "/mi-cuenta.html")

    page.expect("document.querySelector('[data-contenido]') && !document.querySelector('[data-contenido]').hidden")
    assert title(page) == "Mi cuenta"
    assert page.text("[data-dato=nombre]") == "Carolina Torres"
    assert page.text("[data-dato=correo]") == account["email"]
    assert page.js("document.querySelector('[data-acceso]').hidden") is True
    for section in ("reservas", "mensajes", "resenas", "comentarios"):
        assert "Próximamente" in page.text(f"#{section}"), section


@pytest.mark.parametrize("item, anchor", [("Mis reservas", "reservas"), ("Mensajes", "mensajes"), ("Reseñas", "resenas"), ("Comentarios", "comentarios")])
def test_each_client_menu_item_lands_on_its_section(page, site, item, anchor):
    session(page, site)
    page.open_menu()

    page.click(f".cuenta-lista a[href='mi-cuenta.html#{anchor}']")

    arrive(page, "/mi-cuenta.html")
    assert page.js("location.hash") == f"#{anchor}"
    assert page.is_clickable(f"#{anchor} h2") is True


def test_my_account_without_a_session_asks_to_log_in_and_shows_the_content_after_doing_it(page, site):
    account = make_account(site, first_name="Diana")
    go(page, site, "mi-cuenta.html")

    assert title(page) == "Inicia sesión para continuar"
    assert page.js("document.querySelector('[data-contenido]').hidden") is True
    assert page.js("document.body.textContent.indexOf('Diana')") == -1
    page.click("[data-acceso-enlace]")
    page.expect("document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden")
    send_credentials(page, account["email"], account["password"])
    send_code(page, site.codes.code_for(account["email"], "login"))

    page.expect("!document.querySelector('[data-contenido]').hidden")
    assert page.text("[data-dato=nombre]") == "Diana Torres"
    assert page.js("document.querySelector('[data-acceso]').hidden") is True
    assert page.location() == "/mi-cuenta.html"


def test_logging_out_on_my_account_hides_the_data_again(page, site):
    session(page, site, first_name="Elena", path="mi-cuenta.html")
    page.expect("!document.querySelector('[data-contenido]').hidden")

    page.log_out()

    page.expect("document.querySelector('[data-contenido]').hidden")
    assert title(page) == "Inicia sesión para continuar"
    # Los datos no se quedan escondidos en la página: se borran al cerrar la sesión.
    assert page.text("[data-dato=nombre]") == "" and page.text("[data-dato=correo]") == ""
    assert page.js("document.body.textContent.indexOf('Elena')") == -1


# --- Caso 5: lo que un cliente no puede ver ---------------------------------------------------


def test_a_client_who_opens_the_host_space_is_told_why_and_shown_how_to_become_a_host(page, site):
    session(page, site, path="anfitrion.html")

    page.expect("!document.querySelector('[data-acceso]').hidden")
    assert title(page) == "Esta sección es para anfitriones"
    assert page.js("document.querySelector('[data-contenido]').hidden") is True
    assert page.js("document.querySelector('[data-acceso-enlace]').getAttribute('href')") == "anfitriones.html"
    assert page.text("[data-acceso-enlace]") == "Conviértete en anfitrión"
    assert page.js("document.querySelector('main').innerText.indexOf('Mis propiedades')") == -1


def test_a_client_who_opens_the_administration_is_told_it_is_for_the_team(page, site):
    session(page, site, path="administracion.html")

    page.expect("!document.querySelector('[data-acceso]').hidden")
    assert title(page) == "Esta sección es solo para el equipo de Íntegro"
    assert page.js("document.querySelector('[data-contenido]').hidden") is True
    assert page.js("document.querySelector('main').innerText.indexOf('Verificaciones')") == -1
    assert page.js("document.querySelector('[data-acceso-enlace]').getAttribute('href')") == "index.html"


def test_a_host_who_opens_the_administration_is_told_the_same(page, site):
    session(page, site, host=True, path="administracion.html")

    page.expect("!document.querySelector('[data-acceso]').hidden")
    assert title(page) == "Esta sección es solo para el equipo de Íntegro"


@pytest.mark.parametrize("path", ["anfitrion.html", "administracion.html"])
def test_a_visitor_who_opens_a_protected_page_is_asked_to_log_in(page, site, path):
    go(page, site, path)

    assert title(page) == "Inicia sesión para continuar"
    assert page.js("document.querySelector('[data-contenido]').hidden") is True
    assert page.js("document.querySelector('[data-acceso-enlace]').textContent") == "Iniciar sesión"


def test_the_pages_of_the_other_views_do_not_open_by_changing_the_hash_or_the_address(page, site):
    """Una dirección con ancla (anfitrion.html#propiedades) tampoco da lo que la página protege."""
    session(page, site, path="anfitrion.html#propiedades")

    page.expect("!document.querySelector('[data-acceso]').hidden")
    assert page.js("document.querySelector('[data-contenido]').hidden") is True


# --- Caso 6: el anfitrión ----------------------------------------------------------------------


def test_a_host_sees_their_functions_and_no_longer_the_bar_or_become_a_host(page, site):
    session(page, site, host=True)

    assert page.nav() == HOST_BAR
    links = page.js("Array.from(document.querySelectorAll('header.cabecera a, header.cabecera button')).map(e => e.textContent.trim())")
    assert "Conviértete en anfitrión" not in links
    assert "Todo" not in links and "Experiencias" not in links
    assert page.header() == ["Ana"]


def test_the_host_menu_keeps_their_account_their_trips_and_the_search(page, site):
    session(page, site, host=True)

    page.open_menu()

    assert menu_texts(page) == ["Mi cuenta", "Mis reservas", "Buscar hospedaje", "Cerrar sesión"]
    assert page.js("document.querySelector('.cuenta-nota')") is None


def test_the_host_header_links_land_on_the_host_space_sections(page, site):
    session(page, site, host=True)

    page.click("header .enlaces-cabecera a[href='anfitrion.html#resenas']")

    arrive(page, "/anfitrion.html")
    page.expect("!document.querySelector('[data-contenido]').hidden")
    assert title(page) == "Tu espacio de anfitrión"
    assert "responder con un agradecimiento o una disculpa" in page.text("#resenas")
    assert page.js("location.hash") == "#resenas"


def test_a_host_sees_all_six_sections(page, site):
    session(page, site, host=True, path="anfitrion.html")

    page.expect("!document.querySelector('[data-contenido]').hidden")

    assert page.js("Array.from(document.querySelectorAll('[data-contenido] h2')).map(h => h.textContent)") == [
        "Mis propiedades", "Reservas", "Reseñas", "Comentarios", "Chats con clientes", "Subir publicación",
    ]


def test_becoming_a_host_changes_the_header_on_the_next_load_without_logging_in_again(page, site):
    account = session(page, site)
    assert page.nav() == TABS

    make_host(site, account["email"])
    go(page, site)

    assert page.nav() == HOST_BAR


# --- Caso 7: el administrador -------------------------------------------------------------------


def test_an_admin_sees_the_four_sections_and_can_choose_which_view_to_look_at(page, site):
    session(page, site, admin=True)

    assert page.nav() == ADMIN_BAR
    page.open_menu()
    assert menu_texts(page) == [*VIEW_AS, "Mi cuenta", "Cerrar sesión"]
    assert page.js("Array.from(document.querySelectorAll('.cuenta-lista [aria-current=true]')).map(a => a.textContent)") == ["Vista de administrador"]


def test_an_admin_opens_the_administration_page_with_its_own_account(page, site):
    session(page, site, admin=True, path="administracion.html")

    page.expect("!document.querySelector('[data-contenido]').hidden")

    assert title(page) == "Administración"
    assert page.js("Array.from(document.querySelectorAll('[data-contenido] h2')).map(h => h.textContent)") == [
        "Verificaciones", "Casos", "Cargos", "Bitácora",
    ]


def test_an_admin_looks_at_the_client_view_with_their_own_account_and_it_is_remembered_in_the_tab(page, site):
    session(page, site, admin=True)
    page.open_menu()

    page.click(".cuenta-lista a[data-ver-como=cliente]")

    arrive(page, "/index.html")
    assert page.nav() == TABS
    assert page.js("document.querySelector('.cuenta-nota').textContent") == "Viendo como cliente"
    page.open_menu()
    assert menu_texts(page) == [*VIEW_AS, "Mi cuenta", "Mis reservas", "Mensajes", "Reseñas", "Comentarios", "Cerrar sesión"]
    assert page.js("Array.from(document.querySelectorAll('.cuenta-lista [aria-current=true]')).map(a => a.textContent)") == ["Ver como cliente"]
    # Recargar en la misma pestaña conserva lo elegido.
    go(page, site, "propiedad.html?id=2")
    assert page.nav() == TABS


def test_an_admin_looks_at_the_host_view_without_being_a_host(page, site):
    session(page, site, admin=True)
    page.open_menu()

    page.click(".cuenta-lista a[data-ver-como=anfitrion]")

    arrive(page, "/anfitrion.html")
    page.expect("!document.querySelector('[data-contenido]').hidden")
    assert page.nav() == HOST_BAR
    assert page.js("document.querySelector('.cuenta-nota').textContent") == "Viendo como anfitrión"
    # Ver la vista no le dio perfil de anfitrión: la API sigue sin tratarla como anfitriona.
    assert page.js("fetch('/api/v1/auth/me').then(r => r.json()).then(b => [b.is_host, b.is_admin])") == [False, True]


def test_the_admin_goes_back_to_their_own_view_from_the_menu(page, site):
    session(page, site, admin=True)
    page.open_menu()
    page.click(".cuenta-lista a[data-ver-como=cliente]")
    arrive(page, "/index.html")
    page.open_menu()

    page.click(".cuenta-lista a[data-ver-como=administrador]")

    arrive(page, "/administracion.html")
    assert page.nav() == ADMIN_BAR
    assert page.js("document.querySelector('.cuenta-nota')") is None


def test_a_new_tab_starts_with_the_admin_view_again(page, site):
    """Lo elegido vive solo en la pestaña (sessionStorage): otra pestaña del mismo navegador empieza en administrador."""
    session(page, site, admin=True)
    page.open_menu()
    page.click(".cuenta-lista a[data-ver-como=cliente]")
    arrive(page, "/index.html")
    assert page.nav() == TABS
    cookies = page.send("Network.getCookies", urls=[site.url])["cookies"]
    other = page.browser.new_page()
    try:
        for cookie in cookies:
            other.send("Network.setCookie", name=cookie["name"], value=cookie["value"], url=site.url)
        go(other, site)
        assert other.nav() == ADMIN_BAR
    finally:
        other.close()


def test_a_value_left_in_the_tab_does_nothing_for_someone_who_is_not_an_admin(page, site):
    session(page, site)
    page.js("sessionStorage.setItem('integro_view_as', 'anfitrion'); 1")

    go(page, site)

    assert page.nav() == TABS
    assert page.js("sessionStorage.getItem('integro_view_as')") is None
    assert page.js("document.querySelector('.cuenta-nota')") is None


def test_an_unknown_value_in_the_tab_leaves_the_admin_in_their_own_view(page, site):
    session(page, site, admin=True)
    page.js("sessionStorage.setItem('integro_view_as', 'administrador'); 1")
    go(page, site)
    assert page.nav() == ADMIN_BAR

    page.js("sessionStorage.setItem('integro_view_as', '<img src=x>'); 1")
    go(page, site)

    assert page.nav() == ADMIN_BAR
    assert page.js("document.querySelector('img[src=x]')") is None


# --- Caso 8: cerrar sesión ---------------------------------------------------------------------


def test_logging_out_forgets_the_view_the_admin_chose_and_goes_back_to_the_visitor_header(page, site):
    session(page, site, admin=True)
    page.open_menu()
    page.click(".cuenta-lista a[data-ver-como=cliente]")
    arrive(page, "/index.html")

    page.log_out()

    page.expect("document.querySelector('.cuenta-entrar') !== null")
    assert page.nav() == TABS
    assert page.header() == ["Iniciar sesión", "Crear cuenta"]
    assert page.js("sessionStorage.getItem('integro_view_as')") is None


def test_logging_out_from_the_host_view_goes_back_to_the_visitor_bar(page, site):
    session(page, site, host=True)
    assert page.nav() == HOST_BAR

    page.log_out()

    page.expect("document.querySelector('.cuenta-entrar') !== null")
    assert page.nav() == TABS
    assert page.js("document.querySelector('header .cabecera-acciones a').textContent") == "Conviértete en anfitrión"


def test_the_login_window_still_opens_from_the_new_header(page, site):
    account = make_account(site)
    go(page, site)

    open_window(page)
    send_credentials(page, account["email"], account["password"])

    assert page.step() == "codigo"
