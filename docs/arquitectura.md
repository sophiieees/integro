# Arquitectura de Íntegro

Resumen de trabajo de la arquitectura objetivo del MVP, condensado de los documentos del equipo (MVP técnico con MoSCoW, semana 1; ciberseguridad, semana 2; requerimientos y chapa inteligente, de Valeria). Lo que cambia respecto a esos documentos se registra como decisión en `docs/decisiones/`. Al final se explica qué parte de este repositorio corresponde a qué pieza.

## 1. Principios

1. **API primero.** Toda función existe como endpoint REST versionado (`/api/v1/...`) antes de tener pantalla. La web es el primer cliente; la app móvil será el segundo y usará exactamente la misma API. (ADR 0001)
2. **La plataforma no toca dinero ni documentos sensibles.** Tarjetas e identificaciones viven en proveedores certificados; la base propia guarda referencias (tokens, identificadores) y resultados. (ADR 0003)
3. **Monolito modular, no microservicios.** Un solo backend con módulos separados por dominio. Tres personas no pueden operar microservicios; sí pueden partir un monolito bien modulado cuando haga falta. (ADR 0002)

Supuesto de carga de la fase 1: 50 anfitriones, 150 propiedades, 2,000 huéspedes registrados y 500 reservas al mes.

## 2. Vista de contenedores

```
Clientes                      Servicios externos
┌──────────────┐  ┌ ─ ─ ─ ─ ─ ─ ┐
│ Web PWA      │  │ App móvil   │     Cloudflare delante de todo:
│ (primer      │  │ (fase 2,    │     WAF, límite de peticiones,
│  cliente)    │  │  misma API) │     CAPTCHA, protección DDoS
└──────┬───────┘  └ ─ ─ ┬ ─ ─ ─ ┘
       │                │
┌──────▼────────────────▼──────────────────────────┐   ┌────────────────────────┐
│ API REST /api/v1 · monolito modular               │──▶│ Procesador de pagos    │
│                                                   │   │ (cuentas conectadas)   │
│ cuentas · verificación · propiedades · búsqueda   │──▶│ Verificación de        │
│ reservas · pagos · mensajería · reportes · admin  │   │ identidad (INE+rostro) │
│ ia · chapa (llaves digitales)                     │──▶│ Correo, SMS, mapas     │
│                                                   │──▶│ PAC para CFDI          │
│ Tareas programadas: cobros, reintentos, iCal      │──▶│ Modelo de IA (API)     │
│ Autenticación JWT · roles · límite de peticiones  │──▶│ Chapa inteligente (SDK)│
└──────┬───────────────┬───────────────┬────────────┘   └────────────────────────┘
       │               │               │
┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼──────────┐
│ PostgreSQL │  │ Redis o    │  │ Archivos (R2/S3)│
│ + PostGIS  │  │ tabla de   │  │ fotos públicas, │
│ datos      │  │ trabajos   │  │ documentos      │
│ propios    │  │ colas,caché│  │ privados        │
└────────────┘  └────────────┘  └─────────────────┘
```

Lo punteado (app móvil) no se construye en el MVP, pero la API y el modelo de datos lo dejan listo. El módulo `chapa` no estaba en el MVP técnico original: entra con el documento de chapa inteligente del 13 de octubre (ADR 0011).

## 3. Tecnología propuesta

| Capa | Propuesta | Por qué |
|---|---|---|
| Web | Next.js 15 con TypeScript, Tailwind y PWA | Renderizado en servidor para que las fichas indexen; la PWA se instala en el celular y cubre la fase 1 sin app nativa |
| App móvil (fase 2) | React Native con Expo | Comparte TypeScript, tipos de la API y validaciones con la web |
| API | NestJS (TypeScript) o FastAPI (Python); una sola decisión | NestJS si el equipo quiere un solo lenguaje; FastAPI si Shakti integra IA en Python. Fecha programada: 16 de octubre; registrar la decisión como ADR cuando se tome |
| Base de datos | PostgreSQL 16 con PostGIS | Relacional, transaccional, con búsqueda geográfica para el mapa |
| Colas y caché | Redis, o tabla de trabajos en PostgreSQL en la fase 1 | Cobros recurrentes, reintentos y avisos fuera del ciclo de la petición |
| Archivos | Cloudflare R2 o S3 con CDN | Fotos en WebP en tres tamaños; documentos en bucket privado con URL firmada |
| Borde | Cloudflare (WAF, límites, CAPTCHA, DDoS) desde el día uno | Quita de la mesa los ataques de volumen; gratuito al nivel que se necesita |
| Despliegue | Opción B al arrancar: Cloudflare Pages (web) + un VPS con Docker (API, PostgreSQL, Redis) | Entre 22 y 90 USD al mes; el precio real es tiempo de Shakti |
| Observabilidad | Sentry, logs estructurados, UptimeRobot | Tres personas necesitan enterarse de los fallos antes que los usuarios |

Regla de migración de la opción B (económica) a la A (servicios administrados): más de 500 propiedades activas, contratación de alguien fuera del equipo fundador, o dos caídas del servidor en un mes. Como todo corre en contenedores, migrar es mover los mismos contenedores.

## 4. Módulos del backend y sus piezas Must

| Módulo | Piezas Must del MVP | Endpoints clave |
|---|---|---|
| Cuentas | Registro e inicio de sesión con código; roles (huésped, anfitrión, revisor, administrador); segundo factor TOTP obligatorio para anfitriones y panel | `/auth/register`, `/auth/verify-code`, `/auth/login`, `/auth/refresh`, `/auth/2fa/*` |
| Verificación | Identidad (INE o pasaporte y rostro); cuenta CLABE cifrada y tarjeta tokenizada; propiedad por capas con OCR, geocodificación y cola de revisión | `/verification/identity`, `/verification/bank`, `/verification/card`, `/properties/:id/documents`, `/properties/:id/verify` |
| Propiedades | CRUD con PostGIS; procesamiento de imágenes (3 tamaños, WebP, sin EXIF); importación asistida; calendario con iCal; precios y cotización | `/properties`, `/properties/import`, `/properties/:id/calendar`, `/calendar.ics`, `/properties/:id/quote` |
| IA | Descripción y título a partir de fotos; toda llamada pasa por este módulo, nunca desde el navegador | `/ia/describe` |
| Búsqueda | Filtros por ciudad, fechas, personas, precio y servicios; índice geográfico; caché de 60 s | `/search` |
| Reservas | Estados: solicitada, pagada, confirmada, en curso, completada, cancelada; política de cancelación | `/bookings`, `/bookings/:id/cancel` |
| Pagos | Cobro de la reserva en nombre del anfitrión; suscripción con prorrateo, 3 reintentos y suspensión; CFDI; cargo posterior al anfitrión desde el panel | `/payments/intents`, webhooks, `/subscriptions`, `/admin/charges` |
| Mensajería | Hilo por reserva, sondeo cada 10 s, aviso por correo; detección de datos de contacto antes de confirmar | `/bookings/:id/messages` |
| Reportes | Motivo, descripción, fotos; abre caso; suspende depósito si es fraude | `/reports` |
| Admin | Cola de verificaciones, casos, suspender y reactivar, bitácora; cuatro ojos para cargos y exportaciones | `/admin/*` |
| Chapa | Emitir llave digital por reserva (inicio y fin), código de respaldo, registro de aperturas, desactivación automática, aviso de batería | Por definir con el SDK elegido (TTLock o igloohome) |
| Plataforma | Avisos por correo y SMS; bitácora de solo inserción; respaldos diarios cifrados; CI/CD con escaneo de secretos | GitHub Actions |

Estimación del MVP técnico: 57 días-persona de backend más 6 días de controles de seguridad agregados en la semana 2, y 18 días de frontend sobre 14 pantallas.

## 5. Modelo de datos

Llaves UUID, `created_at` y `updated_at` en todas las tablas, montos en centavos como enteros.

| Tabla | Para qué | Nota de diseño |
|---|---|---|
| `users` | Cuenta, rol, segundo factor, estado de identidad | Un usuario puede ser huésped y anfitrión; borrado lógico para derechos ARCO |
| `host_profiles` | Nivel (nuevo, verificado, suspendido), CLABE cifrada, RFC, cuenta en el procesador | CLABE cifrada por campo; solo se muestran los últimos 4 dígitos |
| `verifications` | Resultado de cada verificación por tipo y capa, puntajes de OCR y distancia geográfica | Guarda el resultado del proveedor, nunca el documento; los puntajes mandan a revisión, nunca rechazan solos |
| `properties` | Anuncio, ubicación exacta y aproximada, origen (manual o importado) | La ubicación exacta solo se devuelve con reserva confirmada; la aproximada se desplaza 200 a 400 m |
| `property_photos` | Fotos en tres tamaños | El original se conserva 30 días |
| `rates` | Tarifa base, limpieza, estancia mínima, temporadas | La cotización es una función pura sobre esta tabla |
| `calendar_blocks` | Bloqueos manuales, iCal y por reserva | Índice de exclusión impide dos bloqueos solapados |
| `bookings` | Reserva, total, estado, política, fecha de liberación del depósito | `payout_release_at` según el nivel del anfitrión |
| `subscriptions` | Plan, propiedades activas, periodo, intentos fallidos, prueba gratuita | El plan se recalcula al activar o desactivar una propiedad |
| `invoices` | Cobros de suscripción y CFDI | El XML del CFDI vive en el bucket |
| `messages` | Mensajes por reserva | Retención de 24 meses |
| `reports` | Reportes por reserva y su resolución | Un reporte de fraude pausa el depósito |
| `audit_log` | Acciones sensibles | Solo inserción; sin UPDATE ni DELETE |
| `events` | Búsquedas, clics, cotizaciones, reservas (seudónimos) | Insumo para las capas 2 y 3 de IA; sin nombre ni correo |

Pendiente de agregar al modelo por la chapa inteligente: llaves digitales por reserva y registro de aperturas (dato personal, declarado en el aviso de privacidad).

## 6. Flujos clave

**Reserva y pago.** El huésped paga en la web; la API crea la orden de cobro en nombre de la subcuenta del anfitrión; el procesador cobra; su webhook firmado confirma; el depósito a la CLABE se libera según el nivel (verificado: al confirmar; nuevo: 24 horas después de la llegada). El estado de la reserva cambia solo con el webhook, nunca con la respuesta del navegador. Idempotencia en todos los cobros.

**Suscripción del anfitrión.** Trabajo diario: periodo vencido, cobro a tarjeta tokenizada; si aprueba, CFDI y periodo renovado; si falla, hasta 3 reintentos y después suspensión de anuncios.

**Verificación en capas.** Antes de publicar: identidad (proveedor con INE y rostro), CLABE a su nombre, tarjeta a su nombre. Por propiedad: documento con OCR cruzado contra la identidad (capa 1), geocodificación de la dirección contra el pin (capa 2), número de padrón local donde aplique (capa 4); certificado del Registro Público de la Propiedad solo por excepción (capa 3). Todo produce puntajes y, si son bajos, revisión manual con respuesta en 24 horas.

**Acceso con chapa.** Reserva confirmada, llave digital emitida con inicio y fin, apertura por Bluetooth desde la app o código numérico de respaldo, entrada registrada (confirma la llegada real y puede liberar el pago a anfitriones nuevos), desactivación automática al terminar.

## 7. Seguridad: lo que no se negocia

Del documento de ciberseguridad, los controles obligatorios del MVP:

1. Cloudflare delante de web y API; solo el puerto 443 expuesto.
2. Contraseñas verificadas contra filtraciones; CAPTCHA en registro y login; TOTP obligatorio para anfitriones y panel; sesiones cortas con rotación.
3. Reautenticación y segundo factor para cambiar CLABE, correo o teléfono; bloqueo de depósitos 48 horas tras el cambio; aviso inmediato.
4. Autorización por propietario del recurso en cada endpoint; UUIDs; validación con esquemas; consultas parametrizadas; CSP y HSTS; sin HTML en contenido de usuario.
5. Cifrado por campo de CLABE y RFC con llave en gestor de secretos; buckets privados con URL firmada; EXIF eliminado; antivirus en la cola de archivos.
6. Webhooks del procesador, del verificador y del PAC con firma, ventana de 5 minutos y control de repetidos; total calculado en el servidor; 3-D Secure; conciliación diaria.
7. Mensajería que detecta y oculta CLABEs, teléfonos y enlaces antes de confirmar.
8. IA: lista blanca de campos que salen al modelo, salida JSON validada, solo sugiere, tope diario de gasto.
9. Lockfiles, Dependabot, escaneo de secretos y análisis estático en CI; sin versiones publicadas hace menos de 14 días.
10. Bitácora de solo inserción; cuatro ojos para cargos y exportaciones; soporte nunca cambia datos de cuenta.

Antes de lanzar: respaldo restaurado de verdad, alertas al celular de Sophie y Shakti, prueba de penetración externa, aviso de privacidad y contratos de encargo con cada proveedor. Blockchain: no en el MVP; anclaje de hashes de la bitácora en fase 2 (ADR 0010).

## 8. Del prototipo a producción

Este repositorio contiene hoy un prototipo estático. Así migra cada parte:

| Hoy (prototipo) | Mañana (producción) |
|---|---|
| `web/assets/css/estilos.css`, tokens en `:root` | Configuración de tema de Tailwind en Next.js; mismos nombres de token |
| `web/index.html` | Ruta `/` de Next.js: componentes `Buscador`, `Sellos`, `TarjetaPropiedad`, `Planes`, `Comparativa` |
| `web/propiedad.html` | Ruta `/propiedades/[id]`, renderizada en servidor para indexar |
| `web/assets/js/datos.js` | `GET /api/v1/search` y `GET /api/v1/properties/:id` |
| Filtro por ciudad y huéspedes en `app.js` | `GET /api/v1/search` con PostGIS y caché de 60 s |
| Total fijo de ejemplo en la ficha | `GET /api/v1/properties/:id/quote`, función pura sobre `rates`, calculada en el servidor |
| Marcadores de foto | Fotos en R2/S3 en tres tamaños, servidas por CDN |
| Insignias "Anfitrión verificado" y "Chapa inteligente" | Derivadas de `host_profiles.level` y del módulo `chapa` |
| Mapa aproximado estático | `properties.approx_location`; la exacta solo con reserva confirmada |

Decisiones que bloquean y sus fechas (del MVP técnico): procesador de pagos y proveedor de identidad (16 de octubre), NestJS o FastAPI (16 de octubre), proveedor de LLM (23 de octubre), ciudad de lanzamiento (30 de octubre). Cada una se registra como ADR al tomarse.
