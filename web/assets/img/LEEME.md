# Imágenes del prototipo

Guarda aquí las fotos con estos nombres exactos (minúsculas, sin espacios). Mientras un archivo no exista, la página muestra un marcador en su lugar; en cuanto lo guardes y recargues, aparece.

| Archivo | Dónde se ve | Formato sugerido |
|---|---|---|
| `imagen-bienvenida.jpg` | Fondo del hero de la portada (`index.html`) | Horizontal, 1920 × 1080 o mayor, menos de 600 KB |
| `imagen-anfitriones.jpg` | Fondo del hero de `anfitriones.html` (opcional) | Igual que la anterior |
| `propiedad-1-1.jpg` … `propiedad-9-1.jpg` | Foto principal de cada tarjeta y primera foto de la ficha | 4:3, 1200 × 900, menos de 300 KB |
| `propiedad-1-2.jpg` … `propiedad-1-5.jpg` (y así por propiedad) | Fotos 2 a 5 de la galería de la ficha | 4:3 |

El número después de `propiedad-` es el `id` de la propiedad en `../js/datos.js`; el segundo número es la posición en la galería.

Formato: `.jpg` comprimido (o `.webp` si cambias la extensión en `app.js` y en `index.html`). En producción las fotos se suben desde la app, se convierten a WebP en tres tamaños y se les quitan los metadatos EXIF; aquí basta con que no pesen demasiado.
