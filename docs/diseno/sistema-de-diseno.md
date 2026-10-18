# Sistema de diseño del prototipo

Propuesta de octubre de 2026. La identidad de marca (nombre definitivo, logotipo, paleta, tipografía) es entregable de Valeria para el 30 de octubre; todo lo que aquí se define vive en tokens de `web/assets/css/estilos.css` para que esa identidad se aplique cambiando valores, no reescribiendo páginas.

## Principios

1. **La confianza se muestra, no se promete.** La verificación del anfitrión, el momento en que cobra, el precio total y la entrada con chapa aparecen en la tarjeta y en la ficha, no en una página de "por qué confiar".
2. **Calma.** Dos colores de marca, mucho espacio, nada parpadea ni se mueve en bucle. La única animación es la entrada de los elementos al hacer scroll, una sola vez.
3. **Ligereza.** Fuentes del sistema y sin librerías: la página de búsqueda tiene presupuesto de 400 KB y la ficha de 1.2 MB (MVP técnico).
4. **Contexto mexicano.** Pesos mexicanos, español, CLABE, INE, ciudades reales. Nada traducido del inglés.

## Tokens

| Token | Valor | Uso |
|---|---|---|
| `--color-primario` | `#0F3D52` azul profundo | Marca, botones secundarios, hero, pie oscuro. Comunica solidez y seguridad. |
| `--color-primario-oscuro` | `#0A2A39` | Fondos oscuros (hero, comparativa) |
| `--color-primario-suave` | `#E3ECF1` | Fondos suaves, pastilla de "anfitrión nuevo" |
| `--color-acento` | `#1E8E5A` verde íntegro | Lo verificado, el total sin cargos, el botón principal. Se reserva para "esto está en orden" y "el dinero llega completo". |
| `--color-acento-suave` | `#E2F2E9` | Pastillas, caja de chapa, fila destacada de planes |
| `--color-fondo` | `#F7F5F0` papel cálido | Fondo general; evita el blanco frío de las plataformas grandes |
| `--color-superficie` | `#FFFFFF` | Cabecera, cajas, sellos |
| `--color-tinta` / `--color-tinta-suave` | `#16232B` / `#5A6872` | Texto principal y secundario |
| `--color-borde` | `#E2DED5` | Líneas divisorias |
| `--color-alerta` | `#B8432A` | Errores y avisos de fraude (reservado; aún sin uso en el prototipo) |
| `--fuente-titulos` | Serif del sistema (Iowan Old Style, Palatino, Georgia) | Títulos, números de paso, nombre de la marca |
| `--fuente-texto` | Sans del sistema | Todo lo demás |
| `--radio` / `--radio-chico` | 10 px / 6 px | Cajas y botones. Esquinas discretas a propósito. |
| `--sombra` | Dos capas suaves | Buscador, caja de precio, planes |
| `--ancho-max` | 1180 px | Contenedor |

Para cambiar la paleta: editar `:root` en `estilos.css`. Nada más.

## Tipografía

- Títulos en serif, peso 600, interlineado 1.15. Diferencia a Íntegro de Airbnb y Wander (ambas sans en todo) y transmite permanencia.
- Texto en sans del sistema, 16 px, interlineado 1.55.
- Etiquetas de sección en mayúsculas pequeñas con espaciado de letra (`.etiqueta`), en verde.

## Componentes

| Componente | Dónde | Qué comunica |
|---|---|---|
| Cabecera fija con marca, navegación y "Publica tu propiedad" | Ambas páginas | El anfitrión tiene un camino visible desde cualquier pantalla (como "List on Wander") |
| Buscador de cuatro campos y botón | Inicio | Destino, llegada, salida, huéspedes. Rectangular, no píldora, para separarse de Airbnb |
| Sello de confianza (`.sello`) | Inicio | Cuatro promesas con línea superior verde; elementos libres, sin cajas ni iconos |
| Tarjeta de propiedad (`.tarjeta`) | Inicio | Foto, insignias "Anfitrión verificado" y "Chapa inteligente", título, zona, calificación, precio por noche y total de 2 noches sin cargos |
| Insignia (`.insignia`) y pastilla (`.pastilla`) | Tarjeta y ficha | Estado del anfitrión (verificado o nuevo) y chapa. El rombo verde es la marca de "verificado" en todo el sitio |
| Pasos numerados (`.pasos`) | Inicio | Cómo reservar, con numerales en serif |
| Tabla de planes (`.tabla`) | Inicio | Membresía por propiedades activas; fila destacada en verde |
| Tabla comparativa (`.tabla-comparativa`) | Inicio, fondo oscuro | Modelo por comisión frente a Íntegro, sin cifras de terceros |
| Caja de precio (`.caja-precio`) | Ficha, fija al hacer scroll | Desglose con "Comisión de plataforma $0" en verde; es la pantalla donde la promesa de precio total se cumple |
| Mapa aproximado (`.mapa-aproximado`) | Ficha | Círculo de zona, sin pin exacto: la ubicación exacta solo con reserva confirmada |
| Aviso de seguridad en el pie (`.pie-seguridad`) | Ambas | "Íntegro nunca te pedirá pagar fuera de la plataforma" (control del documento de ciberseguridad) |

## Reglas de estilo aplicadas

- Sin emojis ni iconos en las secciones. Las viñetas son rombos o cuadrados pequeños en el color de marca.
- Esquinas discretas (6 a 10 px). Preferencia por elementos libres sobre el fondo en vez de cajas; las únicas cajas son las que necesitan destacarse (buscador, planes, caja de precio).
- Animaciones solo al entrar en pantalla, una sola vez (`.revelar`), y desactivadas si el sistema pide movimiento reducido.
- Las imágenes las coloca Sophia. Cada hueco tiene un marcador con la proporción esperada (hero 4:5, tarjetas 4:3, galería de ficha 5 fotos).
- Contraste mínimo AA en texto; foco visible en verde; etiquetas en todos los campos de formulario.

## Responsivo

| Corte | Qué cambia |
|---|---|
| Más de 960 px | Hero en dos columnas, cuatro sellos en fila, ficha en dos columnas con caja de precio fija |
| 720 a 960 px | Hero en una columna sin imagen, sellos en dos columnas, ficha en una columna |
| Menos de 720 px | Navegación oculta (queda la marca y "Entrar"), buscador en dos columnas, sellos y pasos en una columna |

Pendiente: menú para celular; hoy la navegación se oculta y el usuario llega a las secciones haciendo scroll.

## Pendientes de diseño

- Identidad de marca (30 de octubre): nombre definitivo, logotipo, paleta final, tipografía con licencia si no es del sistema.
- Fotografías reales de propiedades en la ciudad de lanzamiento.
- Las 12 pantallas restantes (ver `pantallas.md`).
- Textos legales: términos, aviso de privacidad, política de cancelación con plazos definidos.
- Menú para celular y estados de error de formularios.
