# Guía de la rúbrica del Assignment 2

Contraste de cada criterio de la rúbrica con la evidencia que debe existir en este repositorio. Sirve para revisar la entrega antes de mandarla, no para sustituir el trabajo.

## Calendario

| Momento | Qué se captura | Dónde |
|---|---|---|
| Pre-Class Work de la Sesión 19 | 2 o 3 funciones candidatas | `docs/assignment-2/funciones-candidatas.md` y nota de Sophia en `PROMPT_LOG.md` §1 |
| Sesión 19, Checkpoint A | Especificación de 3 campos, auditada en pareja | `PROMPT_LOG.md` §1 |
| Sesión 19, arranque del Checkpoint B | Al menos un prompt que referencia la especificación y una entrada de aceptar/rechazar/revisar con motivo | `PROMPT_LOG.md` §2.1 |
| Antes de la Sesión 20 | Deploy confirmado, un caso de prueba real (input, output, veredicto con razón) | `PROMPT_LOG.md` §3 |
| Antes de la Sesión 21 | Enlace de deploy, enlace de repo, bitácora completa | Campo de entrega en Forum, con `PROMPT_LOG.md` §4 |

## Evidencia obligatoria

- [ ] Especificación con los tres campos concretos (`PROMPT_LOG.md` §1).
- [ ] Auditoría en pareja registrada: quién, qué cuestionó, qué cambió (`PROMPT_LOG.md` §1).
- [ ] Al menos una entrada de aceptar, rechazar o revisar que cite qué campo de la especificación estaba en juego (`PROMPT_LOG.md` §2.1).
- [ ] Registro de validación: input exacto, output real copiado, veredicto con razón que cite el output (`PROMPT_LOG.md` §3).
- [ ] Historial de commits con al menos un mensaje que refleje una decisión real (`git log`).
- [ ] Sección "Uso de IA" al final de la bitácora (`PROMPT_LOG.md` §6).
- [ ] La función existe de forma verificable en el deploy.
- [ ] Si la función usa un modelo de IA: su system prompt guardado en el repositorio.

## Qué pide cada nivel y cómo se demuestra aquí

| Nivel | Lo que pide la rúbrica | Evidencia en este repositorio |
|---|---|---|
| 3 (esperado) | Al menos una sugerencia de la IA rechazada o modificada frente a la especificación, con motivo. Caso de prueba con evidencia real. La función hace lo que la especificación dice, o se documenta honestamente que no. | §2.1 con una entrada de Rechazar o Revisar; §3 con output pegado; §3 veredicto honesto. |
| 4 | Además, cuestionar a la IA en un punto clave (fuente de datos, caso límite, estructura) pidiendo una alternativa antes de aceptar. Detectar y corregir al menos un error sustantivo que la IA no señaló. | §2.1: una entrada donde Sophia pidió alternativa antes de aceptar, y una entrada que describa el error detectado (qué era, cómo se notó, qué se corrigió). Las secciones "Dónde la IA podría salirse de la especificación" de `funciones-candidatas.md` son los puntos donde más probable es que aparezca. |
| 5 | Patrón repetido, no caso aislado, de propuesta, cuestionamiento y ajuste a lo largo de los tres pasos. Articular por qué la función resuelve el problema, citando la propia especificación. | §2.0 (decisiones de diseño previas) + §2.1 (varias entradas) + §3 (veredicto con evidencia) + §5 (argumento que cita §1). |

## Errores que bajan la nota, según la rúbrica

- Copiar la salida de la IA sin cuestionarla; aceptar la primera propuesta completa.
- Especificación que repite el nombre de la función ("qué hace: hace la cotización").
- Veredicto genérico ("funcionó bien") sin citar el output real.
- Corregir solo errores de ejecución (bugs) sin cuestionar ninguna decisión de diseño, fuente de datos o alcance que la IA tomó por su cuenta.
- Commits con mensajes como "update" o "fix".

## Cómo trabajar con el asistente durante el Paso 2

- Pedir el código citando la especificación: "según la especificación de PROMPT_LOG.md §1, construye...".
- Antes de aceptar una propuesta, preguntar: ¿de dónde sale ese dato?, ¿qué pasa con el caso límite X?, ¿hay otra forma de estructurarlo?
- Cuando el asistente avise que su propuesta se sale de la especificación, decidir y registrar la decisión en ese momento, no al final.
- Probar antes de aceptar: correr el caso de prueba de §1 y pegar el output en §3.
