# ADR 0014: Inicio de sesión con contraseña, con código y con los dos

**Estado:** aceptada (Sophia, 17 de noviembre de 2026). Los canales, la regla de seguridad y los límites de los códigos se decidieron ese mismo día; las reglas del inicio de sesión, de la sesión y de la recuperación de contraseña, el 18 de noviembre. Sigue pendiente la empresa que envía por cada canal.

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

### Cómo se inicia sesión mientras no haya WhatsApp
- La persona entra con su correo, su contraseña y un código que le llega al correo.
- Esos tres datos se piden en cada inicio de sesión: en un dispositivo nuevo, después de cerrar sesión y cuando la sesión venció. Mientras la sesión siga abierta no se vuelve a pedir nada.
- La forma 2, solo con código por WhatsApp, no se construye todavía. Queda la carpeta base del canal, que puede estar vacía.
- El teléfono que la persona da al registrarse queda sin comprobar hasta que exista WhatsApp.

### Cuánto dura una sesión
Son valores de configuración. La sesión se cierra sola cuando pasa ese tiempo sin usarse.

| Quién | Tiempo sin uso |
|---|---|
| Huésped | 30 días |
| Anfitrión | 7 días, porque maneja dinero y propiedades |
| Panel de administración | 30 minutos |

### Contraseñas incorrectas
La cuenta nunca se bloquea.

1. A los 3 intentos fallidos se avisa al dueño de la cuenta y se pide otro factor: un mensaje de WhatsApp o una llamada, cuando existan. Hoy el código al correo ya se pide en cada inicio de sesión.
2. Si falla otros 3 intentos, se le pide intentarlo más tarde, 15 minutos después.
3. Esa espera se aplica a quien está intentando, por dispositivo y dirección, y no a la cuenta completa. Así nadie que conozca el correo de otra persona puede dejarla fuera a propósito.

Cómo se cuenta cada cosa:

- **El aviso se cuenta por cuenta.** Son 3 fallos seguidos contra una misma cuenta, vengan de donde vengan. Entrar bien reinicia esa cuenta de fallos. El aviso sale una vez por racha, por correo, y dice cuántos intentos hubo, la fecha y la hora, el navegador y la dirección; nunca una contraseña. Solo se avisa a un correo ya comprobado.
- **La espera se cuenta por dispositivo.** Un dispositivo es la pareja de dirección IP y navegador. Son 6 fallos en 15 minutos desde el mismo dispositivo, contra la cuenta que sea, y ese dispositivo espera 15 minutos para cualquier cuenta. Mientras espera no se mira la contraseña ni se anotan sus intentos, así que la espera no se alarga.
- **Los fallos de hace más de 15 minutos no cuentan,** ni para el aviso ni para la espera.
- **Los tres números son valores de configuración:** fallos para el aviso, fallos para la espera y minutos.

### Anfitriones: la aplicación de códigos se suma
El código enviado no sustituye a la aplicación de códigos (TOTP) que pedía la arquitectura: se suman. Cuando una persona pasa de huésped a anfitrión se toman otras medidas, y el TOTP es una de ellas.

### Recuperar la contraseña
- Se envía al correo una liga que sirve una sola vez y dura 15 minutos.
- Al cambiar la contraseña se cierran todas las sesiones abiertas y la persona tiene que volver a iniciar sesión.

## Consecuencias
- **Tablas.** Ya están construidas `one_time_codes`, que guarda la huella de cada código, para qué es, por dónde salió, a dónde se envió, cuándo vence, cuántos intentos lleva y si ya se usó, y `users.email_verified_at`, la fecha en que se comprobó el correo. La de los teléfonos ya existía en `user_phones.verified_at`. La tabla admite el canal `sms`, así que agregarlo después no necesita otra migración.
- **Empresa que envía.** Falta elegir quién envía los correos y, cuando se decida, los mensajes de WhatsApp. Cada una necesita su cuenta y sus llaves, que viven en variables de entorno.
- **Segundo factor de la arquitectura.** El TOTP para anfitriones y panel se suma al código enviado. Su secreto se guarda cifrado con AES-256-GCM, en una tabla que todavía no está diseñada; se construye con el paso de huésped a anfitrión.
- **Intentos fallidos.** Cada intento, fallido o correcto, se guarda en la tabla `login_attempts`, que solo admite filas nuevas. Guarda la dirección IP y el navegador, que son datos personales.
- **Duración por tipo de persona.** La sesión de anfitrión se distingue porque la persona tiene perfil de anfitrión.
- **Avisos que no son códigos.** `docs/arquitectura.md` menciona avisos por correo y SMS. Esta decisión cubre solo los códigos de acceso; los avisos se deciden con su módulo.
- **Pendiente.** El otro factor por WhatsApp o por llamada, y el tope de días de una sesión aunque se use a diario.

## Fuente
Decisiones de Sophia del 17 y del 18 de noviembre de 2026. Bitácora, decisiones 13.3, 13.8 y 16.21 a 16.25. `docs/arquitectura.md`, sección 4, módulo Cuentas. ADR 0013 y ADR 0015.

## Cambios
- 17 de noviembre de 2026, noche: se decidieron los canales (correo y WhatsApp, sin SMS), la regla de contraseña más código y los límites de los códigos. La versión anterior decía "por SMS o a su correo" en la forma 1 y "por WhatsApp" en la forma 2, y dejaba todas las consecuencias como propuestas pendientes.
- 18 de noviembre de 2026: se decidieron las reglas del inicio de sesión mientras no haya WhatsApp, la duración de la sesión, las contraseñas incorrectas, que el TOTP se suma para anfitriones y la recuperación de contraseña. Sophia había dicho 5 minutos para la liga y eligió 15 al revisarlo.
- 18 de noviembre de 2026, tarde: al construir las contraseñas incorrectas se precisó cómo se cuenta: el aviso por cuenta y la espera por dispositivo, y qué dice el aviso.
