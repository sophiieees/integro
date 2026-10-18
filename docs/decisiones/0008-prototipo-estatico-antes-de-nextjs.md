# ADR 0008 · Prototipo estático antes de Next.js

**Estado:** propuesta de la IA (18 de octubre de 2026), pendiente del veredicto de Sophia (PROMPT_LOG.md, entrada 0.1).

## Contexto
El MVP técnico fija Next.js 15 con TypeScript y Tailwind para la web. El 18 de octubre hacía falta un diseño visible de la página para iterarlo y para el Assignment 2, y la máquina de desarrollo tenía 734 MB libres en disco: instalar Next.js y sus dependencias no era viable ese día.

## Decisión propuesta
Construir el prototipo en HTML, CSS y JavaScript sin dependencias ni paso de compilación, con los tokens de diseño en `:root` y los datos de muestra en un archivo que se carga como script. Migrar a Next.js cuando arranque el frontend del plan (semanas 6 y 7), llevando tokens, estructura de componentes y textos.

## Consecuencias
- A favor: se abre con doble clic, se publica sin compilar, cualquiera edita el HTML, cero peso de dependencias.
- En contra: una parte del trabajo (maquetación) se rehace al migrar a componentes; no hay renderizado en servidor ni PWA en el prototipo.
- La función del Assignment 2 se construye sobre este prototipo; si usa una API con llave, necesitará una función serverless aparte.

## Alternativa descartada por ahora
Arrancar Next.js directamente. Requiere liberar disco y una tarde de configuración; es el camino correcto para las semanas 6 y 7.

## Fuente
MVP técnico, tabla de tecnología propuesta; estado de la máquina el 18 de octubre.
