# ADR 0009 · Tokens de diseño antes de la identidad de marca

**Estado:** aceptada (MVP técnico, tabla de riesgos).

## Contexto
La identidad de marca (nombre, logotipo, paleta, tipografía) es entregable de Valeria para el 30 de octubre. El frontend no puede esperar a esa fecha para empezar.

## Decisión
Construir con variables de diseño (tokens) desde el primer archivo y aplicar colores y tipografía al final. En el prototipo, los tokens viven en `:root` de `web/assets/css/estilos.css`; en Next.js, en la configuración de tema de Tailwind con los mismos nombres.

## Consecuencias
- La paleta "seguridad" propuesta por la IA (azul profundo, verde íntegro, papel cálido) es un valor inicial, no una decisión de marca.
- Cambiar la identidad es cambiar un bloque de valores, no reescribir páginas.

## Fuente
MVP técnico, riesgo "Dependencia de la identidad de marca (semana 4) para estilos".
