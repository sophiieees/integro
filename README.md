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
| `docs/assignment-2/` | Material del Assignment 2: funciones candidatas y guía de la rúbrica. |
| `PROMPT_LOG.md` | Bitácora de prompts del Assignment 2: especificación, decisiones de aceptar, rechazar o revisar, y validación. |
| `index.html` (raíz) | Redirección a `web/index.html` para que GitHub Pages sirva el prototipo sin configuración. |
| `vercel.json` | Le dice a Vercel que la carpeta publicable es `web/`. |

## Cómo ver el prototipo

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

## Para el profesor: dónde está cada pieza del Assignment 2

Íntegro es un producto real en construcción por tres socias; este repositorio es su base técnica. El Assignment 2 agrega una función real dentro de él y documenta cómo se tomó cada decisión con el asistente de IA.

| Pieza del assignment | Dónde está |
|---|---|
| Funciones candidatas (Pre-Class Work de la Sesión 19) | [docs/assignment-2/funciones-candidatas.md](docs/assignment-2/funciones-candidatas.md) |
| Especificación de 3 campos (Paso 1, Checkpoint A) | [PROMPT_LOG.md](PROMPT_LOG.md), sección 1 |
| Registro de aceptar, rechazar o revisar (Paso 2, Checkpoint B) | [PROMPT_LOG.md](PROMPT_LOG.md), sección 2 |
| Registro de validación con caso de prueba real (Paso 3) | [PROMPT_LOG.md](PROMPT_LOG.md), sección 3 |
| Enlaces de deploy y repositorio (Paso 4) | [PROMPT_LOG.md](PROMPT_LOG.md), sección 4 |
| Por qué la función resuelve el problema (nivel 5) | [PROMPT_LOG.md](PROMPT_LOG.md), sección 5 |
| Declaración "Uso de IA" | [PROMPT_LOG.md](PROMPT_LOG.md), sección 6 |
| Código de la función | Ruta anotada en la sección 1 de la bitácora cuando se elija la función |
| Historial de commits con decisiones | `git log --oneline` |
| Cómo se contrasta cada criterio de la rúbrica | [docs/assignment-2/guia-rubrica.md](docs/assignment-2/guia-rubrica.md) |

## Documentos fuente

Los documentos de negocio viven fuera del repositorio por confidencialidad. Las decisiones registradas en `docs/` citan de cuál salen:

- Requerimientos de la plataforma de rentas por suscripción (Valeria, 29 de septiembre de 2026)
- Cronograma de entregables (Valeria, 29 de septiembre de 2026)
- MVP técnico con método MoSCoW (Sophie, semana 1)
- Ciberseguridad: amenazas, controles y respuesta (Sophie, semana 2)
- Mapa de etapas de Íntegro (octubre de 2026)
- Chapa inteligente de Íntegro (Valeria, 13 de octubre de 2026)

## Convenciones

- Todo en español: código comentado, documentos y mensajes de commit.
- Cada commit dice qué decisión tomó, no solo qué archivo tocó.
- Ramas con el patrón `tipo/descripcion-corta` (por ejemplo `web/ficha-propiedad`, `docs/adr-pagos`). Cambios pequeños; Sophia revisa y aprueba antes de fusionar.
- Ningún secreto en el repositorio. `.env` está en `.gitignore`; las llaves viven en un gestor de secretos.
