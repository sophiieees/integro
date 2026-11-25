# Pruebas de principio a fin

Estas pruebas abren la web en un navegador de verdad, que teclea y da clic, contra la API de verdad y la base `integro` de `backend/.env`. Son las pruebas de las pantallas: lo que se ve y lo que se puede hacer, no solo lo que contesta la API.

Decisión de Sophia del 19 de noviembre de 2026: las pruebas de una pantalla no se hacen en una base temporal ni fuera del repositorio; viven aquí y arrancan servidor, base y navegador.

## Qué arranca cada corrida

| Qué | Cómo |
|---|---|
| Servidor | La API de `backend/`, en un hilo del mismo proceso y en un puerto libre, con las páginas de `web/` y la cookie de sesión sin `Secure` (el servidor local no tiene HTTPS). |
| Base | La base `integro` del usuario de `backend/.env`. Todo lo que escribe el navegador va dentro de una sola transacción que se deshace al terminar el archivo: no queda ninguna fila. |
| Navegador | Edge o Chrome sin ventana, con un perfil nuevo que se borra al terminar. Cada prueba usa un contexto limpio, sin cookies de otra, y un nombre de navegador propio para que la espera por dispositivo (ADR 0014) de una no cuente en la siguiente. |
| Códigos | No se envían: la prueba los lee de un anotador, igual que en `tests/backend/`. |
| Authenticator | El servidor de las pruebas usa una llave de cifrado inventada (`TEST_ENCRYPTION_KEY`, en `e2e_support.py`), no la de `backend/.env`. `enroll_authenticator` deja a una persona con el Authenticator activo sin pasar por las rutas. |
| CAPTCHA | No se toca internet. La página recibe un widget de Cloudflare Turnstile de mentira (`FAKE_TURNSTILE`, en `e2e_support.py`) que entrega un resultado nuevo cada vez, y la API comprueba ese resultado como Cloudflare: una sola vez y para la acción de su pantalla (`StubCaptcha`). La llave pública que entrega la API es una de prueba de Cloudflare. |

## Qué hace falta

- Las migraciones aplicadas en la base `integro` y `backend/.env` con sus variables (`backend/README.md`).
- Edge o Chrome instalado. Para usar otro navegador, la variable de entorno `INTEGRO_BROWSER` con la ruta del ejecutable.
- `websocket-client`, que viene en `backend/requirements-dev.txt`: `pip install -r requirements-dev.txt`.

Si falta el navegador, `backend/.env` o `websocket-client`, las pruebas se omiten y `-rs` dice por qué.

## Cómo correrlas

Desde `backend/`, con el entorno virtual activado:

```powershell
python -m pytest ..\tests\e2e -v -rs
```

Tardan unos dos minutos.

## Archivos

| Archivo | Para qué |
|---|---|
| `e2e_support.py` | Servidor, base y navegador, y lo que una persona hace en la pantalla (teclear, dar clic, esperar). |
| `test_entrar_e2e.py` | La ventana de «Iniciar sesión»: los 10 casos aceptados y sus límites. |
| `test_registro_e2e.py` | La pantalla de registro: el formulario, el indicador de la contraseña, los avisos, la cuenta creada en tu base, el código del correo, el teléfono con su código y el recorrido hasta iniciar sesión. |
| `test_estructura_e2e.py` | La cabecera del visitante y el pie armados con un script: la barra y la pestaña de cada página, que los enlaces lleven a donde dicen, el botón dorado, la cabecera fija, el celular y la página sin JavaScript. |
| `test_reservar_e2e.py` | «Reservar» sin sesión: lo que trae la dirección, el aviso, lo que se guarda en la dirección, las fechas que no pueden ser, el viaje completo de registrarse y volver a la misma propiedad, iniciar sesión en la misma página, las direcciones de regreso que no se siguen y el celular. |
| `test_recuperar_e2e.py` | La pantalla de recuperar la contraseña: el enlace de la ventana, los tres pasos, el código y sus intentos, la contraseña débil, las sesiones que se cierran y el celular. Necesita la migración `20261121000005_password_reset_code.sql` en la base. |
| `test_captcha_e2e.py` | El CAPTCHA en las pantallas: el widget de cada zona con su acción, que se dibuje cuando el paso se muestra y no en la portada, que cada petición mande un resultado nuevo, esperar un desafío lento, y qué dice la pantalla si el desafío falla o la API lo rechaza (400 y 503). |
| `test_authenticator_e2e.py` | El paso del Authenticator en la ventana de iniciar sesión: aparece después del código del correo para quien lo tiene activo, el código correcto y los incorrectos, lo que no son 6 números, recargar con la sesión en espera, cerrar la sesión en espera, una página protegida mientras tanto y el celular. El reloj de los códigos lo controla la prueba. |
| `test_vistas_e2e.py` | Las cuatro vistas: la cabecera de cada una, el menú de la cuenta, Próximamente, Mi cuenta, las páginas protegidas con quién las ve y quién no, y el administrador mirando las otras vistas con su propia cuenta. |

Una prueba de pantalla verifica lo que se ve, no solo el HTML: por ejemplo, que una ventana cerrada deje de tapar la página (`covers_the_page`) y que un botón reciba el clic (`is_clickable`).
