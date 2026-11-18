# ADR 0012: API en Python con FastAPI

**Estado:** aceptada (Sophia, 17 de noviembre de 2026).

## Contexto
La arquitectura dejó abierta la elección del framework de la API entre NestJS (TypeScript) y FastAPI (Python), con la indicación de tomar una sola decisión y registrarla. El 17 de noviembre de 2026, al terminar el modelo de datos, Sophia definió que la programación del backend se hace en Python.

## Decisión
El backend se construye en Python con FastAPI, dentro de un entorno virtual. Se mantienen la API primero (ADR 0001) y el monolito modular (ADR 0002): una sola aplicación dividida en los módulos de `docs/arquitectura.md`.

## Consecuencias
- La web y la API quedan en lenguajes distintos, así que no comparten tipos. El contrato entre las dos es la especificación OpenAPI que FastAPI genera a partir del código.
- La validación de entradas con esquemas, que exigen las reglas de seguridad, se hace con los modelos de FastAPI.
- Las pruebas del grupo 1 de la base de datos están en JavaScript (`tests/database/`) y se quedan así. Desde el 17 de noviembre de 2026, las pruebas de las tablas nuevas y las del backend van en Python (`tests/backend/`), en una sola batería que corre contra la base real y deshace todo al terminar.
- El orden de construcción empieza por el esqueleto del backend y el módulo de Cuentas.

## Fuente
Decisión de Sophia del 17 de noviembre de 2026. `docs/arquitectura.md`, secciones 3 y 4.
