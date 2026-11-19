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
# Un dato personal de menos letras daría coincidencias por casualidad: con
# tres, «Ana» aparecería dentro de «Manzana» (decisión del 19 de noviembre).
PERSONAL_DATA_MIN_LENGTH = 4

SHORT = "short"
REPEATED_CHARACTERS = "repeated_characters"
SEQUENCE = "sequence"
PERSONAL_DATA = "personal_data"
COMMON_WORD = "common_word"

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
    if any(word in text for word in COMMON_WORDS):
        weaknesses.append(COMMON_WORD)

    # Dos símbolos distintos suben un nivel, sin pasar del más alto; una
    # contraseña corta (nivel base bajo) no sube.
    raised = base
    if base > 0 and len(distinct_symbols(password)) >= VARIED_SYMBOLS:
        raised = min(base + 1, len(LEVELS) - 1)

    lowered_by = len([weakness for weakness in weaknesses if weakness != SHORT])
    level = LEVELS[max(raised - lowered_by, 0)]
    return PasswordStrength(level=level, label=LABELS[level], weaknesses=tuple(weaknesses))
