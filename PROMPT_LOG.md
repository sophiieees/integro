# Bitácora de prompts · Assignment 2 · Íntegro

| | |
|---|---|
| Alumna | Sophia Pérez |
| Curso | Applied Algorithmic Thinking |
| Proyecto | Íntegro, plataforma de rentas de corta estancia por suscripción |
| Asistente de IA | Claude Code (modelo Claude Fable 5.1), dentro de VS Code |
| Repositorio | (enlace en la sección 4) |
| Estado | Borrador abierto el 18 de octubre de 2026 |

**Cómo leer este documento.** Los campos marcados con `[SOPHIA]` los escribe la alumna: la elección de la función, los tres campos de la especificación, cada veredicto con su razón y el caso de prueba con el output real. El asistente no los redacta. Las entradas registran lo que la IA propuso, qué campo de la especificación estaba en juego y qué se decidió.

---

## 0. Contexto: qué existía antes del assignment

Íntegro es un proyecto de empresa en construcción desde el 5 de octubre de 2026, con siete semanas de plan. Antes de esta bitácora existían los documentos de negocio y técnicos (requerimientos, MVP técnico, ciberseguridad, mapa de etapas, chapa inteligente), pero ningún código.

El 18 de octubre de 2026 se creó este repositorio con:

- un prototipo estático de la web (`web/`): inicio con buscador, sellos de confianza, tarjetas de propiedades, sección de anfitriones, comparativa, y una ficha de propiedad;
- la arquitectura objetivo documentada (`docs/arquitectura.md`) y once decisiones registradas (`docs/decisiones/`);
- el sistema de diseño y el benchmark de competencia (`docs/diseno/`).

El prototipo no tiene ninguna función real: no cotiza, no reserva, no llama a ninguna API. Eso es a propósito, para que la función del Assignment 2 se construya a partir de una especificación y no al revés.

Punto de partida del Assignment 1: `[SOPHIA]` (enlace del repo y deploy del Assignment 1, y una línea sobre por qué el Assignment 2 continúa en Íntegro).

---

## 1. Especificación de 3 campos (Paso 1 · Checkpoint A · Sesión 19)

**Función elegida:** `[SOPHIA]`

**Candidatas consideradas:** ver [docs/assignment-2/funciones-candidatas.md](docs/assignment-2/funciones-candidatas.md). `[SOPHIA]`: anota aquí las 2 o 3 que llevaste a la sesión y por qué descartaste las otras.

| Campo | Contenido |
|---|---|
| **Qué hace** | `[SOPHIA]` La acción exacta, no "ayuda a hacer X". Ejemplo de la forma esperada: "Recibe A y B, calcula C con las reglas D y devuelve E; si F, devuelve el error G". |
| **Qué datos o inputs necesita** | `[SOPHIA]` De dónde sale cada dato, exactamente: un campo que ya existe en `web/assets/js/datos.js`, algo que el usuario escribe en un campo concreto, un archivo que sube, una API externa (cuál, qué endpoint, qué devuelve), o algo que habrá que agregar. |
| **Cómo se sabrá que funciona** | `[SOPHIA]` Criterio verificable con al menos un caso de prueba concreto: input exacto y output esperado. "Que se vea bien" no cuenta. |

**Ruta del código de la función:** `[SOPHIA]` (archivo o archivos donde vive, una vez construida).

### Auditoría en pareja (en vivo, Sesión 19)

| | |
|---|---|
| Compañero o compañera que auditó | `[SOPHIA]` |
| Fecha | `[SOPHIA]` |
| Qué campo cuestionó y por qué | `[SOPHIA]` |
| Qué cambié en la especificación a partir de la auditoría | `[SOPHIA]` |

---

## 2. Registro de construcción (Paso 2 · Checkpoint B)

### Formato de cada entrada

Cada vez que la IA proponga algo que no coincida con la especificación (otra fuente de datos, otro criterio de éxito, una función extra, otra estructura) se registra con estos campos. También se registran las propuestas que sí se aceptaron cuando hubo una decisión real detrás.

```
Entrada N · fecha
Prompt (literal o resumen fiel): ...
Qué propuso la IA: ...
Campo de la especificación en juego: Qué hace / Qué datos necesita / Cómo se sabrá que funciona
Veredicto: Aceptar / Rechazar / Revisar
Razón (específica, citando la especificación): ...
Qué cambió en el código (archivo, commit): ...
```

### 2.0 Decisiones previas a la especificación (sesión 0 · 18 de octubre de 2026)

Estas decisiones son anteriores a la función del assignment, pero son reales y están en este repositorio. No sustituyen las entradas de la sección 2.1 (que deben citar la especificación), pero muestran el mismo patrón: propuesta de la IA, revisión de Sophia, veredicto con razón. Los veredictos siguen pendientes.

**Prompt de origen (18 oct, Sophia):** "con todo lo que sabes de Íntegro, necesito que armemos un diseño de cómo se vería la página web [...] Se le va a dar un estilo propio [...] no tenemos paleta de colores aún, pero me imagino algo de seguridad que es lo que se vende al final [...] también hay que empezar a armar la arquitectura, como para tener bien las bases."

| N | Qué propuso la IA | Por qué lo propuso | Qué dice el proyecto | Veredicto de Sophia | Razón |
|---|---|---|---|---|---|
| 0.1 | Construir el prototipo en HTML, CSS y JavaScript sin dependencias, en lugar de arrancar Next.js. | El disco de la máquina tenía 734 MB libres; cero dependencias permite abrir el archivo con doble clic y publicarlo sin compilar; los tokens CSS migran a Tailwind. | El MVP técnico fija Next.js 15 con TypeScript y Tailwind para la web (ADR 0008 lo registra como propuesta). | `[SOPHIA]` | `[SOPHIA]` |
| 0.2 | Paleta "seguridad": azul profundo como primario, verde como acento de "verificado" e "ingreso íntegro", fondo papel cálido. | Sophia pidió "algo de seguridad". El azul profundo comunica confianza; el verde se reserva para lo verificado y el dinero que llega completo. | La identidad de marca es entregable de Valeria para el 30 de octubre; por eso la paleta vive solo en tokens de `:root`. | `[SOPHIA]` | `[SOPHIA]` |
| 0.3 | Tipografía serif del sistema para títulos y sans del sistema para texto. | Airbnb y Wander usan sans en todo; una serif en títulos diferencia y transmite solidez. Fuentes del sistema por el presupuesto de peso (400 KB en búsqueda). | El MVP técnico pide fuentes del sistema; no dice nada de serif o sans. | `[SOPHIA]` | `[SOPHIA]` |
| 0.4 | Omitir el chip "~$X menos que en otras plataformas" que Wander muestra en cada tarjeta. | En los requerimientos, "Comparación de precio" es de segunda fase y depende de que el anfitrión lo autorice. Se reemplazó por "Total 2 noches · sin cargos de servicio". | Requerimientos, módulo del huésped: comparación de precio, segunda fase. | `[SOPHIA]` | `[SOPHIA]` |
| 0.5 | Omitir el corazón de favoritos en las tarjetas. | Favoritos es de segunda fase (requerimientos) y "Could have" (MVP técnico). | Igual que 0.4. | `[SOPHIA]` | `[SOPHIA]` |
| 0.6 | No calcular ninguna cotización en el prototipo: la ficha muestra un total fijo de ejemplo para 2 noches, tomado de los datos de muestra. | Si la IA construye la cotización antes de que exista la especificación, el assignment pierde su sentido (la función debe nacer de la especificación de Sophia, no al revés). | La cotización es "Must" en el MVP técnico (`GET /properties/:id/quote`) y candidata del assignment. | `[SOPHIA]` | `[SOPHIA]` |
| 0.7 | "Ciudad de México" como ciudad por defecto en los datos de muestra. | Hacía falta una ciudad para que la portada tuviera resultados. | La ciudad de lanzamiento no está decidida; fecha límite 30 de octubre (MVP técnico, decisiones que bloquean). | `[SOPHIA]` | `[SOPHIA]` |
| 0.8 | Mostrar la tabla de planes con los montos de la propuesta inicial (2,000 / 3,000 / 5,000 / 10,000 MXN). | Da realismo al diseño y muestra la estructura por propiedades activas. | Pricing y modelo de ingresos es entregable de Valeria para el 30 de octubre; los montos son "propuesta inicial" (requerimientos). | `[SOPHIA]` | `[SOPHIA]` |
| 0.9 | Sin iconos ni emojis en las secciones, esquinas poco redondeadas, elementos libres sobre el fondo, animaciones solo al entrar. | Son preferencias que Sophia dio para la landing de otro proyecto; la IA las aplicó por defecto. Las referencias de Airbnb y Wander usan iconos y curvas. | No hay lineamiento de marca de Íntegro todavía. | `[SOPHIA]` | `[SOPHIA]` |
| 0.10 | Plazos de ejemplo en las políticas de cancelación (Flexible 24 h, Moderada 5 días, Estricta 7 días). | La ficha necesitaba texto; los requerimientos solo nombran las tres políticas. | Reglas de reembolso "fijas", por definir en la revisión legal (semana 3). La ficha lo marca como propuesta. | `[SOPHIA]` | `[SOPHIA]` |

### 2.1 Entradas durante la construcción de la función

Mínimo una entrada que cite qué campo de la especificación estaba en juego. Para el nivel 5, un patrón repetido: propuesta de la IA, cuestionamiento, ajuste o rechazo justificado.

```
Entrada 1 · [SOPHIA] fecha
Prompt: [SOPHIA]
Qué propuso la IA: [SOPHIA]
Campo de la especificación en juego: [SOPHIA]
Veredicto: [SOPHIA]
Razón: [SOPHIA]
Qué cambió en el código: [SOPHIA]
```

```
Entrada 2 · [SOPHIA]
...
```

---

## 3. Registro de validación (Paso 3 · antes de la Sesión 20)

| | |
|---|---|
| URL del deploy | `[SOPHIA]` |
| Fecha y hora en que se confirmó que responde | `[SOPHIA]` |
| Cómo se confirmó (qué se abrió, qué respondió) | `[SOPHIA]` |

### Caso de prueba 1

**Input exacto** (lo que se escribió o envió, tal cual):

```
[SOPHIA]
```

**Output real** (copiado y pegado, no resumido):

```
[SOPHIA]
```

**Veredicto:** `[SOPHIA]` Aceptar / Rechazar / Revisar

**Razón** (1 o 2 líneas que citen algo específico del output real): `[SOPHIA]`

### Caso de prueba 2 (opcional)

(Mismo formato.)

---

## 4. Entrega final (Paso 4 · antes de la Sesión 21)

| | |
|---|---|
| Enlace del deploy con la función integrada | `[SOPHIA]` |
| Enlace del repositorio | `[SOPHIA]` |
| Bitácora | Este archivo, `PROMPT_LOG.md`, en la raíz del repositorio |

---

## 5. Por qué la función resuelve el problema que se propuso resolver

`[SOPHIA]` Dos o tres párrafos que citen la especificación de la sección 1: qué problema de Íntegro ataca la función, cómo el criterio de éxito demuestra que lo resuelve (más allá de que el caso de prueba haya pasado), y qué quedó fuera a propósito.

---

## 6. Uso de IA

`[SOPHIA]` Qué herramienta o herramientas usaste, para qué las usaste, y qué decidiste o verificaste tú. (Este campo es obligatorio en la entrega; si no se usó IA, se escribe "No usé IA en esta entrega".)
