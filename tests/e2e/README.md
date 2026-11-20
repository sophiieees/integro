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
| `test_entrar_e2e.py` | La ventana de «Entrar»: los 10 casos aceptados y sus límites. |

Una prueba de pantalla verifica lo que se ve, no solo el HTML: por ejemplo, que una ventana cerrada deje de tapar la página (`covers_the_page`) y que un botón reciba el clic (`is_clickable`).
