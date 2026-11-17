# -*- coding: utf-8 -*-
"""Bitácora de prompts de Íntegro (Assignment 2), fuente única para PROMPT_LOG.md y para el Word.

Cada prompt se transcribe en limpio con la estructura rol, tarea, contexto y salida.
La conversación original fue hablada y más larga; el contenido es el mismo.
Los veredictos y razones de Sophia se citan con sus palabras.
"""

NOTA_TRANSPARENCIA = (
    "Los prompts se transcriben en limpio con la estructura rol, tarea, contexto y salida; la conversación "
    "original con el asistente fue hablada y más extensa, pero las peticiones, las propuestas de la IA y los "
    "veredictos son los mismos. Las razones de Sophia se citan con sus palabras."
)

ROL_BASE = ("Eres un ingeniero de software senior, experto en desarrollo web (UX, frontend y backend) y en "
            "arquitectura de plataformas. Trabajas en el proyecto Íntegro, una plataforma de rentas de corta "
            "estancia por suscripción.")

# Rol único desde el prompt 6 (16 de noviembre de 2026): es el mismo de CLAUDE.md.
# Desde ese prompt cada entrada se lee en el orden rol, contexto, tarea y salida.
ROL_PROYECTO = ("Actúas como ingeniero de software senior del proyecto, encargado y experto en la base de datos, "
                "backend, experiencia de usuario, ciberseguridad, documentación, frontend, estructuras de programación "
                "e inteligencia artificial.")

SALIDA_BASE = ("Al terminar, entrega: la fecha, la carpeta o archivo que se creó o modificó, por qué se modificó, "
               "qué sugerencias hiciste y por qué, y las líneas o secciones modificadas. Todo en el repositorio de "
               "GitHub y desglosado para la bitácora.")

PROMPTS = [
    # ------------------------------------------------------------------ 1
    {
        "n": 1,
        "titulo": "Diseño de la web, arquitectura y base del Assignment 2",
        "fecha": "18 de octubre de 2026, tarde",
        "rol": ROL_BASE,
        "tarea": ("Diseña cómo se verá la página web de Íntegro con un estilo propio, tomando como referencia las "
                  "capturas de Airbnb y Wander, y súbela al repositorio de GitHub de mi cuenta profesional. Arma además "
                  "la base de la arquitectura del sistema y la documentación completa para el Assignment 2, cuyo objetivo "
                  "es el nivel 5 de la rúbrica, sin que falte ningún punto. Si tienes dudas, pregunta."),
        "contexto": ("Documentos adjuntos: requerimientos de la plataforma, cronograma de entregables, MVP técnico con "
                     "método MoSCoW, ciberseguridad (amenazas, controles y respuesta), mapa de etapas y chapa inteligente. "
                     "Notas sobre iCal, importación desde Airbnb y verificación de propiedades en México. Capturas de Airbnb "
                     "y Wander. El nombre Íntegro es provisional, no hay paleta de colores y la marca vende seguridad. "
                     "El proyecto es mucho más grande que la tarea; la tarea se adapta a él."),
        "salida": SALIDA_BASE,
        "respuesta": {
            "fecha": "18 de octubre de 2026",
            "commits": "30565d4, 559b8f1 y a1bac93",
            "archivos": [
                ("README.md, .gitignore, index.html (raíz), vercel.json",
                 "base del repositorio, mapa de carpetas, tabla para el profesor y configuración de publicación."),
                ("web/index.html, web/propiedad.html, web/assets/css/estilos.css, web/assets/js/app.js, web/assets/js/datos.js",
                 "prototipo estático de la portada y la ficha, con la paleta y la tipografía en tokens de :root y datos ficticios."),
                ("docs/arquitectura.md y docs/decisiones/0001 a 0011",
                 "arquitectura objetivo condensada de los documentos del equipo y un registro por decisión."),
                ("docs/diseno/sistema-de-diseno.md, benchmark-competencia.md, pantallas.md, capturas/",
                 "sistema de diseño, comparación con Airbnb y Wander y lista de pantallas."),
                ("PROMPT_LOG.md y docs/assignment-2/ (funciones candidatas y guía de rúbrica)",
                 "estructura de la bitácora y material de apoyo; Sophia borró después docs/assignment-2 desde GitHub."),
            ],
            "sugerencias": [
                ("Prototipo en HTML, CSS y JavaScript sin dependencias en lugar de Next.js.",
                 "la máquina tenía 734 MB libres en disco y el prototipo debía abrirse con doble clic y publicarse sin compilar; los tokens migran a Tailwind."),
                ("Paleta de seguridad (azul profundo, verde para lo verificado, fondo papel) y serif en títulos, solo como valores iniciales en tokens.",
                 "la identidad de marca llega el 30 de octubre; así se cambia en un solo lugar."),
                ("No construir ninguna cotización en el prototipo.",
                 "la función real del assignment debe nacer de la especificación de Sophia, no al revés."),
                ("Omitir el chip de ahorro de Wander y los favoritos.",
                 "los requerimientos los ponen en segunda fase."),
            ],
            "lineas": "Todo el contenido es nuevo; el detalle línea por línea está en el diff de los tres commits.",
        },
        "decisiones": [
            ("0.1", "Prototipo estático (HTML, CSS, JS) en lugar de Next.js, que es lo que fija el MVP técnico.", "Disco con 734 MB libres; cero dependencias; publicación sin compilar.", "Pendiente", "Está en revisión.", "ADR 0008 como propuesta."),
            ("0.2", "Paleta azul profundo, verde íntegro y papel cálido.", "Sophia pidió algo que comunique seguridad; vive solo en tokens.", "Pendiente", "No se ha definido la paleta de colores.", "Tokens en :root de estilos.css."),
            ("0.3", "Serif del sistema en títulos, sans en texto.", "Diferencia frente a Airbnb y Wander; fuentes del sistema por peso.", "Pendiente", "No se ha definido tipografía.", "Tokens de tipografía."),
            ("0.4", "Omitir el chip de ahorro frente a otras plataformas.", "Es de segunda fase en los requerimientos.", "Pendiente", "Necesita revisión del equipo.", "Se muestra el total sin cargos de servicio."),
            ("0.5", "Omitir favoritos (corazón) en las tarjetas.", "Segunda fase y Could have.", "Rechazar", "Se colocará más adelante.", "Sin corazón por ahora."),
            ("0.6", "Sin cálculo de cotización; total fijo de ejemplo.", "La función del assignment debe nacer de la especificación.", "Rechazar", "Se colocará más adelante.", "Caja de precio con nota."),
            ("0.7", "Ciudad de México como ciudad por defecto de los datos de muestra.", "Hacía falta una ciudad; la de lanzamiento se decide antes del 30 de octubre.", "Pendiente", "Necesita revisión del equipo.", "datos.js, ciudadPorDefecto."),
            ("0.8", "Mostrar los montos de la propuesta inicial de planes.", "Dan realismo; el pricing lo define Valeria el 30 de octubre.", "Pendiente", "Necesita revisión del equipo.", "Tabla de planes."),
            ("0.9", "Sin iconos ni emojis, esquinas discretas, animaciones solo al entrar.", "Preferencias que Sophia dio en otro proyecto.", "Aceptar", "La página debe verse formal.", "Reglas del sistema de diseño."),
            ("0.10", "Plazos de ejemplo en las políticas de cancelación.", "La ficha necesitaba texto; la revisión legal los define.", "Pendiente", "Necesita revisión del equipo.", "Ficha, marcado como propuesta."),
        ],
    },
    # ------------------------------------------------------------------ 2
    {
        "n": 2,
        "titulo": "Primera revisión visual de la portada",
        "fecha": "18 de octubre de 2026, noche",
        "rol": ROL_BASE,
        "tarea": ("Modifica la portada: la barra de destino, llegada, salida y huéspedes debe ir arriba, compacta como la de "
                  "Wander; el hero lleva una imagen de fondo a lo ancho; se muestran seis propiedades de Ciudad de México; los "
                  "sellos de confianza bajan debajo de las propiedades; la sección de anfitriones se va a una página aparte, "
                  "porque la portada es solo para el huésped. Crea una carpeta de imágenes con nombres fijos para que yo "
                  "coloque las fotos."),
        "contexto": ("Capturas de Airbnb y Wander: ambas dirigen la portada al huésped y ponen la entrada del anfitrión como un "
                     "botón. Todavía no hay logo ni fotografías. La ficha de propiedad, con su mapa, gusta y se conserva."),
        "salida": SALIDA_BASE,
        "respuesta": {
            "fecha": "18 de octubre de 2026",
            "commits": "5382b40",
            "archivos": [
                ("web/index.html", "cabecera con la barra de búsqueda compacta, hero con imagen de fondo, seis propiedades, sellos y cómo funciona debajo; sin la sección de anfitriones."),
                ("web/anfitriones.html (nuevo)", "beneficios, planes, tres pasos para publicar y comparativa frente a plataformas por comisión."),
                ("web/assets/css/estilos.css", "secciones Cabecera, Buscador, Hero, Tarjetas (foto real opcional) y Responsivo; tonos nuevos para Polanco y Juárez."),
                ("web/assets/js/app.js", "función tarjeta (imagen real si existe) y revelado al hacer scroll por posición, en lugar de IntersectionObserver."),
                ("web/assets/js/datos.js", "propiedades 8 (Polanco) y 9 (Juárez) para llegar a seis en Ciudad de México."),
                ("web/assets/img/LEEME.md", "nombres de archivo que esperan las páginas: imagen-bienvenida.jpg y propiedad-<id>-<n>.jpg."),
                ("docs/diseno/*.md, README.md, PROMPT_LOG.md", "documentación y bitácora actualizadas."),
            ],
            "sugerencias": [
                ("Mover la insignia de chapa a la esquina inferior de la foto.", "en tarjetas de 260 px se encimaba con la de anfitrión verificado."),
                ("Dejar cómo funciona al final de la portada junto a los sellos.", "Sophia no definió dónde iba; se ofreció moverlo a otra página."),
                ("Revelado por posición en lugar de IntersectionObserver.", "en una prueba a 900 px el observador dejó cuatro tarjetas invisibles; el contenido no puede depender de una animación."),
                ("Mecanismo de fotos opcionales con marcador.", "si el archivo no existe, la página muestra el marcador; al guardarlo aparece la foto sin tocar código."),
            ],
            "lineas": "estilos.css: bloques .cabecera, .buscador, .hero, .tarjeta-foto img, media queries de 1080 y 720 px. app.js: función tarjeta y funciones registrarRevelado y revelarVisibles. datos.js: objetos con id 8 y 9.",
        },
        "decisiones": [
            ("0.11", "Buscador grande dentro del hero, debajo del titular.", "Patrón de Airbnb.", "Revisar", "Me gustaría que lo de destino, llegada, salida y huéspedes estuviera arriba. Wander, me gusta mucho que la barra buscadora la tiene arriba, no se ve tan grande.", "Buscador compacto en la cabecera."),
            ("0.12", "Imagen del hero en una columna lateral 4:5.", "Legibilidad y peso.", "Revisar", "El fondo de pantalla me gusta, como una imagen; crea un repositorio de imágenes y conéctala.", "Hero con foto a lo ancho y carpeta assets/img con LEEME.md."),
            ("0.13", "Sellos de confianza entre el hero y las propiedades.", "Poner la promesa antes de la oferta.", "Revisar", "Hay que quitarlo para ponerlo abajo, yo creo. O ponerlo como en otra página.", "Sellos y cómo funciona debajo de las propiedades."),
            ("0.14", "Sección de anfitriones, planes y comparativa en la portada.", "Una sola página con todo el modelo.", "Rechazar", "Anfitriones tienen que ser de otra página web. Forzosamente. En la página principal solo se vean las propiedades. Para no revolverlos.", "Página nueva web/anfitriones.html."),
            ("0.15", "Cuatro propiedades de muestra en Ciudad de México.", "Bastaban para probar el filtro.", "Revisar", "Hay que poner otros dos para que sean seis.", "Dos propiedades más en datos.js."),
        ],
    },
    # ------------------------------------------------------------------ 3
    {
        "n": 3,
        "titulo": "Portada solo con buscador y propiedades; cómo funciona aparte; pie verde",
        "fecha": "18 de octubre de 2026, noche",
        "rol": ROL_BASE,
        "tarea": ("Quita todo el texto del hero y coloca ahí el buscador. Deja la cabecera solo con Íntegro y un botón "
                  "\"Conviértete en anfitrión\" que lleve a la página de anfitriones. Mueve los sellos de confianza y los tres "
                  "pasos para reservar a una página aparte llamada \"Cómo funciona\". Cambia el pie de página a verde, quita "
                  "\"Hospedajes\", conserva Cómo funciona, Anfitriones, Términos y Aviso de privacidad, y destaca \"Reportar un "
                  "problema\", que es muy importante. Con esto la portada queda lista como primer avance."),
        "contexto": ("La portada debe mostrar solo propiedades para que el huésped elija. Cómo funciona interesa más al "
                     "anfitrión y quizá termine dentro de su página. Términos y Aviso no necesitan enlace todavía."),
        "salida": SALIDA_BASE,
        "respuesta": {
            "fecha": "18 de octubre de 2026",
            "commits": "80894c4 y 7482304 (tras integrar las ediciones de Sophia en GitHub: f4768e9, 8a69ce7 y 61d6b3a)",
            "archivos": [
                ("web/index.html", "cabecera mínima, hero con imagen y buscador al centro sin texto, seis propiedades, pie verde con reporte destacado."),
                ("web/como-funciona.html (nuevo)", "encabezado con las tres promesas, cuatro sellos y tres pasos para reservar."),
                ("web/anfitriones.html, web/propiedad.html", "cabeceras y pies iguales a la portada; se retira \"Entrar\"."),
                ("web/assets/css/estilos.css", "token --color-pie, bloque Pie, .btn-reportar, .encabezado-pagina, .buscador al centro del hero."),
                ("README.md, PROMPT_LOG.md, docs/diseno/*.md", "referencias corregidas tras el borrado de docs/assignment-2 y bitácora actualizada."),
            ],
            "sugerencias": [
                ("Quitar \"Entrar\" de todas las cabeceras.", "la instrucción fue dejar solo la marca y el botón de anfitrión; el inicio de sesión es Must del MVP y queda como pendiente 0.20."),
                ("Interpretar \"el verde que se usa como fondo\" como un verde profundo derivado del acento.", "la portada no tenía fondos verdes; se dejó en un token para cambiarlo en un lugar."),
                ("Aplicar el pie simplificado de Sophia (solo la marca, sin nota de nombre provisional ni línea de seguridad) a las cuatro páginas.", "ella lo editó en la portada desde GitHub; las páginas deben ser consistentes."),
            ],
            "lineas": "index.html completo. estilos.css: :root (--color-pie), bloque Pie, .buscador, .hero-contenido. anfitriones.html y propiedad.html: bloques header y footer.",
        },
        "decisiones": [
            ("0.16", "Titular con las tres promesas y subtítulo sobre la imagen del hero.", "Poner la promesa donde Wander pone su lema.", "Rechazar", "Eso lo vamos a quitar, todo lo vamos a quitar.", "Hero solo con imagen y buscador."),
            ("0.17", "Buscador compacto dentro de la cabecera (segunda revisión).", "Seguir la barra de Wander.", "Revisar", "Donde está la imagen vamos a colocar lo de destino, llegada, salida. En el header solo quede Íntegro y conviértete en anfitrión.", "Buscador al centro del hero; cabecera mínima."),
            ("0.18", "Sellos y tres pasos al final de la portada.", "Mantener la explicación en la misma página.", "Revisar", "Eso que va en texto lo vamos a colocar en una página aparte que va a ser cómo funciona.", "Página web/como-funciona.html."),
            ("0.19", "Pie claro con seis enlaces y el reporte como uno más.", "Pie neutro.", "Revisar", "Que tenga un color, el verde que se usa como fondo. Quitar hospedajes. Reportar un problema, eso sí es muy importante.", "Pie verde, sin Hospedajes, reporte como botón."),
            ("0.20", "La IA quitó \"Entrar\" de las cabeceras.", "Instrucción literal; el prototipo no tiene inicio de sesión.", "Pendiente", "", "Decidir dónde vivirá Entrar."),
        ],
    },
    # ------------------------------------------------------------------ 4
    {
        "n": 4,
        "titulo": "Eslogan, cabecera sin bordes, pie blanco y ficha reorganizada",
        "fecha": "18 de octubre de 2026, noche",
        "rol": ROL_BASE,
        "tarea": ("El buscador se queda al centro, pero la zona se ve vacía: agrega arriba un eslogan como \"Su lugar íntegro\", "
                  "con \"íntegro\" en azul. Coloca \"Conviértete en anfitrión\" más a la izquierda y sin bordes. El pie vuelve a "
                  "blanco con el mismo acomodo, y \"Reportar un problema\" en un color que resalte. Quita todos los separadores "
                  "\" · \" de los textos. En la ficha, la ubicación debe abrir Google Maps, y ubicación y reseñas salen de la "
                  "columna de descripción a secciones que abarquen todo el ancho, porque se pierde espacio junto a la caja de "
                  "reserva. En la página de anfitrión, el botón \"Publica tu propiedad\" no puede ser verde."),
        "contexto": ("Es un juego de palabras con el nombre. Las reseñas funcionan por ahora como un foro. Lo demás de la "
                     "portada y de la página de anfitrión sigue bien."),
        "salida": SALIDA_BASE,
        "respuesta": {
            "fecha": "18 de octubre de 2026",
            "commits": "ae907ba y 3a90077 (tras integrar d0ece85, la imagen de anfitriones que subió Sophia)",
            "archivos": [
                ("web/index.html", "eslogan \"Su lugar, íntegro.\" sobre el buscador; enlace de anfitrión junto a la marca; pie blanco."),
                ("web/propiedad.html", "ubicación y reseñas como secciones a lo ancho debajo de las dos columnas; el mapa y un botón abren Google Maps."),
                ("web/anfitriones.html, web/como-funciona.html", "botones azules en anfitriones; cabecera con enlaces de texto; pie blanco."),
                ("web/assets/css/estilos.css", "tokens --color-pie (blanco) y --color-resalte; .eslogan, .resalte, .enlaces-cabecera, .btn-azul, .pie, .bloque-ancho, .mapa-aproximado, .resenas-lista."),
                ("web/assets/js/app.js", "función plural; textos de tarjeta y ficha sin separadores; enlace a Google Maps con colonia y ciudad."),
            ],
            "sugerencias": [
                ("Escribir el eslogan con coma: \"Su lugar, íntegro.\"", "espeja \"Tu ingreso, íntegro.\" de la página de anfitriones; Sophia decide si se queda y si prefiere tú en vez de su."),
                ("Azul claro para la palabra resaltada, en un token.", "sobre una foto oscura un azul oscuro no se vería."),
                ("Enlazar a Google Maps con la colonia y la ciudad, nunca con la dirección exacta.", "regla de seguridad: la dirección se comparte solo con reserva confirmada."),
                ("Dejar \"Buscar\" y \"Reservar\" en verde.", "Sophia solo mencionó los botones de la página de anfitrión; pendiente confirmar si el verde sale de todos."),
                ("Plurales calculados (\"1 baño\").", "al quitar los separadores se vio que \"1 baños\" estaba mal."),
            ],
            "lineas": "estilos.css: :root, .eslogan y .resalte, .enlaces-cabecera, .btn-azul, bloque Pie, .bloque-ancho, .mapa-aproximado, .resenas-lista y media query de 720 px. app.js: plural, tarjeta, pintarFicha (campos capacidad y calif, enlace [data-mapa]). propiedad.html: estructura después de .ficha-cuerpo. anfitriones.html: tres botones con .btn-azul.",
        },
        "decisiones": [
            ("0.21", "Hero solo con imagen y buscador, sin texto (aplicado en 0.16 a petición suya).", "Instrucción previa.", "Revisar", "Ahora lo veo un poco pelón. Se coloque un eslogan, algo como su lugar íntegro, haciendo un juego de palabras.", "Eslogan con íntegro en azul claro."),
            ("0.22", "Botón de anfitrión con borde, a la derecha.", "Patrón List on Wander.", "Revisar", "Hay que colocarlo más a la izquierda y no me gusta que tenga bordes.", "Enlace de texto junto a la marca."),
            ("0.23", "Pie verde profundo con botón blanco.", "Interpretación del verde de fondo.", "Rechazar", "Ya no me gustó el color, sí lo prefiero blanco. Me gusta el acomodo. Reportar un problema de algún otro color que resalte.", "Pie blanco; reporte en azul."),
            ("0.24", "Separador \" · \" entre datos.", "Convención de Airbnb y Wander.", "Rechazar", "Quita todos los puntos que aparecen en los textos.", "Comas, paréntesis y líneas separadas."),
            ("0.25", "Ubicación y reseñas dentro de la columna de descripción; mapa sin enlace.", "Agrupar el contenido junto a la caja de precio.", "Revisar", "Se pierde mucho espacio entre la descripción y la reserva. Que abarque todo. Redireccionamiento a Google Maps.", "Secciones a lo ancho; mapa y botón abren Google Maps por zona."),
            ("0.26", "Botones verdes en la página de anfitrión.", "Un solo color de botón principal.", "Rechazar", "Publica tu propiedad, ese color verde tampoco me gusta.", "Botones azules (.btn-azul)."),
            ("0.27", "Textos de apoyo en el prototipo y el repositorio: subtítulo del hero de anfitriones, notas de \"montos por confirmar\" y \"comparación sin cifras\", comentarios HTML explicativos, \"íntegro\" en minúscula en el eslogan y encabezado \"Para el profesor\" en el README.", "Dar contexto a quien lee el prototipo y el repositorio.", "Revisar", "Ediciones directas de Sophia en GitHub, sin prompt: \"Íntegro\" con mayúscula en el eslogan, \"¿Cómo funciona?\" y \"¿Cómo empezar?\" con signos de interrogación, sin notas ni comentarios, y README sin referencias al curso.", "Commits de Sophia 15a6599 a a712ba6; la IA corrigió después la errata \"Ìntegro\" por \"Íntegro\" en anfitriones.html."),
        ],
    },
    # ------------------------------------------------------------------ 5
    {
        "n": 5,
        "titulo": "Entrega al profesor y bitácora presentable",
        "fecha": "18 de octubre de 2026, noche",
        "rol": ("Eres el mismo ingeniero senior y además redactas documentación técnica clara para un lector de negocios "
                "que sabe programar."),
        "tarea": ("Dime qué debo entregarle a Oscar para el Assignment 2 y redáctalo en formato escrito con enlaces. Haz un "
                  "documento en Word, sencillo y rápido, de unas cinco páginas, que explique el nuevo proyecto. Incluye en el "
                  "documento la bitácora de prompts, con cada prompt presentable en la estructura rol, tarea, contexto y salida, "
                  "y la respuesta de la IA desglosada: fecha, carpeta o archivo modificado, por qué, sugerencias y líneas."),
        "contexto": ("Cambio el proyecto del curso de LÍA a Íntegro por confidencialidad; LÍA sigue aparte hasta diciembre. "
                     "La entrega se sube en el espacio del Assignment aunque el enunciado parta del repositorio del Assignment 1. "
                     "Mis prompts originales son hablados y repetitivos; deben verse presentables sin cambiar lo que pedí."),
        "salida": ("Documento Word en el escritorio, texto listo para pegar en Forum con los enlaces, y la bitácora "
                   "actualizada en el repositorio con la misma estructura."),
        "respuesta": {
            "fecha": "18 de octubre de 2026",
            "commits": "(bitácora regenerada en el repositorio; el Word vive fuera del repositorio)",
            "archivos": [
                ("Escritorio/Integro_Presentacion_Oscar_2026-10-18.docx", "presentación de seis secciones más el anexo con esta bitácora."),
                ("PROMPT_LOG.md (sección 2.0)", "regenerada desde una fuente de datos única para que el repositorio y el Word digan lo mismo."),
            ],
            "sugerencias": [
                ("Añadir una nota de transparencia que diga que los prompts se transcriben en limpio.", "la rúbrica evalúa el juicio sobre lo que la IA propone; una transcripción fiel y ordenada es legítima, una reescritura silenciosa no."),
                ("Dejar el enlace del deploy como hueco a llenar.", "todavía no existe un deploy de Íntegro."),
                ("Tratar la entrega de hoy como aviso de cambio y primer avance, no como la entrega final.", "la entrega final exige la función construida y validada, que llega después de la Sesión 19."),
            ],
            "lineas": "PROMPT_LOG.md entre los marcadores de la sección 2.0; el Word se genera completo cada vez.",
        },
        "decisiones": [],
    },
    # ------------------------------------------------------------------ 6
    {
        "n": 6,
        "titulo": "Requisitos del backend y dudas de arquitectura",
        "fecha": "16 de noviembre de 2026, noche",
        "rol": ROL_PROYECTO,
        "contexto": ("La arquitectura de Íntegro se divide en frontend y backend. El frontend lleva la interfaz (la "
                     "aplicación web, los formularios, los paneles de búsqueda, las reservas y las vistas del usuario, del "
                     "anfitrión y del administrador) y otra carpeta de monitoreo y auditoría (logs, alertas, trazabilidad de "
                     "cambios y bitácora administrativa); de momento queda aparte. El backend cubre todo lo demás, desde la "
                     "carpeta «datos y archivos» (base de datos, caché y almacenamiento privado de documentos). Detalles del "
                     "backend: pagos con la API de Stripe; PostgreSQL, sin nombres de usuario repetidos; Vercel, porque AWS es "
                     "caro y aún no hay ingresos; acceso por SSH con puerto distinto del 22, respaldo local y Linux; políticas "
                     "de pagos, propiedades y reservas nada flexibles, probando cada caso al límite; la privacidad es muy "
                     "importante. El proyecto saldrá al mercado y también sirve para el Assignment 2 (enunciado adjunto). Hay "
                     "dos chats: uno para programar y otro, este, para dudas y construcción de la arquitectura."),
        "tarea": ("Ayúdame a definir bien estos aspectos y resuelve mis dudas. 1) Afinar la base de datos: clientes, "
                  "anfitriones, propiedades y mensajería. 2) Pagos: avisos de en espera, aceptado, rechazado o cancelado, con "
                  "sus motivos, y restricciones muy serias de cuándo aplica cada uno. 3) Membresías: inicia cuando el "
                  "anfitrión paga; no sé bien cómo manejar el término y la cancelación (pensaba en 15 días sin pago y cancelar "
                  "a los 16); quiero ser flexible, pero no tanto. 4) Propiedades: activa cuando el anfitrión pagó y la subió; "
                  "desactivada cuando no paga o la baja de la plataforma. 5) Documentos del anfitrión (INE, acta de "
                  "nacimiento) que sube y revisa la IA: deben ir cifrados, con SHA o alguna librería. 6) Formularios de pago: "
                  "que no haya pagos repetidos si se recarga la página o se va la luz. 7) Dos directorios, ejemplos "
                  "(prellenados) y pruebas (en sandbox, sobre todo para pagos). 8) Qué pasa si la plataforma marca un acceso "
                  "indebido pero se trata de una emergencia."),
        "salida": "Tu opinión como ingeniero sobre cada punto. Cada prompt se guarda sin muletillas para el reporte.",
        "respuesta": {
            "fecha": "16 de noviembre de 2026",
            "commits": ("Respuesta de diseño, sin cambios en el código. Las reglas acordadas quedaron después en CLAUDE.md "
                        "(commit 97867a7)."),
            "archivos": [
                ("CLAUDE.md", "reglas permanentes del proyecto, con la plataforma y la seguridad acordadas en esta respuesta."),
            ],
            "sugerencias": [
                ("Tabla de estados de pago: creado, en espera, pagado, rechazado, expirado, cancelado y reembolsado, cada cambio con quién lo dispara.",
                 "Sophia pidió restricciones muy serias; una tabla cerrada prohíbe todo cambio que no esté escrito."),
                ("Tabla de estados de membresía: activa, en gracia, suspendida y cancelada, con los días en una configuración.",
                 "evita pasar de activa a cancelada de un salto y deja el número de días a decisión de Sophia."),
                ("Pruebas por tabla de estados: cada fila es un caso, más los prohibidos, con el modo de prueba de Stripe.",
                 "Sophia pidió probar cada caso posible y llevarlo al límite."),
            ],
            "lineas": "No aplica: no se modificó código en esta respuesta.",
        },
        "decisiones": [
            ("6.1", "Cifrar los datos sensibles con AES-256-GCM; SHA es un hash y no cifra.", "SHA no permite recuperar el documento. Campo: qué datos necesita.", "Pendiente", "", "Quedó escrito en CLAUDE.md, que Sophia autorizó."),
            ("6.2", "No guardar el INE ni el acta de nacimiento: solo el resultado, la fecha y la referencia del proveedor de verificación.", "Menos datos sensibles, menos riesgo y menos obligaciones de ley. Campo: qué datos necesita.", "Pendiente", "", "Quedó escrito en CLAUDE.md."),
            ("6.3", "No construir un formulario propio de tarjeta: componentes de Stripe, llave de idempotencia en cada cobro y cambio de estado solo con el webhook firmado.", "El número de tarjeta y el CVC nunca pasan por el servidor, y el reintento con la misma llave no cobra dos veces. Campo: qué hace.", "Pendiente", "", "Quedó escrito en CLAUDE.md."),
            ("6.4", "Vercel para la web y la API, Supabase para PostgreSQL, autenticación y archivos privados, y Stripe para pagos; sin servidor con SSH, Linux ni respaldo local por ahora.", "Vercel no ofrece base de datos ni servidor con SSH; Supabase es PostgreSQL administrado y gratuito a este tamaño. Campo: qué datos necesita.", "Pendiente", "", "Quedó escrito en CLAUDE.md."),
            ("6.5", "Membresía con estado intermedio: en gracia los días 1 a 7 con tres reintentos, suspendida el día 8 y cancelada el día 30, con los días configurables.", "Sophia pensaba en 15 días y pidió ayuda para definirlo. Campo: qué hace.", "Pendiente", "", "Sin cambios en el código."),
            ("6.6", "Propiedad activa solo si la verificación está aprobada, la membresía está activa o en gracia y el anfitrión no la pausó; seis estados.", "Sophia definió activa y desactivada; la propuesta agrega la verificación y los estados intermedios. Campo: qué hace.", "Pendiente", "", "Sin cambios en el código."),
            ("6.7", "Ante un acceso indebido: pedir segundo factor, avisar y congelar 48 horas solo lo que mueve dinero; nunca bloquear ni borrar en automático.", "El usuario legítimo pasa el segundo factor aunque sea una emergencia; el atacante no. Campo: qué hace.", "Pendiente", "", "Quedó escrito en CLAUDE.md."),
            ("6.8", "Dos estados de pago que Sophia no pidió: expirado a los 30 minutos sin confirmación y reembolsado.", "Un pago en espera no puede quedarse así para siempre y un reembolso no es lo mismo que una cancelación. Campo: qué hace.", "Pendiente", "", "Sin cambios en el código."),
        ],
    },
    # ------------------------------------------------------------------ 7
    {
        "n": 7,
        "titulo": "Base de datos: entidades, decisiones del modelo y grupo 1",
        "fecha": "17 de noviembre de 2026, mañana",
        "rol": ROL_PROYECTO,
        "contexto": ("Tengo un borrador de las entidades de la base de datos. Respuestas de Sophia a las cuatro preguntas de "
                     "la IA antes de construir: el correo se guarda solo en Supabase Auth; todos los datos son obligatorios "
                     "desde el registro; cada propiedad tiene un titular y coanfitriones; las pruebas corren en un PostgreSQL "
                     "temporal fuera del repositorio. El mensaje empezó con la palabra «explorar»."),
        "tarea": ("Paso 1. Vamos a construir la base de datos de la plataforma. Mi borrador tiene estas entidades: Usuario "
                  "(CURP como llave primaria, nombre, apellido, edad, propiedades como llave foránea, teléfono, correo); "
                  "Propiedades (id como llave primaria, ubicación, usuario como llave foránea, capacidad de personas, "
                  "¿detalles?); Mensajería (usuario como llave foránea, id como llave primaria, ¿qué más?, estado: enviado, no "
                  "enviado, en espera). ¿Qué otro dato de la base de datos necesito? Paso 2. Sí habrá clientes extranjeros. "
                  "De momento la plataforma se maneja en dos idiomas, inglés y español. Los nombres de las tablas y las "
                  "carpetas van en inglés, es más fácil. La propiedad sí puede tener más de un anfitrión. Autorizo la base de "
                  "datos."),
        "salida": "No se indicó. Se aplicó el desglose de cierre de CLAUDE.md.",
        "respuesta": {
            "fecha": "17 de noviembre de 2026",
            "commits": "12fb753 y 5ee993c, en la rama datos/users-host-profiles-verifications",
            "archivos": [
                ("supabase/migrations/20261117000001_users_host_profiles_verifications.sql",
                 "migración del grupo 1: tablas users, host_profiles y verifications, con sus reglas y permisos."),
                ("tests/database/group1_users.test.js", "59 casos de prueba del grupo 1."),
                ("tests/database/supabase_stub.sql", "imitación de los roles y del esquema auth de Supabase, solo para pruebas."),
                ("tests/database/README.md", "cómo correr las pruebas y cómo leer un rechazo."),
            ],
            "sugerencias": [
                ("Exigir mayoría de edad en el registro.", "hoy la base acepta cualquier fecha de nacimiento hasta el día de hoy."),
                ("Bloquear nombre y fecha de nacimiento después de verificar la identidad.", "hoy una persona verificada puede cambiarse el nombre."),
                ("Actualizar la línea «Todo en español» de CLAUDE.md y decidir si las carpetas existentes se renombran.", "los nombres de tablas y carpetas ahora van en inglés."),
                ("Registrar como ADR las decisiones del modelo de datos y la plataforma Vercel, Supabase y Stripe.", "CLAUDE.md la marca como pendiente de registrar."),
            ],
            "lineas": "Cuatro archivos nuevos completos (217, 227, 33 y 40 líneas). Ningún archivo existente se modificó.",
            "pruebas": ("Corridas en un PostgreSQL en memoria (PGlite) con una imitación de Supabase, no en el proyecto real. "
                        "Primera corrida: 59 casos, 44 coinciden y 15 no; el error era de la prueba (la simulación del registro "
                        "mandaba el id vacío), no de la migración, y se corrigió sin cambiar lo esperado. Segunda corrida: "
                        "«Total: 59 casos, 59 coinciden, 0 no coinciden.» Salida completa copiada en "
                        "herramientas/bitacora/evidencias/grupo1_pruebas_2026-11-17.txt."),
        },
        "decisiones": [
            ("7.1", "Llave primaria con un id generado (UUID) en lugar de la CURP, y no guardar la CURP.", "Un huésped extranjero no tiene CURP y como llave se copiaría a todas las tablas. Campo: qué datos necesita.", "Aceptar", "Autorizo la base de datos.", "Tabla users con id."),
            ("7.2", "La referencia a las propiedades vive en Propiedades, no en Usuario.", "Un anfitrión tiene muchas propiedades. Campo: qué datos necesita.", "Aceptar", "Autorizo la base de datos.", "Se aplicará en el grupo 2."),
            ("7.3", "Guardar la fecha de nacimiento en lugar de la edad.", "La edad cambia cada año. Campo: qué datos necesita.", "Aceptar", "Autorizo la base de datos.", "Columna birth_date."),
            ("7.4", "Ubicación en dos datos: la dirección exacta privada y la zona aproximada pública.", "En un solo campo, tarde o temprano se filtra la exacta. Campo: qué datos necesita.", "Aceptar", "Autorizo la base de datos.", "Se aplicará en el grupo 2."),
            ("7.5", "Mensajería en dos tablas, conversaciones y mensajes, con estados enviado, leído y retenido en lugar de enviado, no enviado y en espera.", "Un mensaje pertenece a una conversación entre huésped y anfitrión; lo no enviado no existe. Campo: qué datos necesita.", "Aceptar", "Autorizo la base de datos.", "Se aplicará en el grupo 6."),
            ("7.6", "Diecisiete tablas construidas en seis grupos.", "Sophia preguntó qué otro dato necesitaba; se construye pieza por pieza. Campo: qué hace.", "Aceptar", "Autorizo la base de datos.", "Grupo 1 construido."),
            ("7.7", "Pedir al registrarse solo nombre, apellido y correo, y lo demás antes de reservar o publicar.", "Registro más corto. Campo: qué datos necesita.", "Rechazar", "Sophia eligió la opción «Todo desde el registro».", "Nombre, apellido, teléfono, país y fecha de nacimiento son obligatorios."),
            ("7.8", "La fila en users se crea sola cuando Supabase Auth crea la cuenta.", "Garantiza que no exista una cuenta sin sus datos. Campo: qué hace.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Función handle_new_auth_user."),
            ("7.9", "Columna preferred_language (es o en).", "Sale de la decisión de dos idiomas; no estaba en la tabla autorizada. Campo: qué datos necesita.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Columna en users."),
            ("7.10", "verifications todavía sin property_id.", "La tabla properties no existe hasta el grupo 2. Campo: qué datos necesita.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Se agrega en el grupo 2."),
            ("7.11", "Listas de valores en inglés elegidas por la IA (estado de identidad, nivel del anfitrión, tipo y resultado de verificación).", "Los nombres van en inglés por decisión de Sophia; los valores no estaban definidos. Campo: qué datos necesita.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Reglas de valores en la migración."),
            ("7.12", "Borrar el acceso de una persona no borra sus datos: se rechaza.", "Regla de no borrar en automático. Campo: qué hace.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Llave foránea sin borrado en cascada."),
            ("7.13", "Límites de formato: teléfono internacional, país de dos letras, nombre de 1 a 80 caracteres y fecha de nacimiento entre 1900 y hoy.", "Sin límites la base acepta datos que no se pueden usar. Campo: cómo se sabrá que funciona.", "Aceptar", "Acepto los 6 veredictos, puedes aplicar los cambios.", "Reglas de formato en la migración."),
        ],
    },
    # ------------------------------------------------------------------ 8
    {
        "n": 8,
        "titulo": "Documento final, dudas y vista de administrador",
        "fecha": "17 de noviembre de 2026, mediodía",
        "rol": ROL_PROYECTO,
        "contexto": ("Me faltaron algunas especificaciones y tengo dudas. Todas las pruebas se deben hacer con mi usuario: "
                     "como administradora debo tener acceso a la vista de anfitrión, a la de usuario (cliente) y a la de "
                     "administrador, para hacer todas las pruebas yo. Estamos definiendo la arquitectura antes de programar "
                     "tanto el backend como el frontend."),
        "tarea": ("1) Acepto los seis veredictos; puedes aplicar los cambios. 2) El documento en Word se crea hasta el final; "
                  "/bitacora sigue guardando las conversaciones, las dudas y los prompts como hasta ahora. ¿Podríamos agregar "
                  "otro comando, /doc, que cree el documento final con las especificaciones de CLAUDE.md? 3) Registra el "
                  "primer prompt de ayer, lo de la base de datos y esta conversación. 4) ¿Cómo creo la Supabase? Que yo "
                  "recuerde iba a usar PostgreSQL y creo que aún no lo instalo. 5) Si los datos no se envían, se redirecciona "
                  "de nuevo al formulario, ¿no? 6) Ya puedes aplicar las especificaciones de main."),
        "salida": "No se indicó. Se aplicó el desglose de cierre de CLAUDE.md.",
        "respuesta": {
            "fecha": "17 de noviembre de 2026",
            "commits": "5d95de1 y el commit de este registro, en la rama config/skill-doc; 5ee993c en la rama de datos",
            "archivos": [
                (".claude/skills/doc/SKILL.md", "comando /doc: documento final con la especificación de requisitos según ISO/IEC/IEEE 29148 y la bitácora como anexo, en azul marino #0E0E55."),
                (".claude/skills/bitacora/SKILL.md", "ya no genera el Word; rol único y orden rol, contexto, tarea y salida."),
                ("CLAUDE.md", "lista de skills con /doc."),
                ("herramientas/bitacora/bitacora_datos.py", "prompts 6, 7 y 8."),
                ("herramientas/bitacora/evidencias/grupo1_pruebas_2026-11-17.txt", "salida real de las pruebas del grupo 1."),
            ],
            "sugerencias": [
                ("Construir el generador del Word después, como pieza aparte.", "el documento se crea hasta el final y todavía no hay contenido suficiente."),
                ("Comparar el índice de secciones de /doc contra la norma.", "se escribió de memoria de la edición 2018; la IA no pudo abrir la norma."),
                ("Antes de fusionar la rama de datos, revisar si la integración de Supabase con GitHub aplica migraciones sola.", "si está encendida, fusionar a main crearía las tablas en la base real."),
            ],
            "lineas": ("doc/SKILL.md nuevo completo; bitacora/SKILL.md: descripción inicial, puntos de «Qué se registra» y "
                       "pasos; CLAUDE.md: lista de skills; bitacora_datos.py: constante ROL_PROYECTO y prompts 6 a 8."),
        },
        "decisiones": [
            ("8.1", "La IA preguntó si «corre /pieza» significaba registrar en la bitácora o construir una pieza de arquitectura.", "El mensaje hablaba de guardar prompts, y la regla es no suponer. Campo: qué hace.", "Aceptar", "Sophia eligió la opción «Registrarlos en la bitácora».", "Prompts 6 a 8 registrados; no se construyó nada."),
            ("8.2", "Documento final con la especificación de requisitos en el cuerpo y la bitácora como anexo.", "CLAUDE.md pide el formato ISO/IEC/IEEE 29148, que es de requisitos. Campo: qué hace.", "Aceptar", "Sophia eligió la opción «Especificación y bitácora como anexo».", "Skill /doc."),
            ("8.3", "Administradores en una tabla aparte, admins, que solo se escribe desde el SQL Editor de Supabase.", "El permiso más delicado no vive junto a los datos que la persona puede editar. Campo: qué datos necesita.", "Aceptar", "Sophia eligió la opción «Tabla aparte admins».", "Requisito de arquitectura; sin construir."),
            ("8.4", "Construir el generador del Word después, como pieza aparte.", "El Word se crea hasta el final. Campo: qué hace.", "Pendiente", "", "Sin cambios."),
            ("8.5", "Pruebas automáticas con personas ficticias en la base temporal; las pruebas sobre la plataforma real las hace Sophia con su usuario.", "No se guardan datos reales en el repositorio. Campo: cómo se sabrá que funciona.", "Pendiente", "", "Sin cambios."),
            ("8.6", "Transcripción de los prompts 6 a 8 con un rol distinto en cada uno, la tarea antes que el contexto y un punto sobre skills en el prompt 6.", "Formato usado en los prompts 1 a 5.", "Revisar", "El prompt está bien, solo quita lo de las skills (punto 9) y primero dar contexto. Rol único para todas las bitácoras. Especificar que tengo un borrador, que es el paso 1. Pon que me faltaron algunas especificaciones y tengo dudas.", "Rol único de CLAUDE.md, orden rol, contexto, tarea y salida, y prompts 6 a 8 corregidos."),
        ],
    },
]
