# ADR 0017: Correo real con Resend; si un código no sale, cada ruta dice lo que corresponde

**Estado:** aceptada (Sophia, 22 de noviembre de 2026).

## Contexto
Hasta ahora los códigos y los avisos solo se escribían en la ventana del servidor (`EMAIL_DELIVERY=console`, ADR 0014): nadie fuera del equipo podía registrarse ni iniciar sesión. `docs/decisiones/README.md` dejaba pendiente «la empresa que envía los correos». Íntegro no tiene dominio todavía.

## Decisión
- Proveedor: **Resend**, plan gratuito para empezar (3,000 correos al mes y 100 al día, según su página de precios el 22 de noviembre de 2026). Amazon SES queda como alternativa: exigiría pedir acceso a producción con un sitio público y un dominio. El envío vive detrás de la interfaz `CodeSender`, así que cambiar de proveedor es cambiar un archivo.
- Con `EMAIL_DELIVERY=resend`, los tres códigos (comprobar el correo, iniciar sesión, recuperar la contraseña) y los dos avisos de seguridad (intentos fallidos, contraseña cambiada) salen por correo. `console` sigue siendo el modo de la computadora de Sophia.
- Los correos van en español y de tú, en texto y en HTML con los colores de la web. Ninguno lleva contraseñas. El código va en el cuerpo y **no** en el asunto, que se ve en la pantalla bloqueada. Lo que viene de fuera (el navegador de quien intentó entrar) se escapa en el HTML.
- Variables: `EMAIL_API_KEY` (secreta, solo en Vercel) y `EMAIL_FROM`. Si `EMAIL_DELIVERY=resend` y falta alguna, **la API no arranca** y dice cuál: es una elección hecha a propósito, y fingir que se envía sería peor.
- Un envío que falla por la red, por tiempo (5 segundos), por 429, por 409 o por un error 5xx se intenta una vez más con la **misma** `Idempotency-Key` (Resend la recuerda 24 horas): si el primer intento sí llegó, no se manda un correo repetido. Los demás errores (llave mala, dominio sin verificar, correo mal escrito) no se reintentan.
- No se agrega ninguna dependencia: la llamada usa la biblioteca estándar de Python.
- En el registro del servidor solo van el código HTTP y el nombre del error de Resend. Nunca la llave, el destinatario, el código ni el texto del correo.

### Si el código no sale
El correo sale después de guardar lo que la persona pidió. Si el proveedor falla, el código existe pero no va a llegar:
- `resend-code` y el primer paso de `login`: `503` con el código `email_unavailable` y el texto «No pudimos enviar el correo. Espera un minuto e inténtalo de nuevo.» (el minuto es la espera normal entre códigos).
- `register` y `correct-unverified-email`: lo guardado queda guardado, porque volver a mandar el formulario diría «ya existe una cuenta» o «es el mismo correo». Contestan lo de siempre, con `"email_sent": false`, y la persona pide otro código.
- `password-reset/request`: contesta exactamente lo mismo de siempre. Si fallara distinto cuando la cuenta existe, la respuesta diría quién tiene cuenta.
- Un aviso de seguridad que no sale nunca cambia lo que contesta la ruta: lo que avisa ya pasó y no se deshace.

## Consecuencias
- Hace falta un dominio propio, verificado en Resend con registros SPF y DKIM, y un remitente. Sin eso no sale nada.
- El plan gratuito tiene 100 correos al día; pasado eso, el plan de pago o esperar al día siguiente.
- Un código que no llegó por culpa del proveedor cuenta para la espera de un minuto y el máximo por hora de códigos.
- Las pantallas todavía no muestran que «el correo no salió» al registrarse o corregir el correo (`email_sent: false`); hasta esa pieza, la persona ve el paso del código y pide otro con «Enviar otro código». Y ante un `503` por `email_unavailable` verán el aviso genérico de respuesta inesperada.
- WhatsApp sigue pendiente (ADR 0014): `ResendCodeSender` solo sabe de correo.
- Mientras `EMAIL_DELIVERY=console` en la nube, los códigos aparecen en los registros de Vercel.

## Fuente
Decisión de Sophia del 22 de noviembre de 2026 (Resend, siguiendo la recomendación de la IA).
