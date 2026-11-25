# Las vistas de Íntegro

**Estado:** decididas por Sophia el 20 de noviembre de 2026 (las diez decisiones quedaron cerradas el 21) y construidas en dos piezas: la vista en la API (rama `api/view-roles`) y la cabecera por vista con sus páginas (rama `web/views`). Siguen pendientes tres piezas (sección «Orden de construcción»).

## Para qué sirve

Íntegro tiene cuatro tipos de persona frente a la web y cada una ve cosas distintas: qué hay en la cabecera, a qué pantallas puede entrar y qué se le ofrece. A eso se le llama una **vista**. Este documento fija cuáles son, cómo sabe la web en cuál está la persona y qué lleva cada una, para construirlas pieza por pieza.

El diseño de las pantallas es de Sophia (ADR 0008). Aquí se define qué hay en cada vista, no cómo se ve.

## Las cuatro vistas

| Vista | Quién la ve | Cómo lo sabe la web |
|---|---|---|
| Visitante | Quien no ha iniciado sesión, tenga cuenta o no | `GET /auth/me` responde 401 |
| Cliente | Una persona con sesión que todavía no es anfitriona | `/auth/me` con `is_host: false` |
| Anfitrión | Una persona con sesión y perfil de anfitrión | `/auth/me` con `is_host: true` |
| Administrador | Solo tres personas: Shakti, Valeria y Sophia | `/auth/me` con `is_admin: true`, que sale de la tabla `admins` |

Reglas que ya están decididas y se mantienen:
- Un solo registro sirve para huésped y para anfitrión; el perfil de anfitrión se crea después, cuando la persona lo pide (`POST /api/v1/host-profile`, pieza 3.1, decisión del 24 de noviembre de 2026). Queda con nivel `new`; la verificación de identidad lo pasa a `verified` (pieza 3.5).
- Los administradores se dan de alta solo a mano, en pgAdmin; la API nunca escribe en `admins`.
- Un administrador no es anfitrión por serlo, ni al revés: son dos permisos distintos y la API los revisa por separado.
- La sesión del anfitrión dura 7 días sin uso; la del administrador, 30 minutos sin uso y 12 horas como tope, en todo el sitio (ADR 0014; el tope ya existe desde el 21 de noviembre de 2026). El segundo factor es obligatorio para anfitriones y panel (arquitectura, sección 7). **El segundo factor todavía no existe**: una ruta de administrador con datos no se publica hasta tenerlos.

## La cabecera de cada vista

La cabecera la arma `web/assets/js/estructura.js` con una tabla de vistas (`VISTAS`). Al cargar arma la del visitante; `cuenta.js` pregunta a `GET /auth/me` y, si hace falta, la vuelve a armar con la vista que toca. La marca va siempre a la izquierda y la cuenta, siempre a la derecha. Una vista nueva es una entrada nueva de la tabla.

| Vista | Enlaces junto a la marca | A la derecha |
|---|---|---|
| Visitante | La barra «Todo», «Alojamientos», «Experiencias» y «Servicios» | «Conviértete en anfitrión», «Iniciar sesión» y «Crear cuenta» |
| Cliente | La misma barra | «Conviértete en anfitrión» y su nombre, con un menú de texto: «Mi cuenta», «Mis reservas», «Mensajes», «Reseñas», «Comentarios» y «Cerrar sesión» |
| Anfitrión | «Mis propiedades», «Reservas», «Reseñas», «Comentarios», «Chats con clientes» y «Subir publicación». Ya no hay barra ni «Conviértete en anfitrión» | Su nombre, con el menú: «Mi cuenta», «Mis reservas», «Buscar hospedaje» y «Cerrar sesión» |
| Administrador | «Verificaciones», «Casos», «Cargos» y «Bitácora» | Su nombre, con el menú: «Vista de administrador», «Ver como cliente», «Ver como anfitrión», «Mi cuenta» y «Cerrar sesión» |

Cómo funciona la barra:
- «Todo» lleva a la portada; «Alojamientos», a los resultados de la portada. «Experiencias» y «Servicios» llevan a una página «Próximamente» con su nombre, porque todavía no existen.
- Cada página marca su pestaña con un subrayado dorado arena: la portada, «Todo»; la ficha de propiedad, «Alojamientos»; Próximamente, la que corresponda.
- En la página de anfitriones, «Conviértete en anfitrión» se cambia por «Publica tu propiedad», porque ya se está ahí.
- En celular, la marca y la cuenta quedan en la primera fila y la barra baja a la segunda. «Conviértete en anfitrión» y «Publica tu propiedad» se ocultan; el pie de página sigue llevando a «Anfitriones».
- El nombre abre su menú con un clic; se cierra con otro clic en el nombre, con un clic en otra parte o con Escape.

Un enlace solo aparece cuando la página a la que lleva existe. No se publican enlaces que dan 404; una prueba lo comprueba con todas las cabeceras, menús y el pie.

Lo que Sophia pidió, tal cual, para la vista principal: una cabecera con «Todo», «Alojamientos», «Experiencias» y «Servicios», por ejemplo, como la de Airbnb; la barra de navegación y las publicaciones de los alojamientos que suban los anfitriones. Su captura de Wander muestra otra forma: el buscador dentro de la cabecera y «For operators» a la derecha.

## Qué hace cada vista

### Visitante
- Ve la portada y las fichas de propiedad: buscar, comparar y ver precios no pide cuenta.
- Para reservar o para escribirle a un anfitrión necesita una cuenta: al dar clic en «Reservar» sin sesión, la web le ofrece iniciar sesión o crear su cuenta y, al terminar, lo regresa a la misma propiedad con sus fechas y sus huéspedes, guardados en la dirección de la página (`propiedad.html?id=2&llegada=…&salida=…&huespedes=…`). Si inicia sesión en la misma página, no se va a ningún lado y el aviso cambia; si crea una cuenta, `registro.html?siguiente=…` lo regresa al iniciar sesión. Solo se acepta como regreso una página de Íntegro de una lista (`siguienteSeguro` en `cuenta-logica.js`); cualquier otra cosa se ignora. Para quien ya tiene sesión, «Reservar» dice que las reservas se abren pronto: todavía no existen.
- Puede ver cómo convertirse en anfitrión (`anfitriones.html`) antes de crear su cuenta.

### Cliente
- Todo lo del visitante, ya con su sesión.
- Su página es `mi-cuenta.html`: sus datos (nombre y correo, tal como los contesta la API) y las secciones de reservas, mensajes, reseñas y comentarios, que dicen «Próximamente».
- Reseñas y comentarios, en sus palabras: la vista del cliente solo tiene el apartado para ver lo que escriben los demás (**Reseñas**) y el de redactar un comentario (**Comentarios**); si acaso, reaccionar con un corazón o un «me gusta». Todavía no existen.
- Mientras no sea anfitrión, «Conviértete en anfitrión» lo lleva a la página que explica cómo y le deja empezar.

### Anfitrión
- Deja de ver la página que explica cómo ser anfitrión y ve sus funciones. Su página es `anfitrion.html`, con una sección por cada función; todas dicen «Próximamente».
- **Reseñas:** el anfitrión ve las reseñas que le dejan los clientes y puede responder con un agradecimiento o una disculpa. Más adelante, una inteligencia artificial le resumirá las reseñas y le dará sugerencias. Las reseñas también aparecen en la ventana del cliente.
- Sigue pudiendo reservar como cliente: una sola cuenta puede ser huésped y anfitrión (decisión del modelo de datos). Por eso su menú trae «Mis reservas» y «Buscar hospedaje».
- Sus cobros y su membresía viven en su vista, no en la del cliente.
- El perfil de anfitrión lo crea la persona al pedirlo, con sesión y correo comprobado (pieza 3.1). La API ya lo permite; el botón de la web que lo pide va con las pantallas del anfitrión (pieza 3.4), así que desde la web todavía nadie llega a esta vista.

### Administrador
- Es la vista de mantenimiento de las páginas y de la plataforma: cola de verificaciones, casos, suspender y reactivar, cargos con cuatro ojos, bitácora (módulo Admin de la arquitectura). Su página es `administracion.html`, con una sección por cada una; todas dicen «Próximamente».
- Ve las vistas del anfitrión y del cliente **con su propia cuenta** (decisión de Sophia): desde el menú de su nombre elige «Ver como cliente» o «Ver como anfitrión», y la cabecera cambia. Un aviso junto a su nombre dice «Viendo como cliente» o «Viendo como anfitrión». Verlas no es actuar en nombre de otra persona ni le da el permiso de anfitrión: la API sigue tratándola como administradora.
- Lo que elige se recuerda solo en esa pestaña del navegador (`sessionStorage`) y se olvida al cerrar la pestaña o la sesión. Una persona que no es administradora no puede activarlo: la web lo ignora y lo borra.
- Solo la ven las tres personas del equipo. Entra con segundo factor y su sesión se cierra a los 30 minutos sin uso (pendiente, ver arriba).

## Cómo se decide la vista, y dónde está el permiso

1. La web pregunta a `GET /auth/me`, que contesta nombre, correo, país, idioma, `is_host`, `is_admin` y la clave anti-falsificación.
2. Con esa respuesta, `cuenta.js` elige la vista (`vistaDe` en `cuenta-logica.js`) y `estructura.js` arma la cabecera.
3. **La cabecera es comodidad, no seguridad.** El permiso de cada cosa lo da la API en cada ruta, por dueño del recurso (`CLAUDE.md`): que un anfitrión no vea el enlace de «Cargos» no significa que no pueda pedirlo. La API ofrece `require_host` y `require_admin` (y sus variantes `_for_change`, que además piden las tres defensas) en `backend/app/api/roles.py`. Sin sesión responden 401; con sesión y sin el papel, 403 con el código `host_only` o `admin_only`. El papel se lee en la base en cada petición: quien deja de ser administrador deja de serlo en su siguiente petición, aunque su sesión siga abierta.
4. Las páginas del cliente, del anfitrión y del administrador llevan `data-requiere` en el `body`. Si alguien entra a su dirección sin poder verlas, la página lo explica y le dice a dónde ir (no es un error de la API): sin sesión, «Inicia sesión para continuar»; un cliente en el espacio del anfitrión, «Esta sección es para anfitriones» con el camino para serlo; cualquiera que no sea del equipo en la administración, «Esta sección es solo para el equipo de Íntegro». El contenido está oculto hasta saber quién mira, y los datos de la persona se borran de la página al cerrar la sesión. Un administrador puede ver las páginas del anfitrión.

## Decisiones

Las diez decisiones propuestas el 20 de noviembre de 2026 y lo que decidió Sophia el mismo día.

1. **La barra de navegación.** ¿Solo «Alojamientos» o «Todo, Alojamientos, Experiencias, Servicios»? **La barra completa, desde ya.** «Experiencias» y «Servicios» llevan a una página «Próximamente»; «Todo» lleva a la portada y «Alojamientos», a sus resultados.
2. **El buscador.** Se queda en el centro de la portada; se decide aparte cuando se defina la portada del cliente. Aceptada.
3. **La cuenta en la cabecera.** El nombre como texto con un menú desplegable de texto, sin íconos (la flecha del menú se dibuja con bordes). Aceptada.
4. **«Crear cuenta» en la cabecera del visitante.** Como enlace de texto junto a «Iniciar sesión». Aceptada.
5. **Reseñas y comentarios.** Definidos por Sophia: ver las respuestas de la sección «Cliente» y «Anfitrión».
6. **«Reservas» del anfitrión.** Agregado a su cabecera. Aceptada.
7. **El revisor.** La arquitectura nombra el rol «revisor» junto al de administrador (sección Cuentas) sin definirlo. **Sophia decidió el 21 de noviembre de 2026 que, con solo tres vistas de administrador, el rol de revisor lo hace el administrador:** no hay revisor aparte, y las tres personas del equipo atienden la cola de verificaciones desde su vista. Si más adelante entra alguien que solo deba revisar, se agrega el rol.
8. **«Ver como» del administrador.** **Con su propia cuenta**, sin actuar como otra persona. Si más adelante hiciera falta ver lo que ve otra persona, exige permisos y bitácora.
9. **Un anfitrión que aún no termina Verificación.** Sigue en la vista de cliente hasta tener el perfil de anfitrión. Aceptada.
10. **Regreso después de iniciar sesión.** Guardar las fechas y los huéspedes en la dirección de la página, no en el navegador. Aceptada; se construye en la pieza 3.

## Orden de construcción

1. **La vista en la API.** `is_admin` en `GET /auth/me` y las dependencias `require_host` y `require_admin`, con sus pruebas contra la base. Hecha (rama `api/view-roles`).
2. **La cabecera por vista.** Las cuatro variantes de la cabecera, la barra, «Crear cuenta», el menú de la cuenta, las páginas de cada vista, «Próximamente» y el aviso de la página protegida. Hecha (rama `web/views`).
3. **Reservar sin sesión.** El camino de la ficha al inicio de sesión o al registro y de vuelta, con sus fechas y huéspedes. Hecha (rama `web/reserve-without-session`).
4. **La vista del anfitrión.** Sus pantallas de verdad, cuando exista Verificación: sin perfil de anfitrión no hay vista de anfitrión. Pendiente.
5. **La vista del administrador.** La cola de verificaciones, con el segundo factor y el tope de sesión. Pendiente.

Cada paso es una pieza con su especificación, sus pruebas contra la base y su veredicto.

## Fuente

Descripción de Sophia del 20 de noviembre de 2026, sus dos capturas de referencia (Airbnb y Wander) y sus respuestas del mismo día. `docs/arquitectura.md`, módulos Cuentas y Admin. ADR 0008, 0014 y 0015. `docs/diseno/pantallas.md` y `benchmark-competencia.md`.
