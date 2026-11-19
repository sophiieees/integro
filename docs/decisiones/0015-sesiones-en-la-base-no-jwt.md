# ADR 0015: La sesión se guarda en la base de datos, no en un JWT

**Estado:** aceptada (Sophia, 17 de noviembre de 2026).

## Contexto
`docs/arquitectura.md`, de octubre, decía "Autenticación JWT" y preveía una ruta `/auth/refresh` para renovar el pase. El modelo de datos aceptado en noviembre (`docs/database/data-model.md`, decisión 6) diseñaba una tabla `sessions` con la huella de una llave. Son dos mecanismos distintos y había que elegir uno antes de construir el módulo de Cuentas.

Con un JWT la persona recibe un pase firmado con fecha de vencimiento y la base no guarda nada: no se puede cerrar la sesión de verdad, porque una copia robada sigue sirviendo hasta que vence.

## Decisión
- Al iniciar sesión se crea una fila en `sessions` y la persona recibe una llave al azar. La base guarda solo la huella de esa llave (SHA-256), nunca la llave.
- En cada petición la API busca la huella. La sesión sirve mientras exista, no haya vencido y `revoked_at` siga vacía.
- Cerrar sesión anota la fecha en `revoked_at` y la llave deja de servir en ese instante. Así también se puede cerrar la sesión de un celular robado.
- De cada sesión se guarda desde dónde se abrió: dirección IP, navegador y último uso (`ip_address`, `user_agent`, `last_used_at`).
- La persona puede leer sus propias sesiones, sin la huella, para ver dónde tiene sesión iniciada. Crear, cambiar y cerrar sesiones lo hace solo el sistema.

### Cómo viaja la llave
Decidido por Sophia el 19 de noviembre de 2026, al construir la primera pantalla conectada a la API.

- La llave viaja en una cookie, `integro_session`, que el código de la página no puede leer (`HttpOnly`). Si un script malicioso llegara a entrar a la página, no podría copiarla.
- Solo la cookie: la API ya no acepta la llave en el encabezado `Authorization: Bearer`, que fue la decisión del 18 de noviembre, ni la entrega en el texto de la respuesta del inicio de sesión.
- La cookie solo se manda en peticiones hechas desde el mismo sitio (`SameSite=Strict`) y vale para todo el sitio (`Path=/`).
- Dura el plazo sin uso de la sesión, 30 días para un huésped y 7 para un anfitrión, y cada petición con sesión la vuelve a entregar para renovarlo.
- Exige HTTPS (`Secure`). Solo en desarrollo se apaga, con `SESSION_COOKIE_SECURE=false`, porque el servidor local no tiene HTTPS.

### Cerrar sesión y defensas
Decidido por Sophia el 19 de noviembre de 2026.

- La persona cierra su sesión actual, ve dónde tiene sesión abierta (fecha, navegador, dirección y cuál es la actual) y puede cerrar una en particular o todas las demás. Al cerrar la actual, la API borra la cookie.
- Toda petición con sesión que cambie algo pasa tres defensas contra peticiones hechas desde páginas ajenas: la cookie solo viaja desde el mismo sitio; se revisa que la petición venga de una dirección de Íntegro; y la petición trae una clave anti-falsificación ligada a su sesión, que la API entrega a la página y una página ajena no puede leer. Si falla una, la API responde `403` y no cambia nada.
- La clave anti-falsificación no se guarda: se calcula con la llave secreta del servidor a partir de la llave de sesión.

Se descartaron el JWT solo, porque no se puede revocar, y el JWT corto con una llave de renovación guardada, porque son dos mecanismos que construir y probar para tres personas.

## Consecuencias
- Cada petición con sesión hace una consulta a la base. Con la carga de la fase 1 no es un problema.
- La ruta `/auth/refresh` de la arquitectura ya no aplica. Las rutas del módulo de Cuentas se fijan al construir cada pieza.
- La dirección IP y el navegador son datos personales: van en el aviso de privacidad. Sophia lo revisa con Valeria, que lleva la parte legal, después de la arquitectura.
- El sistema no borra sesiones, así que las vencidas se acumulan. Hace falta una tarea de limpieza más adelante.
- Falta decidir cuánto dura una sesión. Se decide al construir el inicio de sesión.
- Con la llave en una cookie, la página y la API tienen que estar en el mismo sitio para que el navegador la mande. En desarrollo la API muestra también la web; al publicar, las dos van bajo el mismo dominio. Queda por decidir con el alojamiento.
- Una cookie viaja sola, así que las rutas con sesión que cambian algo llevan las tres defensas de arriba. Cada ruta nueva de ese tipo tiene que pedirlas, y cada pantalla nueva tiene que mandar la clave anti-falsificación.
- La página no puede borrar la cookie: cerrar sesión lo hace la API.
- Al publicar, las direcciones de la web van en `ALLOWED_ORIGINS`.
- Una app de celular no usa cookies. Si llega a haberla, el encabezado se agrega en su propia pieza.

## Fuente
Decisiones de Sophia del 17 y del 19 de noviembre de 2026. Bitácora, decisiones 16.2, 16.5, 16.6 y 16.15. `database/migrations/20261117000003_sessions_codes_password_resets.sql`. `docs/database/data-model.md`, decisiones 15, 16 y 19.

## Cambios
- 19 de noviembre de 2026: se agregó cómo viaja la llave. Pasa del encabezado `Authorization: Bearer` a una cookie que la página no puede leer.
- 19 de noviembre de 2026, más tarde: se agregaron cerrar sesión, la lista de sesiones y las tres defensas.
