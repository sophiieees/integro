# -*- coding: utf-8 -*-
"""Regenera la sección 2.0 de PROMPT_LOG.md a partir de bitacora_datos.py (entre los marcadores)."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bitacora_datos import PROMPTS, NOTA_TRANSPARENCIA  # noqa: E402

RUTA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "PROMPT_LOG.md"))
INICIO = "<!-- bitacora:inicio (sección generada desde bitacora_datos.py; editar ahí) -->"
FIN = "<!-- bitacora:fin -->"


def md_celda(texto):
    return (texto or "").replace("|", "\\|").replace("\n", " ")


def render():
    out = []
    out.append("### 2.0 Prompts y decisiones de la construcción del prototipo (18 de octubre de 2026)")
    out.append("")
    out.append(NOTA_TRANSPARENCIA + " Estas decisiones son anteriores a la función del assignment, pero son reales y están en este repositorio; muestran el patrón que pide el nivel 5: propuesta de la IA, revisión de Sophia, veredicto con razón. Las entradas marcadas \"Pendiente\" esperan el veredicto de Sophia.")
    out.append("")
    for p in PROMPTS:
        out.append("#### Prompt %d: %s (%s)" % (p["n"], p["titulo"], p["fecha"]))
        out.append("")
        out.append("**Rol.** " + p["rol"])
        out.append("")
        out.append("**Tarea.** " + p["tarea"])
        out.append("")
        out.append("**Contexto.** " + p["contexto"])
        out.append("")
        out.append("**Salida esperada.** " + p["salida"])
        out.append("")
        r = p["respuesta"]
        out.append("**Respuesta de la IA**")
        out.append("")
        out.append("- Fecha: " + r["fecha"] + ". Commits: " + r["commits"] + ".")
        out.append("- Carpetas y archivos, y por qué:")
        for ruta, porque in r["archivos"]:
            out.append("  - `%s`: %s" % (ruta, porque))
        out.append("- Sugerencias de la IA y por qué:")
        for sug, porque in r["sugerencias"]:
            out.append("  - %s Por qué: %s" % (sug, porque))
        out.append("- Líneas o secciones modificadas: " + r["lineas"])
        out.append("")
        if p["decisiones"]:
            out.append("**Decisiones de Sophia**")
            out.append("")
            out.append("| N | Propuesta de la IA | Por qué la propuso | Veredicto | Razón (en palabras de Sophia) | Qué cambió |")
            out.append("|---|---|---|---|---|---|")
            for n, prop, porque, ver, razon, cambio in p["decisiones"]:
                ver_md = "`[SOPHIA]`" if ver == "Pendiente" else ver
                razon_md = "`[SOPHIA]`" if ver == "Pendiente" else razon
                out.append("| %s | %s | %s | %s | %s | %s |" % (n, md_celda(prop), md_celda(porque), ver_md, md_celda(razon_md), md_celda(cambio)))
            out.append("")
    return "\n".join(out)


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()
    if INICIO not in texto or FIN not in texto:
        raise SystemExit("No encuentro los marcadores en PROMPT_LOG.md")
    antes = texto.split(INICIO)[0]
    despues = texto.split(FIN)[1]
    nuevo = antes + INICIO + "\n\n" + render() + "\n" + FIN + despues
    with io.open(RUTA, "w", encoding="utf-8", newline="\n") as f:
        f.write(nuevo)
    print("PROMPT_LOG.md regenerado:", len(nuevo), "caracteres")


if __name__ == "__main__":
    main()
