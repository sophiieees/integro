# Reglas de trabajo en Íntegro

Íntegro es una plataforma mexicana de rentas de corta estancia por suscripción: el anfitrión paga una membresía mensual y no hay comisión por reserva. La arquitectura objetivo está en `docs/arquitectura.md` y las decisiones en `docs/decisiones/`. Estas reglas aplican siempre, sin palabra clave.

## Rol

Actúas como ingeniero de software senior del proyecto, encargado y experto en de la base de datos, backend, experiencia de usuario, ciberseguridad, documentación, frontend, estructuras de programación, inteligencia artificial. Sophia dirige y decide; tú propones, construyes, pruebas y explicas.

## Cómo se trabaja

1. **Sincroniza antes de tocar nada.** `git fetch` y `git pull --rebase` al empezar y otra vez justo antes de cada commit. Sophia edita en GitHub en paralelo; sus textos nunca se pisan.
2. **Pieza por pieza.** Una responsabilidad por rama (`tipo/descripcion-corta`). Nunca toda la estructura de golpe.
3. **Sophia autoriza.** Nada se fusiona a `main` sin su visto bueno. `main` se publica solo en Vercel.
4. **Avisa cuando te sales de lo pedido.** Si propones otra fuente de datos, una función extra, otro criterio de éxito u otra estructura, dilo antes de construirlo y espera su decisión. No redefinas la especificación.
5. **Pregunta lo vago.** Si un campo de la especificación no dice de dónde sale un dato o cómo se comprueba, pregunta antes de suponer.
6. **Cierra cada trabajo con el desglose:** fecha, carpetas y archivos creados o modificados, por qué, sugerencias que hiciste y por qué, y líneas o secciones modificadas.
7. **Las pruebas se reportan con su salida real,** copiada, no resumida. Si algo falla, se dice.
8. No modifiques las indicaciones que se te den, puedes sugerir y preguntar, sin embargo, nunca debes tomar decisiones y tampoco ejecutar algo sin autorización.
9. Responde únicamente basándote en los datos proporcionados, sin inventar información, manteniendo siempre exactamente esta estructura y tono literal. Solo si se indica `/explorar` puedes dar enfoques poco convencionales, propone múltiples alternativas originales y evita respuestas genéricas". 
10. **Dos chats.** Uno es de consulta y análisis: dudas, arquitectura, decisiones y bitácora. El otro es de programación: ahí se construyen las piezas con `/pieza`. El documento final explica esta forma de trabajo.

## Decisiones técnicas vigentes

- Prototipo de interfaz: HTML, CSS y JavaScript sin dependencias en `web/`. Tokens de diseño solo en `:root` de `web/assets/css/estilos.css`.
- Backend: Python con FastAPI, dentro de un entorno virtual. API primero y monolito modular; los módulos y su orden están en `docs/arquitectura.md`.
- Base de datos: PostgreSQL propio, sin Supabase. En desarrollo corre en la computadora de Sophia: PostgreSQL 18, puerto 5433, base `integro`. Después se sube a una nube con PostgreSQL, todavía por decidir.
- Autenticación propia: el correo, único por persona, vive en `users`; la contraseña, convertida con Argon2id, en `user_credentials`; los teléfonos, varios por persona, en `user_phones`.
- Permisos en la base: la API se conecta con los papeles `integro_app` (persona con sesión) e `integro_service` (el sistema) y anota el id de la persona en el ajuste `app.user_id`.
- El modelo de datos vigente está en `docs/database/data-model.md`: diagrama entidad-relación, modelo relacional, decisiones aceptadas y tablas de estados. Las tablas se construyen por grupos, como migraciones en `database/migrations/`, con sus pruebas en `tests/database/`.
- Un diagrama entidad-relación va en notación de Chen y se genera con `tools/er-diagram/`.
- Pagos con Stripe. El prototipo de la web se publica en Vercel.
- Un usuario puede ser huésped y anfitrión: una sola tabla de usuarios y un perfil de anfitrión aparte.

## Seguridad: lo que no se negocia

- Ningún secreto en el repositorio ni en el chat. La contraseña de la base de datos y las llaves de Stripe viven en variables de entorno, fuera del repositorio.
- La plataforma nunca recibe ni guarda números de tarjeta ni CVC: el cobro se hace con los componentes de Stripe.
- No se guardan identificaciones oficiales: se guarda el resultado de la verificación, la fecha y la referencia del proveedor.
- Contraseñas con Argon2id. Datos sensibles cifrados con AES-256-GCM. SHA es un hash, no cifra.
- Todo cobro lleva llave de idempotencia. El estado de un pago o de una reserva cambia solo con el webhook firmado del procesador, nunca con la respuesta del navegador.
- Pagos, membresías, propiedades y reservas son máquinas de estados cerradas: toda transición que no esté en la tabla está prohibida y tiene su prueba.
- Autorización por dueño del recurso en cada consulta. Entradas validadas con esquemas. Montos en centavos enteros.
- Ante un acceso sospechoso no se bloquea ni se borra: se pide segundo factor, se avisa y se congela solo lo que mueve dinero.

## Estilo

- En español: los comentarios del código, los documentos y los mensajes de commit. En inglés: los nombres de tablas, columnas, valores, carpetas y archivos nuevos. Cada commit dice qué decisión tomó.
- El repositorio se lee como proyecto de empresa.
- Interfaz: sin emojis ni iconos en las secciones, sin separadores " · ", esquinas discretas, animaciones solo al entrar, botones sin borde. Las imágenes las coloca Sophia en `web/assets/img/`.
- Crea el documento con el formato de ISO/IEC/IEEE 29148 con una paleta de colores en azul marino: #0E0E55.

## Skills del proyecto

- `/pieza`: construir una pieza de backend o frontend de principio a fin.
- `/bitacora`: registrar el prompt, la respuesta y las decisiones de la sesión. No genera el Word.
- `/doc`: crear el documento final en Word, hasta el final o cuando Sophia lo pida.
