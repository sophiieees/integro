# Pantallas del MVP y estado del prototipo

El MVP técnico habla de 14 pantallas y remite al documento de diseño del MVP para la lista. Esta es la lista de trabajo derivada de los requerimientos; conciliar con ese documento cuando esté a la mano.

| # | Pantalla | Para quién | Estado en el prototipo |
|---|---|---|---|
| 1 | Portada del huésped: cabecera con la marca y el enlace "Conviértete en anfitrión", hero con imagen de fondo, eslogan y el buscador al centro, seis propiedades | Huésped | Hecha: `web/index.html` (primer avance entregable, 18 oct) |
| 2 | Ficha de propiedad con precio total y caja de reserva; ubicación (enlace a Google Maps con la zona) y reseñas a lo ancho | Huésped | Hecha: `web/propiedad.html` |
| 2b | Página del anfitrión: beneficios, planes, tres pasos para publicar y comparativa | Anfitrión | Hecha: `web/anfitriones.html` (separada de la portada por decisión de Sophia, 18 oct) |
| 2c | Cómo funciona: cuatro sellos de confianza y tres pasos para reservar | Ambos | Hecha: `web/como-funciona.html` (Sophia prevé que termine dentro de anfitriones) |
| 3 | Resultados con filtros y mapa aproximado | Huésped | Parcial: la cuadrícula de inicio hace de resultados; faltan filtros de precio y servicios y el mapa |
| 4 | Reserva y pago (tarjeta, transferencia, tienda) | Huésped | Pendiente |
| 5 | Registro e inicio de sesión con código | Ambos | Pendiente |
| 6 | Verificación de identidad del huésped (antes de la primera reserva) | Huésped | Pendiente |
| 7 | Mensajería por reserva | Ambos | Pendiente |
| 8 | Historial de estancias y comprobantes | Huésped | Pendiente |
| 9 | Reportar un problema | Huésped | Pendiente (hay enlace en la ficha) |
| 10 | Registro y verificación del anfitrión (identidad, CLABE, tarjeta, segundo factor) | Anfitrión | Pendiente |
| 11 | Publicar propiedad con importación asistida y descripción por IA | Anfitrión | Pendiente |
| 12 | Calendario y sincronización iCal | Anfitrión | Pendiente |
| 13 | Precios y temporadas | Anfitrión | Pendiente |
| 14 | Reservas del anfitrión y suscripción (plan, cobros, facturas) | Anfitrión | Pendiente |
| 15 | Panel interno (verificaciones, casos, bitácora) | Equipo | Pendiente |
| 16 | Llave digital y apertura de la chapa | Huésped | Pendiente; depende del SDK (prueba de Shakti, 30 de octubre) |

Regla de la portada (Sophia, 18 oct): la página principal es solo para el huésped y muestra el buscador y las propiedades, sin texto de venta; todo lo del anfitrión vive en `anfitriones.html` y la explicación del modelo en `como-funciona.html`. El pie de página es verde, igual en todas las páginas, con "Reportar un problema" destacado.
