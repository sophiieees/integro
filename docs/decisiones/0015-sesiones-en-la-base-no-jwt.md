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

Se descartaron el JWT solo, porque no se puede revocar, y el JWT corto con una llave de renovación guardada, porque son dos mecanismos que construir y probar para tres personas.

## Consecuencias
- Cada petición con sesión hace una consulta a la base. Con la carga de la fase 1 no es un problema.
- La ruta `/auth/refresh` de la arquitectura ya no aplica. Las rutas del módulo de Cuentas se fijan al construir cada pieza.
- La dirección IP y el navegador son datos personales: van en el aviso de privacidad. Sophia lo revisa con Valeria, que lleva la parte legal, después de la arquitectura.
- El sistema no borra sesiones, así que las vencidas se acumulan. Hace falta una tarea de limpieza más adelante.
- Falta decidir cuánto dura una sesión. Se decide al construir el inicio de sesión.

## Fuente
Decisiones de Sophia del 17 de noviembre de 2026. Bitácora, decisiones 16.2, 16.5, 16.6 y 16.15. `database/migrations/20261117000003_sessions_codes_password_resets.sql`. `docs/database/data-model.md`, decisiones 15, 16 y 19.
