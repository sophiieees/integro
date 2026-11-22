# Backend de Íntegro

API REST en Python con FastAPI (ADR 0012), conectada a PostgreSQL propio (ADR 0013). Es un monolito modular (ADR 0002): una sola aplicación, con todas las rutas bajo `/api/v1` (ADR 0001).

Esta carpeta contiene hoy solo el esqueleto: la aplicación arranca, lee su configuración, abre el grupo de conexiones a la base y responde dos rutas de comprobación. Los módulos de `docs/arquitectura.md`, sección 4, se agregan uno por pieza; el primero es Cuentas.

## Estructura

| Ruta | Para qué |
|---|---|
| `app/main.py` | Punto de entrada. Construye la aplicación y abre y cierra el grupo de conexiones. |
| `app/core/config.py` | Lee y valida las variables de entorno. Si falta una, el backend no arranca y dice cuál. |
| `app/database/connection.py` | Grupo de conexiones a PostgreSQL con psycopg 3 y la comprobación de que la base responde. |
| `app/database/transaction.py` | Transacciones con papel: como el sistema o como una persona con sesión. Todo acceso a las tablas pasa por aquí. |
| `app/api/v1/router.py` | Reúne las rutas de la versión 1. Cada módulo agrega aquí las suyas. |
| `app/api/v1/health.py` | Las dos rutas de comprobación. |
| `app/modules/` | Módulos de dominio. Cada módulo crea su carpeta en su pieza. |
| `app/modules/accounts/` | Cuentas: reglas del formulario (`validation.py`), qué tan confiable es una contraseña (`password_strength.py`), contraseñas, códigos y llaves (`security.py`), códigos de un solo uso (`codes.py`), registro y comprobación del correo (`registration.py`), inicio de sesión (`login.py`), sesiones (`sessions.py`) y sus rutas (`router.py`). |
| `app/api/protection.py` | Defensas de las peticiones con sesión que cambian algo: de dónde viene la petición y la clave anti-falsificación. |
| `app/web.py` | Muestra las páginas de `web/` desde la misma dirección de la API. |
| `app/api/auth.py` | Quién hace la petición: lee la llave de la cookie de sesión, entrega la sesión a la ruta que la pida y renueva la cookie. |
| `app/notifications/` | Envío de códigos. Hoy solo el modo desarrollo (`console.py`); WhatsApp queda pendiente (`whatsapp.py`). |
| `requirements.txt` | Incluye la lista de dependencias, que vive en `requirements.txt` de la raíz del repositorio (Vercel solo lee ese). |
| `requirements-dev.txt` | Lo anterior más lo necesario para correr las pruebas. |
| `.env.example` | Plantilla de las variables de entorno, sin contraseña. |

Las tablas no viven aquí: están en `database/migrations/`, en la raíz del repositorio. Las pruebas del backend están en `tests/backend/`.

## Rutas

| Ruta | Respuesta |
|---|---|
| `GET /api/v1/health` | `200 {"status": "ok"}`. No toca la base de datos. |
| `GET /api/v1/health/database` | `200 {"status": "ok", "database": "integro", "port": 5433, "server_version": "18.x"}` si la base responde. `503 {"status": "unavailable"}` si no, sin el motivo ni datos de conexión. |
| `POST /api/v1/auth/register` | Crea la cuenta y envía un código de 6 dígitos al correo. `201 {"status": "verification_required", "email": "..."}`. `422` si falta o no sirve un dato; `409` si el correo o el teléfono ya tienen cuenta. |
| `POST /api/v1/auth/verify-email` | Comprueba el correo con el código. `200 {"status": "verified"}`. `400` si el código es incorrecto, venció o agotó sus 5 intentos; `409` si el correo ya estaba comprobado. |
| `POST /api/v1/auth/resend-code` | Envía otro código. `200 {"status": "sent"}`. `429` si no han pasado 60 segundos o ya van 5 en una hora. |
| `POST /api/v1/auth/correct-unverified-email` | Corrige el correo de una cuenta que todavía no lo ha comprobado. Se manda el correo, la contraseña con la que se registró y el correo correcto. `200 {"status": "verification_required", "email": "..."}`: la cuenta cambia de correo, el código anterior deja de servir y llega uno nuevo al correo nuevo. `401` si la contraseña no es correcta o el correo no tiene cuenta (la misma respuesta); `409` si la cuenta ya estaba comprobada o el correo nuevo es de otra cuenta; `422` si falta un dato, está mal escrito o es el mismo correo; `429` por la espera del dispositivo o el máximo de códigos por hora. Cuenta como un intento de entrar (ADR 0014). |
| `POST /api/v1/auth/password-reset/request` | Recuperar la contraseña, paso 1. Se manda el correo. Contesta siempre `200 {"status": "code_requested"}`, tenga o no cuenta ese correo, esté comprobado o no, y aunque no se envíe nada por los límites (un minuto entre envíos y 5 por hora): así la respuesta no dice quién tiene cuenta. Solo una cuenta con el correo comprobado recibe el código de 6 dígitos, que vence a los 30 minutos (`PASSWORD_RESET_TTL_SECONDS`) y deja sin efecto a los anteriores. `422` si falta el correo. |
| `POST /api/v1/auth/password-reset/confirm` | Recuperar la contraseña, paso 2. Se manda el correo, el código y `new_password`. `200 {"status": "password_changed"}`: la contraseña nueva (mismas reglas del registro, revisadas antes de gastar el código) se guarda con Argon2id, el código queda gastado, **se cierran todas las sesiones de la cuenta** y se avisa por correo al dueño (aviso `password_changed`: cuándo, navegador y dirección, sin contraseñas ni códigos); la persona inicia sesión de nuevo. `400` con `invalid_code` (y `attempts_left`), `code_expired` o `too_many_attempts`; un correo sin cuenta o sin comprobar y un código de otro propósito contestan `invalid_code`. `422` con las faltas de la contraseña por campo `new_password`, o `too_weak` si cumple las reglas pero es fácil de adivinar, como en el registro. `429 try_later` si ese dispositivo juntó 6 fallos en 15 minutos: los códigos equivocados cuentan para la misma espera del inicio de sesión, sin avisar al dueño de la cuenta. |
| `POST /api/v1/auth/password-strength` | Califica una contraseña mientras la persona la escribe. `200 {"level": "reliable", "label": "Confiable", "weaknesses": [], "hints": [], "strengths": [], "raise_hints": ["Usa dos símbolos distintos para subir un nivel."], "meets_rules": true, "accepted": true, "errors": []}`. No guarda ni anota nada. `accepted` dice si el registro la aceptaría. `weaknesses` y `hints` dicen lo que le resta; `strengths` y `raise_hints`, lo que le suma: `strengths` trae `varied_symbols` cuando dos símbolos distintos ya le subieron el nivel y `raise_hints` trae el consejo cuando todavía puede subir. |
| `POST /api/v1/auth/login` | Inicio de sesión, paso 1: correo y contraseña. `200 {"status": "code_required"}` y envía un código al correo. `401` si el correo o la contraseña no son correctos (la misma respuesta en los dos casos); `403` si el correo no está comprobado; `429` si no han pasado 60 segundos o ya van 5 códigos en una hora. |
| `POST /api/v1/auth/login/verify` | Inicio de sesión, paso 2: el código. `200 {"status": "session_opened", "expires_at": "..."}` y entrega la llave en la cookie `integro_session`; el texto de la respuesta no trae la llave. `400` si el código es incorrecto, venció o agotó sus 5 intentos, y entonces no hay cookie. |
| `GET /api/v1/auth/captcha` | La llave pública del CAPTCHA: `200 {"site_key": "..."}`. La página la pide para mostrar el desafío de Cloudflare Turnstile. No es secreta. `503` si no está configurada. |
| `GET /api/v1/auth/me` | Los datos de la persona con sesión, con `is_host` e `is_admin`, que dicen qué vistas tiene (docs/diseno/vistas.md). La llave llega en la cookie `integro_session`, que el navegador manda solo; sin una cookie que sirva responde `401`. Cada uso renueva la cookie. |
| `POST /api/v1/auth/logout` | Cierra la sesión actual y borra su cookie. `200 {"status": "signed_out"}`. `401` sin sesión; `403` si la petición no pasa las defensas. |
| `GET /api/v1/auth/sessions` | Las sesiones abiertas de la persona: `{"sessions": [{"id", "created_at", "last_used_at", "expires_at", "ip_address", "user_agent", "current"}]}`. Nunca la llave ni su huella. |
| `DELETE /api/v1/auth/sessions/{id}` | Cierra una de sus sesiones. `200 {"status": "closed", "closed": 1}`. `404` si es de otra persona, no existe o ya estaba cerrada. |
| `POST /api/v1/auth/sessions/close-others` | Cierra todas sus sesiones menos la actual. `200 {"status": "closed", "closed": 2}`. |
| `GET /docs` | Documentación OpenAPI que FastAPI genera a partir del código. Desde ahí se pueden probar las rutas. |
| `GET /` y lo demás | Las páginas de `web/`: la portada en `/`, y `propiedad.html`, `anfitriones.html`, `como-funciona.html` y `assets/` por su nombre. Las rutas de arriba ganan siempre. |

La API muestra también la web (`app/web.py`): al arrancarla, `http://127.0.0.1:8000/` abre la portada. Así la página y la API viven en la misma dirección y el navegador manda la cookie de sesión. Ocurre si la carpeta `web/` existe junto a `backend/` y se apaga con `SERVE_WEB=false`. Solo entrega archivos de `web/`, solo para leerlos, y pide al navegador que pregunte siempre si cambiaron.

**CAPTCHA (ADR 0016).** Cinco rutas lo piden: `register`, `login` (paso 1), `password-reset/request`, `resend-code` y `correct-unverified-email`. La página resuelve el desafío de Cloudflare Turnstile y manda el resultado en el encabezado `X-Captcha-Token`; la API se lo pregunta a Cloudflare con la llave secreta (`app/api/captcha.py`). Un resultado sirve una sola vez y dura 5 minutos, así que la página pide uno nuevo antes de cada petición. Se revisa antes que el formulario. Cada ruta espera su acción, que el widget de su pantalla declara y Cloudflare devuelve al comprobar: `register`, `login`, `password_reset`, `resend_code` y `correct_email`; un resultado de otra acción es `captcha_failed`. Sin resultado, vacío, repetido o falso: `400` con el código `captcha_failed`. Si Cloudflare no responde (red, tiempo de 5 segundos, error suyo) o la llave secreta falta o no sirve: `503` con `captcha_unavailable`; nunca se deja pasar. En los dos casos no se crea ni se envía nada y el aviso sale con el campo `captcha`. Los pasos en los que se escribe un código (`verify-email`, `login/verify`, `password-reset/confirm`) no lo piden. **No hay interruptor:** el CAPTCHA siempre está activo; en la computadora y en las pruebas valen las llaves de prueba de Cloudflare.

Los avisos de las rutas de Cuentas salen siempre con la misma forma, para ponerlos junto a su campo: `{"errors": [{"field": "password", "code": "missing_symbol", "message": "..."}]}`.

Reglas del registro: todos los datos son obligatorios, 18 años cumplidos (contados con la fecha del país que la persona eligió; si el país tiene varios husos horarios, con el más adelantado), y contraseña de 10 a 20 caracteres con mayúscula, minúscula, número y símbolo, sin espacios, que alcance al menos el nivel medio.

Niveles de la contraseña: bajo, medio, confiable y muy confiable. El largo da el nivel base (10 a 12 medio, 13 a 15 confiable, 16 a 20 muy confiable) dos símbolos distintos o más lo suben un nivel (sin pasar de muy confiable; el mismo símbolo dos veces no cuenta) y después cada debilidad lo baja un nivel: tres caracteres iguales seguidos, cuatro seguidos en orden (1234, abcd, qwer, y símbolos en fila en el teclado como `!"#$` o `$%&/`), el nombre o el correo de la persona (palabras de cuatro letras o más), o una palabra de la lista de palabras comunes (password, contraseña, íntegro, qwerty, admin, bienvenido, welcome, letmein, 1234, gato, yo, perro, cuenta2026, 123456, 111111, 000000, 123123, 123456789, Pass@123, 1234567890, abcd1234), sin distinguir mayúsculas ni acentos; «yo» solo cuenta como palabra suelta, sin otra letra pegada, para que no baje el nivel de «mayo». Una misma parte puede contar dos veces: 1234 es secuencia y palabra común. La cuenta no puede iniciar sesión hasta comprobar el correo.

Reglas del inicio de sesión (ADR 0014): en cada inicio se piden correo, contraseña y un código que llega al correo; no se recuerdan dispositivos. La sesión se guarda en la base (ADR 0015): la persona recibe una llave y la base guarda solo su huella. La sesión se cierra sola a los 30 días sin uso si la persona es huésped y a los 7 si es anfitriona; cada uso renueva el plazo. **Quien es administrador (tabla `admins`) tiene una sesión corta en todo el sitio, no solo en las pantallas de administración:** se cierra a los 30 minutos sin uso (`SESSION_IDLE_MINUTES_ADMIN`) y, aunque se use todo el tiempo, a las 12 horas de haber iniciado sesión (`SESSION_MAX_HOURS_ADMIN`); su cookie dura lo que le queda a la sesión. El papel se lee en cada petición, así que también vale para una sesión abierta antes de que la persona fuera administradora, y si es anfitriona y administradora a la vez gana el límite del administrador. Una sesión vencida por estos límites se cierra en la base y la petición es `401`. Una persona puede tener varias sesiones abiertas a la vez, cada una con su propio plazo.

La llave de sesión viaja en una cookie (ADR 0015): `integro_session`, con `HttpOnly` (el código de la página no puede leerla), `SameSite=Strict` (solo se manda desde el mismo sitio), `Path=/` y la duración del plazo sin uso. Lleva `Secure` (solo HTTPS) salvo que `SESSION_COOKIE_SECURE=false`, que es para desarrollo. La API no acepta la llave en el encabezado `Authorization`.

Contraseñas incorrectas (ADR 0014): la cuenta nunca se bloquea. A los 3 fallos seguidos contra una cuenta se le avisa a su dueño por correo. A los 6 fallos en 15 minutos desde el mismo dispositivo (dirección IP y navegador), ese dispositivo recibe `429` con el código `try_later` y los segundos que faltan, aunque escriba la contraseña correcta; desde otro dispositivo se entra normal. Cada intento queda en la tabla `login_attempts`.

Una ruta que necesita sesión la pide con `Depends(require_session)`, de `app/api/auth.py`, y abre su transacción con `user_transaction(pool, session.user_id)`.

Una ruta de anfitrión o de administrador la pide con `Depends(require_host)` o `Depends(require_admin)` (y `require_host_for_change` o `require_admin_for_change` si cambia algo), de `app/api/roles.py`: sin sesión responde `401`; con sesión pero sin el papel, `403` con el código `host_only` o `admin_only`. El papel se lee en la base en cada petición. Anfitrión es quien tiene perfil de anfitrión; administrador, quien está en la tabla `admins`. Falta, para las rutas del panel, el tope de 30 minutos sin uso y de 12 horas de sesión, y el segundo factor.

Una ruta con sesión que cambia algo la pide con `Depends(require_session_for_change)`, de `app/api/protection.py`. Son las tres defensas contra peticiones hechas desde páginas ajenas (ADR 0015): la cookie solo viaja desde el mismo sitio; el encabezado `Origin` de la petición tiene que ser la dirección de la propia API o una de `ALLOWED_ORIGINS`; y la petición tiene que traer, en el encabezado `X-CSRF-Token`, la clave anti-falsificación de su sesión, que la API entrega como `csrf_token` en `/auth/login/verify` y en `/auth/me`. Si falla el origen o la clave responde `403` con el código `origin_not_allowed` o `csrf_failed`, y no cambia nada.

En modo desarrollo (`EMAIL_DELIVERY=console`) el código no se envía: aparece en la ventana donde corre el servidor, en una línea que empieza con `[MODO DESARROLLO]`.

## Con qué papel se habla con la base

La API entra a PostgreSQL como `integro_api`, que por sí solo no puede leer ninguna tabla. En cada transacción elige un papel (ADR 0013):

| Función de `app/database/transaction.py` | Papel en la base | Qué alcanza |
|---|---|---|
| `system_transaction(pool)` | `integro_service` | Todo lo que el sistema puede leer y escribir: registro, inicio de sesión, avisos de proveedores. |
| `user_transaction(pool, user_id)` | `integro_app`, con el id anotado en `app.user_id` | Solo las filas de esa persona. Sin un id válido se rechaza antes de tocar la base. |

El papel y el id duran lo que dura la transacción. Al terminar, con éxito o con error, la conexión vuelve al grupo como `integro_api` y sin persona anotada: una petición nunca hereda la identidad de otra.

## Preparar el entorno, una sola vez

Hace falta Python 3.13 y PostgreSQL 18 corriendo en el puerto 5433 con la base `integro` y las migraciones aplicadas. Los comandos son de PowerShell y se corren desde la carpeta `backend/`.

### 1. Crear el usuario de conexión en PostgreSQL

Las migraciones crean los papeles `integro_app` e `integro_service`, que no pueden iniciar sesión. La API entra con un usuario aparte, `integro_api`, que no tiene permisos propios y es miembro de los dos papeles. En pgAdmin, sobre la base `integro`, se corre:

```sql
create role integro_api login noinherit;
grant integro_app to integro_api;
grant integro_service to integro_api;
```

La contraseña no se escribe en SQL. Se pone desde pgAdmin: Login/Group Roles, `integro_api`, Properties, pestaña Definition, campo Password, Save.

`noinherit` significa que `integro_api` no recibe permisos por el solo hecho de ser miembro: en cada transacción la API elige con cuál de los dos papeles actúa.

### 2. Crear el entorno virtual

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Con el entorno activo, la línea de PowerShell empieza con `(.venv)`. Si PowerShell no deja correr el script de activación, se permite solo para esa ventana y se repite la activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 3. Instalar las dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### 4. Escribir la configuración

```powershell
Copy-Item .env.example .env
```

Se abre el archivo con `notepad .env` y se escribe la contraseña de `integro_api` después de `DATABASE_PASSWORD=`. Ese archivo no se sube al repositorio: git lo ignora.

La llave secreta de los códigos se genera al azar y se guarda sin mostrarla. Con el entorno virtual activo:

```powershell
Add-Content .env ""
Add-Content .env "CODE_HASH_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Si el archivo `.env` es anterior a la pieza del registro y no trae la línea del modo de envío, se agrega:

```powershell
Add-Content .env "EMAIL_DELIVERY=console"
```

Y la que deja que la cookie de sesión viaje sin HTTPS, porque el servidor de esta computadora no lo tiene. Solo va en desarrollo; en la nube no se pone:

```powershell
Add-Content .env "SESSION_COOKIE_SECURE=false"
```

Las llaves del CAPTCHA. En tu computadora van las **llaves de prueba** de Cloudflare, que son públicas y siempre pasan, así que no hace falta una cuenta ni un dominio:

```powershell
Add-Content .env "TURNSTILE_SITE_KEY=1x00000000000000000000AA"
Add-Content .env "TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA"
```

Las llaves reales (la pública empieza con `0x4`) van solo en las variables de Vercel. Las de prueba empiezan con `1x`, `2x` o `3x` y siempre pasan, así que la API solo las acepta con `SESSION_COOKIE_SECURE=false`, que es tu computadora: donde la cookie exige HTTPS (la nube) las trata como si faltaran y las cinco rutas del CAPTCHA contestan `503`. Con ellas Cloudflare no devuelve la acción y por eso no se compara. Sin estas dos líneas la API arranca, pero esas rutas contestan `503`.

Cada variable va una sola vez. Si `CODE_HASH_SECRET=` quedó vacía por haber copiado la plantilla, esa línea se borra en el Bloc de notas.

### 5. Dar de alta a un administrador

La API no puede crear ni quitar administradores: las altas y las bajas las hace el dueño de la base, a mano. La persona debe tener ya su cuenta. En pgAdmin, sobre la base `integro` y con el usuario `postgres`:

```sql
insert into admins (user_id)
select id from users where email = 'correo-de-la-persona';
```

Debe contestar `INSERT 0 1`. Si contesta `INSERT 0 0`, ese correo no tiene cuenta. Para quitarla: `delete from admins where user_id = (select id from users where email = 'correo-de-la-persona');`.

## Arrancar el servidor

Con el entorno virtual activo, desde `backend/`:

```powershell
uvicorn app.main:app --reload
```

El servidor queda en `http://127.0.0.1:8000`. Para comprobar que responde, se abren en el navegador:

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/api/v1/health/database`
- `http://127.0.0.1:8000/docs`

Se detiene con Ctrl+C. En los días siguientes solo hace falta activar el entorno y arrancar el servidor.

## Correr las pruebas

Con el entorno virtual activo, desde `backend/`:

```powershell
python -m pytest ..\tests\backend -v -rs
```

Las pruebas no dejan nada guardado en la base. Las que necesitan personas de prueba (`test_transaction.py` y `test_account_access_tables.py`) las crean dentro de una transacción en `integro` y la deshacen al terminar. Las de `test_account_access_tables.py` comprueban las tablas de `database/migrations/20261117000003_sessions_codes_password_resets.sql`; si esa migración no se ha corrido en la base, se omiten y la salida lo dice. Las de `test_login_attempts_admins_tables.py` comprueban las tablas de `database/migrations/20261118000004_login_attempts_admins.sql` y también se omiten si esa migración no se ha corrido. Las del registro (`test_accounts_registration.py`) llaman a las rutas de verdad, también dentro de una transacción que se deshace, y leen el código de un anotador en lugar de enviarlo. Las que usan la base real se omiten si no existe `backend/.env`, y la salida lo dice. Las de `test_health.py` apuntan a un puerto donde no escucha nadie, y por eso tardan unos segundos cada una.

Las pruebas de la web son de dos tipos. Las que leen los archivos de `web/` y la lógica de la pantalla (sin navegador) se corren con `python -m pytest ..\tests\web -v`. Las de principio a fin abren un navegador de verdad contra la API y la base `integro`, también dentro de una transacción que se deshace, y se corren con `python -m pytest ..\tests\e2e -v -rs`; hace falta Edge o Chrome y `websocket-client` (`pip install -r requirements-dev.txt`). Detalles en `tests/e2e/README.md`.

## Si algo falla

| Lo que se ve | Qué significa |
|---|---|
| `ConfigurationError: Configuración incompleta...` al arrancar | Falta `backend/.env` o una de sus variables. El mensaje nombra cuál. |
| `/api/v1/health` responde y `/api/v1/health/database` da 503 | La API está bien y la base no contesta: el servicio de PostgreSQL está detenido, el puerto no es 5433, o el usuario o la contraseña de `.env` no coinciden. El motivo exacto sale en la ventana donde corre el servidor. |
| `uvicorn` no se reconoce como comando | El entorno virtual no está activo. |
