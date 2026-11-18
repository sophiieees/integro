# ADR 0014: Inicio de sesión con contraseña, con código y con los dos

**Estado:** aceptada (Sophia, 17 de noviembre de 2026). Los canales, la regla de seguridad y los límites de los códigos se decidieron ese mismo día. Siguen pendientes los detalles del registro y la empresa que envía por cada canal.

## Contexto
La arquitectura de octubre decía "registro e inicio de sesión con código". La base de datos construida en noviembre guarda una contraseña por persona. Había que definir cómo entra una persona, huésped o anfitrión, a su cuenta de Íntegro.

## Decisión
Se ofrecen las tres formas, "para tener una buena verificación":

1. **Contraseña más código.** La persona escribe su correo y su contraseña; al escribir la contraseña se le envía un código.
2. **Solo código.** Cuando vuelve a iniciar sesión, la persona escribe su correo o su teléfono y le llega un código.
3. **Contraseña.** La combinación de correo y contraseña ya existe en la base y es la primera mitad de la forma 1.

### Por dónde llegan los códigos
- Los códigos se envían por **correo** y por **WhatsApp**. El **SMS queda fuera**.
- El correo va primero y queda firme: "el correo tiene que llegar forzosamente".
- WhatsApp queda pendiente. Hoy no hay un número de WhatsApp para Íntegro y Sophia lo va a platicar con sus socias; la plantilla del código, que Meta debe aprobar, no se pide todavía. Mientras tanto los códigos salen solo por correo, y la arquitectura deja previsto el segundo canal.
- Mientras no haya una empresa contratada para enviar, se trabaja en modo desarrollo: el código se escribe en la ventana del servidor en lugar de enviarse.

La razón es el costo. Al 17 de noviembre de 2026, el costo aproximado por mensaje era de 0.0001 USD por correo, 0.0085 USD por un código de WhatsApp a un número de México y 0.18 USD por un SMS a México. Son cifras de terceros y hay que confirmarlas en las páginas oficiales antes de presupuestar.

### Cuándo es obligatorio contraseña más código
- Para cambiar el correo, el teléfono o la contraseña.
- Para cambiar la cuenta bancaria.
- Para todo lo que mueve dinero.
- Para los anfitriones y para el panel de administración.

### Límites de los códigos
Son valores de configuración, no fijos en el código:

| Regla | Valor |
|---|---|
| Largo del código | 6 dígitos |
| Vencimiento | 5 minutos |
| Intentos permitidos | 5 |
| Espera entre un envío y otro | 60 segundos |
| Envíos por hora | 5 como máximo |

La huella del código se calcula con una llave secreta del servidor, porque un código de seis dígitos se adivina rápido si alguien roba la base.

## Consecuencias
- **Tablas.** Ya están construidas `one_time_codes`, que guarda la huella de cada código, para qué es, por dónde salió, a dónde se envió, cuándo vence, cuántos intentos lleva y si ya se usó, y `users.email_verified_at`, la fecha en que se comprobó el correo. La de los teléfonos ya existía en `user_phones.verified_at`. La tabla admite el canal `sms`, así que agregarlo después no necesita otra migración.
- **Empresa que envía.** Falta elegir quién envía los correos y, cuando se decida, los mensajes de WhatsApp. Cada una necesita su cuenta y sus llaves, que viven en variables de entorno.
- **Segundo factor de la arquitectura.** `docs/arquitectura.md` pedía un segundo factor TOTP obligatorio para anfitriones y panel. Falta decidir si el código enviado lo sustituye o si se suman.
- **Avisos que no son códigos.** `docs/arquitectura.md` menciona avisos por correo y SMS. Esta decisión cubre solo los códigos de acceso; los avisos se deciden con su módulo.
- **Pendiente.** Los detalles del registro, las reglas de la contraseña y cuánto dura una sesión.

## Fuente
Decisiones de Sophia del 17 de noviembre de 2026. Bitácora, decisiones 13.3, 13.8 y 16.21 a 16.25. `docs/arquitectura.md`, sección 4, módulo Cuentas. ADR 0013 y ADR 0015.

## Cambios
- 17 de noviembre de 2026, noche: se decidieron los canales (correo y WhatsApp, sin SMS), la regla de contraseña más código y los límites de los códigos. La versión anterior decía "por SMS o a su correo" en la forma 1 y "por WhatsApp" en la forma 2, y dejaba todas las consecuencias como propuestas pendientes.
