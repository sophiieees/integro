---
name: doc
description: Genera el documento final de Íntegro en Word, con el formato de ISO/IEC/IEEE 29148 y la paleta azul marino de CLAUDE.md: la especificación de requisitos en el cuerpo y la bitácora como anexo. Úsala solo cuando Sophia escriba /doc o pida el documento final. No se genera al cerrar cada pieza.
---

# /doc

El documento final se crea una sola vez, al final, o cuando Sophia lo pida. Mientras tanto, `/bitacora` guarda los prompts, las dudas y las decisiones en `herramientas/bitacora/bitacora_datos.py` sin generar ningún Word.

## Qué contiene

El cuerpo es la especificación de requisitos de la plataforma. La bitácora de prompts y decisiones va como anexo.

Estructura, según el esquema de especificación de requisitos de software de ISO/IEC/IEEE 29148 (edición 2018):

1. **Introducción**
   - 1.1 Propósito
   - 1.2 Alcance
   - 1.3 Visión general del producto: perspectiva, funciones, características de los usuarios (huésped, anfitrión, administrador) y limitaciones
   - 1.4 Definiciones
2. **Referencias**
3. **Requisitos**
   - 3.1 Funciones
   - 3.2 Requisitos de desempeño
   - 3.3 Requisitos de usabilidad
   - 3.4 Requisitos de interfaz
   - 3.5 Requisitos lógicos de la base de datos
   - 3.6 Restricciones de diseño
   - 3.7 Atributos del sistema (seguridad, disponibilidad, mantenibilidad)
   - 3.8 Información de apoyo
4. **Verificación:** las mismas subsecciones de la sección 3, con la forma en que se comprueba cada requisito
5. **Apéndices**
   - 5.1 Supuestos y dependencias
   - 5.2 Siglas y abreviaturas
   - Anexo A: bitácora de prompts, respuestas y decisiones

Si Sophia tiene la norma a la mano y su esquema difiere de este, manda el de la norma.

## De dónde sale cada cosa

Solo de lo que ya está escrito en el repositorio. Nada se inventa ni se completa de memoria.

| Sección | Fuente |
|---|---|
| Introducción, funciones, interfaces, restricciones | `docs/arquitectura.md` y `docs/decisiones/` |
| Requisitos de la base de datos | `supabase/migrations/` |
| Atributos de seguridad | sección de seguridad de `CLAUDE.md` y `docs/decisiones/` |
| Usabilidad | `docs/diseno/` |
| Verificación | `tests/` y `herramientas/pruebas/`, con la salida real de cada corrida |
| Anexo A | `herramientas/bitacora/bitacora_datos.py` |

Si una sección no tiene fuente, se escribe "Por definir" y se le reporta a Sophia. No se rellena.

## Cómo se escribe cada requisito

- Un identificador único por requisito: `RF-001` (función), `RD-001` (datos), `RS-001` (seguridad), `RU-001` (usabilidad), `RI-001` (interfaz), `RP-001` (desempeño).
- Una sola obligación por requisito, redactada con "deberá", sin palabras vagas ("rápido", "fácil", "seguro") y que se pueda comprobar.
- Cada requisito lleva su origen (la decisión, el prompt de la bitácora o el archivo de donde sale) y, en la sección 4, su verificación: el caso de prueba y su resultado real. Si todavía no tiene prueba, se dice.

## Formato

- Word (`.docx`), en español.
- Azul marino `#0E0E55` en la portada, los títulos y el encabezado de las tablas (texto blanco sobre azul). Cuerpo en negro.
- Portada con el nombre del proyecto, la versión y la fecha. Tabla de control de cambios e índice.
- Sin emojis ni iconos. Sin separadores " · ".
- El documento se guarda fuera del repositorio, en el Escritorio de Sophia, salvo que ella indique otro lugar.

## Pasos

1. `git fetch` y `git pull --rebase` sobre `main`, para leer la versión vigente de todas las fuentes.
2. Lee las fuentes y arma el índice con los requisitos numerados. Antes de generar, muestra a Sophia la lista de requisitos y las secciones que quedarían "Por definir", para que decida si se genera así o se espera.
3. Genera el Word con el generador del proyecto. Si el generador todavía no existe, avisa a Sophia y constrúyelo primero como pieza aparte (`/pieza`), con su autorización.
4. Como el Word no se puede ver aquí, verifica leyendo el archivo generado: número de secciones, de requisitos, de tablas y de entradas del anexo, contra las fuentes.
5. Entrega a Sophia: dónde quedó el documento, cuántos requisitos tiene por sección, qué quedó "Por definir" y qué veredictos de la bitácora siguen pendientes.
