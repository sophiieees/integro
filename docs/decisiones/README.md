# Registros de decisiones de arquitectura (ADR)

Un archivo por decisión, numerado en orden de registro. Formato: contexto, decisión, consecuencias, fuente. El estado dice si ya está aceptada por el equipo o si es una propuesta pendiente de Sophia.

| N | Decisión | Estado |
|---|---|---|
| 0001 | API primero | Aceptada |
| 0002 | Monolito modular, no microservicios | Aceptada |
| 0003 | La plataforma no toca dinero ni documentos sensibles | Aceptada |
| 0004 | PWA antes que app nativa | Aceptada |
| 0005 | Importación asistida; sin scraping de Airbnb | Aceptada |
| 0006 | Calendario por iCal con aviso inmediato contra la doble reserva | Aceptada |
| 0007 | Verificación de propiedad por capas | Aceptada |
| 0008 | Frontend en HTML, CSS y JavaScript; Next.js se decide más adelante | Aceptada |
| 0009 | Tokens de diseño antes de la identidad de marca | Aceptada |
| 0010 | Sin blockchain en el MVP; anclaje de hashes en fase 2 | Aceptada |
| 0011 | Chapa inteligente: integrar, no fabricar | Aceptada (recomendación del documento de chapa) |
| 0012 | API en Python con FastAPI | Aceptada |
| 0013 | PostgreSQL propio, sin Supabase, con autenticación propia | Aceptada |
| 0014 | Inicio de sesión con contraseña, con código y con los dos; códigos por correo y WhatsApp, sin SMS | Aceptada; detalles del registro pendientes |
| 0015 | La sesión se guarda en la base de datos, no en un JWT | Aceptada |
| 0016 | CAPTCHA con Cloudflare Turnstile, siempre activo | Aceptada |

Decisiones programadas que todavía no tienen ADR: procesador de pagos, proveedor de verificación de identidad, proveedor de LLM, ciudad de lanzamiento, nube de la base de datos y de la API, almacenamiento de archivos privados y la empresa que envía los correos y los mensajes de WhatsApp.
