# Íntegro

Plataforma de rentas de corta estancia por suscripción, para México. El anfitrión paga una membresía mensual fija y no hay comisión por reserva. El huésped ve el precio total desde la búsqueda, paga dentro de la plataforma y el dinero llega directo a la cuenta del anfitrión. Cada anfitrión aprueba tres verificaciones (identidad, cuenta bancaria y tarjeta) antes de publicar, y cada propiedad se verifica por capas.

**Íntegro es un nombre provisional**, sujeto a validación ante el IMPI.

Estado al 18 de octubre de 2026: semana 2 de 7 del plan de construcción del MVP. Equipo técnico: Sophie (Sophia Pérez) y Shakti. Valeria lleva negocio, legal y marca.

## Qué hay en este repositorio

| Ruta | Qué es |
|---|---|
| `web/` | Prototipo estático de la interfaz: portada del huésped (`index.html`), ficha de propiedad (`propiedad.html`), cómo funciona (`como-funciona.html`) y página del anfitrión (`anfitriones.html`). HTML, CSS y JavaScript sin dependencias ni paso de compilación. |
| `web/assets/img/LEEME.md` | Nombres de archivo que esperan las páginas para las fotos (hero y propiedades). Sophia guarda ahí las imágenes. |
| `web/assets/css/estilos.css` | Hoja de estilos. Los tokens de diseño (paleta, tipografía, radios) viven en `:root` y son el único lugar que cambia cuando llegue la identidad de marca. |
| `web/assets/js/datos.js` | Datos ficticios de muestra. En producción salen de la API. |
| `web/assets/js/app.js` | Pinta tarjetas, filtra por ciudad y huéspedes, pinta la ficha. No cotiza ni reserva: eso es trabajo del backend. |
| `docs/arquitectura.md` | Arquitectura objetivo: módulos, modelo de datos, flujos, infraestructura, seguridad y cómo este prototipo migra a ella. |
| `docs/decisiones/` | Registros de decisiones de arquitectura (ADR), numerados y con fuente. |
| `docs/diseno/` | Sistema de diseño, comparación con la competencia y lista de pantallas. |
| `herramientas/bitacora/` | Datos y generador del documento de presentación en Word (`bitacora_datos.py`, `generar_presentacion.py`). |
| `index.html` (raíz) | Redirección a `web/index.html` para que GitHub Pages sirva el prototipo sin configuración. |
| `vercel.json` | Le dice a Vercel que la carpeta publicable es `web/`. |

## Cómo ver el prototipo

Versión publicada: https://integro-ruby.vercel.app (Vercel la actualiza con cada push a `main` y conserva un deploy por commit).

1. Abre `web/index.html` en el navegador con doble clic. No necesita servidor ni instalar nada.
2. Para verlo en el celular o compartirlo, publica el repositorio en cualquiera de estos servicios, sin paso de compilación:
   - **Vercel**: importar el repo; `vercel.json` ya apunta a `web/`.
   - **Cloudflare Pages**: directorio de salida `web`.
   - **GitHub Pages**: rama `main`, carpeta raíz; `index.html` redirige a `web/`.

## Arquitectura en una pantalla

Tres decisiones gobiernan todo lo demás (detalle en [docs/arquitectura.md](docs/arquitectura.md) y en [docs/decisiones/](docs/decisiones/)):

1. **API primero.** Toda función existe como endpoint REST versionado (`/api/v1/...`) antes de tener pantalla. La web es el primer cliente; la app móvil será el segundo y usará la misma API.
2. **La plataforma no toca dinero ni documentos sensibles.** Tarjetas e identificaciones viven en proveedores certificados; la base propia guarda referencias y resultados.
3. **Monolito modular, no microservicios.** Un backend con módulos por dominio: cuentas, verificación, propiedades, búsqueda, reservas, pagos, mensajería, reportes, admin e IA.

Este repositorio contiene hoy solo la capa de presentación, como prototipo estático. La sección "Del prototipo a producción" de `docs/arquitectura.md` dice qué parte de este código migra a qué pieza del sistema.

## Documentos fuente

Los documentos de negocio viven fuera del repositorio por confidencialidad. Las decisiones registradas en `docs/` citan de cuál salen:

- Requerimientos de la plataforma de rentas por suscripción (Valeria, 29 de septiembre de 2026)
- Cronograma de entregables (Valeria, 29 de septiembre de 2026)
- MVP técnico con método MoSCoW (Sophie, semana 1)
- Ciberseguridad: amenazas, controles y respuesta (Sophie, semana 2)
- Mapa de etapas de Íntegro (octubre de 2026)
- Chapa inteligente de Íntegro (Valeria, 13 de octubre de 2026)

## Historial de versiones

Cada ronda de cambios del prototipo tiene una etiqueta de git (`v0.1-mockup-inicial`, `v0.2-portada-huesped`, `v0.3-primer-avance`, `v0.4-eslogan-y-ficha`) y capturas del estado anterior en [docs/diseno/capturas/historial/](docs/diseno/capturas/historial/). Así se puede ver cómo estaba el sitio antes de cada modificación.

## Convenciones

- Todo en español: código comentado, documentos y mensajes de commit.
- Cada commit dice qué decisión tomó, no solo qué archivo tocó.
- Ramas con el patrón `tipo/descripcion-corta` (por ejemplo `web/ficha-propiedad`, `docs/adr-pagos`). Cambios pequeños; Sophia revisa y aprueba antes de fusionar.
- Ningún secreto en el repositorio. `.env` está en `.gitignore`; las llaves viven en un gestor de secretos.
