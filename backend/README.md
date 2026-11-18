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
| `app/modules/accounts/` | Cuentas: reglas del formulario (`validation.py`), contraseñas y códigos (`security.py`), registro y comprobación del correo (`registration.py`) y sus rutas (`router.py`). |
| `app/notifications/` | Envío de códigos. Hoy solo el modo desarrollo (`console.py`); WhatsApp queda pendiente (`whatsapp.py`). |
| `requirements.txt` | Dependencias del backend, con versión exacta. |
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
| `GET /docs` | Documentación OpenAPI que FastAPI genera a partir del código. Desde ahí se pueden probar las rutas. |

Los avisos de las rutas de Cuentas salen siempre con la misma forma, para ponerlos junto a su campo: `{"errors": [{"field": "password", "code": "missing_symbol", "message": "..."}]}`.

Reglas del registro: todos los datos son obligatorios, 18 años cumplidos (contados con la fecha del país que la persona eligió; si el país tiene varios husos horarios, con el más adelantado), y contraseña de 8 a 12 caracteres con mayúscula, minúscula, número y símbolo, sin espacios. La cuenta no puede iniciar sesión hasta comprobar el correo.

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

Cada variable va una sola vez. Si `CODE_HASH_SECRET=` quedó vacía por haber copiado la plantilla, esa línea se borra en el Bloc de notas.

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

Las pruebas no dejan nada guardado en la base. Las que necesitan personas de prueba (`test_transaction.py` y `test_account_access_tables.py`) las crean dentro de una transacción en `integro` y la deshacen al terminar. Las de `test_account_access_tables.py` comprueban las tablas de `database/migrations/20261117000003_sessions_codes_password_resets.sql`; si esa migración no se ha corrido en la base, se omiten y la salida lo dice. Las del registro (`test_accounts_registration.py`) llaman a las rutas de verdad, también dentro de una transacción que se deshace, y leen el código de un anotador en lugar de enviarlo. Las que usan la base real se omiten si no existe `backend/.env`, y la salida lo dice. Las de `test_health.py` apuntan a un puerto donde no escucha nadie, y por eso tardan unos segundos cada una.

## Si algo falla

| Lo que se ve | Qué significa |
|---|---|
| `ConfigurationError: Configuración incompleta...` al arrancar | Falta `backend/.env` o una de sus variables. El mensaje nombra cuál. |
| `/api/v1/health` responde y `/api/v1/health/database` da 503 | La API está bien y la base no contesta: el servicio de PostgreSQL está detenido, el puerto no es 5433, o el usuario o la contraseña de `.env` no coinciden. El motivo exacto sale en la ventana donde corre el servidor. |
| `uvicorn` no se reconoce como comando | El entorno virtual no está activo. |
