# Pruebas de la base de datos

Estas pruebas corren las migraciones de `database/migrations/` sobre un PostgreSQL en memoria ([PGlite](https://pglite.dev)) y comprueban cada regla de las tablas: datos obligatorios, formatos, duplicados y permisos. No se conectan a ninguna base real ni necesitan contraseñas.

## Archivos

| Archivo | Para qué |
|---|---|
| `group1_users.test.js` | Casos del grupo 1: `users`, `user_credentials`, `host_profiles` y `verifications`. |

## Cómo correrlas

PGlite se instala fuera del repositorio, en cualquier carpeta temporal, para que el proyecto siga sin dependencias:

```bash
mkdir ~/pglite-pruebas && cd ~/pglite-pruebas
npm init -y && npm install @electric-sql/pglite
```

Después, desde la raíz del repositorio:

```bash
NODE_PATH=~/pglite-pruebas/node_modules node tests/database/group1_users.test.js
```

Cada caso imprime lo esperado, lo obtenido y `COINCIDE` o `NO COINCIDE`. La última línea da el total. El programa termina con código 0 solo si todos coinciden.

## Quién hace cada cosa en las pruebas

| En la prueba | Papel de la base | Qué representa |
|---|---|---|
| "Ana, con sesión" | `integro_app` con su id anotado | La API atendiendo a una persona que inició sesión |
| "Alguien sin sesión" | `integro_app` sin id | Una petición sin persona identificada |
| "El sistema" | `integro_service` | La API actuando por su cuenta: registro, avisos de proveedores |
| "El dueño de la base" | usuario que corrió la migración | Quien administra la base directamente |

## Cómo leer un rechazo

Un rechazo se imprime con el código de PostgreSQL y la regla que lo causó:

| Código | Significa |
|---|---|
| `23502` | Falta un dato obligatorio (se indica la columna) |
| `23503` | Se hace referencia a una fila que no existe, o se quiere borrar una fila que otras usan |
| `23505` | Valor repetido donde debe ser único |
| `23514` | El valor no cumple el formato o la lista permitida (se indica la regla) |
| `22008` | Fecha que no existe |
| `42501` | Quien lo intenta no tiene permiso |
