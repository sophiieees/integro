# ADR 0016: CAPTCHA con Cloudflare Turnstile, siempre activo

**Estado:** aceptada (Sophia, 22 de noviembre de 2026).

## Contexto
`docs/arquitectura.md` pide CAPTCHA en el registro y en el inicio de sesión, y no existía. Con la API abierta al público, un programa podía crear cuentas en masa y pedir códigos al correo de otras personas sin límite que no fuera el de cada código. Los pasos en los que se escribe un código ya tienen límite de intentos.

## Decisión
- Servicio: **Cloudflare Turnstile**, plan gratuito, modo Managed (casi nunca pide hacer algo a la persona).
- Se pide en cinco rutas, las que cualquiera puede llamar sin sesión y que envían un correo o crean una cuenta: crear la cuenta (`register`), el primer paso de iniciar sesión (`login`), pedir el código de recuperar la contraseña (`password-reset/request`), pedir otro código de verificación (`resend-code`) y corregir el correo de una cuenta sin comprobar (`correct-unverified-email`). Los pasos en los que se escribe un código (`verify-email`, `login/verify`, `password-reset/confirm`) no lo piden.
- La página resuelve el desafío y manda el resultado en el encabezado `X-Captcha-Token`. La API se lo pregunta a Cloudflare con la llave secreta (`siteverify`), antes de revisar el formulario. Un resultado sirve una sola vez y dura 5 minutos.
- **Sin resultado, vacío, repetido, vencido o falso:** `400`, `captcha_failed`. **Si Cloudflare no responde** (red caída, 5 segundos sin respuesta, error de su servidor, respuesta que no se entiende) **o la llave secreta falta o no sirve:** `503`, `captcha_unavailable`. En los dos casos no se crea ni se envía nada.
- **Siempre activo, sin interruptor.** Una variable mal escrita o borrada en Vercel dejaría el sistema sin protección sin que nadie lo notara. En la computadora y en las pruebas se usan las llaves de prueba de Cloudflare, que siempre pasan, y las pruebas automáticas usan un verificador que acepta solo un resultado inventado, así que ninguna llama a Cloudflare.
- **Una acción por ruta** (sugerencia aceptada el 22 de noviembre de 2026): el widget de cada pantalla declara su acción (`register`, `login`, `password_reset`, `resend_code`, `correct_email`), Cloudflare la devuelve al comprobar y la API la compara con la que espera la ruta. Un resultado de una acción no sirve en otra; sin acción o con otra es `captcha_failed`.
- **Las llaves de prueba solo valen en la computadora de Sophia** (sugerencia aceptada el 22 de noviembre de 2026): siempre pasan, así que con `SESSION_COOKIE_SECURE=false` se aceptan y, donde la cookie exige HTTPS (la nube), se tratan como si faltaran: `503`, tanto la llave secreta como la pública. Con llaves de prueba Cloudflare no devuelve la acción (lo dice su documentación), y por eso solo con ellas no se compara.
- La llave pública no se escribe en las páginas: la API la entrega en `GET /auth/captcha`, para que cada ambiente use la suya (de prueba en la computadora, real en la nube). La secreta solo vive en el servidor.
- Variables: `TURNSTILE_SITE_KEY` y `TURNSTILE_SECRET_KEY`. Sin ellas la API arranca (la salud sigue respondiendo) y las cinco rutas contestan `503`.
- No se agrega ninguna dependencia: la comprobación usa la biblioteca estándar de Python.

### En las pantallas
- Cada zona del widget es un `div` con `data-captcha="<acción>"` en el HTML (`register`, `login`, `password_reset`, `resend_code` o `correct_email`). La acción se declara una sola vez, ahí: es la que el widget le dice a Cloudflare y la que la API espera en su ruta. Una zona sin una acción conocida no se dibuja.
- La zona va justo antes de los botones del formulario: en el registro (tres: datos, código y corrección del correo), en recuperar la contraseña (dos: pedir el código y pedir otro) y en el primer paso de la ventana de iniciar sesión.
- El widget se pide con `appearance: interaction-only`: queda escondido y solo aparece si Cloudflare necesita que la persona haga algo.
- El widget de cada paso se dibuja cuando el paso se muestra, para que el resultado esté listo antes de que la persona termine de escribir. La ventana de iniciar sesión lo dibuja al abrirse. Quien ya tiene sesión no lo dibuja.
- Un resultado sirve una sola vez: al mandarlo, el widget se reinicia y ya va por el siguiente. Si el resultado no llega en 20 segundos, o el desafío falla, la pantalla avisa y no manda nada.
- El script de Cloudflare y la llave pública solo se piden cuando una pantalla necesita un widget, no en cada página del sitio. La portada no contacta a Cloudflare.
- Si la API contesta 400 o 503 por el CAPTCHA, la pantalla muestra «No pudimos comprobar que eres una persona. Inténtalo de nuevo.» y conserva lo escrito.

## Consecuencias
- Si Cloudflare cae, nadie puede registrarse ni iniciar sesión hasta que vuelva. Se aceptó porque es poco frecuente y breve, y porque dejar pasar abriría la puerta justo cuando no hay filtro. Con usuarios reales se puede revisar si conviene dejar entrar a quien ya tiene cuenta durante una caída.
- En el plan gratuito el widget lista los hostnames exactos (sin comodín, hasta 10): hay que agregar el dominio propio cuando se compre.
- Hay que decir en el aviso de privacidad que Cloudflare recibe datos del navegador (pendiente con Valeria).
- Quien use un entorno que no sea ni la computadora de Sophia ni la nube con HTTPS (por ejemplo, una segunda computadora de desarrollo con la cookie sin `Secure`) también puede usar las llaves de prueba: la guarda mira `SESSION_COOKIE_SECURE`, que ya solo se apaga en desarrollo.

## Fuente
Decisión de Sophia del 21 y 22 de noviembre de 2026 (prompt 38 de la bitácora y la conversación que le siguió).
