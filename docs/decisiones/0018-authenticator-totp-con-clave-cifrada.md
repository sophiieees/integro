# ADR 0018: Authenticator (TOTP) para anfitriones y administradores, con la clave cifrada

**Estado:** aceptada (Sophia, 24 y 25 de noviembre de 2026).

## Contexto
`docs/arquitectura.md` pide un segundo factor TOTP obligatorio para anfitriones y panel, y el ADR 0014 dejó dicho que se suma al código del correo y que su clave se guarda cifrada con AES-256-GCM en una tabla que no estaba diseñada. Sophia confirmó el 24 de noviembre que los anfitriones usan una aplicación Authenticator, que no reemplaza al código del correo sino que se le suma (bitácora 41.11 y 41.12), y partió el trabajo en subpasos: activar y comprobar (3.2), pedirlo al iniciar sesión (3.3), pantallas (3.4) y recuperar el acceso (3.6).

## Decisión
- **Estándar:** TOTP, RFC 6238 sobre RFC 4226, con SHA-1, 6 dígitos y periodos de 30 segundos, que es lo que entienden Google Authenticator y Microsoft Authenticator. La clave tiene 20 bytes al azar.
- **Reloj:** se aceptan el código del periodo actual, el del anterior y el del siguiente. Un código no sirve dos veces: se guarda el último periodo aceptado y no se acepta ese ni uno anterior.
- **Quién:** lo activan los anfitriones y los administradores. Un cliente recibe `403`.
- **Activación en dos pasos:** `POST /auth/2fa/setup` genera la clave, la guarda cifrada y la entrega una sola vez (en base32 y como dirección `otpauth://`); queda pendiente. `POST /auth/2fa/confirm` la comprueba con un código de la aplicación y queda activa. Mientras está pendiente se puede volver a empezar, y la clave anterior deja de servir. `GET /auth/2fa` dice el estado y nunca la clave.
- **Contraseña al empezar:** quien tome una sesión abierta no puede ponerle su propio Authenticator a la cuenta. Una contraseña incorrecta cuenta como intento fallido de entrar (ADR 0014): a los 3 se avisa al dueño y a los 6 ese dispositivo espera.
- **Aviso por correo** cuando se activa, igual que con el cambio de contraseña.
- **Códigos incorrectos:** a los 5 seguidos, 15 minutos de espera, también para el código correcto. Los dos números viven en la configuración.
- **Cifrado:** AES-256-GCM (`app/core/encryption.py`). La llave maestra es `DATA_ENCRYPTION_KEY`, de al menos 43 caracteres al azar, fuera del repositorio y de la base y distinta en cada ambiente. De ella se saca con HKDF-SHA256 una llave por uso, y lo cifrado queda amarrado al id de la persona: movido a la fila de otra, no se descifra. La tabla guarda con qué versión de la llave se cifró.
- **Sin la llave:** la API arranca y las rutas del Authenticator contestan `503`; nunca se guarda una clave sin cifrar. Si la variable viene pero es más corta de 43 caracteres, el backend no arranca y lo dice.
- **Tabla:** `user_totp`, una fila por persona; solo el sistema la lee y la escribe, y la persona no lee ni su propia fila.
- **Dependencia nueva:** `cryptography`, porque la biblioteca estándar de Python no trae AES-256-GCM. Los códigos TOTP sí se calculan con la biblioteca estándar.

### Al iniciar sesión (pieza 3.3, 25 de noviembre de 2026)
- Quien tiene el Authenticator activo inicia sesión con su contraseña, el código del correo y el código de su aplicación. La sesión se abre con el código del correo, pero **queda en espera** hasta que escribe el de la aplicación en `POST /auth/2fa/verify`. La fecha en que lo pasó se anota en `sessions.second_factor_at`.
- Mientras la sesión está en espera, toda ruta con sesión responde `403` con `second_factor_required` y ningún dato. Solo aceptan una sesión en espera la ruta del código, cerrar sesión y `/auth/me`, que contesta el mismo `403` más la clave anti-falsificación que la página necesita.
- Cada 30 días (`TWO_FACTOR_REVERIFY_DAYS`) la misma sesión vuelve a quedar en espera, aunque se use a diario. Cada inicio de sesión nuevo lo pide siempre.
- Los mismos límites: un código no sirve dos veces; a los 5 incorrectos seguidos, 15 minutos de espera y un aviso por correo al dueño, porque quien llegó ahí ya escribió la contraseña y el código del correo. La cuenta de intentos es de la persona, no de la sesión.
- Al activar el Authenticator, la sesión con la que se activó ya lo pasó; las demás sesiones abiertas de la persona quedan en espera.
- Un anfitrión o un administrador que todavía no lo activa entra y usa lo de cliente, pero las rutas de anfitrión y de administrador le responden `403` con `two_factor_setup_required` (bitácora 42.2).
- Se construyó antes que la recuperación del acceso (3.6) por decisión de Sophia: mientras solo el equipo use el sitio, quien pierda el celular se recupera a mano, en pgAdmin.

## Consecuencias
- La ventana de iniciar sesión tiene un tercer paso, «Código de Authenticator», que aparece después del código del correo solo para quien lo tiene activo. Mientras la sesión está en espera la cabecera es la del visitante; si la persona recarga o cierra la ventana, «Iniciar sesión» la lleva directo a ese paso, y «Cerrar sesión» en ese paso cierra la sesión en espera. Un código que no sirvió no se deja escrito. Activar el Authenticator desde la web sigue sin pantalla: es la pieza 3.4.
- Con el Authenticator activo no se puede volver a activar aquí. Cambiar de celular, los diez códigos de recuperación y la ayuda del equipo son la pieza 3.6 (bitácora 41.13 y 42.3). **Antes de abrir el sitio a personas de fuera hace falta la 3.6:** quien pierda el celular quedaría sin poder entrar.
- Una sesión en espera sigue existiendo hasta que vence o se cierra. Quien tenga la contraseña y el correo de alguien puede intentar 5 códigos cada 15 minutos; el dueño recibe un aviso cada vez que empieza la espera.
- Si se pierde `DATA_ENCRYPTION_KEY`, o se cambia sin más, las claves guardadas ya no se pueden descifrar y cada persona tiene que activar su Authenticator de nuevo. Cambiar la llave con orden (cifrar de nuevo lo guardado, con `key_version`) queda por construir.
- El código QR lo dibuja la pantalla, en la pieza 3.4, a partir de la dirección `otpauth://`.
- SHA-1 se usa aquí solo para mezclar la clave con la hora, como manda el estándar; no firma ni resume contraseñas.

## Fuente
Decisiones de Sophia del 24 y 25 de noviembre de 2026 (bitácora 41.11, 41.12, 41.13, 42.3 y 42.4, y la especificación de la pieza 3.2, con todas las recomendaciones de la IA aceptadas).
