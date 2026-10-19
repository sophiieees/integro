# Bitácora de prompts Íntegro

| | |
|---|---|
| Alumna | Sophia Pérez |
| Proyecto | Íntegro, plataforma de rentas de corta estancia por suscripción |
| Asistente de IA | Claude Code (modelo Claude Fable 5.1), dentro de VS Code |

**Cómo leer este documento.** Los campos marcados con `[SOPHIA]` los escribe la alumna: la elección de la función, los tres campos de la especificación, cada veredicto con su razón y el caso de prueba con el output real. El asistente no los redacta. Las entradas registran lo que la IA propuso, qué campo de la especificación estaba en juego y qué se decidió.

---

## 0. Contexto: qué existía antes del assignment

Íntegro es un proyecto de empresa en construcción desde el 5 de octubre de 2026, con siete semanas de plan. Antes de esta bitácora existían los documentos de negocio y técnicos (requerimientos, MVP técnico, ciberseguridad, mapa de etapas, chapa inteligente), pero ningún código.

El 18 de octubre de 2026 se creó este repositorio con:

- un prototipo estático de la web (`web/`): portada del huésped con buscador en la cabecera y tarjetas de propiedades, ficha de propiedad, y página del anfitrión con planes y comparativa (separada de la portada en la segunda revisión del mismo día, ver entradas 0.11 a 0.15);
- la arquitectura objetivo documentada (`docs/arquitectura.md`) y once decisiones registradas (`docs/decisiones/`);
- el sistema de diseño y el benchmark de competencia (`docs/diseno/`).

El prototipo no tiene ninguna función real: no cotiza, no reserva, no llama a ninguna API. Eso es a propósito, para que la función del Assignment 2 se construya a partir de una especificación y no al revés.

Punto de partida del Assignment 1: `[SOPHIA]` (enlace del repo y deploy del Assignment 1, y una línea sobre por qué el Assignment 2 continúa en Íntegro).

---

## 1. Especificación de 3 campos (Paso 1 · Checkpoint A · Sesión 19)

**Función elegida:** `[SOPHIA]`

**Candidatas consideradas:** `[SOPHIA]` anota aquí las 2 o 3 que llevaste a la sesión y por qué descartaste las otras.

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

Estas decisiones son anteriores a la función del assignment, pero son reales y están en este repositorio. No sustituyen las entradas de la sección 2.1 (que deben citar la especificación), pero muestran el mismo patrón: propuesta de la IA, revisión de Sophia, veredicto con razón. Las entradas 0.1 a 0.10 siguen pendientes de veredicto. Las entradas 0.11 a 0.15 registran los veredictos que Sophia dio por escrito el mismo 18 de octubre al revisar el primer prototipo; la IA los transcribió citando sus palabras y Sophia puede corregir la redacción.

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

**Segunda revisión (18 de octubre, tras ver el primer prototipo).** Prompt de Sophia: "vamos a modificar el main [...] me gustaría que lo de destino, llegada, salida y huéspedes estuviera arriba [...] hay que poner otros dos para que sean seis [...] anfitrión verificado, precio total visible [...] hay que quitarlo para ponerlo abajo [...] Anfitriones tienen que ser de otra página web. Forzosamente [...] la idea es que en la página principal solo se vean las propiedades."

| N | Qué propuso la IA | Por qué lo propuso | Veredicto de Sophia | Razón (en sus palabras) | Qué cambió |
|---|---|---|---|---|---|
| 0.11 | Buscador grande dentro del hero, debajo del titular. | Seguía el patrón de Airbnb (barra bajo la cabecera). | Revisar | "Me gustaría que lo de destino, llegada, salida y huéspedes estuviera arriba [...] Wander, me gusta mucho que la barra buscadora la tiene arriba, no se ve tan grande." | Buscador compacto en la cabecera, una sola línea; el hero queda para la imagen y el titular. |
| 0.12 | Imagen del hero en una columna lateral 4:5. | Evitar texto sobre foto por legibilidad y peso. | Revisar | "El fondo de pantalla me gusta, o sea, como una imagen, poner una imagen así estaría bastante bien [...] crea un repositorio de imágenes y conéctala." | Hero con foto a lo ancho tipo Wander, velo oscuro para legibilidad; carpeta `web/assets/img/` con `LEEME.md` y nombre fijo `imagen-bienvenida.jpg`. |
| 0.13 | Sellos de confianza entre el hero y las propiedades. | Poner la promesa de seguridad antes de la oferta. | Revisar | "Hay que quitarlo para ponerlo abajo, yo creo. O ponerlo como en otra página." | Sellos y "cómo funciona" debajo de las propiedades; la portada abre con las propiedades. |
| 0.14 | Sección de anfitriones, planes y comparativa en la portada. | Una sola página con todo el modelo. | Rechazar | "Anfitriones tienen que ser de otra página web. Forzosamente. La idea es que en la página principal solo se vean las propiedades para que el huésped pueda seleccionarlas [...] Para no revolverlos." | Página nueva `web/anfitriones.html`; en la portada solo queda el botón "Publica tu propiedad". |
| 0.15 | Cuatro propiedades de muestra en Ciudad de México. | Bastaban para probar el filtro. | Revisar | "Hay que poner otros dos para que sean seis. Se muestren seis." | Dos propiedades más (Polanco y Juárez) en `datos.js`; la portada muestra seis. |

**Tercera revisión (18 de octubre, noche).** Prompt de Sophia: "donde dice rentas de corta estancia [...] hospedaje verificado, precio total, cero comisión [...] eso lo vamos a quitar, todo lo vamos a quitar. Y donde está la imagen [...] vamos a colocar lo de destino, llegada, salida, etc. Para que en el header solo quede Íntegro y [...] conviértete en anfitrión [...] anfitrión verificado, precio visible, pago protegido, entrada con tu teléfono, reservar toma tres pasos [...] en una página aparte que va a ser cómo funciona [...] el pie de página [...] el verde que se usa como fondo [...] quitar hospedajes [...] reportar algún problema, eso sí es muy importante."

| N | Qué propuso la IA | Por qué lo propuso | Veredicto de Sophia | Razón (en sus palabras) | Qué cambió |
|---|---|---|---|---|---|
| 0.16 | Titular con las tres promesas y subtítulo sobre la imagen del hero. | Poner la promesa verificable donde Wander pone su lema. | Rechazar | "Eso lo vamos a quitar, todo lo vamos a quitar." | El hero queda solo con la imagen y el buscador; la promesa vive en `como-funciona.html`. |
| 0.17 | Buscador compacto dentro de la cabecera (segunda revisión). | Seguir la barra de Wander. | Revisar | "Donde está la imagen [...] vamos a colocar lo de destino, llegada, salida, etc. Para que en el header solo quede Íntegro y [...] conviértete en anfitrión." | Buscador al centro del hero, sobre la imagen; cabecera solo con la marca y "Conviértete en anfitrión" hacia `anfitriones.html`. |
| 0.18 | Sellos de confianza y "Reservar toma tres pasos" al final de la portada. | Mantener la explicación en la misma página. | Revisar | "Eso que va en texto lo vamos a colocar en una página aparte que va a ser cómo funciona [...] yo creo que cómo funciona va a ir dentro de anfitriones." | Página nueva `web/como-funciona.html`; la portada queda solo con buscador y propiedades. |
| 0.19 | Pie de página claro con seis enlaces, "Reportar un problema" como uno más. | Pie neutro, igual en todas las páginas. | Revisar | "Que tenga un color, pues el verde que se usa como fondo [...] quitar hospedajes [...] reportar algún problema, eso sí es muy importante. Muy, muy, muy importante." | Pie en verde profundo (token `--color-pie`, derivado del acento), sin "Hospedajes", "Reportar un problema" como botón blanco destacado; Términos y Aviso sin enlace todavía. Aplicado a las cuatro páginas. |
| 0.20 | La IA quitó "Entrar" de todas las cabeceras para cumplir "solo quede Íntegro y conviértete en anfitrión". El inicio de sesión es una pieza Must del MVP, así que en algún momento tiene que volver. | Instrucción literal de Sophia; el prototipo no tiene inicio de sesión. | `[SOPHIA]` | `[SOPHIA]` | Pendiente: decidir dónde vivirá "Entrar" (cabecera o dentro del flujo de reserva). |

**Cuarta revisión (18 de octubre, noche).** Prompt de Sophia: "me gusta que [el buscador] se quede ahí en el centro [...] ahora lo veo un poco pelón en esta zona y en el header [...] arriba [...] se coloque un eslogan. Algo como su lugar íntegro [...] que íntegro tenga una coloración azul [...] conviértete en anfitrión hay que colocarlo más a la izquierda y [...] quitarle los bordes [...] el pie de página ya no me gustó el color, lo prefiero blanco [...] me gusta el acomodo [...] reportar un problema [...] de algún otro color que resalte [...] quita todos los puntos [...] ubicación [...] redireccionamiento a Google Maps [...] se pierde mucho espacio entre [...] la descripción y la reserva [...] que abarque todo [...] publica tu propiedad, ese color verde tampoco me gusta."

| N | Qué propuso la IA | Por qué lo propuso | Veredicto de Sophia | Razón (en sus palabras) | Qué cambió |
|---|---|---|---|---|---|
| 0.21 | Hero solo con la imagen y el buscador, sin texto (aplicado en 0.16 a petición suya). | Instrucción previa de Sophia. | Revisar | "Ahora lo veo un poco pelón [...] se coloque un eslogan. Algo como su lugar íntegro [...] haciendo un juego de palabras." | Eslogan "Su lugar, íntegro." sobre el buscador, con "íntegro" en azul claro (token `--color-resalte`). La coma la puso la IA para espejear "Tu ingreso, íntegro."; Sophia decide si se queda. |
| 0.22 | Botón "Conviértete en anfitrión" con borde, pegado a la derecha de la cabecera. | Patrón "List on Wander". | Revisar | "Hay que colocarlo más a la izquierda y no me gusta que tenga bordes." | Enlace de texto sin borde junto a la marca, en todas las páginas del huésped. |
| 0.23 | Pie de página verde profundo con botón blanco de reporte. | Interpretación de "el verde que se usa como fondo". | Rechazar | "Ya no me gustó el color, sí lo prefiero blanco. Sin embargo, me gusta el acomodo [...] reportar un problema [...] de algún otro color que resalte." | Pie blanco con el mismo acomodo; "Reportar un problema" en azul primario. |
| 0.24 | Separador " · " entre datos (zona, tipo, huéspedes; calificación y reseñas; total y cargos). | Convención de Airbnb y Wander. | Rechazar | "Quita todos los puntos que aparecen en los textos." | Comas, paréntesis y líneas separadas; plurales correctos ("1 baño"). Los títulos de pestaña usan "\|". |
| 0.25 | Ubicación y reseñas dentro de la columna de descripción de la ficha; mapa decorativo sin enlace. | Agrupar todo el contenido a la izquierda de la caja de precio. | Revisar | "Se pierde mucho espacio entre [...] la descripción y la reserva [...] que abarque todo [...] redireccionamiento a Google Maps." | Ubicación y reseñas como secciones a lo ancho debajo de las dos columnas; el mapa y un botón abren Google Maps con la zona aproximada (colonia y ciudad), nunca la dirección exacta. |
| 0.26 | Botones verdes (`.btn-primario`) para "Publica tu propiedad" y "Empezar la verificación" en la página de anfitrión. | Un solo color de botón principal en todo el sitio. | Rechazar | "Publica tu propiedad, ese color verde tampoco me gusta. En el botón." | Los tres botones de la página de anfitrión pasan a azul primario (`.btn-azul`). "Buscar" (portada) y "Reservar" (ficha) siguen verdes porque Sophia no los mencionó: pendiente confirmar si el verde sale de todos los botones. |

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
