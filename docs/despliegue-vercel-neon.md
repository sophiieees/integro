# Publicar la API y la base en Vercel con Neon

**Estado:** investigación y plan del 21 de noviembre de 2026. Todavía no se construyó nada ni se creó ninguna cuenta. Decisión de Sophia: la opción A, la API en Vercel y la base en Neon. «Nube de la base de datos y de la API» no tiene ADR todavía (`docs/decisiones/README.md`); se escribe cuando se confirmen las decisiones de la sección 4.

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

1. **El papel por transacción en la conexión agrupada.** Un script (`herramientas/neon/verificar.py`, por escribir) se conecta como `integro_api` y comprueba: que `set local role integro_service` y `set_config('app.user_id', …, true)` funcionan dentro de una transacción; que al terminar la conexión vuelve a ser `integro_api` y sin persona anotada; y que 200 transacciones seguidas, alternando entre sistema y personas distintas, **nunca heredan** la identidad de otra. Esto es lo más importante de seguridad de todo el plan.
2. **El SSL.** La conexión tiene que ir cifrada (`sslmode=require`).
3. **Las migraciones.** Que las cinco corran en orden en Neon y que las pruebas de tablas pasen contra esa base.
4. **Vercel en una previsualización.** Que la función arranque con nuestra estructura, que `/api/v1/health` y `/api/v1/health/database` contesten, que las páginas salgan y que el registro, el inicio de sesión y la cookie funcionen en la dirección de la previsualización.

## 4. Decisiones que toma Sophia

1. **Plan de Vercel.** ¿Hobby para probar solo con el equipo, o Pro desde el principio? Recomendación: probar en Hobby con Vercel Authentication encendida, y pasar a Pro antes de que entre una persona que no sea del equipo.
2. **Correos en modo desarrollo.** Hoy los códigos se escriben en la ventana del servidor (`EMAIL_DELIVERY=console`). En la nube se escribirían en el registro de la función de Vercel: quien lo vea, ve los códigos. Con ese modo, alguien de fuera no puede registrarse (no le llega nada). Recomendación: publicar como demostración solo para el equipo, con Vercel Authentication, hasta tener el correo real. El correo real viene después en el orden ya acordado.
3. **Región.** Recomendación: Neon en Virginia (`aws-us-east-1`) y las funciones de Vercel en su región de Washington D.C. (`iad1`), para que la API y la base queden juntas. No hay región en México.
4. **Dónde se crea la base.** Recomendación: crear el proyecto directo en neon.com y no desde la integración de Vercel, que trae variables con el rol poderoso. Se copian a Vercel solo los datos de `integro_api`.
5. **Un solo proyecto de Vercel con la web y la API juntas**, porque la cookie exige un solo dominio. Las ramas generan previsualizaciones; la producción cambia solo cuando Sophia fusiona a `main`. Recomendación: la primera vez, que la propia API muestre también la web, como en local (`SERVE_WEB`): se comporta igual que hoy y no hay dudas de rutas. Mover las páginas al CDN es una mejora posterior.

## 5. Pasos, en orden

**Sophia**
1. Contestar las decisiones de la sección 4.
2. Crear la cuenta de Neon (neon.com) y un proyecto llamado `integro`, con PostgreSQL 18 y la región elegida. No crear roles desde la consola.
3. Desde pgAdmin, conectarse a la dirección **directa** de Neon con el rol del proyecto, y correr una por una, en orden, las migraciones de `database/migrations/` (en el Query Tool, abriendo cada archivo, sin guardarlos). Es lo que ya se hizo en la base local.
4. En el mismo Query Tool, crear a `integro_api` con las tres líneas de `backend/README.md` y ponerle su contraseña ahí mismo (pgAdmin: Login/Group Roles → `integro_api` → Properties → Definition). La contraseña no se escribe en SQL, ni en el chat, ni en el repositorio.
5. Crear en un archivo local `backend/.env.neon` (git lo ignora) los datos de conexión de `integro_api`: servidor agrupado, puerto 5432, base, usuario y contraseña. Sirve para que el script de verificación corra en su computadora.
6. Generar la llave de los códigos con `python -c "import secrets; print(secrets.token_urlsafe(48))"` y guardarla; es el valor de `CODE_HASH_SECRET` en Vercel. No se comparte.

**La IA, cada paso en su rama, con pruebas y sin fusionar**
1. `herramientas/neon/verificar.py`: las pruebas reales de la sección 3, puntos 1 y 2, contra `backend/.env.neon`.
2. Ajustes a la conexión, solo si la verificación los pide: `sslmode`, tiempo de espera de conexión más largo (la primera conexión tras suspenderse tarda más que los 3 segundos de hoy), y `prepare_threshold` apagado para la dirección agrupada. Cada uno es un valor de configuración, no un cambio de comportamiento.
3. La estructura de Vercel: punto de entrada, `vercel.json`, `.vercelignore`, versión de Python y dependencias.

**Sophia, en Vercel**
1. En el proyecto: variables de entorno `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `CODE_HASH_SECRET`, `EMAIL_DELIVERY=console` y la configuración de SSL, primero en el ambiente de previsualización. Vercel Authentication encendida.
2. Abrir la previsualización de la rama y recorrer una lista de pruebas a mano que la IA preparará: registro, código, inicio de sesión, cerrar sesión, recuperar contraseña y reservar sin sesión.
3. Solo cuando todo funcione, fusionar a `main` y repetir con las variables de producción. Comprar el dominio en Vercel y asignarlo es lo último.

## 6. Riesgos

- Sin el correo real, nadie de fuera puede crear una cuenta. Es lo esperado para esta etapa.
- Cualquiera con acceso a los registros de la función de Vercel ve los códigos mientras el modo sea `console`.
- El registro de cuentas todavía no tiene CAPTCHA (ADR de seguridad pendiente): con la API abierta al público, alguien podría crear cuentas en masa. Por eso la demostración va detrás de Vercel Authentication.
- El plan gratuito de Neon se queda sin horas si algo mantiene la base despierta; las conexiones fallan hasta el mes siguiente.
- El dominio con el nombre «Íntegro» sigue sujeto al registro de marca (IMPI).

## Fuentes

- [FastAPI en Vercel](https://vercel.com/docs/frameworks/backend/fastapi) y [Python en Vercel Functions](https://vercel.com/docs/functions/runtimes/python)
- [Directorio api en Python](https://vercel.com/docs/functions/runtimes/python/api-directory) y [reglas de ruta en proyectos de Python](https://vercel.com/changelog/python-projects-now-support-routing-rules)
- [Archivos de la raíz expuestos como estáticos](https://community.vercel.com/t/internal-files-being-exposed-as-static-assets/3266) (comunidad, no oficial)
- [Plan Hobby de Vercel](https://vercel.com/docs/plans/hobby) y [precios de Deployment Protection](https://vercel.com/docs/deployment-protection/usage-and-pricing)
- [Agrupación de conexiones en Neon](https://neon.com/docs/connect/connection-pooling), [compatibilidad](https://neon.com/docs/reference/compatibility) y [roles](https://neon.com/docs/manage/roles)
- [Integración de Vercel con Neon](https://neon.com/docs/guides/vercel-managed-integration), [regiones](https://neon.com/docs/introduction/regions) y [límites del plan gratuito](https://neon.com/faqs/free-plan-limits-and-quotas)
