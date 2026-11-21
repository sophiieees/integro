# Sistema de diseño del prototipo

Nació como propuesta en octubre de 2026. Desde el 19 de noviembre de 2026 la paleta y la tipografía son las del manual de identidad de Íntegro (`manual-de-identidad.pdf`, en esta carpeta), aplicadas con las reglas del ADR 0008. El diseño es de Sophia. Todo vive en tokens de `web/assets/css/estilos.css`, para que la identidad se aplique cambiando valores y no reescribiendo páginas. El logotipo sigue pendiente.

## Principios

1. **La confianza se muestra, no se promete.** La verificación del anfitrión, el momento en que cobra, el precio total y la entrada con chapa aparecen en la tarjeta y en la ficha, no en una página de "por qué confiar".
2. **Calma.** Dos colores de marca, mucho espacio, nada parpadea ni se mueve en bucle. La única animación es la entrada de los elementos al hacer scroll, una sola vez.
3. **Ligereza.** Sin librerías, y una sola tipografía guardada en el proyecto (Outfit, 47 KB en dos archivos): la página de búsqueda tiene presupuesto de 400 KB y la ficha de 1.2 MB (MVP técnico).
4. **Contexto mexicano.** Pesos mexicanos, español, CLABE, INE, ciudades reales. Nada traducido del inglés.

## Tokens

| Token | Valor | Uso |
|---|---|---|
| `--color-primario` | `#1F4D3A` verde íntegro (manual) | La marca, todos los botones, el hero sin foto, el total sin cargos |
| `--color-primario-oscuro` | `#142A21` verde noche (manual) | El botón con el cursor encima; fondos oscuros (hero, comparativa) |
| `--color-primario-suave` | `#E4ECE7` | Fondos suaves, pastilla de "anfitrión nuevo". Tono propio, derivado del verde íntegro |
| `--color-acento` | `#C9A66B` dorado arena (manual) | Solo en botones o en algo que resalte: el botón al dar clic, "Reportar un problema", rombos y líneas. Nunca en texto corrido |
| `--color-acento-texto` | `#8A6A2F` dorado texto (manual) | Etiquetas de sección y numerales de los pasos |
| `--color-acento-suave` | `#E2F2E9` | Pastillas, caja de chapa, fila destacada de planes. Se conserva de octubre |
| `--color-fondo` | `#F3EEE4` arena (manual) | Fondo general |
| `--color-superficie` | `#FFFFFF` | Cabecera, cajas, sellos |
| `--color-tinta` / `--color-tinta-suave` | `#142A21` verde noche (manual) / `#5A6872` | Texto principal y secundario. El secundario se conserva de octubre |
| `--color-borde` | `#E2DED5` | Líneas divisorias |
| `--color-alerta` | `#B8432A` | Errores y avisos de fraude (reservado; aún sin uso en el prototipo) |
| `--color-pie` | `#FFFFFF` | Fondo del pie de página (Sophia lo prefiere blanco; el verde se probó y se descartó) |
| `--color-resalte` | `#C9A66B` dorado arena (manual) | La palabra "Íntegro" del eslogan sobre la foto del hero |
| `--fuente-titulos` | Outfit; alternas Helvetica Neue y Arial | Títulos, números de paso, nombre de la marca, en SemiBold (600) |
| `--fuente-texto` | Outfit; alternas Helvetica Neue y Arial | Todo lo demás, en Regular (400) |
| `--radio` / `--radio-chico` | 10 px / 6 px | Cajas y botones. Esquinas discretas a propósito. |
| `--sombra` | Dos capas suaves | Buscador, caja de precio, planes |
| `--ancho-max` | 1180 px | Contenedor |

Para cambiar la paleta: editar `:root` en `estilos.css`. Nada más.

## Tipografía

- Una sola familia, Outfit, la del manual de identidad. Títulos en SemiBold (600), interlineado 1.15; texto en Regular (400), 16 px, interlineado 1.55.
- Los archivos de la fuente están en `web/assets/fonts/` (`outfit-latin.woff2` y `outfit-latin-ext.woff2`, con su licencia `OFL.txt`): no se piden a Google en cada visita (ADR 0008). Si no cargan, se usan las alternas del manual.
- Etiquetas de sección en mayúsculas pequeñas con espaciado de letra (`.etiqueta`), en dorado texto.

## Componentes

| Componente | Dónde | Qué comunica |
|---|---|---|
| Cabecera fija con la marca y enlaces de texto (`.enlaces-cabecera`) | Todas | La marca y, junto a ella, los enlaces de la vista de quien mira (visitante, cliente, anfitrión o administrador; `docs/diseno/vistas.md`). Visitante y cliente: la barra «Todo», «Alojamientos», «Experiencias» y «Servicios», con la pestaña de la página subrayada en dorado arena (`aria-current`), y a la derecha «Conviértete en anfitrión». A la derecha, la cuenta (`[data-cuenta]`): «Iniciar sesión» y «Crear cuenta», o el nombre de la persona con un menú de texto (`.cuenta-menu`, `.cuenta-lista`) que termina en «Cerrar sesión»; la flecha del menú se dibuja con bordes, no es un ícono. La arma `web/assets/js/estructura.js`, una sola copia, según la vista y la página (`data-cabecera`: `portada`, `interior` o `anfitriones`); `cuenta.js` la vuelve a armar cuando sabe quién tiene sesión. En celular, la barra baja bajo la marca y «Conviértete en anfitrión» se oculta |
| Página de una vista (`.pagina-vista`, `.vista-seccion`) | `mi-cuenta.html`, `anfitrion.html`, `administracion.html`, `proximamente.html` | Un título, una frase y una sección por cada función, separadas por una línea; las que todavía no existen dicen «Próximamente». Las tres primeras llevan `data-requiere` y muestran su contenido solo a quien puede verlo; a los demás, una explicación y a dónde ir (`.aviso-acceso`) |
| Registro (`.registro`, `.formulario-tarjeta`) | `registro.html` | Página aparte, porque pide más datos: nombre, apellidos, correo, contraseña, teléfono (código de marcación y número), país de residencia y fecha de nacimiento. Tres pasos en la misma tarjeta: los datos, el código que llega al correo y «Tu cuenta está lista». Quien se equivocó de correo lo corrige desde el paso del código, con su contraseña. Los datos llevan la casilla de términos y aviso de privacidad, sin nada que desplegar mientras no haya texto legal. Avisos en cada campo, en tono formal, de tú. La lógica vive en `registro-logica.js`, sin pantalla, para probarse con node |
| Recuperar la contraseña (`.registro`, `.formulario-tarjeta`, `.fortaleza`) | `recuperar-contrasena.html` | Página aparte con la misma tarjeta del registro y tres pasos: el correo; el código de 6 dígitos con la contraseña nueva y el indicador del registro; y «Tu contraseña cambió», con «Iniciar sesión». La respuesta al pedir el código es la misma tenga o no cuenta ese correo, y el texto no promete que llegó. Si la contraseña es fácil de adivinar, el campo trae una sola línea que remite a los consejos del indicador. Con una sesión iniciada pide cerrarla primero. Se llega desde «¿Olvidaste tu contraseña?» en la ventana de iniciar sesión (`.ventana-olvido`). La lógica vive en `recuperar-logica.js`, sin pantalla, para probarse con node |
| Indicador de la contraseña (`.fortaleza`) | Registro | Cuatro cuadros que se llenan según el nivel que contesta la API (bajo 1, medio 2, confiable 3, muy confiable 4), el nombre del nivel y los consejos. Colores de la paleta: alerta en bajo, dorado arena en medio (solo relleno, nunca letra) y verde íntegro en confiable y muy confiable |
| Ventana de "Iniciar sesión" (`.ventana`) | Todas, sobre la página | Dos pasos: correo y contraseña, y el código de 6 dígitos. Al terminar se cierra y la persona sigue donde estaba. Avisos en el color de alerta y en tono formal, de tú; enlace a registro.html. La lógica vive en `cuenta-logica.js`, sin pantalla, para probarse con node |
| Eslogan (`.eslogan`) | Hero de la portada | "Su lugar, Íntegro." en blanco con "Íntegro" en dorado arena; juego de palabras con el nombre |
| Buscador de cuatro campos y botón (`.buscador`) | Centro del hero de la portada, bajo el eslogan | Destino, llegada, salida, huéspedes, sobre la imagen de bienvenida; en celular se apila en dos columnas |
| Botones (`.btn-primario` y `.btn-azul`) | Todas | Regla del ADR 0008: fondo verde íntegro con letra blanca; con el cursor encima, verde noche; al dar clic, dorado arena con la letra en verde noche. Las dos clases se ven igual; `.btn-azul` conserva su nombre de octubre |
| Hero con imagen de fondo (`.hero`) | Portada y anfitriones | Foto a lo ancho con velo oscuro. En la portada solo lleva el buscador; en anfitriones lleva titular. Sin imagen, degradado y marcador que dice qué archivo guardar |
| Encabezado de página interior (`.encabezado-pagina`) | Cómo funciona | Etiqueta, titular de las tres promesas e introducción, sobre el fondo papel |
| Sello de confianza (`.sello`) | Cómo funciona | Cuatro promesas con línea superior dorada; elementos libres, sin cajas ni iconos |
| Pie de página blanco (`.pie`) con botón "Reportar un problema" | Todas | Lo arma `estructura.js`, igual en todas. Fondo `--color-pie`, enlaces a Cómo funciona, Anfitriones, Términos y Aviso; el reporte es un botón en dorado arena con letra verde noche (ADR 0008), porque es la vía de protección del huésped y debe verse |
| Secciones a lo ancho de la ficha (`.bloque-ancho`) | Ficha | Ubicación (mapa de zona que abre Google Maps con colonia y ciudad) y reseñas en dos columnas, debajo de la descripción y la caja de precio, para que la columna de texto no deje hueco junto a la caja |
| Textos sin separador " · " | Todas | Sophia pidió quitar todos los puntos medios: se usan comas, paréntesis y líneas separadas |
| Tarjeta de propiedad (`.tarjeta`) | Inicio | Foto, insignias "Anfitrión verificado" y "Chapa inteligente", título, zona, calificación, precio por noche y total de 2 noches sin cargos |
| Insignia (`.insignia`) y pastilla (`.pastilla`) | Tarjeta y ficha | Estado del anfitrión (verificado o nuevo) y chapa. El rombo dorado es la marca de "verificado" en todo el sitio |
| Pasos numerados (`.pasos`) | Inicio | Cómo reservar, con numerales grandes en dorado texto |
| Tabla de planes (`.tabla`) | Anfitriones | Membresía por propiedades activas; fila destacada en verde |
| Tabla comparativa (`.tabla-comparativa`) | Anfitriones, fondo oscuro | Modelo por comisión frente a Íntegro, sin cifras de terceros |
| Caja de precio (`.caja-precio`) | Ficha, fija al hacer scroll | Desglose con "Comisión de plataforma $0" en verde íntegro; es la pantalla donde la promesa de precio total se cumple |
| Mapa aproximado (`.mapa-aproximado`) | Ficha | Círculo de zona, sin pin exacto: la ubicación exacta solo con reserva confirmada |

## Reglas de estilo aplicadas

- Sin emojis ni iconos en las secciones. Las viñetas son rombos o cuadrados pequeños en el color de marca.
- Esquinas discretas (6 a 10 px). Preferencia por elementos libres sobre el fondo en vez de cajas; las únicas cajas son las que necesitan destacarse (buscador, planes, caja de precio).
- Animaciones solo al entrar en pantalla, una sola vez (`.revelar`), y desactivadas si el sistema pide movimiento reducido.
- Las imágenes las coloca Sophia en `web/assets/img/` con los nombres de `web/assets/img/LEEME.md` (`imagen-bienvenida.jpg` para el hero, `propiedad-<id>-<n>.jpg` para tarjetas y galería). Si un archivo no existe, la página muestra el marcador; en cuanto existe, aparece la foto.
- Contraste mínimo AA en texto; foco visible en verde íntegro; etiquetas en todos los campos de formulario. El dorado arena no se usa como color de letra: sobre fondo claro no alcanza el contraste.

## Responsivo

| Corte | Qué cambia |
|---|---|
| Más de 960 px | Buscador en una línea al centro del hero; cuatro sellos en fila (cómo funciona); ficha en dos columnas con caja de precio fija |
| 720 a 960 px | Sellos en dos columnas; ficha en una columna; el buscador sigue en una línea |
| Menos de 720 px | Buscador en dos columnas (destino y huéspedes a lo ancho); en las páginas interiores el botón de anfitrión se oculta y queda el enlace del pie; sellos y pasos en una columna |

Los enlaces a Cómo funciona y Anfitriones viven en el pie de página en todos los tamaños.

## Pendientes de diseño

- Logotipo: todavía no se tiene; la cabecera usa el nombre con un rombo dorado. El nombre definitivo sigue sujeto al registro de marca.
- Fotografías reales de propiedades en la ciudad de lanzamiento.
- Las 12 pantallas restantes (ver `pantallas.md`).
- Textos legales: términos, aviso de privacidad, política de cancelación con plazos definidos.
- Menú para celular. Los estados de error de la ventana de "Iniciar sesión" ya existen; faltan los del registro.
