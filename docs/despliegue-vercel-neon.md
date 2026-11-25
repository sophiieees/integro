# Publicar la API y la base en Vercel con Neon

**Estado:** plan del 21 de noviembre de 2026, con las decisiones de Sophia de ese día (sección 4). La cuenta de Neon ya está creada, con el proyecto en Ohio. Falta crear las tablas ahí, comprobar la conexión y armar la estructura de Vercel. «Nube de la base de datos y de la API» no tiene ADR todavía (`docs/decisiones/README.md`); se escribe cuando se confirmen las decisiones de la sección 4.

**Para quién es:** Sophia, y quien del equipo (Valeria, Shakti) vaya a crear cuentas o revisar costos. No lleva ninguna contraseña ni llave, y no debe llevarlas nunca.

## 1. Por qué hoy no funciona en Vercel

Vercel publica solo la carpeta `web/` (`vercel.json` dice `"outputDirectory": "web"`). La API es Python con PostgreSQL y hoy solo corre en la computadora de Sophia. Por eso en Vercel «Iniciar sesión» y «Crear cuenta» dicen «El servidor respondió de forma inesperada»: no hay nada que conteste en `/api/v1/...`.

La web llama a la API en la misma dirección (`/api/v1/...`) y la cookie de sesión es `SameSite=Strict` (ADR 0015). Por eso la página y la API tienen que vivir **en el mismo dominio**. Es lo que obliga a que sea un solo proyecto de Vercel.

## 2. Qué se encontró

Lo que sigue sale de la documentación oficial. Lo marcado **(sin verificar)** no aparece escrito y se comprueba con una prueba real antes de contarlo como cierto (sección 3).

**Vercel**
- FastAPI se publica sin configuración como una sola Vercel Function (con Fluid compute). Vercel busca una variable `app` en `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py` o `asgi.py`, en la raíz o en `src/`, `app/` o `api/`. Nuestro `backend/app/main.py` no está en esos lugares: hace falta `tool.vercel.entrypoint` en un `pyproject.toml` de la raíz, o un `api/index.py` que importe la app. **(sin verificar cuál funciona con nuestra estructura y con `create_app()`)**
- Python 3.12 (por defecto), 3.13 y 3.14; se elige con `.python-version` o `pyproject.toml`. Las dependencias salen de `requirements.txt` o `pyproject.toml`. **(sin verificar si se encuentra un `requirements.txt` dentro de `backend/`)**
- Los eventos `lifespan` de FastAPI sí se ejecutan. Al apagarse, la limpieza tiene como máximo 500 ms.
- Tamaño máximo del paquete de Python: 500 MB sin comprimir. Nuestras dependencias caben de sobra.
- Los archivos estáticos pueden salir del CDN (carpeta `public/` o `app.frontend`) o de la propia función. Un archivo que existe gana sobre una regla de redirección, y comunidad de Vercel reporta que con una regla que manda todo a `api/index` se llegaron a exponer archivos de la raíz (`README.md`, `requirements.txt`) como estáticos; se evita con `.vercelignore`. **(sin verificar cómo conviven `web/` como sitio estático y la función en un mismo proyecto)**
- **Plan Hobby:** la documentación de Vercel dice que es solo para uso personal y no comercial. Íntegro es un proyecto de negocio. Hay que revisarlo con las reglas de uso justo de Vercel antes de publicar con clientes reales; probablemente haga falta el plan Pro.
- **Protección del despliegue:** «Vercel Authentication» está en todos los planes y cubre previsualizaciones y producción: solo entra quien tenga cuenta del equipo en Vercel. La protección con contraseña no está en Hobby y en Pro cuesta 20 dólares al mes por proyecto. Cada rama que se sube crea una previsualización con su propia dirección.

**Neon**
- Neon acepta PostgreSQL 14 a 19, y 18 es el predeterminado: igual que la base local de Sophia. Regiones en AWS que existen: Virginia (`aws-us-east-1`), Ohio (`aws-us-east-2`), Oregón (`aws-us-west-2`) y São Paulo (`aws-sa-east-1`); no hay una en México. La lista de cada organización puede variar.
- Plan gratuito (según su página de preguntas frecuentes, actualizada en octubre de 2026): 100 horas de cómputo por proyecto al mes, 1 GB de almacenamiento por proyecto, hasta 2 CU, y el cómputo se suspende a los 5 minutos sin uso. Al despertar tarda unos cientos de milisegundos y se pierde todo lo que viva solo en la sesión. Si se acaban las horas, las conexiones fallan hasta el siguiente mes o hasta cambiar de plan.
- Hay dos direcciones para conectarse: la **directa** (`DATABASE_URL_UNPOOLED` en la integración de Vercel) y la **agrupada** (`-pooler`, con PgBouncer en modo de transacción; `DATABASE_URL`). Neon recomienda la agrupada para funciones serverless y la directa para migraciones.
- En la agrupada **no sirven** `SET`/`RESET` de sesión, `LISTEN`/`NOTIFY`, `PREPARE` en SQL, tablas temporales con `PRESERVE`, `LOAD` ni candados de sesión. Sí sirven los *prepared statements* del protocolo. Neon recomienda `SET LOCAL` dentro de una transacción como solución para ajustes. **(sin verificar `SET LOCAL ROLE` ni `set_config(..., true)`, que son justo lo que usa nuestra API para elegir el papel y la persona en cada transacción)**
- Un rol creado con `CREATE ROLE` desde SQL no es de `neon_superuser`: solo tiene lo que se le dé. Eso es lo que queremos para `integro_api`. Los roles que se crean desde la consola de Neon **sí** reciben `neon_superuser`: no se debe usar la consola para crear a `integro_api`, `integro_app` ni `integro_service`.
- La integración de Neon con Vercel pone variables como `DATABASE_URL` y `PGPASSWORD` con el rol del proyecto, que es muy poderoso. La API de Íntegro no debe usar ese rol; usa `integro_api`.

## 3. Lo que hay que comprobar con pruebas reales

Son cuatro, y se corren en cuanto exista la base en Neon. No se afirma nada de esto hasta verlo.

1. **El papel por transacción en la conexión agrupada.** Un script (`tools/database/verify_connection.py`, ya escrito y probado contra la base local) se conecta como `integro_api` y comprueba: que `set local role integro_service` y `set_config('app.user_id', …, true)` funcionan dentro de una transacción; que al terminar la conexión vuelve a ser `integro_api` y sin persona anotada; y que 200 transacciones seguidas, alternando entre sistema y personas distintas, **nunca heredan** la identidad de otra. Esto es lo más importante de seguridad de todo el plan.
2. **El SSL.** La conexión tiene que ir cifrada (`sslmode=require`).
3. **Las migraciones.** Que las cinco corran en orden en Neon y que las pruebas de tablas pasen contra esa base.
4. **Vercel en una previsualización.** Que la función arranque con nuestra estructura, que `/api/v1/health` y `/api/v1/health/database` contesten, que las páginas salgan y que el registro, el inicio de sesión y la cookie funcionen en la dirección de la previsualización.

## 4. Decisiones de Sophia

Decididas el 21 de noviembre de 2026:

1. **Opción A:** la API en Vercel y la base en Neon, en **un solo proyecto de Vercel**, porque la cookie exige un solo dominio.
2. **Plan de Vercel:** se prueba en Hobby con la protección de Vercel Authentication encendida. Se pasa a Pro antes de que entre alguien que no sea del equipo; antes de eso, Sophia avisa a Shakti y a Valeria. Todavía no se ha comprado nada.
3. **Demostración solo para el equipo**, hasta tener el correo real.
4. **La base se crea directo en Neon**, no desde la integración de Vercel.
5. **CAPTCHA:** Cloudflare Turnstile, plan gratuito (ADR 0016, 22 de noviembre de 2026). Siempre activo, sin interruptor. Si Cloudflare no responde, se rechaza. Detalles en la sección 5 bis.

Por decidir:

6. **Región.** El proyecto de Neon quedó en Ohio (`aws-us-east-2`). Neon **no permite cambiar la región de un proyecto**; para cambiarla hay que crear otro y borrar el primero (hoy está vacío, así que no se pierde nada). Hay dos caminos:
   - **Quedarse en Ohio (recomendado).** Vercel tiene una región en Cleveland (`cle1`) que, según su tabla de regiones, es la de AWS `us-east-2`: la misma que Neon. La función se configura en esa región y quedan juntas. Hobby permite una sola región, y alcanza. Falta comprobar en una previsualización que la función respete la región.
   - **Virginia.** Crear otro proyecto de Neon en `aws-us-east-1` y borrar el de Ohio. Quedaría junto a la región por defecto de Vercel (Washington D.C., `iad1`). Funciona igual y cuesta unos minutos.

## 5. Pasos, en orden

**Sophia, ahora**
1. Decidir la región (sección 4, punto 6).
2. En Neon, abrir el proyecto y presionar **Connect**. Elegir la rama `main`, la base (por defecto `neondb`) y el rol que Neon creó con el proyecto. Con **Connection pooling apagado** se ve la dirección **directa** (`ep-…`, sin `-pooler`); con **encendido**, la **agrupada** (`ep-…-pooler…`). Se usan las dos. Neon muestra ahí la contraseña de ese rol: se escribe solo en pgAdmin, nunca en el chat.
3. En pgAdmin: clic derecho en Servers, Register, Server. Pestaña General: nombre «Neon Íntegro». Pestaña Connection: **Host name/address** = la dirección **directa** (es el primer campo; si queda vacío, pgAdmin dice «Either Host name or Service must be specified»), Port 5432, Maintenance database `neondb`, Username = el rol del proyecto (no `postgres`), Password. Pestaña **Parameters**: SSL mode `require`. Guardar.
4. Abrir Query Tool en la base `neondb` y correr, **una por una y en este orden**, abriendo cada archivo con el icono de carpeta y presionando F5 (sin guardarlos): `20261117000001_users_host_profiles_verifications.sql`, `20261117000002_user_phones.sql`, `20261117000003_sessions_codes_password_resets.sql`, `20261118000004_login_attempts_admins.sql`, `20261121000005_password_reset_code.sql` y `20261124000006_user_totp.sql`, todos de `database/migrations/`. La base de Neon y la de la computadora son independientes: cada migración nueva se corre en las dos. Si alguno da error, se manda el texto del error (sin contraseñas).
5. En el mismo Query Tool, crear a `integro_api` con las tres líneas de `backend/README.md` y ponerle su contraseña en pgAdmin (Login/Group Roles, `integro_api`, Properties, pestaña Definition). **No** crear roles desde la consola de Neon.
6. Generar la llave de los códigos con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
7. Crear con el Bloc de notas el archivo `backend\.env.neon` (git lo ignora; el nombre no debe terminar en `.txt`) con estas líneas, llenando cada valor:

```
DATABASE_HOST=<dirección agrupada, la que lleva -pooler>
DATABASE_HOST_DIRECT=<dirección directa>
DATABASE_PORT=5432
DATABASE_NAME=neondb
DATABASE_USER=integro_api
DATABASE_PASSWORD=<la contraseña de integro_api>
CODE_HASH_SECRET=<la llave del paso 6>
EMAIL_DELIVERY=console
```

8. Avisarle a la IA que el archivo está listo. La IA corre `python tools/database/verify_connection.py --env backend/.env.neon` (solo lee; no imprime contraseñas) y reporta la salida tal cual.

**La IA, cada paso en su rama, con pruebas y sin fusionar**
1. Correr `tools/database/verify_connection.py` contra Neon (sección 3, puntos 1 y 2) y reportar la salida real. Ya se probó contra la base local: 9 de 9 casos coinciden.
2. Ajustes a la conexión, solo si la verificación los pide: `sslmode`, tiempo de espera de conexión más largo (la primera conexión tras suspenderse tarda más que los 3 segundos de hoy), y `prepare_threshold` apagado para la dirección agrupada. Cada uno es un valor de configuración, no un cambio de comportamiento.
3. La estructura de Vercel: punto de entrada, `vercel.json`, `.vercelignore`, versión de Python y dependencias.

**Sophia, en Vercel**
1. En el proyecto: variables de entorno `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `CODE_HASH_SECRET`, `EMAIL_DELIVERY=console` y la configuración de SSL, primero en el ambiente de previsualización. Vercel Authentication encendida.
2. Abrir la previsualización de la rama y recorrer una lista de pruebas a mano que la IA preparará: registro, código, inicio de sesión, cerrar sesión, recuperar contraseña y reservar sin sesión.
3. Solo cuando todo funcione, fusionar a `main` y repetir con las variables de producción. Comprar el dominio en Vercel y asignarlo es lo último.

## 5 ter. Lo que ya está en el código (rama `api/vercel-ready`)

- **`api/index.py`:** el punto de entrada. Vercel lo ejecuta como función y le manda todo lo que empiece con `/api/`. Es la misma aplicación de `backend/app/main.py`; no muestra las páginas.
- **`vercel.json`:** `outputDirectory: web` (las páginas las entrega la red de Vercel, como hoy), una regla que manda `/api/(.*)` a la función, la región `cle1` (Cleveland, la de AWS `us-east-2`, la misma de Neon) y que la función incluya `backend/app/**`.
- **`.vercelignore`:** no se sube nada de `tests/`, `docs/`, `database/`, `tools/`, `herramientas/`, `.git`, `.claude`, ni ningún `.env` ni entorno virtual.
- **`requirements.txt` de la raíz:** la lista real de dependencias, con versiones exactas y sin `-r`. La primera previsualización falló con `[PYTHON_REQUIREMENTS_PARSE_ERROR]` porque el lector de Vercel no entiende `-r backend/requirements.txt`. Por eso la lista vive en la raíz y `backend/requirements.txt` la incluye (`-r ../requirements.txt`), para que `pip install` desde `backend/` siga igual.
- **`.python-version`:** 3.13, la versión con la que se prueba todo.
- **Variables nuevas:** `DATABASE_SSLMODE` (en Neon, `require`), `DATABASE_CONNECT_TIMEOUT_SECONDS` (en Neon, `10`, porque la primera conexión tras suspenderse tarda más) y `TRUST_PROXY_HEADERS`.
- **Detrás del proxy de Vercel:** la API ve HTTP aunque la persona entró por HTTPS, y la dirección de quien pide es la del proxy. Con `TRUST_PROXY_HEADERS=true` (solo en Vercel), el origen propio se arma con `X-Forwarded-Proto` y la IP sale de `X-Forwarded-For`. Sin eso, toda petición que cambia algo daría 403, y todas las personas compartirían la espera por dispositivo. Con la variable apagada (como en tu computadora), esos encabezados se ignoran: nadie puede fingir otra dirección.

## 5 bis. CAPTCHA con Cloudflare Turnstile

Decidido el 22 de noviembre de 2026 (ADR 0016): Turnstile, plan gratuito, modo Managed, en cinco rutas (registro, primer paso de iniciar sesión, pedir el código de recuperar la contraseña, pedir otro código de verificación y corregir el correo). Siempre activo; si Cloudflare no responde o falta la llave secreta, la acción se rechaza.

**Qué hay que cargar en Vercel antes de fusionar** (Settings, Environment Variables, Production). Sin esto, el registro y el inicio de sesión contestan `503` en producción, porque nada se deja pasar sin comprobar:

| Variable | Valor |
|---|---|
| `TURNSTILE_SITE_KEY` | la llave **pública** del widget «Integro» (empieza con `0x4`) |
| `TURNSTILE_SECRET_KEY` | la llave **secreta** del mismo widget, como **Secret**. Solo en Vercel y en tu gestor de contraseñas; nunca en el chat ni en el repositorio |

**El widget en Cloudflare** (Application security, Turnstile): modo Managed, y en Hostname Management los **hostnames exactos** donde se muestra, uno por línea y sin comodines: hoy `integro-ruby.vercel.app`. Al comprar el dominio propio se agrega aquí también, o el desafío no carga en ese dominio. Si se borra el widget y se crea otro, las dos llaves cambian y hay que actualizar las dos variables de Vercel.

**Cómo se comprueba que quedó bien:** `/api/v1/auth/captcha` contesta la llave pública y no `503`; en el registro aparece el desafío; con una llave secreta equivocada, las acciones contestan `503` y el registro de la función dice `invalid-input-secret`. Si por error se pusiera en Vercel una llave de prueba de Cloudflare (empieza con `1x`, `2x` o `3x`), la API la rechaza: `/api/v1/auth/captcha` y las cinco acciones contestan `503`, y el registro de la función lo dice.

**Qué se ve en las pantallas:** el widget está escondido y casi nunca aparece. Para comprobar que dibuja bien, en el navegador (herramientas de desarrollo, pestaña Network) al abrir el registro, la recuperación de contraseña o la ventana de iniciar sesión se ve una petición a `/api/v1/auth/captcha` y otra a `challenges.cloudflare.com`; en la portada no hay ninguna de las dos hasta abrir la ventana. Si el hostname del sitio no está en el widget de Cloudflare, el desafío falla y las pantallas avisan «No pudimos comprobar que eres una persona».

**Pendiente con Valeria:** qué decir de Cloudflare en el aviso de privacidad (Turnstile recibe datos del navegador de quien se registra o inicia sesión).

## 5 quinquies. Correo real con Resend

Decidido el 22 de noviembre de 2026 (ADR 0017): Resend, plan gratuito para empezar. Según su página de precios (leída ese día): 3,000 correos al mes y **100 al día**, 3 dominios; el plan de 20 USD al mes sube a 50,000 correos y quita el tope diario. Revísalo en resend.com/pricing antes de contratar. Cada inicio de sesión manda un correo, así que 100 al día alcanzan para unas decenas de personas.

**Lo que hace Sophia, en este orden** (la IA no puede entrar a Resend, a Vercel ni al DNS):
1. **Un dominio.** Íntegro todavía no tiene, y sin uno propio Resend no envía a nadie. Se puede comprar en Vercel, que además administra su DNS. (El nombre «Íntegro» sigue sujeto al registro de marca, IMPI.)
2. **Cuenta en Resend** (resend.com) y, en Domains, agregar el dominio. Resend muestra los registros DNS (SPF y DKIM, de tipo TXT, MX o CNAME) que hay que copiar **tal cual** en el DNS del dominio. Suele verificar en unos 15 minutos, a veces tarda hasta 72 horas. Después conviene agregar un registro DMARC; Resend lo recomienda.
3. **Una llave de API** en Resend (API Keys). **(sin verificar cómo se llaman los permisos en la pantalla)** si hay un permiso de solo envío, elegir ese. La llave se guarda en el gestor de contraseñas y nunca va al chat ni al repositorio.
4. **Variables en Vercel** (Settings, Environment Variables, Production), y después Redeploy:

   | Variable | Valor |
   |---|---|
   | `EMAIL_DELIVERY` | `resend` (cambia el `console` de hoy) |
   | `EMAIL_API_KEY` | la llave de Resend, como **Sensitive** |
   | `EMAIL_FROM` | `Íntegro <no-responder@tu-dominio>`, con el dominio verificado |

   Si falta `EMAIL_API_KEY` o `EMAIL_FROM`, la API no arranca y el registro de la función dice cuál.
5. **Prueba tuya:** crear una cuenta con tu propio correo. Debe llegar el código; si no está en la bandeja, revisar spam. Para ver si SPF y DKIM pasaron, en Gmail: los tres puntos del correo, «Mostrar original»; deben decir `PASS`.

**Cuando falla el proveedor:** el registro de la función de Vercel (Logs) dice `Resend no envió el correo: HTTP <código> <nombre del error>`. Los más comunes: `401` (llave equivocada o borrada), `403` o `422` con `validation_error` (el dominio del remitente no está verificado o el remitente está mal escrito), `429` (se pasó del tope de envíos).

**Mientras `EMAIL_DELIVERY=console`:** los códigos siguen apareciendo en los registros de Vercel. Con personas reales hay que cambiarlo, porque cualquiera con acceso a los registros vería sus códigos.

## 5 quater. Probar en Vercel, paso a paso

Lo hace Sophia en vercel.com, con el proyecto que ya publica la web. La IA no puede entrar a Vercel.

1. **Variables de entorno.** En el proyecto: Settings, Environment Variables. Se agregan estas diez, primero para **Preview** y, cuando todo funcione, también para **Production**. Los valores salen de `backend/.env.neon`; **nunca** se pegan en el chat:

   | Variable | Valor |
   |---|---|
   | `DATABASE_HOST` | la dirección **agrupada** (con `-pooler`) |
   | `DATABASE_PORT` | `5432` |
   | `DATABASE_NAME` | `neondb` |
   | `DATABASE_USER` | `integro_api` |
   | `DATABASE_PASSWORD` | la contraseña de `integro_api` |
   | `DATABASE_SSLMODE` | `require` |
   | `DATABASE_CONNECT_TIMEOUT_SECONDS` | `10` |
   | `CODE_HASH_SECRET` | la llave de los códigos |
   | `EMAIL_DELIVERY` | `console` |
   | `TRUST_PROXY_HEADERS` | `true` |
   | `TURNSTILE_SITE_KEY` | la llave pública del widget (desde la pieza del CAPTCHA; ver 5 bis) |
   | `TURNSTILE_SECRET_KEY` | la llave secreta del widget, como Secret (ver 5 bis) |
   | `DATA_ENCRYPTION_KEY` | la llave maestra de cifrado, de al menos 43 caracteres, como Secret. Distinta a la de tu computadora (desde la pieza 3.2, ADR 0018) |

   Para las que son secretas (`DATABASE_PASSWORD`, `CODE_HASH_SECRET`, `TURNSTILE_SECRET_KEY` y `DATA_ENCRYPTION_KEY`), activar la opción **Sensitive** si Vercel la ofrece.
2. **Protección.** Settings, Deployment Protection: **Vercel Authentication** encendida. Si Vercel da a elegir qué cubre, elegir que cubra todos los despliegues, producción incluida. **(sin verificar cómo se llama cada opción en la pantalla)**
3. **Conectar la rama.** Cuando la rama `api/vercel-ready` esté en GitHub, Vercel crea una previsualización sola. Se abre desde la pestaña Deployments; hay que iniciar sesión en Vercel para verla.
4. **Lista de pruebas a mano en la previsualización:**
   - `/api/v1/health` contesta `ok`, y `/api/v1/health/database` dice que la base responde.
   - La portada, una ficha de propiedad y el registro se ven.
   - Crear una cuenta: el código aparece en el registro de la función (Vercel, pestaña Logs, línea que empieza con `[MODO DESARROLLO]`).
   - Comprobar el correo, iniciar sesión (con su código), ver «Mi cuenta», cerrar sesión.
   - Recuperar la contraseña y reservar sin sesión.
   - El tiempo que tarda cada paso. Debe ser menor al que se vio desde la computadora (0.5 s por transacción), porque la función y la base están en la misma región.
5. **Solo cuando todo funcione:** fusionar a `main` y comprobar lo mismo en producción. **Importante:** al fusionar, producción también intenta arrancar la función; si las variables de Production no están, `/api` falla (las páginas siguen igual que hoy). Por eso las variables se cargan en Production *antes* de fusionar.

## 6. Riesgos

- Sin el correo real, nadie de fuera puede crear una cuenta. Es lo esperado para esta etapa.
- La conexión de la API hoy no exige SSL: usa `prefer`, que cifra cuando el servidor lo ofrece. Neon sí lo ofrece, y el script lo comprueba; después se agrega `sslmode=require` como valor de configuración.
- Cualquiera con acceso a los registros de la función de Vercel ve los códigos mientras el modo sea `console`.
- El CAPTCHA (ADR 0016) frena que un programa cree cuentas en masa o pida códigos sin parar, pero depende de Cloudflare: si cae, nadie puede registrarse ni iniciar sesión hasta que vuelva (se rechaza en lugar de dejar pasar). Mientras no haya correo real, la demostración sigue detrás de Vercel Authentication.
- El plan gratuito de Neon se queda sin horas si algo mantiene la base despierta; las conexiones fallan hasta el mes siguiente.
- Vercel Authentication exige ser miembro del equipo en Vercel para ver el sitio. **(sin verificar si el plan Hobby permite agregar a Shakti y a Valeria como miembros)**: si no, ellas necesitarían Pro, o un enlace compartible de Vercel, o ver la demostración en pantalla compartida. Hay que comprobarlo antes de avisarles.
- Vercel Authentication solo cubre producción si se elige «All Deployments»; con la opción estándar el dominio de producción queda abierto (se comprobó el 21 de noviembre de 2026).
- El dominio con el nombre «Íntegro» sigue sujeto al registro de marca (IMPI).

## Fuentes

- [FastAPI en Vercel](https://vercel.com/docs/frameworks/backend/fastapi) y [Python en Vercel Functions](https://vercel.com/docs/functions/runtimes/python)
- [Directorio api en Python](https://vercel.com/docs/functions/runtimes/python/api-directory) y [reglas de ruta en proyectos de Python](https://vercel.com/changelog/python-projects-now-support-routing-rules)
- [Archivos de la raíz expuestos como estáticos](https://community.vercel.com/t/internal-files-being-exposed-as-static-assets/3266) (comunidad, no oficial)
- [Plan Hobby de Vercel](https://vercel.com/docs/plans/hobby) y [precios de Deployment Protection](https://vercel.com/docs/deployment-protection/usage-and-pricing)
- [Agrupación de conexiones en Neon](https://neon.com/docs/connect/connection-pooling), [compatibilidad](https://neon.com/docs/reference/compatibility) y [roles](https://neon.com/docs/manage/roles)
- [Regiones de Vercel](https://vercel.com/docs/regions) y [cómo cambiar la región de un proyecto de Neon](https://neon.com/faqs/change-project-region)
- [Integración de Vercel con Neon](https://neon.com/docs/guides/vercel-managed-integration), [regiones](https://neon.com/docs/introduction/regions) y [límites del plan gratuito](https://neon.com/faqs/free-plan-limits-and-quotas)
