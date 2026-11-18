# ADR 0014: Inicio de sesión con contraseña, con código y con los dos

**Estado:** aceptada en lo general (Sophia, 17 de noviembre de 2026). Los detalles del registro están pendientes: Sophia los entregará por separado.

## Contexto
La arquitectura de octubre decía "registro e inicio de sesión con código". La base de datos construida en noviembre guarda una contraseña por persona. Había que definir cómo entra una persona, huésped o anfitrión, a su cuenta de Íntegro.

## Decisión
Se ofrecen las tres formas, "para tener una buena verificación":

1. **Contraseña más código.** La persona escribe su correo y su contraseña; al escribir la contraseña se le envía un código, que le llega por SMS o a su correo.
2. **Solo código.** Cuando vuelve a iniciar sesión, la persona escribe su correo o su teléfono y le llega un código por WhatsApp.
3. **Contraseña.** La combinación de correo y contraseña ya existe en la base y es la primera mitad de la forma 1.

## Consecuencias
Todas son propuestas de diseño pendientes de la autorización de Sophia.

- **Tablas.** Hace falta una tabla de códigos de un solo uso: a quién pertenece, por qué canal salió, para qué es, cuándo vence, cuántos intentos lleva y si ya se usó. Se guarda la huella del código, no el código. También hace falta la fecha en que se comprobó el correo; la de los teléfonos ya existe en `user_phones.verified_at`.
- **Proveedores.** Enviar códigos por SMS, por WhatsApp y por correo necesita un proveedor por canal, y cada mensaje cuesta. En WhatsApp, la plantilla del código debe estar aprobada por Meta. Orden sugerido: primero correo, después SMS y WhatsApp.
- **Seguridad.** Si se puede entrar solo con un código de WhatsApp, la cuenta queda tan protegida como el teléfono de la persona. Propuesta: exigir contraseña más código para lo que mueve dinero o cambia el correo, el teléfono o la cuenta bancaria, y para anfitriones y el panel de administración, donde la arquitectura ya pedía segundo factor obligatorio.
- **Límites.** Vencimiento de cada código, intentos permitidos y tiempo de espera entre envíos: por definir.

## Fuente
Decisión de Sophia del 17 de noviembre de 2026. `docs/arquitectura.md`, sección 4, módulo Cuentas. ADR 0013.
