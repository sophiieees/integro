# Bitácora de prompts Íntegro

| | |
|---|---|
| Alumna | Sophia Pérez |
| Proyecto | Íntegro, plataforma de rentas de corta estancia por suscripción |
| Asistente de IA | Claude Code (modelo Claude Fable 5.1), dentro de VS Code |

**Cómo leer este documento.** Los campos marcados con `[SOPHIA]` los escribe la alumna: la elección de la función, los tres campos de la especificación, cada veredicto con su razón y el caso de prueba con el output real. El asistente no los redacta. Los prompts se presentan con la estructura rol, tarea, contexto y salida; cada respuesta de la IA se desglosa en fecha, archivos, por qué, sugerencias y líneas modificadas; y cada decisión de Sophia lleva veredicto y razón.

---

## 0. Contexto: qué existía antes del assignment

Íntegro es un proyecto de empresa en construcción desde el 5 de octubre de 2026, con siete semanas de plan. Antes de esta bitácora existían los documentos de negocio y técnicos (requerimientos, MVP técnico, ciberseguridad, mapa de etapas, chapa inteligente), pero ningún código.

El 18 de octubre de 2026 se creó este repositorio con:

- un prototipo estático de la web (`web/`): portada del huésped con eslogan, buscador e imagen, y tarjetas de propiedades; ficha de propiedad; página "Cómo funciona"; y página del anfitrión con planes y comparativa;
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

### Formato de cada prompt y de cada entrada

Cada prompt se registra con cuatro partes: **rol** (quién es la IA), **tarea** (qué debe hacer), **contexto** (qué documentos, restricciones y referencias tiene) y **salida** (qué debe entregar y cómo). La respuesta de la IA se desglosa en fecha, carpeta o archivo modificado, por qué se modificó, sugerencias que hizo y por qué, y líneas o secciones modificadas. Cada vez que la IA proponga algo que no coincida con la especificación (otra fuente de datos, otro criterio de éxito, una función extra, otra estructura) se registra una decisión con estos campos:

```
Entrada N · fecha
Campo de la especificación en juego: Qué hace / Qué datos necesita / Cómo se sabrá que funciona
Qué propuso la IA: ...
Veredicto: Aceptar / Rechazar / Revisar
Razón (específica, citando la especificación): ...
Qué cambió en el código (archivo, commit): ...
```

<!-- bitacora:inicio (sección generada desde bitacora_datos.py; editar ahí) -->

### 2.0 Prompts y decisiones de la construcción del prototipo (18 de octubre de 2026)

Los prompts se transcriben en limpio con la estructura rol, tarea, contexto y salida; la conversación original con el asistente fue hablada y más extensa, pero las peticiones, las propuestas de la IA y los veredictos son los mismos. Las razones de Sophia se citan con sus palabras. Estas decisiones son anteriores a la función del assignment, pero son reales y están en este repositorio; muestran el patrón que pide el nivel 5: propuesta de la IA, revisión de Sophia, veredicto con razón. Las entradas marcadas "Pendiente" esperan el veredicto de Sophia.

#### Prompt 1: Diseño de la web, arquitectura y base del Assignment 2 (18 de octubre de 2026, tarde)

**Rol.** Eres un ingeniero de software senior, experto en desarrollo web (UX, frontend y backend) y en arquitectura de plataformas. Trabajas en el proyecto Íntegro, una plataforma de rentas de corta estancia por suscripción.

**Tarea.** Diseña cómo se verá la página web de Íntegro con un estilo propio, tomando como referencia las capturas de Airbnb y Wander, y súbela al repositorio de GitHub de mi cuenta profesional. Arma además la base de la arquitectura del sistema y la documentación completa para el Assignment 2, cuyo objetivo es el nivel 5 de la rúbrica, sin que falte ningún punto. Si tienes dudas, pregunta.

**Contexto.** Documentos adjuntos: requerimientos de la plataforma, cronograma de entregables, MVP técnico con método MoSCoW, ciberseguridad (amenazas, controles y respuesta), mapa de etapas y chapa inteligente. Notas sobre iCal, importación desde Airbnb y verificación de propiedades en México. Capturas de Airbnb y Wander. El nombre Íntegro es provisional, no hay paleta de colores y la marca vende seguridad. El proyecto es mucho más grande que la tarea; la tarea se adapta a él.

**Salida esperada.** Al terminar, entrega: la fecha, la carpeta o archivo que se creó o modificó, por qué se modificó, qué sugerencias hiciste y por qué, y las líneas o secciones modificadas. Todo en el repositorio de GitHub y desglosado para la bitácora.

**Respuesta de la IA**

- Fecha: 18 de octubre de 2026. Commits: 30565d4, 559b8f1 y a1bac93.
- Carpetas y archivos, y por qué:
  - `README.md, .gitignore, index.html (raíz), vercel.json`: base del repositorio, mapa de carpetas, tabla para el profesor y configuración de publicación.
  - `web/index.html, web/propiedad.html, web/assets/css/estilos.css, web/assets/js/app.js, web/assets/js/datos.js`: prototipo estático de la portada y la ficha, con la paleta y la tipografía en tokens de :root y datos ficticios.
  - `docs/arquitectura.md y docs/decisiones/0001 a 0011`: arquitectura objetivo condensada de los documentos del equipo y un registro por decisión.
  - `docs/diseno/sistema-de-diseno.md, benchmark-competencia.md, pantallas.md, capturas/`: sistema de diseño, comparación con Airbnb y Wander y lista de pantallas.
  - `PROMPT_LOG.md y docs/assignment-2/ (funciones candidatas y guía de rúbrica)`: estructura de la bitácora y material de apoyo; Sophia borró después docs/assignment-2 desde GitHub.
- Sugerencias de la IA y por qué:
  - Prototipo en HTML, CSS y JavaScript sin dependencias en lugar de Next.js. Por qué: la máquina tenía 734 MB libres en disco y el prototipo debía abrirse con doble clic y publicarse sin compilar; los tokens migran a Tailwind.
  - Paleta de seguridad (azul profundo, verde para lo verificado, fondo papel) y serif en títulos, solo como valores iniciales en tokens. Por qué: la identidad de marca llega el 30 de octubre; así se cambia en un solo lugar.
  - No construir ninguna cotización en el prototipo. Por qué: la función real del assignment debe nacer de la especificación de Sophia, no al revés.
  - Omitir el chip de ahorro de Wander y los favoritos. Por qué: los requerimientos los ponen en segunda fase.
- Líneas o secciones modificadas: Todo el contenido es nuevo; el detalle línea por línea está en el diff de los tres commits.

**Decisiones de Sophia**

| N | Propuesta de la IA | Por qué la propuso | Veredicto | Razón (en palabras de Sophia) | Qué cambió |
|---|---|---|---|---|---|
| 0.1 | Prototipo estático (HTML, CSS, JS) en lugar de Next.js, que es lo que fija el MVP técnico. | Disco con 734 MB libres; cero dependencias; publicación sin compilar. | `[SOPHIA]` | `[SOPHIA]` | ADR 0008 como propuesta. |
| 0.2 | Paleta azul profundo, verde íntegro y papel cálido. | Sophia pidió algo que comunique seguridad; vive solo en tokens. | `[SOPHIA]` | `[SOPHIA]` | Tokens en :root de estilos.css. |
| 0.3 | Serif del sistema en títulos, sans en texto. | Diferencia frente a Airbnb y Wander; fuentes del sistema por peso. | `[SOPHIA]` | `[SOPHIA]` | Tokens de tipografía. |
| 0.4 | Omitir el chip de ahorro frente a otras plataformas. | Es de segunda fase en los requerimientos. | `[SOPHIA]` | `[SOPHIA]` | Se muestra el total sin cargos de servicio. |
| 0.5 | Omitir favoritos (corazón) en las tarjetas. | Segunda fase y Could have. | `[SOPHIA]` | `[SOPHIA]` | Sin corazón. |
| 0.6 | Sin cálculo de cotización; total fijo de ejemplo. | La función del assignment debe nacer de la especificación. | `[SOPHIA]` | `[SOPHIA]` | Caja de precio con nota. |
| 0.7 | Ciudad de México como ciudad por defecto de los datos de muestra. | Hacía falta una ciudad; la de lanzamiento se decide antes del 30 de octubre. | `[SOPHIA]` | `[SOPHIA]` | datos.js, ciudadPorDefecto. |
| 0.8 | Mostrar los montos de la propuesta inicial de planes. | Dan realismo; el pricing lo define Valeria el 30 de octubre. | `[SOPHIA]` | `[SOPHIA]` | Tabla de planes. |
| 0.9 | Sin iconos ni emojis, esquinas discretas, animaciones solo al entrar. | Preferencias que Sophia dio en otro proyecto. | `[SOPHIA]` | `[SOPHIA]` | Reglas del sistema de diseño. |
| 0.10 | Plazos de ejemplo en las políticas de cancelación. | La ficha necesitaba texto; la revisión legal los define. | `[SOPHIA]` | `[SOPHIA]` | Ficha, marcado como propuesta. |

#### Prompt 2: Primera revisión visual de la portada (18 de octubre de 2026, noche)

**Rol.** Eres un ingeniero de software senior, experto en desarrollo web (UX, frontend y backend) y en arquitectura de plataformas. Trabajas en el proyecto Íntegro, una plataforma de rentas de corta estancia por suscripción.

**Tarea.** Modifica la portada: la barra de destino, llegada, salida y huéspedes debe ir arriba, compacta como la de Wander; el hero lleva una imagen de fondo a lo ancho; se muestran seis propiedades de Ciudad de México; los sellos de confianza bajan debajo de las propiedades; la sección de anfitriones se va a una página aparte, porque la portada es solo para el huésped. Crea una carpeta de imágenes con nombres fijos para que yo coloque las fotos.

**Contexto.** Capturas de Airbnb y Wander: ambas dirigen la portada al huésped y ponen la entrada del anfitrión como un botón. Todavía no hay logo ni fotografías. La ficha de propiedad, con su mapa, gusta y se conserva.

**Salida esperada.** Al terminar, entrega: la fecha, la carpeta o archivo que se creó o modificó, por qué se modificó, qué sugerencias hiciste y por qué, y las líneas o secciones modificadas. Todo en el repositorio de GitHub y desglosado para la bitácora.

**Respuesta de la IA**

- Fecha: 18 de octubre de 2026. Commits: 5382b40.
- Carpetas y archivos, y por qué:
  - `web/index.html`: cabecera con la barra de búsqueda compacta, hero con imagen de fondo, seis propiedades, sellos y cómo funciona debajo; sin la sección de anfitriones.
  - `web/anfitriones.html (nuevo)`: beneficios, planes, tres pasos para publicar y comparativa frente a plataformas por comisión.
  - `web/assets/css/estilos.css`: secciones Cabecera, Buscador, Hero, Tarjetas (foto real opcional) y Responsivo; tonos nuevos para Polanco y Juárez.
  - `web/assets/js/app.js`: función tarjeta (imagen real si existe) y revelado al hacer scroll por posición, en lugar de IntersectionObserver.
  - `web/assets/js/datos.js`: propiedades 8 (Polanco) y 9 (Juárez) para llegar a seis en Ciudad de México.
  - `web/assets/img/LEEME.md`: nombres de archivo que esperan las páginas: imagen-bienvenida.jpg y propiedad-<id>-<n>.jpg.
  - `docs/diseno/*.md, README.md, PROMPT_LOG.md`: documentación y bitácora actualizadas.
- Sugerencias de la IA y por qué:
  - Mover la insignia de chapa a la esquina inferior de la foto. Por qué: en tarjetas de 260 px se encimaba con la de anfitrión verificado.
  - Dejar cómo funciona al final de la portada junto a los sellos. Por qué: Sophia no definió dónde iba; se ofreció moverlo a otra página.
  - Revelado por posición en lugar de IntersectionObserver. Por qué: en una prueba a 900 px el observador dejó cuatro tarjetas invisibles; el contenido no puede depender de una animación.
  - Mecanismo de fotos opcionales con marcador. Por qué: si el archivo no existe, la página muestra el marcador; al guardarlo aparece la foto sin tocar código.
- Líneas o secciones modificadas: estilos.css: bloques .cabecera, .buscador, .hero, .tarjeta-foto img, media queries de 1080 y 720 px. app.js: función tarjeta y funciones registrarRevelado y revelarVisibles. datos.js: objetos con id 8 y 9.

**Decisiones de Sophia**

| N | Propuesta de la IA | Por qué la propuso | Veredicto | Razón (en palabras de Sophia) | Qué cambió |
|---|---|---|---|---|---|
| 0.11 | Buscador grande dentro del hero, debajo del titular. | Patrón de Airbnb. | Revisar | Me gustaría que lo de destino, llegada, salida y huéspedes estuviera arriba. Wander, me gusta mucho que la barra buscadora la tiene arriba, no se ve tan grande. | Buscador compacto en la cabecera. |
| 0.12 | Imagen del hero en una columna lateral 4:5. | Legibilidad y peso. | Revisar | El fondo de pantalla me gusta, como una imagen; crea un repositorio de imágenes y conéctala. | Hero con foto a lo ancho y carpeta assets/img con LEEME.md. |
| 0.13 | Sellos de confianza entre el hero y las propiedades. | Poner la promesa antes de la oferta. | Revisar | Hay que quitarlo para ponerlo abajo, yo creo. O ponerlo como en otra página. | Sellos y cómo funciona debajo de las propiedades. |
| 0.14 | Sección de anfitriones, planes y comparativa en la portada. | Una sola página con todo el modelo. | Rechazar | Anfitriones tienen que ser de otra página web. Forzosamente. En la página principal solo se vean las propiedades. Para no revolverlos. | Página nueva web/anfitriones.html. |
| 0.15 | Cuatro propiedades de muestra en Ciudad de México. | Bastaban para probar el filtro. | Revisar | Hay que poner otros dos para que sean seis. | Dos propiedades más en datos.js. |

#### Prompt 3: Portada solo con buscador y propiedades; cómo funciona aparte; pie verde (18 de octubre de 2026, noche)

**Rol.** Eres un ingeniero de software senior, experto en desarrollo web (UX, frontend y backend) y en arquitectura de plataformas. Trabajas en el proyecto Íntegro, una plataforma de rentas de corta estancia por suscripción.

**Tarea.** Quita todo el texto del hero y coloca ahí el buscador. Deja la cabecera solo con Íntegro y un botón "Conviértete en anfitrión" que lleve a la página de anfitriones. Mueve los sellos de confianza y los tres pasos para reservar a una página aparte llamada "Cómo funciona". Cambia el pie de página a verde, quita "Hospedajes", conserva Cómo funciona, Anfitriones, Términos y Aviso de privacidad, y destaca "Reportar un problema", que es muy importante. Con esto la portada queda lista como primer avance.

**Contexto.** La portada debe mostrar solo propiedades para que el huésped elija. Cómo funciona interesa más al anfitrión y quizá termine dentro de su página. Términos y Aviso no necesitan enlace todavía.

**Salida esperada.** Al terminar, entrega: la fecha, la carpeta o archivo que se creó o modificó, por qué se modificó, qué sugerencias hiciste y por qué, y las líneas o secciones modificadas. Todo en el repositorio de GitHub y desglosado para la bitácora.

**Respuesta de la IA**

- Fecha: 18 de octubre de 2026. Commits: 80894c4 y 7482304 (tras integrar las ediciones de Sophia en GitHub: f4768e9, 8a69ce7 y 61d6b3a).
- Carpetas y archivos, y por qué:
  - `web/index.html`: cabecera mínima, hero con imagen y buscador al centro sin texto, seis propiedades, pie verde con reporte destacado.
  - `web/como-funciona.html (nuevo)`: encabezado con las tres promesas, cuatro sellos y tres pasos para reservar.
  - `web/anfitriones.html, web/propiedad.html`: cabeceras y pies iguales a la portada; se retira "Entrar".
  - `web/assets/css/estilos.css`: token --color-pie, bloque Pie, .btn-reportar, .encabezado-pagina, .buscador al centro del hero.
  - `README.md, PROMPT_LOG.md, docs/diseno/*.md`: referencias corregidas tras el borrado de docs/assignment-2 y bitácora actualizada.
- Sugerencias de la IA y por qué:
  - Quitar "Entrar" de todas las cabeceras. Por qué: la instrucción fue dejar solo la marca y el botón de anfitrión; el inicio de sesión es Must del MVP y queda como pendiente 0.20.
  - Interpretar "el verde que se usa como fondo" como un verde profundo derivado del acento. Por qué: la portada no tenía fondos verdes; se dejó en un token para cambiarlo en un lugar.
  - Aplicar el pie simplificado de Sophia (solo la marca, sin nota de nombre provisional ni línea de seguridad) a las cuatro páginas. Por qué: ella lo editó en la portada desde GitHub; las páginas deben ser consistentes.
- Líneas o secciones modificadas: index.html completo. estilos.css: :root (--color-pie), bloque Pie, .buscador, .hero-contenido. anfitriones.html y propiedad.html: bloques header y footer.

**Decisiones de Sophia**

| N | Propuesta de la IA | Por qué la propuso | Veredicto | Razón (en palabras de Sophia) | Qué cambió |
|---|---|---|---|---|---|
| 0.16 | Titular con las tres promesas y subtítulo sobre la imagen del hero. | Poner la promesa donde Wander pone su lema. | Rechazar | Eso lo vamos a quitar, todo lo vamos a quitar. | Hero solo con imagen y buscador. |
| 0.17 | Buscador compacto dentro de la cabecera (segunda revisión). | Seguir la barra de Wander. | Revisar | Donde está la imagen vamos a colocar lo de destino, llegada, salida. En el header solo quede Íntegro y conviértete en anfitrión. | Buscador al centro del hero; cabecera mínima. |
| 0.18 | Sellos y tres pasos al final de la portada. | Mantener la explicación en la misma página. | Revisar | Eso que va en texto lo vamos a colocar en una página aparte que va a ser cómo funciona. | Página web/como-funciona.html. |
| 0.19 | Pie claro con seis enlaces y el reporte como uno más. | Pie neutro. | Revisar | Que tenga un color, el verde que se usa como fondo. Quitar hospedajes. Reportar un problema, eso sí es muy importante. | Pie verde, sin Hospedajes, reporte como botón. |
| 0.20 | La IA quitó "Entrar" de las cabeceras. | Instrucción literal; el prototipo no tiene inicio de sesión. | `[SOPHIA]` | `[SOPHIA]` | Decidir dónde vivirá Entrar. |

#### Prompt 4: Eslogan, cabecera sin bordes, pie blanco y ficha reorganizada (18 de octubre de 2026, noche)

**Rol.** Eres un ingeniero de software senior, experto en desarrollo web (UX, frontend y backend) y en arquitectura de plataformas. Trabajas en el proyecto Íntegro, una plataforma de rentas de corta estancia por suscripción.

**Tarea.** El buscador se queda al centro, pero la zona se ve vacía: agrega arriba un eslogan como "Su lugar íntegro", con "íntegro" en azul. Coloca "Conviértete en anfitrión" más a la izquierda y sin bordes. El pie vuelve a blanco con el mismo acomodo, y "Reportar un problema" en un color que resalte. Quita todos los separadores " · " de los textos. En la ficha, la ubicación debe abrir Google Maps, y ubicación y reseñas salen de la columna de descripción a secciones que abarquen todo el ancho, porque se pierde espacio junto a la caja de reserva. En la página de anfitrión, el botón "Publica tu propiedad" no puede ser verde.

**Contexto.** Es un juego de palabras con el nombre. Las reseñas funcionan por ahora como un foro. Lo demás de la portada y de la página de anfitrión sigue bien.

**Salida esperada.** Al terminar, entrega: la fecha, la carpeta o archivo que se creó o modificó, por qué se modificó, qué sugerencias hiciste y por qué, y las líneas o secciones modificadas. Todo en el repositorio de GitHub y desglosado para la bitácora.

**Respuesta de la IA**

- Fecha: 18 de octubre de 2026. Commits: ae907ba y 3a90077 (tras integrar d0ece85, la imagen de anfitriones que subió Sophia).
- Carpetas y archivos, y por qué:
  - `web/index.html`: eslogan "Su lugar, íntegro." sobre el buscador; enlace de anfitrión junto a la marca; pie blanco.
  - `web/propiedad.html`: ubicación y reseñas como secciones a lo ancho debajo de las dos columnas; el mapa y un botón abren Google Maps.
  - `web/anfitriones.html, web/como-funciona.html`: botones azules en anfitriones; cabecera con enlaces de texto; pie blanco.
  - `web/assets/css/estilos.css`: tokens --color-pie (blanco) y --color-resalte; .eslogan, .resalte, .enlaces-cabecera, .btn-azul, .pie, .bloque-ancho, .mapa-aproximado, .resenas-lista.
  - `web/assets/js/app.js`: función plural; textos de tarjeta y ficha sin separadores; enlace a Google Maps con colonia y ciudad.
- Sugerencias de la IA y por qué:
  - Escribir el eslogan con coma: "Su lugar, íntegro." Por qué: espeja "Tu ingreso, íntegro." de la página de anfitriones; Sophia decide si se queda y si prefiere tú en vez de su.
  - Azul claro para la palabra resaltada, en un token. Por qué: sobre una foto oscura un azul oscuro no se vería.
  - Enlazar a Google Maps con la colonia y la ciudad, nunca con la dirección exacta. Por qué: regla de seguridad: la dirección se comparte solo con reserva confirmada.
  - Dejar "Buscar" y "Reservar" en verde. Por qué: Sophia solo mencionó los botones de la página de anfitrión; pendiente confirmar si el verde sale de todos.
  - Plurales calculados ("1 baño"). Por qué: al quitar los separadores se vio que "1 baños" estaba mal.
- Líneas o secciones modificadas: estilos.css: :root, .eslogan y .resalte, .enlaces-cabecera, .btn-azul, bloque Pie, .bloque-ancho, .mapa-aproximado, .resenas-lista y media query de 720 px. app.js: plural, tarjeta, pintarFicha (campos capacidad y calif, enlace [data-mapa]). propiedad.html: estructura después de .ficha-cuerpo. anfitriones.html: tres botones con .btn-azul.

**Decisiones de Sophia**

| N | Propuesta de la IA | Por qué la propuso | Veredicto | Razón (en palabras de Sophia) | Qué cambió |
|---|---|---|---|---|---|
| 0.21 | Hero solo con imagen y buscador, sin texto (aplicado en 0.16 a petición suya). | Instrucción previa. | Revisar | Ahora lo veo un poco pelón. Se coloque un eslogan, algo como su lugar íntegro, haciendo un juego de palabras. | Eslogan con íntegro en azul claro. |
| 0.22 | Botón de anfitrión con borde, a la derecha. | Patrón List on Wander. | Revisar | Hay que colocarlo más a la izquierda y no me gusta que tenga bordes. | Enlace de texto junto a la marca. |
| 0.23 | Pie verde profundo con botón blanco. | Interpretación del verde de fondo. | Rechazar | Ya no me gustó el color, sí lo prefiero blanco. Me gusta el acomodo. Reportar un problema de algún otro color que resalte. | Pie blanco; reporte en azul. |
| 0.24 | Separador " · " entre datos. | Convención de Airbnb y Wander. | Rechazar | Quita todos los puntos que aparecen en los textos. | Comas, paréntesis y líneas separadas. |
| 0.25 | Ubicación y reseñas dentro de la columna de descripción; mapa sin enlace. | Agrupar el contenido junto a la caja de precio. | Revisar | Se pierde mucho espacio entre la descripción y la reserva. Que abarque todo. Redireccionamiento a Google Maps. | Secciones a lo ancho; mapa y botón abren Google Maps por zona. |
| 0.26 | Botones verdes en la página de anfitrión. | Un solo color de botón principal. | Rechazar | Publica tu propiedad, ese color verde tampoco me gusta. | Botones azules (.btn-azul). |
| 0.27 | Textos de apoyo en el prototipo y el repositorio: subtítulo del hero de anfitriones, notas de "montos por confirmar" y "comparación sin cifras", comentarios HTML explicativos, "íntegro" en minúscula en el eslogan y encabezado "Para el profesor" en el README. | Dar contexto a quien lee el prototipo y el repositorio. | Revisar | Ediciones directas de Sophia en GitHub, sin prompt: "Íntegro" con mayúscula en el eslogan, "¿Cómo funciona?" y "¿Cómo empezar?" con signos de interrogación, sin notas ni comentarios, y README sin referencias al curso. | Commits de Sophia 15a6599 a a712ba6; la IA corrigió después la errata "Ìntegro" por "Íntegro" en anfitriones.html. |

#### Prompt 5: Entrega al profesor y bitácora presentable (18 de octubre de 2026, noche)

**Rol.** Eres el mismo ingeniero senior y además redactas documentación técnica clara para un lector de negocios que sabe programar.

**Tarea.** Dime qué debo entregarle a Oscar para el Assignment 2 y redáctalo en formato escrito con enlaces. Haz un documento en Word, sencillo y rápido, de unas cinco páginas, que explique el nuevo proyecto. Incluye en el documento la bitácora de prompts, con cada prompt presentable en la estructura rol, tarea, contexto y salida, y la respuesta de la IA desglosada: fecha, carpeta o archivo modificado, por qué, sugerencias y líneas.

**Contexto.** Cambio el proyecto del curso de LÍA a Íntegro por confidencialidad; LÍA sigue aparte hasta diciembre. La entrega se sube en el espacio del Assignment aunque el enunciado parta del repositorio del Assignment 1. Mis prompts originales son hablados y repetitivos; deben verse presentables sin cambiar lo que pedí.

**Salida esperada.** Documento Word en el escritorio, texto listo para pegar en Forum con los enlaces, y la bitácora actualizada en el repositorio con la misma estructura.

**Respuesta de la IA**

- Fecha: 18 de octubre de 2026. Commits: (bitácora regenerada en el repositorio; el Word vive fuera del repositorio).
- Carpetas y archivos, y por qué:
  - `Escritorio/Integro_Presentacion_Oscar_2026-10-18.docx`: presentación de seis secciones más el anexo con esta bitácora.
  - `PROMPT_LOG.md (sección 2.0)`: regenerada desde una fuente de datos única para que el repositorio y el Word digan lo mismo.
- Sugerencias de la IA y por qué:
  - Añadir una nota de transparencia que diga que los prompts se transcriben en limpio. Por qué: la rúbrica evalúa el juicio sobre lo que la IA propone; una transcripción fiel y ordenada es legítima, una reescritura silenciosa no.
  - Dejar el enlace del deploy como hueco a llenar. Por qué: todavía no existe un deploy de Íntegro.
  - Tratar la entrega de hoy como aviso de cambio y primer avance, no como la entrega final. Por qué: la entrega final exige la función construida y validada, que llega después de la Sesión 19.
- Líneas o secciones modificadas: PROMPT_LOG.md entre los marcadores de la sección 2.0; el Word se genera completo cada vez.

<!-- bitacora:fin -->

### 2.1 Entradas durante la construcción de la función

Mínimo una entrada que cite qué campo de la especificación estaba en juego. Para el nivel 5, un patrón repetido: propuesta de la IA, cuestionamiento, ajuste o rechazo justificado.

```
Prompt 6 · [SOPHIA] fecha
Rol: [SOPHIA]
Tarea: [SOPHIA] (cita la especificación de la sección 1)
Contexto: [SOPHIA]
Salida: [SOPHIA]

Respuesta de la IA: fecha, archivos, por qué, sugerencias, líneas.

Entrada 1
Campo de la especificación en juego: [SOPHIA]
Qué propuso la IA: [SOPHIA]
Veredicto: [SOPHIA]
Razón: [SOPHIA]
Qué cambió en el código: [SOPHIA]
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
| Enlace del repositorio | https://github.com/sophiieees/integro |
| Bitácora | Este archivo, `PROMPT_LOG.md`, en la raíz del repositorio |

---

## 5. Por qué la función resuelve el problema que se propuso resolver

`[SOPHIA]` Dos o tres párrafos que citen la especificación de la sección 1: qué problema de Íntegro ataca la función, cómo el criterio de éxito demuestra que lo resuelve (más allá de que el caso de prueba haya pasado), y qué quedó fuera a propósito.

---

## 6. Uso de IA

`[SOPHIA]` Qué herramienta o herramientas usaste, para qué las usaste, y qué decidiste o verificaste tú. (Este campo es obligatorio en la entrega; si no se usó IA, se escribe "No usé IA en esta entrega".)
