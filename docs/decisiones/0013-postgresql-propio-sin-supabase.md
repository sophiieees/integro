# ADR 0013: PostgreSQL propio, sin Supabase, con autenticación propia

**Estado:** aceptada (Sophia, 17 de noviembre de 2026).

## Contexto
El 16 de noviembre de 2026 se había acordado usar Vercel para la web y la API, Supabase para PostgreSQL, autenticación y archivos privados, y Stripe para pagos. El 17 de noviembre Sophia decidió no usar Supabase: la base de datos se desarrolla en PostgreSQL instalado en su computadora, para subirla después a la nube, y sus migraciones no deben depender de ningún servicio externo.

## Decisión
- La base de datos es PostgreSQL propio. En desarrollo corre en la computadora de Sophia: PostgreSQL 18, puerto 5433, base `integro`.
- Las tablas se construyen por grupos, como migraciones de PostgreSQL puro en `database/migrations/`, con sus pruebas en `tests/database/`. El modelo vigente está en `docs/database/data-model.md`.
- La autenticación es propia: el correo, único por persona, vive en `users`; la contraseña, convertida con Argon2id, en `user_credentials`; los teléfonos, varios por persona, en `user_phones`.
- Los permisos por fila usan dos papeles de la base, `integro_app` (persona con sesión) e `integro_service` (el sistema), y el id de la persona que la API anota en el ajuste `app.user_id`.

## Consecuencias
- La misma base corre en cualquier nube que ofrezca PostgreSQL. La nube todavía está por decidir.
- Lo que Supabase daba hecho ahora se construye en el backend: sesiones, comprobación del correo, recuperación de contraseña, códigos de un solo uso, segundo factor y límite de intentos.
- El almacenamiento de archivos privados, que también iba a ser de Supabase, queda por decidir.
- La arquitectura hablaba de PostgreSQL 16 con PostGIS. La instalación es la versión 18 y falta comprobar si PostGIS está instalado; se necesita para la búsqueda geográfica del módulo de Propiedades.
- Se mantiene el ADR 0003: la plataforma no toca dinero ni guarda documentos sensibles. Los pagos siguen con Stripe.

## Fuente
Decisiones de Sophia del 17 de noviembre de 2026. Bitácora, decisión 6.4. `docs/database/data-model.md`.
