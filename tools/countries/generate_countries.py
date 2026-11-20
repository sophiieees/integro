"""Genera web/assets/js/paises.js: los países de la lista de registro y su código de marcación.

Los países son los que la API conoce: los de la tabla pública de zonas horarias (zone.tab, del paquete tzdata
de backend/requirements.txt), la misma con la que cuenta la edad según el país (backend/app/modules/accounts/validation.py).
Los códigos de marcación (+52, +1...) salen de la librería phonenumbers, la versión de libphonenumber de Google.
Los nombres no se guardan: el navegador los da en español con Intl.DisplayNames.

phonenumbers no es una dependencia del proyecto: solo hace falta para volver a generar el archivo. Se instala aparte,
en una versión publicada hace más de 14 días (arquitectura.md, sección 7, punto 9):

    pip install phonenumbers==9.0.42

Uso, desde la raíz del repositorio y con el entorno del backend activo:

    python tools/countries/generate_countries.py
"""

import importlib.resources as resources
from pathlib import Path

import phonenumbers

DESTINO = Path(__file__).resolve().parents[2] / "web" / "assets" / "js" / "paises.js"


def countries() -> list[str]:
    """Los países de zone.tab, con su código de dos letras, en orden."""
    table = resources.files("tzdata").joinpath("zoneinfo", "zone.tab").read_text(encoding="utf-8")
    return sorted({line.split("\t")[0] for line in table.splitlines() if line and not line.startswith("#")})


def main() -> None:
    rows = []
    for code in countries():
        # 0 es un país sin código de marcación (la Antártida, por ejemplo): sale en la lista de países de
        # residencia, no en la de códigos del teléfono.
        rows.append(f'["{code}", {phonenumbers.country_code_for_region(code)}]')
    body = ",\n      ".join(rows)
    DESTINO.write_text(
        f"""/* Íntegro, los países de la lista de registro y su código de marcación
   -------------------------------------------------------------------
   Archivo generado por tools/countries/generate_countries.py: no se edita a mano.
   Cada país es [código de dos letras, código de marcación]; 0 si no tiene.
   Los países son los que conoce la API; los códigos, de phonenumbers {phonenumbers.__version__}.
   Los nombres los da el navegador, en español, con Intl.DisplayNames.
*/
(function (raiz, fabrica) {{
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.INTEGRO_PAISES = fabrica();
}})(typeof window !== "undefined" ? window : this, function () {{
  "use strict";
  return {{
    PRIMERO: "MX",
    PAISES: [
      {body}
    ]
  }};
}});
""",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(rows)} países escritos en {DESTINO}")


if __name__ == "__main__":
    main()
