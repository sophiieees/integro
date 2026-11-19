"""Casos de la pieza "paleta y tipografía del manual de identidad".

Reglas del ADR 0008, decididas por Sophia el 19 de noviembre de 2026:

    1. Los tokens de estilos.css traen los colores del manual: verde íntegro
       #1F4D3A, verde noche #142A21, dorado arena #C9A66B y arena #F3EEE4.
    2. Botones: fondo verde íntegro; con el cursor encima, verde noche; al dar
       clic, dorado arena con la letra en verde noche.
    3. La palabra «Íntegro» del eslogan y el botón «Reportar un problema» van
       en dorado arena.
    4. El dorado arena nunca es color de texto.
    5. La tipografía es Outfit, guardada en el proyecto: no se pide a Google.
    6. No queda ningún color ni tipografía de la propuesta de octubre.

No usan base de datos ni navegador: leen los archivos de web/.
Se corren desde la raíz del repositorio con:  python -m pytest tests/web
"""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
# La hoja de estilos sin sus comentarios, para leer solo las reglas.
CSS = re.sub(r"/\*.*?\*/", "", (WEB / "assets" / "css" / "estilos.css").read_text(encoding="utf-8"), flags=re.S)
PAGES = sorted(WEB.glob("*.html"))

GREEN = "#1F4D3A"
NIGHT = "#142A21"
GOLD = "#C9A66B"
SAND = "#F3EEE4"
GOLD_TEXT = "#8A6A2F"


def token(name: str) -> str:
    """El valor de un token de :root."""
    root = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S).group(1)
    return re.search(rf"--{re.escape(name)}:\s*([^;]+);", root).group(1).strip()


def rule(selector: str) -> str:
    """Las declaraciones de la primera regla que nombra ese selector."""
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if selector in [part.strip() for part in selectors.split(",")]:
            return body
    raise AssertionError(f"no hay regla para {selector}")


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    """Contraste entre dos colores, como lo mide WCAG: de 1 a 21."""
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# --- Caso 1 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "name, value",
    [
        ("color-primario", GREEN),
        ("color-primario-oscuro", NIGHT),
        ("color-acento", GOLD),
        ("color-acento-texto", GOLD_TEXT),
        ("color-fondo", SAND),
        ("color-tinta", NIGHT),
        ("color-resalte", GOLD),
        ("color-superficie", "#FFFFFF"),
        ("color-pie", "#FFFFFF"),
    ],
)
def test_tokens_carry_the_colours_of_the_manual(name, value):
    assert token(name).upper() == value.upper()


def test_the_page_uses_the_tokens_for_text_and_background():
    body = rule("body")

    assert "color: var(--color-tinta)" in body
    assert "background: var(--color-fondo)" in body


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_the_browser_bar_is_green(page):
    assert f'<meta name="theme-color" content="{GREEN}">' in page.read_text(encoding="utf-8")


# --- Caso 2 ----------------------------------------------------------------


@pytest.mark.parametrize("button", [".btn-primario", ".btn-azul"])
def test_buttons_are_green_night_on_hover_and_gold_on_click(button):
    assert "background: var(--color-primario)" in rule(button)
    assert "color: #fff" in rule(button)
    assert "background: var(--color-primario-oscuro)" in rule(f"{button}:hover")
    active = rule(f"{button}:active")
    assert "background: var(--color-acento)" in active
    assert "color: var(--color-tinta)" in active


def test_the_letter_can_be_read_on_every_state_of_a_button():
    # AA pide 4.5 para texto normal.
    assert contrast("#FFFFFF", GREEN) >= 4.5
    assert contrast("#FFFFFF", NIGHT) >= 4.5
    assert contrast(NIGHT, GOLD) >= 4.5
    # La letra blanca sobre dorado no alcanza: por eso va en verde noche.
    assert contrast("#FFFFFF", GOLD) < 3


# --- Caso 3 ----------------------------------------------------------------


def test_the_word_of_the_slogan_is_gold():
    assert "color: var(--color-resalte)" in rule(".resalte")
    assert token("color-resalte").upper() == GOLD
    assert '<span class="resalte">Íntegro</span>' in (WEB / "index.html").read_text(encoding="utf-8")


def test_report_a_problem_is_gold_with_night_green_letter():
    report = rule(".btn-reportar")

    assert "background: var(--color-acento)" in report
    assert "color: var(--color-tinta)" in report
    for page in PAGES:
        assert 'class="btn btn-reportar"' in page.read_text(encoding="utf-8"), page.name


# --- Caso 4 ----------------------------------------------------------------


def test_gold_is_never_a_text_colour():
    """El dorado arena solo pinta fondos, líneas y rombos; la única letra dorada es la del eslogan, sobre la foto."""
    as_text = re.findall(r"(?<![\w-])color:\s*var\(--color-acento\)", CSS)
    literal = re.findall(rf"(?<![\w-])color:\s*{GOLD}", CSS, re.I)

    assert as_text == [] and literal == []
    assert [selectors.strip() for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS)
            if re.search(r"(?<![\w-])color:\s*var\(--color-resalte\)", body)] == [".resalte"]


def test_text_colours_can_be_read_on_the_backgrounds():
    for background in (SAND, "#FFFFFF"):
        assert contrast(NIGHT, background) >= 7
        assert contrast(token("color-tinta-suave"), background) >= 4.5
        assert contrast(GOLD_TEXT, background) >= 4.5 or background == SAND
        assert contrast(GREEN, background) >= 4.5
    # Sobre arena el dorado texto se usa en etiquetas en negritas: pide al menos 3.
    assert contrast(GOLD_TEXT, SAND) >= 3
    # Y el dorado arena como letra no alcanzaría en ningún fondo claro.
    assert contrast(GOLD, SAND) < 3 and contrast(GOLD, "#FFFFFF") < 3


def test_labels_use_the_gold_for_text_of_the_manual():
    assert "color: var(--color-acento-texto)" in rule(".etiqueta")


def test_focus_is_visible_in_green():
    assert "outline: 3px solid var(--color-primario)" in rule(":focus-visible")
    assert contrast(GREEN, SAND) >= 3


# --- Caso 5 ----------------------------------------------------------------


def test_the_typeface_is_outfit_with_the_fallbacks_of_the_manual():
    expected = '"Outfit", "Helvetica Neue", Arial, sans-serif'

    assert token("fuente-titulos") == expected
    assert token("fuente-texto") == expected
    assert "font-weight: 600" in rule("h1")


@pytest.mark.parametrize("name", ["outfit-latin.woff2", "outfit-latin-ext.woff2"])
def test_the_font_files_are_inside_the_project(name):
    font = WEB / "assets" / "fonts" / name

    assert font.is_file()
    assert font.read_bytes()[:4] == b"wOF2"
    assert f'url("../fonts/{name}")' in CSS


def test_the_font_covers_spanish():
    latin = re.search(r'outfit-latin\.woff2"\)[^}]*unicode-range:\s*([^;]+);', CSS).group(1)

    # U+0000-00FF trae á, é, í, ó, ú, ñ, ü, ¿ y ¡.
    assert "U+0000-00FF" in latin
    assert all(ord(letter) <= 0xFF for letter in "áéíóúñüÁÉÍÓÚÑÜ¿¡")


def test_the_font_has_its_licence():
    licence = (WEB / "assets" / "fonts" / "OFL.txt").read_text(encoding="utf-8")

    assert "SIL Open Font License" in licence and "Outfit" in licence


def test_nothing_is_asked_from_google_or_any_other_site():
    for file in [*PAGES, *WEB.glob("assets/css/*.css"), *WEB.glob("assets/js/*.js")]:
        text = file.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in text and "fonts.gstatic.com" not in text, file.name
        assert not re.search(r"@import\s", text), file.name
        assert not re.search(r'<link[^>]+href="https?://', text), file.name


def test_font_weight_stays_within_the_page_budget():
    """Presupuesto del MVP técnico: 400 KB la página de búsqueda. Las dos fuentes juntas no pasan de 60 KB."""
    total = sum((WEB / "assets" / "fonts" / name).stat().st_size for name in ("outfit-latin.woff2", "outfit-latin-ext.woff2"))

    assert total < 60_000


# --- Caso 6 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "old",
    ["#0F3D52", "#0A2A39", "#E3ECF1", "#1E8E5A", "#8CCDF2", "#F7F5F0", "#16232B", "#17754A", "#1F6A86",
     "Iowan Old Style", "Palatino", "Georgia", "system-ui", "Segoe UI"],
)
def test_nothing_is_left_of_the_october_proposal(old):
    for file in [*PAGES, *WEB.glob("assets/css/*.css")]:
        assert old.lower() not in file.read_text(encoding="utf-8").lower(), file.name
