"""Reglas del formulario de registro. Funciones puras: no tocan la base.

Decisiones de Sophia del 17 de noviembre de 2026:
- Todos los datos son obligatorios: nombre, apellido, correo, contraseña,
  teléfono, país y fecha de nacimiento. El idioma es español si no se indica.
- Edad mínima: 18 años cumplidos el día del registro, con la fecha del país
  que la persona eligió, porque hay huéspedes extranjeros.
- Contraseña: de 8 a 12 caracteres, con mayúscula, minúscula, número y símbolo,
  y sin espacios. Si trae espacios se rechaza con un aviso; no se le quitan.

Los formatos son los mismos que exige la base de datos (migraciones del
grupo 1), para avisar por campo antes de intentar guardar.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from importlib import resources
from zoneinfo import ZoneInfo

MINIMUM_AGE_YEARS = 18
# La hora más adelantada del planeta (UTC+14). Se usa cuando no se sabe el país.
MOST_ADVANCED_TIME = timezone(timedelta(hours=14))
PASSWORD_MIN_LENGTH = 8
# Máximo decidido por Sophia el 17 de noviembre de 2026, al revisar la pieza.
PASSWORD_MAX_LENGTH = 12
NAME_MAX_LENGTH = 80
EMAIL_MAX_LENGTH = 254
EARLIEST_BIRTH_DATE = date(1900, 1, 1)
LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Formato internacional E.164: signo de más, código de país y número.
PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
# País de residencia, ISO 3166-1 de dos letras.
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")

REQUIRED_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "password",
    "phone",
    "country",
    "birth_date",
)


@dataclass(frozen=True)
class FieldError:
    """Un aviso para un campo del formulario."""

    field: str
    code: str
    message: str


@dataclass(frozen=True)
class RegistrationData:
    """Los datos del registro, ya revisados y en la forma en que se guardan."""

    first_name: str
    last_name: str
    email: str
    password: str
    phone: str
    country: str
    birth_date: date
    preferred_language: str


@lru_cache(maxsize=1)
def time_zones_by_country() -> dict[str, tuple[str, ...]]:
    """Husos horarios de cada país, de la tabla pública de zonas (zone.tab).

    Es la tabla que mantiene la IANA y que trae el paquete tzdata: una fila
    por zona, con el código de dos letras del país.
    """
    table = resources.files("tzdata").joinpath("zoneinfo", "zone.tab").read_text(encoding="utf-8")
    zones: dict[str, list[str]] = {}
    for line in table.splitlines():
        if line and not line.startswith("#"):
            country, _coordinates, zone = line.split("\t")[:3]
            zones.setdefault(country, []).append(zone)
    return {country: tuple(names) for country, names in zones.items()}


def today_in_country(country: str | None, now: datetime) -> date:
    """Qué fecha es hoy en el país de la persona, en ese instante.

    Hay huéspedes extranjeros: la edad se cuenta con la fecha de su país, no
    con la de México. Si el país tiene varios husos horarios se toma el más
    adelantado, para no rechazar a nadie que ya cumplió años donde vive. Si el
    país no está en la tabla se usa la hora más adelantada del planeta.
    """
    zones = time_zones_by_country().get(country or "")
    if not zones:
        return now.astimezone(MOST_ADVANCED_TIME).date()
    return max(now.astimezone(ZoneInfo(zone)).date() for zone in zones)


def is_adult(birth_date: date, today: date) -> bool:
    """Dice si ya cumplió 18 años ese día. Quien nació un 29 de febrero los
    cumple el 1 de marzo en los años que no son bisiestos."""
    try:
        eighteenth_birthday = birth_date.replace(year=birth_date.year + MINIMUM_AGE_YEARS)
    except ValueError:
        eighteenth_birthday = date(birth_date.year + MINIMUM_AGE_YEARS, 3, 1)
    return today >= eighteenth_birthday


def password_errors(password: str) -> list[FieldError]:
    """Una falta por cada regla de la contraseña que no se cumple."""
    errors = []

    def fail(code: str, message: str) -> None:
        errors.append(FieldError("password", code, message))

    if len(password) < PASSWORD_MIN_LENGTH:
        fail("too_short", f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(password) > PASSWORD_MAX_LENGTH:
        fail("too_long", f"La contraseña debe tener como máximo {PASSWORD_MAX_LENGTH} caracteres.")
    if any(character.isspace() for character in password):
        fail("has_spaces", "La contraseña no puede tener espacios.")
    if not any(character.isupper() for character in password):
        fail("missing_uppercase", "La contraseña debe tener al menos una mayúscula.")
    if not any(character.islower() for character in password):
        fail("missing_lowercase", "La contraseña debe tener al menos una minúscula.")
    if not any(character.isdigit() for character in password):
        fail("missing_digit", "La contraseña debe tener al menos un número.")
    if not any(not character.isalnum() and not character.isspace() for character in password):
        fail("missing_symbol", "La contraseña debe tener al menos un símbolo.")
    return errors


def validate_registration(raw: dict, now: datetime) -> tuple[RegistrationData | None, list[FieldError]]:
    """Revisa el formulario completo.

    now es el instante del registro, con su zona horaria; la fecha de hoy se
    saca de ahí según el país de la persona. Devuelve los datos listos para
    guardar, o None y la lista de avisos por campo. Revisa todos los campos
    aunque uno falle, para avisarlos juntos.
    """
    errors: list[FieldError] = []
    text: dict[str, str] = {}

    for field in REQUIRED_FIELDS:
        value = raw.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors.append(FieldError(field, "required", "Este dato es obligatorio."))
        elif not isinstance(value, str):
            errors.append(FieldError(field, "invalid", "Este dato debe ser un texto."))
        else:
            # La contraseña no se toca (si trae espacios se rechaza más abajo);
            # lo demás se guarda sin espacios a los lados.
            text[field] = value if field == "password" else value.strip()

    for field in ("first_name", "last_name"):
        if field in text and len(text[field]) > NAME_MAX_LENGTH:
            errors.append(
                FieldError(field, "too_long", f"Máximo {NAME_MAX_LENGTH} caracteres.")
            )

    if "email" in text:
        text["email"] = text["email"].lower()
        if len(text["email"]) > EMAIL_MAX_LENGTH or not EMAIL_PATTERN.match(text["email"]):
            errors.append(FieldError("email", "invalid", "El correo no tiene un formato válido."))

    if "password" in text:
        errors.extend(password_errors(text["password"]))

    if "phone" in text and not PHONE_PATTERN.match(text["phone"]):
        errors.append(
            FieldError(
                "phone",
                "invalid",
                "El teléfono va en formato internacional: signo de más, código de país y número.",
            )
        )

    if "country" in text:
        text["country"] = text["country"].upper()
        if not COUNTRY_PATTERN.match(text["country"]):
            errors.append(
                FieldError("country", "invalid", "El país va con su código de dos letras, como MX.")
            )

    country = text.get("country")
    today = today_in_country(country if country and COUNTRY_PATTERN.match(country) else None, now)

    birth_date = None
    if "birth_date" in text:
        try:
            birth_date = date.fromisoformat(text["birth_date"])
        except ValueError:
            errors.append(
                FieldError("birth_date", "invalid", "La fecha va como año-mes-día, por ejemplo 1995-03-14.")
            )
        else:
            if birth_date < EARLIEST_BIRTH_DATE or birth_date > today:
                errors.append(FieldError("birth_date", "invalid", "La fecha de nacimiento no es válida."))
            elif not is_adult(birth_date, today):
                errors.append(
                    FieldError(
                        "birth_date",
                        "under_age",
                        f"Hay que tener {MINIMUM_AGE_YEARS} años cumplidos para crear una cuenta.",
                    )
                )

    language = raw.get("preferred_language")
    if language is None or (isinstance(language, str) and language.strip() == ""):
        language = DEFAULT_LANGUAGE
    elif not isinstance(language, str) or language.strip().lower() not in LANGUAGES:
        errors.append(FieldError("preferred_language", "invalid", "El idioma debe ser es o en."))
    else:
        language = language.strip().lower()

    if errors:
        return None, errors
    return (
        RegistrationData(
            first_name=text["first_name"],
            last_name=text["last_name"],
            email=text["email"],
            password=text["password"],
            phone=text["phone"],
            country=text["country"],
            birth_date=birth_date,
            preferred_language=language,
        ),
        [],
    )
