---
name: bitacora
description: Registra en la bitácora de Íntegro el prompt de Sophia, la respuesta de la IA y las decisiones de aceptar, rechazar o revisar. Úsala cuando Sophia escriba /bitacora, al cerrar una pieza, o cuando pida guardar, registrar o documentar un prompt o una decisión.
---

# /bitacora

La bitácora deja constancia de cómo se tomó cada decisión: qué pidió Sophia, qué propuso la IA y qué decidió ella. La fuente única es `herramientas/bitacora/bitacora_datos.py`; de ahí se genera el documento de Word.

## Qué se registra por cada prompt

1. **El prompt, transcrito en limpio.** Sophia dicta; sus mensajes traen muletillas y repeticiones. Se transcribe con la estructura de cuatro partes, sin agregar ni quitar peticiones:
   - **Rol:** quién es la IA en ese prompt.
   - **Tarea:** qué pidió, en el orden en que lo pidió.
   - **Contexto:** documentos, restricciones, referencias y lo que dijo que ya estaba bien.
   - **Salida:** qué debía entregar y cómo.
2. **La respuesta de la IA, desglosada:** fecha, commits, carpetas y archivos con su porqué, sugerencias con su porqué, y líneas o secciones modificadas.
3. **Las decisiones:** una fila por cada propuesta de la IA que no coincidía con lo pedido o con la especificación. Cada fila lleva: número, propuesta de la IA, por qué la propuso, campo de la especificación en juego (qué hace, qué datos necesita, cómo se sabrá que funciona), veredicto, razón y qué cambió.

## Reglas

- **Fidelidad.** Transcribir no es reescribir. No se mejora lo que Sophia pidió ni se le atribuyen razones que no dio. La bitácora lleva la nota de transparencia que lo dice.
- **Los veredictos y las razones son de Sophia.** Se citan con sus palabras. Si todavía no decide, el veredicto queda "Pendiente" y la razón vacía; nunca se inventa.
- **Los casos de prueba se registran con la entrada exacta y la salida real copiada.** Si una prueba corrió en local y no en la versión publicada, se dice.
- **Las ediciones directas de Sophia en GitHub también son decisiones:** se registran con sus commits.
- Nada de secretos, llaves ni datos personales en la bitácora.

## Pasos

1. Lee `herramientas/bitacora/bitacora_datos.py` y agrega un elemento a `PROMPTS` con el número siguiente y los campos `titulo`, `fecha`, `rol`, `tarea`, `contexto`, `salida`, `respuesta` (`fecha`, `commits`, `archivos`, `sugerencias`, `lineas`) y `decisiones`.
2. Muestra a Sophia la transcripción del prompt y la lista de decisiones antes de guardar, para que corrija lo que no refleje lo que pidió.
3. Genera el documento con `herramientas/bitacora/generar_presentacion.py` (necesita un intérprete de Python con `python-docx` y `Pillow`). Como no se puede renderizar aquí, verifica leyendo el archivo: número de prompts, tablas e imágenes.
4. Commit de `bitacora_datos.py` en la rama de la pieza, con un mensaje que diga qué decisiones se registraron.
5. Dile a Sophia dónde quedó el documento y qué veredictos siguen pendientes.
