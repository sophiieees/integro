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
]
