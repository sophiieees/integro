# ADR 0008: Frontend en HTML, CSS y JavaScript; Next.js se decide más adelante

**Estado:** aceptada (Sophia, 19 de noviembre de 2026). Nació como propuesta de la IA el 18 de octubre de 2026.

## Contexto
El MVP técnico fija Next.js 15 con TypeScript y Tailwind para la web. El 18 de octubre de 2026 hacía falta un diseño visible de la página para poder iterarlo, y la máquina de desarrollo tenía 734 MB libres en disco: instalar Next.js y sus dependencias no era viable ese día. Se propuso entonces un prototipo estático, con la idea de migrar a Next.js en las semanas 6 y 7 del plan.

Desde entonces el prototipo creció a cuatro páginas publicadas, y el backend se construye aparte, en Python con FastAPI (ADR 0012). El 19 de noviembre de 2026 Sophia definió que el frontend lo desarrolla y lo diseña ella, y eligió seguir con HTML, CSS y JavaScript.

## Decisión
- El frontend sigue en HTML, CSS y JavaScript, sin dependencias ni paso de compilación, en `web/`, con los tokens de diseño en `:root` de `web/assets/css/estilos.css`.
- La migración a Next.js deja de tener fecha: se decide más adelante.
- El diseño es de Sophia. La web usa la paleta y la tipografía del manual de identidad de Íntegro (versión provisional, octubre de 2026):

| Elemento | Valor |
|---|---|
| Verde íntegro | `#1F4D3A` |
| Verde noche | `#142A21` |
| Dorado arena | `#C9A66B` |
| Arena | `#F3EEE4` |
| Tipografía | Outfit: SemiBold en títulos y Regular en texto |

- El logotipo queda pendiente: todavía no se tiene.
- Los documentos del proyecto siguen en azul marino `#0E0E55`; esta paleta es de la web.

## Consecuencias
- A favor: se abre con doble clic, se publica sin compilar, cualquiera edita el HTML y no hay peso de dependencias.
- En contra: no hay renderizado en servidor, así que las fichas de propiedad se indexan peor en buscadores, ni PWA (ADR 0004). Si más adelante se migra a Next.js, la maquetación se rehace como componentes.
- El frontend habla con la API de FastAPI (ADR 0001 y ADR 0012). Las pantallas de cuenta, empezando por el inicio de sesión y «Entrar» en la cabecera, se construyen sobre este prototipo.
- Falta guardar el manual de identidad en `docs/diseno/` y aplicar su paleta y su tipografía a los tokens de `estilos.css`, que todavía tienen los colores de octubre.

## Alternativa descartada por ahora
Arrancar Next.js directamente. Sigue siendo lo que fija el MVP técnico; se retoma cuando haga falta el renderizado en servidor o la PWA.

## Fuente
Decisiones de Sophia del 19 de noviembre de 2026. Bitácora, decisiones 0.1, 0.2, 0.3, 23.2, 23.3, 23.5 y 23.6. Manual de identidad de Íntegro, versión provisional de octubre de 2026. MVP técnico, tabla de tecnología propuesta.

## Cambios
- 19 de noviembre de 2026: pasa de propuesta a aceptada. La versión anterior daba fecha a la migración a Next.js (semanas 6 y 7) y no hablaba de la identidad de marca.
