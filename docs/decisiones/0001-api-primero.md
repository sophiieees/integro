# ADR 0001 · API primero

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
La web es el primer cliente y la app móvil llegará en la fase 2. Si la lógica vive en las pantallas, la app obliga a reescribir.

## Decisión
Toda función existe como endpoint REST versionado (`/api/v1/...`) antes de tener pantalla. La web consume la API igual que lo hará la app nativa.

## Consecuencias
- La app en React Native reutiliza el backend sin cambios.
- El prototipo estático de este repositorio es solo presentación; sus datos de muestra se reemplazan por llamadas a la API (ver `docs/arquitectura.md`, sección 8).
- Cada pieza del MoSCoW se estima y se cierra por endpoint, no por pantalla.

## Fuente
MVP técnico (MoSCoW), "Alcance técnico del MVP", decisión 1.
