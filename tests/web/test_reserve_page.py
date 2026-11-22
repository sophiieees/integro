"""Casos de «Reservar sin sesión» que se comprueban sin navegador.

Decisión de Sophia del 20 de noviembre de 2026 (docs/diseno/vistas.md): un visitante que da clic en «Reservar» sin
sesión ve el aviso de iniciar sesión o crear su cuenta y, al terminar, vuelve a la misma propiedad con sus fechas y
sus huéspedes, guardados en la dirección de la página y no en el navegador.

La lógica se prueba con node en reservar_logica.test.js. Cómo se ve y se comporta con navegador, servidor y base está
en tests/e2e/test_reservar_e2e.py.

Se corren desde backend/ con:  python -m pytest ..\\tests\\web -v
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"
PAGE = (WEB / "propiedad.html").read_text(encoding="utf-8")
SCREEN = (WEB / "assets" / "js" / "reservar.js").read_text(encoding="utf-8")
LOGIC = (WEB / "assets" / "js" / "reservar-logica.js").read_text(encoding="utf-8")
ACCOUNT_SCREEN = (WEB / "assets" / "js" / "cuenta.js").read_text(encoding="utf-8")
ACCOUNT_LOGIC = (WEB / "assets" / "js" / "cuenta-logica.js").read_text(encoding="utf-8")
REGISTER_SCREEN = (WEB / "assets" / "js" / "registro.js").read_text(encoding="utf-8")
REGISTER_PAGE = (WEB / "registro.html").read_text(encoding="utf-8")
CSS = (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8")


def code_of(text: str) -> str:
    """El texto sin los comentarios."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_the_property_page_has_the_fields_the_address_fills_and_a_place_for_the_notice():
    for name in ("llegada", "salida", "huespedes"):
        assert f'name="{name}"' in PAGE, name
    assert '<div class="reserva-aviso" data-reserva-aviso role="status" hidden></div>' in PAGE
    assert PAGE.count("data-reserva-aviso") == 1
    assert '<button class="btn btn-primario" type="button">Reservar</button>' in PAGE


def test_the_property_page_loads_the_scripts_in_order():
    scripts = re.findall(r'<script src="assets/js/([a-z-]+)\.js"></script>', PAGE)

    assert scripts == ["datos", "app", "estructura", "cuenta-logica", "cuenta", "reservar-logica", "reservar"]


def test_the_notice_is_written_as_text_never_as_html():
    assert "p.textContent = texto;" in SCREEN
    assert 'entrar.textContent = "Iniciar sesión";' in SCREEN and 'crear.textContent = "Crear cuenta";' in SCREEN
    assert not re.search(r"innerHTML\s*=\s*[^\"'\s]", code_of(SCREEN))  # solo se vacía: innerHTML = ""
    assert "innerHTML" not in code_of(LOGIC)


def test_what_is_chosen_goes_in_the_address_and_nothing_goes_in_the_browser():
    code = code_of(SCREEN)

    assert "window.history.replaceState(null, \"\", direccion)" in code
    assert not re.search(r"localStorage|sessionStorage|document\.cookie|pushState", code)
    assert not re.search(r"console\.|fetch\(", code)


def test_the_sign_up_link_carries_the_way_back_only_through_the_logic():
    assert "crear.href = LOGICA.enlaceDeRegistro(direccion);" in SCREEN
    # La pantalla no arma esa dirección a mano ni lee ?siguiente= ella misma.
    assert "siguiente" not in code_of(SCREEN).replace("enlaceDeRegistro", "")
    assert 'registro.html?siguiente=" + encodeURIComponent(segura)' in LOGIC


def test_the_logic_works_in_the_browser_and_in_node_and_does_not_touch_the_page():
    assert 'module.exports = fabrica(require("./cuenta-logica.js"))' in LOGIC
    assert "raiz.INTEGRO_RESERVAR = fabrica(raiz.INTEGRO_CUENTA)" in LOGIC
    code = code_of(LOGIC)
    assert "document." not in code and "fetch(" not in code and "history" not in code
    assert "window." not in code.replace("typeof window", "")


def test_the_only_way_back_after_logging_in_goes_through_the_safe_address():
    """El regreso a otra página pasa siempre por siguienteSeguro: nunca se navega a lo que trae la dirección tal cual."""
    code = code_of(ACCOUNT_SCREEN)
    assignments = re.findall(r"window\.location\.href\s*=\s*([^;]+);", code)

    assert assignments == ["decision.destino"]
    assert "var decision = LOGICA.destinoTrasIniciarSesion(" in code
    assert 'new URLSearchParams(window.location.search).get("siguiente")' in code
    assert "if (!estado.sesion) return;" in code
    assert "cargarSesion().then(regresarSiHaceFalta);" in code
    assert not re.search(r"location\.(assign|replace)\(", code)


def test_the_safe_address_only_accepts_a_page_of_the_list_with_no_foreign_characters():
    assert 'var partes = /^([a-z-]+\\.html)(\\?[A-Za-z0-9_=&%.\\-]*)?(#[A-Za-z0-9_\\-]*)?$/.exec(valor);' in ACCOUNT_LOGIC
    assert "PAGINAS_DE_REGRESO.indexOf(partes[1]) === -1" in ACCOUNT_LOGIC
    assert "valor.length > 300" in ACCOUNT_LOGIC


def test_the_registration_only_tells_the_person_they_will_go_back_when_the_address_is_a_permitted_one():
    assert "window.INTEGRO_CUENTA.siguienteSeguro(" in REGISTER_SCREEN
    assert 'data-nota-siguiente hidden>Cuando inicies sesión volverás a la página donde estabas.</p>' in REGISTER_PAGE


def test_the_sessions_event_is_sent_each_time_the_session_is_read():
    assert 'document.dispatchEvent(new CustomEvent("integro:sesion", { detail: { sesion: estado.sesion } }));' in ACCOUNT_SCREEN
    assert "window.INTEGRO_SESION = { activa: function () { return estado.sesion; } };" in ACCOUNT_SCREEN


def test_the_notice_is_styled_with_the_palette():
    assert ".reserva-aviso {" in CSS and ".reserva-aviso[hidden] { display: none; }" in CSS
    block = CSS[CSS.index(".reserva-aviso {"):CSS.index(".ventana-olvido {")]
    assert "var(--color-primario-suave)" in block and "var(--color-acento)" in block
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", block)  # solo los colores de la paleta, por sus nombres
