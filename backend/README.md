# Backend de Íntegro

API REST en Python con FastAPI (ADR 0012), conectada a PostgreSQL propio (ADR 0013). Es un monolito modular (ADR 0002): una sola aplicación, con todas las rutas bajo `/api/v1` (ADR 0001).

Esta carpeta contiene hoy solo el esqueleto: la aplicación arranca, lee su configuración, abre el grupo de conexiones a la base y responde dos rutas de comprobación. Los módulos de `docs/arquitectura.md`, sección 4, se agregan uno por pieza; el primero es Cuentas.

## Estructura

| Ruta | Para qué |
|---|---|
| `app/main.py` | Punto de entrada. Construye la aplicación y abre y cierra el grupo de conexiones. |
| `app/core/config.py` | Lee y valida las variables de entorno. Si falta una, el backend no arranca y dice cuál. |
| `app/database/connection.py` | Grupo de conexiones a PostgreSQL con psycopg 3 y la comprobación de que la base responde. |
| `app/api/v1/router.py` | Reúne las rutas de la versión 1. Cada módulo agrega aquí las suyas. |
| `app/api/v1/health.py` | Las dos rutas de comprobación. |
| `app/modules/` | Módulos de dominio. Vacío: cada módulo crea su carpeta en su pieza. |
| `requirements.txt` | Dependencias del backend, con versión exacta. |
| `requirements-dev.txt` | Lo anterior más lo necesario para correr las pruebas. |
| `.env.example` | Plantilla de las variables de entorno, sin contraseña. |

Las tablas no viven aquí: están en `database/migrations/`, en la raíz del repositorio. Las pruebas del backend están en `tests/backend/`.

## Rutas

| Ruta | Respuesta |
|---|---|
| `GET /api/v1/health` | `200 {"status": "ok"}`. No toca la base de datos. |
| `GET /api/v1/health/database` | `200 {"status": "ok", "database": "integro", "port": 5433, "server_version": "18.x"}` si la base responde. `503 {"status": "unavailable"}` si no, sin el motivo ni datos de conexión. |
| `GET /docs` | Documentación OpenAPI que FastAPI genera a partir del código. |

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

Se abre `backend/.env` y se escribe la contraseña de `integro_api` después de `DATABASE_PASSWORD=`. Ese archivo no se sube al repositorio: git lo ignora.

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

Las pruebas no escriben en la base. Una sola usa la base real, la que comprueba `integro` en el puerto 5433; si no existe `backend/.env` esa prueba se omite y la salida lo dice. Las demás apuntan a un puerto donde no escucha nadie, y por eso tardan unos segundos cada una.

## Si algo falla

| Lo que se ve | Qué significa |
|---|---|
| `ConfigurationError: Configuración incompleta...` al arrancar | Falta `backend/.env` o una de sus variables. El mensaje nombra cuál. |
| `/api/v1/health` responde y `/api/v1/health/database` da 503 | La API está bien y la base no contesta: el servicio de PostgreSQL está detenido, el puerto no es 5433, o el usuario o la contraseña de `.env` no coinciden. El motivo exacto sale en la ventana donde corre el servidor. |
| `uvicorn` no se reconoce como comando | El entorno virtual no está activo. |
