# Benchmark de competencia para el diseño

Referencias que Sophia compartió el 18 de octubre de 2026: la portada de Airbnb (versión en español, con buscador de destino, fechas y huéspedes, carrusel de experiencias y tarjetas "Disponibles en Acapulco el próximo fin de semana") y dos capturas de Wander (hero "Find your happy place" con "No fees or markups", buscador en la cabecera, tarjetas "Homes our guests love" con etiquetas Iconic y Luxury y la línea "~$675 less than other sites").

## Qué hace cada una

| Elemento | Airbnb | Wander | Íntegro (prototipo) |
|---|---|---|---|
| Promesa en el hero | Ninguna; va directo al buscador y a categorías | "Find your happy place. Guest-first travel. No fees or markups." | "Hospedaje verificado. Precio total. Cero comisión." Tres promesas verificables, no un lema emocional |
| Buscador | Píldora de tres campos bajo la cabecera | Píldora en la cabecera (Where, When, Who) | Barra rectangular de cuatro campos dentro del hero; llegada y salida separadas porque el total depende de las noches |
| Entrada para el anfitrión | "Conviértete en anfitrión" en la cabecera | "List on Wander" en la cabecera | "Publica tu propiedad" en la cabecera y sección propia con planes |
| Tarjetas | Foto, "Favorito entre huéspedes", corazón | Foto, etiqueta Iconic o Luxury, corazón, precio por N noches, "~$X less than other sites" en verde | Foto, insignias de verificación y chapa, precio por noche y total de 2 noches "sin cargos de servicio" en verde |
| Precio | Por noche; cargos de servicio aparecen al final | Total por N noches, sin cargos | Por noche y total desde la tarjeta; desglose en la ficha con "Comisión de plataforma $0" |
| Señal de confianza | "Favorito entre huéspedes", reseñas | Curaduría ("only the best homes"), concierge 24/7 | Verificación por capas visible, momento del pago, reseñas solo tras estancia, entrada con chapa |
| Tono visual | Blanco, iconos de colores, curvas, foto como protagonista | Oscuro, foto a pantalla completa, sans moderna | Papel cálido y azul profundo, serif en títulos, sin iconos, curvas discretas |
| Categorías | Carrusel de experiencias y servicios | "Fall colors", colecciones | No aplica al MVP: una ciudad, hospedaje únicamente |

## Qué tomamos

- De Airbnb: la estructura de búsqueda por destino, fechas y huéspedes, y la sección "Disponibles en [ciudad] este fin de semana" con tarjetas en cuadrícula.
- De Wander (decisión de Sophia, 18 oct): la barra de búsqueda compacta dentro de la cabecera, el hero con una foto a lo ancho y el titular encima, y una portada dirigida solo al huésped con la entrada del anfitrión como un botón que lleva a su propia página. También la promesa económica en el hero, el total por estancia en la tarjeta y el verde para "lo que te ahorras".
- De ambas: la portada no habla con el anfitrión. Esa conversación vive en `anfitriones.html`.

## Qué cambiamos

- La promesa no es emocional ("happy place") sino verificable: verificado, total, cero comisión.
- El verde no marca "más barato que otros" sino "verificado" y "sin cargos". Comparar precios con otras plataformas es de segunda fase y requiere autorización del anfitrión (requerimientos); se evita afirmar cifras de terceros.
- Serif en títulos y fondo papel: ninguna de las dos referencias lo usa.
- Sin corazones de favoritos (segunda fase) ni carruseles de categorías (no aplican a una sola ciudad de lanzamiento).
- La ficha muestra una zona aproximada en lugar de un pin exacto (regla de seguridad: la dirección exacta solo con reserva confirmada).

## Qué no copiamos y por qué

- "~$X menos que otros sitios": afirma datos de la competencia que no tenemos validados; en Íntegro entra en fase 2 como "comparación de precio si el anfitrión lo autoriza".
- Iconos de colores por categoría: Sophia prefiere secciones sin iconos, y el MVP no tiene categorías.
- Foto de pantalla completa con texto encima: reduce legibilidad del buscador en celular y pesa; se deja un hueco 4:5 al lado del texto.
