# Las vistas de Íntegro

**Estado:** propuesta del 20 de noviembre de 2026, a partir de lo que Sophia describió ese día. Nada de lo que está aquí se construyó todavía; cada punto espera su decisión (sección «Decisiones por tomar»).

## Para qué sirve

Íntegro tiene cuatro tipos de persona frente a la web y cada una ve cosas distintas: qué hay en la cabecera, a qué pantallas puede entrar y qué se le ofrece. A eso se le llama una **vista**. Este documento fija cuáles son, cómo sabe la web en cuál está la persona y qué lleva cada una, para construirlas pieza por pieza.

El diseño de las pantallas es de Sophia (ADR 0008). Aquí se define qué hay en cada vista, no cómo se ve.

## Las cuatro vistas

| Vista | Quién la ve | Cómo lo sabe la web |
|---|---|---|
| Visitante | Quien no ha iniciado sesión, tenga cuenta o no | `GET /auth/me` responde 401 |
| Cliente | Una persona con sesión que todavía no es anfitriona | `/auth/me` con `is_host: false` |
| Anfitrión | Una persona con sesión y perfil de anfitrión | `/auth/me` con `is_host: true` |
| Administrador | Solo tres personas: Shakti, Valeria y Sophia | Dato nuevo en `/auth/me` (`is_admin`), que sale de la tabla `admins` |

Reglas que ya están decididas y se mantienen:
- Un solo registro sirve para huésped y para anfitrión; el perfil de anfitrión se crea después, en Verificación.
- Los administradores se dan de alta solo a mano, en pgAdmin; la API nunca escribe en `admins`.
- La sesión del anfitrión dura 7 días sin uso; la del panel, 30 minutos sin uso y 12 horas como tope (ADR 0014). El segundo factor es obligatorio para anfitriones y panel (arquitectura, sección 7).

## La cabecera de cada vista

La cabecera la arma `web/assets/js/estructura.js` con una tabla de variantes. Cada vista de abajo es una variante nueva de esa tabla; las páginas no cambian. La marca va siempre a la izquierda y la cuenta, siempre a la derecha.

| Vista | Enlaces y navegación | Cuenta, a la derecha |
|---|---|---|
| Visitante | «Alojamientos» y lo que se decida de la barra (ver Decisión 1). «Conviértete en anfitrión» | «Iniciar sesión» y «Crear cuenta» |
| Cliente | Lo mismo que el visitante, con «Conviértete en anfitrión» mientras no lo sea | Nombre de la persona con su menú: «Mis reservas», «Mensajes», «Mi cuenta» y «Cerrar sesión» |
| Anfitrión | «Mis propiedades», «Reservas», «Reseñas», «Comentarios», «Chats con clientes» y «Subir publicación». Ya no aparece «Conviértete en anfitrión» | Nombre con su menú y «Cerrar sesión» |
| Administrador | «Verificaciones», «Casos», «Cargos», «Bitácora» y «Ver como»: cliente o anfitrión | Nombre con su menú y «Cerrar sesión» |

Lo que Sophia pidió, tal cual, para la vista principal: una cabecera con «Todo», «Alojamientos», «Experiencias» y «Servicios», por ejemplo, como la de Airbnb; la barra de navegación y las publicaciones de los alojamientos que suban los anfitriones. Su captura de Wander muestra otra forma: el buscador dentro de la cabecera y «For operators» a la derecha.

Un enlace solo aparece cuando la pantalla a la que lleva existe. No se publican enlaces que dan 404.

## Qué hace cada vista

### Visitante
- Ve la portada y las fichas de propiedad: buscar, comparar y ver precios no pide cuenta.
- Para reservar o para escribirle a un anfitrión necesita una cuenta: al dar clic en «Reservar» sin sesión, la web le ofrece iniciar sesión o crear su cuenta y, al terminar, lo regresa a la misma propiedad con sus fechas.
- Puede ver cómo convertirse en anfitrión (`anfitriones.html`) antes de crear su cuenta.

### Cliente
- Todo lo del visitante, ya con su sesión.
- Reserva, paga, ve sus reservas, sus mensajes con los anfitriones y su cuenta.
- Mientras no sea anfitrión, «Conviértete en anfitrión» lo lleva a la página que explica cómo y le deja empezar.

### Anfitrión
- Deja de ver la página que explica cómo ser anfitrión y ve sus funciones: sus propiedades, las reservas que le llegan, las reseñas y comentarios que recibe, los chats con sus clientes y publicar una propiedad nueva.
- Sigue pudiendo reservar como cliente: una sola cuenta puede ser huésped y anfitrión (decisión del modelo de datos).
- Sus cobros y su membresía viven en su vista, no en la del cliente.

### Administrador
- Es la vista de mantenimiento de las páginas y de la plataforma: cola de verificaciones, casos, suspender y reactivar, cargos con cuatro ojos, bitácora (módulo Admin de la arquitectura).
- Puede ver las vistas del anfitrión y del cliente, para probar la plataforma con su propio usuario. Verlas no es actuar en nombre de otra persona.
- Solo la ven las tres personas del equipo. Entra con segundo factor y su sesión se cierra a los 30 minutos sin uso.

## Cómo se decide la vista, y dónde está el permiso

1. La web pregunta a `GET /auth/me`. Hoy contesta nombre, correo, país, idioma, `is_host` y la clave anti-falsificación. Falta `is_admin`.
2. Con esa respuesta, la web elige la variante de la cabecera.
3. **La cabecera es comodidad, no seguridad.** El permiso de cada cosa lo da la API en cada ruta, por dueño del recurso (`CLAUDE.md`): que un anfitrión no vea el enlace de «Cargos» no significa que no pueda pedirlo. Cada ruta de anfitrión o de administrador comprueba quién es la persona antes de contestar.
4. Las pantallas del anfitrión y del administrador, si alguien entra a su dirección sin serlo, responden con una página que lo explica y lo lleva a su vista, no con un error de la API.

## Decisiones por tomar

Cada una con mi recomendación; ninguna se construye hasta que Sophia decida.

1. **La barra de navegación del cliente.** Íntegro solo tiene alojamientos hoy. ¿Se pone la barra «Todo, Alojamientos, Experiencias, Servicios» desde ya, o solo «Alojamientos»? Recomendación: solo «Alojamientos» hasta que existan experiencias y servicios; agregarlos después es una entrada más de la tabla de variantes.
2. **El buscador.** Hoy vive en el centro de la portada. Airbnb lo pone debajo de la cabecera y Wander dentro de ella. Recomendación: dejarlo donde está hasta definir la portada del cliente; se decide aparte.
3. **La cuenta en la cabecera.** Hoy es texto («Iniciar sesión» o el nombre y «Cerrar sesión»). Airbnb usa un ícono con menú. Las reglas de estilo del proyecto piden no usar íconos. Recomendación: el nombre como texto con un menú desplegable de texto.
4. **«Crear cuenta» en la cabecera del visitante.** Hoy solo está en la ventana de iniciar sesión. Recomendación: agregarlo como enlace de texto junto a «Iniciar sesión».
5. **Reseñas y comentarios del anfitrión.** Sophia los nombró por separado. ¿Qué es cada uno? Recomendación: «Reseñas» son las que los huéspedes dejan de una estancia; «Comentarios» necesitaría una definición propia (¿comentarios de Íntegro sobre su propiedad, preguntas de huéspedes antes de reservar?).
6. **«Reservas» del anfitrión.** No estaba en su lista. Recomendación: agregarlo, porque sin él el anfitrión no ve quién le llega; en la arquitectura es la pantalla 14.
7. **El revisor.** La arquitectura lista un rol de revisor (quien atiende la cola de verificaciones) además del administrador, y Sophia dijo que solo tres personas tienen la vista de administrador. Recomendación: por ahora no hay revisor aparte; las tres personas del equipo hacen ese trabajo desde su vista.
8. **«Ver como» del administrador.** Dos maneras de que vea las vistas de cliente y de anfitrión: abrir esas páginas con su propia cuenta, o ver exactamente lo que ve otra persona. Recomendación: la primera, sin actuar como otra persona; ver los datos de otra persona exige permisos y bitácora, y se agrega solo si hace falta.
9. **Un anfitrión que aún no termina Verificación.** ¿Ve ya la vista de anfitrión o sigue en la de cliente con un aviso de lo que le falta? Recomendación: sigue en la de cliente hasta tener el perfil de anfitrión; en la vista de anfitrión nadie ve funciones que todavía no puede usar.
10. **Regreso después de iniciar sesión.** Hoy, al iniciar sesión la persona se queda en la página donde estaba. Para «Reservar» sin sesión hace falta además conservar las fechas y el número de huéspedes. Recomendación: guardarlos en la dirección de la página, no en el navegador.

## Orden propuesto para construirlas

1. **La vista en la API.** Agregar `is_admin` a `GET /auth/me`, con sus pruebas contra la base.
2. **La cabecera por vista.** Las variantes del visitante y del cliente en `estructura.js`, con «Crear cuenta» y el menú de la cuenta, y el aviso de la página protegida.
3. **Reservar sin sesión.** El camino de la ficha al inicio de sesión o al registro y de vuelta, con sus fechas.
4. **La vista del anfitrión.** Su cabecera y sus pantallas, cuando exista Verificación (punto 3): sin perfil de anfitrión no hay vista de anfitrión.
5. **La vista del administrador.** Su cabecera y la cola de verificaciones, con el segundo factor.

Cada paso es una pieza con su especificación, sus pruebas contra la base y su veredicto.

## Fuente

Descripción de Sophia del 20 de noviembre de 2026 y sus dos capturas de referencia, Airbnb y Wander. `docs/arquitectura.md`, módulos Cuentas y Admin. ADR 0008, 0014 y 0015. `docs/diseno/pantallas.md` y `benchmark-competencia.md`.
