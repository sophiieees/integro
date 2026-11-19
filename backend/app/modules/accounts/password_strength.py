"""Qué tan confiable es una contraseña. Funciones puras: no tocan la base.

Decisiones de Sophia del 19 de noviembre de 2026:

- Cuatro niveles: bajo, medio, confiable y muy confiable.
- El largo da el nivel base, dos símbolos distintos lo suben un nivel y cada
  debilidad lo baja un nivel, nunca por debajo de bajo.
- Para registrarse hace falta al menos el nivel medio.

    Largo             Nivel base
    hasta 9           bajo
    10 a 12           medio
    13 a 15           confiable
    16 o más          muy confiable

La cuenta, en este orden:

    1. nivel base por el largo;
    2. si trae dos símbolos distintos o más (por ejemplo - y !), sube un nivel,
       sin pasar de muy confiable. Dos veces el mismo símbolo no cuenta, y una
       contraseña de menos de 10 caracteres no sube;
    3. cada debilidad baja un nivel.

Además de lo que resta (weaknesses y hints), el resultado dice lo que suma:
strengths trae "varied_symbols" cuando los dos símbolos ya le subieron el
nivel, y raise_hints trae el consejo de usarlos cuando todavía puede subir.
Con 16 caracteres o más no hay nivel al que subir y las dos van vacías.

Debilidades (cada tipo cuenta una vez):

    repeated_characters   tres caracteres iguales seguidos: aaa, 111
    sequence              cuatro seguidos en orden: 1234, abcd, 4321, qwer, y
                          también símbolos en fila en el teclado: !"#$, $%&/
    personal_data         contiene su nombre, su apellido o su correo, en
                          palabras de cuatro letras o más
    common_word           contiene una palabra de la lista de palabras comunes:
                          la que propuso la IA más la que dio Sophia
                          (password, qwerty, 1234, gato, admin...)

Las mayúsculas y los acentos no cuentan: "Contraseña" y "contrasena" son la
misma palabra.

Una entrada de la lista puede coincidir con otra debilidad: "1234" es a la vez
secuencia y palabra común, y entonces baja dos niveles.

"yo" solo cuenta como palabra suelta, sin otra letra pegada: baja el nivel en
"Yo-Kz7-Xv9" pero no en "Mayo-Kz7-Xv9". Las demás palabras de la lista se
buscan en cualquier parte.
"""

import re
import unicodedata
from dataclasses import dataclass

LEVELS = ("low", "medium", "reliable", "very_reliable")
LABELS = {"low": "Bajo", "medium": "Medio", "reliable": "Confiable", "very_reliable": "Muy confiable"}
# Nivel mínimo para poder registrarse.
MINIMUM_LEVEL = "medium"

# (largo mínimo, nivel base), del más alto al más bajo.
LENGTH_LEVELS = ((16, 3), (13, 2), (10, 1), (0, 0))

REPEAT_LENGTH = 3
SEQUENCE_LENGTH = 4
# Filas donde se buscan los caracteres seguidos: números, abecedario, teclado
# y, desde el 19 de noviembre, los símbolos de la fila de los números (teclado
# en español de Latinoamérica y teclado en inglés).
SEQUENCE_ROWS = (
    "0123456789",
    "abcdefghijklmnopqrstuvwxyz",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    '!"#$%&/()=?',
    "!@#$%^&*()",
)
# Cuántos símbolos distintos hacen falta para subir un nivel.
VARIED_SYMBOLS = 2
# Palabras comunes. Decisión de Sophia del 19 de noviembre de 2026: «complementa
# tu lista con la mía». Son dos listas que se suman: la que propuso la IA al
# construir el indicador y la que dio Sophia, tal como la escribió. Se comparan
# sin mayúsculas ni acentos (COMMON_WORDS, más abajo), así que "admin" y
# "ADMIN" son la misma, y una palabra que está en las dos cuenta una vez.
COMMON_WORDS_FROM_AI = (
    "password", "contraseña", "íntegro", "qwerty", "admin", "bienvenido", "welcome", "letmein",
)
COMMON_WORDS_FROM_SOPHIA = (
    "1234", "gato", "yo", "perro", "cuenta2026", "123456", "111111", "000000", "123123",
    "123456789", "admin", "password", "contraseña", "Pass@123", "1234567890", "abcd1234", "ADMIN",
)
# Palabras de la lista que solo cuentan como palabra suelta, es decir, sin otra
# letra pegada antes ni después. Decisión de Sophia del 19 de noviembre de
# 2026, para que «yo» no castigue a «mayo» ni a «apoyo».
WHOLE_WORD_ONLY = ("yo",)
# Un dato personal de menos letras daría coincidencias por casualidad: con
# tres, «Ana» aparecería dentro de «Manzana» (decisión del 19 de noviembre).
PERSONAL_DATA_MIN_LENGTH = 4

SHORT = "short"
REPEATED_CHARACTERS = "repeated_characters"
SEQUENCE = "sequence"
PERSONAL_DATA = "personal_data"
COMMON_WORD = "common_word"

# Lo que suma: lo que ya subió el nivel de la contraseña.
VARIED_SYMBOLS_STRENGTH = "varied_symbols"
# Lo que sumaría: se dice cuando todavía puede subir un nivel con símbolos.
VARIED_SYMBOLS_RAISE_HINT = "Usa dos símbolos distintos para subir un nivel."

HINTS = {
    SHORT: "Usa al menos 10 caracteres.",
    REPEATED_CHARACTERS: "Evita repetir el mismo carácter tres veces seguidas.",
    SEQUENCE: "Evita secuencias como 1234 o abcd.",
    PERSONAL_DATA: "No uses tu nombre ni tu correo.",
    COMMON_WORD: "Evita palabras muy comunes.",
}


@dataclass(frozen=True)
class PasswordStrength:
    level: str
    label: str
    # Por qué no sale más alta, en el orden en que se revisa. SHORT no baja el
    # nivel: explica que el largo no da para más que bajo.
    weaknesses: tuple[str, ...]
    # Lo que suma (decisión de Sophia del 19 de noviembre de 2026): strengths
    # es lo que ya le subió el nivel y raise_hints, cómo subirlo todavía.
    strengths: tuple[str, ...] = ()
    raise_hints: tuple[str, ...] = ()

    @property
    def is_enough(self) -> bool:
        """Dice si alcanza para registrarse."""
        return LEVELS.index(self.level) >= LEVELS.index(MINIMUM_LEVEL)

    @property
    def hints(self) -> tuple[str, ...]:
        return tuple(HINTS[weakness] for weakness in self.weaknesses)


def plain(text: str) -> str:
    """En minúsculas y sin acentos, para comparar."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


# Las dos listas juntas, ya en la forma en que se comparan y sin entradas repetidas.
COMMON_WORDS = tuple(
    dict.fromkeys(plain(word) for word in (*COMMON_WORDS_FROM_AI, *COMMON_WORDS_FROM_SOPHIA))
)


def has_repeated_characters(password: str) -> bool:
    return re.search(r"(.)\1{%d}" % (REPEAT_LENGTH - 1), password) is not None


def has_sequence(password: str) -> bool:
    for row in SEQUENCE_ROWS:
        for direction in (row, row[::-1]):
            for start in range(len(direction) - SEQUENCE_LENGTH + 1):
                if direction[start : start + SEQUENCE_LENGTH] in password:
                    return True
    return False


def stands_alone(word: str, text: str) -> bool:
    """Dice si la palabra aparece suelta: sin una letra pegada antes ni después.

    Un número o un símbolo al lado no la esconden: en "yo2026" y en "mi-yo-9"
    está suelta; en "mayo" y en "yoga" no."""
    start = text.find(word)
    while start != -1:
        end = start + len(word)
        letter_before = start > 0 and text[start - 1].isalpha()
        letter_after = end < len(text) and text[end].isalpha()
        if not letter_before and not letter_after:
            return True
        start = text.find(word, start + 1)
    return False


def has_common_word(text: str) -> bool:
    """Dice si trae una palabra de la lista. text ya viene sin mayúsculas ni acentos."""
    for word in COMMON_WORDS:
        if word in WHOLE_WORD_ONLY:
            if stands_alone(word, text):
                return True
        elif word in text:
            return True
    return False


def distinct_symbols(password: str) -> set[str]:
    """Los símbolos distintos que trae: lo que no es letra, número ni espacio."""
    return {character for character in password if not character.isalnum() and not character.isspace()}


def personal_words(first_name: str | None, last_name: str | None, email: str | None) -> set[str]:
    """Las palabras de su nombre, su apellido y lo que va antes de la arroba en su correo."""
    pieces = [first_name or "", last_name or "", (email or "").split("@")[0]]
    words = set()
    for piece in pieces:
        for word in re.split(r"[^a-z0-9]+", plain(piece)):
            if len(word) >= PERSONAL_DATA_MIN_LENGTH:
                words.add(word)
    return words


def password_strength(
    password: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> PasswordStrength:
    """Califica una contraseña. No revisa las reglas de formato: eso lo hace el registro."""
    text = plain(password)
    base = next(level for minimum, level in LENGTH_LEVELS if len(password) >= minimum)

    weaknesses = [SHORT] if base == 0 else []
    if has_repeated_characters(text):
        weaknesses.append(REPEATED_CHARACTERS)
    if has_sequence(text):
        weaknesses.append(SEQUENCE)
    if any(word in text for word in personal_words(first_name, last_name, email)):
        weaknesses.append(PERSONAL_DATA)
    if has_common_word(text):
        weaknesses.append(COMMON_WORD)

    # Dos símbolos distintos suben un nivel, sin pasar del más alto; una
    # contraseña corta (nivel base bajo) no sube.
    # Solo se dice lo que suma cuando de verdad hay un nivel al que subir: con
    # 16 caracteres o más ya está en el más alto.
    raised = base
    strengths = []
    raise_hints = []
    if 0 < base < len(LEVELS) - 1:
        if len(distinct_symbols(password)) >= VARIED_SYMBOLS:
            raised = base + 1
            strengths.append(VARIED_SYMBOLS_STRENGTH)
        else:
            raise_hints.append(VARIED_SYMBOLS_RAISE_HINT)

    lowered_by = len([weakness for weakness in weaknesses if weakness != SHORT])
    level = LEVELS[max(raised - lowered_by, 0)]
    return PasswordStrength(
        level=level,
        label=LABELS[level],
        weaknesses=tuple(weaknesses),
        strengths=tuple(strengths),
        raise_hints=tuple(raise_hints),
    )
