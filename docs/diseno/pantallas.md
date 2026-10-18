# Pantallas del MVP y estado del prototipo

El MVP técnico habla de 14 pantallas y remite al documento de diseño del MVP para la lista. Esta es la lista de trabajo derivada de los requerimientos; conciliar con ese documento cuando esté a la mano.

| # | Pantalla | Para quién | Estado en el prototipo |
|---|---|---|---|
| 1 | Portada del huésped: buscador compacto en la cabecera, hero con imagen de fondo, seis propiedades, sellos de confianza y cómo funciona | Huésped | Hecha: `web/index.html` |
| 2 | Ficha de propiedad con precio total y caja de reserva | Huésped | Hecha: `web/propiedad.html` |
| 2b | Página del anfitrión: beneficios, planes, tres pasos para publicar y comparativa | Anfitrión | Hecha: `web/anfitriones.html` (separada de la portada por decisión de Sophia, 18 oct) |
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

Regla de la portada (Sophia, 18 oct): la página principal es solo para el huésped y muestra propiedades; todo lo del anfitrión vive en `anfitriones.html`. Los sellos de confianza y "cómo funciona" quedan debajo de las propiedades.
