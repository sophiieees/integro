-- Íntegro, base de datos, grupo 1: cuándo pasó cada sesión el Authenticator.
-- sessions.second_factor_at.
--
-- PostgreSQL puro, igual que las migraciones anteriores.
--
-- Decisiones de Sophia del 25 de noviembre de 2026 que implementa esta migración
-- (bitácora 41.12 y 42.4, y la especificación de la pieza 3.3):
--   1. Quien tiene el Authenticator activo inicia sesión con su contraseña, el
--      código del correo y el código de su aplicación. La sesión se abre con el
--      código del correo, pero queda en espera hasta que escribe el de la
--      aplicación: mientras tanto no sirve para nada.
--   2. Cada 30 días la misma sesión vuelve a quedar en espera, aunque se use a
--      diario. El número vive en la configuración de la API.
--
-- Para saber si una sesión ya pasó el Authenticator, y hace cuánto, se anota
-- la fecha en la propia sesión.

alter table public.sessions
  -- Fecha en que esta sesión pasó el Authenticator por última vez. Vacía si
  -- nunca lo ha pasado: de quien no lo tiene activo, o de quien todavía no
  -- escribe el código en esta sesión.
  add column second_factor_at timestamptz;

alter table public.sessions
  add constraint sessions_second_factor_after_created check (second_factor_at >= created_at);

-- Permisos: no cambian. El sistema ya lee y escribe toda la tabla. La persona
-- lee de sus sesiones solo las columnas de la lista de la migración
-- 20261117000003, y esta no está en ella: no la puede leer ni cambiar.
