-- Íntegro, base de datos, grupo 1: la clave del Authenticator de cada persona.
-- user_totp.
--
-- PostgreSQL puro, igual que las migraciones anteriores.
--
-- Decisiones de Sophia del 24 de noviembre de 2026 que implementa esta migración
-- (bitácora 41.11 y 41.12, y la especificación de la pieza 3.2):
--   1. Los anfitriones y los administradores usan una aplicación Authenticator
--      (códigos de 6 dígitos que cambian cada 30 segundos), que se suma al código
--      del correo. La clave que comparten la aplicación y el servidor se guarda
--      aquí, cifrada con AES-256-GCM (ADR 0014).
--   2. La activación tiene dos pasos: se genera la clave y queda pendiente; la
--      persona la comprueba con un código y queda activa.
--   3. Un código no sirve dos veces, y a los 5 códigos incorrectos seguidos la
--      persona espera 15 minutos. Los dos números viven en la configuración de
--      la API; la tabla guarda la cuenta y hasta cuándo espera.
--   4. Solo el sistema lee y escribe esta tabla. La persona no puede leer ni su
--      propia fila: si pudiera, quien tome su sesión podría copiar la clave.

-- ---------------------------------------------------------------------------
-- user_totp: la clave del Authenticator, cifrada
-- ---------------------------------------------------------------------------
-- Una fila por persona. Nada se borra: si la persona vuelve a empezar la
-- activación, o cambia de celular, la misma fila recibe la clave nueva.

create table public.user_totp (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  -- La clave, cifrada por la API con AES-256-GCM. En base64: los 12 bytes que
  -- hacen único cada cifrado, la clave cifrada y los 16 bytes que delatan
  -- cualquier cambio. La llave de cifrado no vive en la base: está en una
  -- variable de entorno de la API.
  secret_ciphertext text not null,
  -- Con qué versión de la llave se cifró, para poder cambiar la llave sin
  -- perder las claves ya guardadas.
  key_version smallint not null default 1,
  -- Fecha en que la persona comprobó la clave con un código de su aplicación.
  -- Vacía mientras la activación está pendiente.
  confirmed_at timestamptz,
  -- El último periodo de 30 segundos cuyo código se aceptó, contado desde 1970.
  -- Un código de ese periodo o de uno anterior ya no se acepta.
  last_used_step bigint,
  -- Códigos incorrectos seguidos. Un código correcto la regresa a cero.
  failed_attempts integer not null default 0,
  -- Hasta cuándo espera la persona por haber fallado demasiadas veces. Vacía
  -- si no está esperando.
  locked_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint user_totp_user_unique unique (user_id),
  -- Base64 de al menos 48 bytes (12 + una clave de 20 bytes o más + 16).
  constraint user_totp_ciphertext_format check (
    secret_ciphertext ~ '^[A-Za-z0-9+/]+={0,2}$'
    and char_length(secret_ciphertext) between 64 and 256
  ),
  constraint user_totp_key_version_positive check (key_version >= 1),
  constraint user_totp_last_used_step_not_negative check (last_used_step >= 0),
  constraint user_totp_failed_attempts_not_negative check (failed_attempts >= 0),
  -- La clave se comprueba con un código, así que una clave activa siempre tiene
  -- anotado el periodo de ese código.
  constraint user_totp_confirmed_has_step check (confirmed_at is null or last_used_step is not null)
);

create trigger user_totp_set_updated_at
  before update on public.user_totp
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Permisos
-- ---------------------------------------------------------------------------
-- Nadie tiene permiso por defecto, igual que en las tablas anteriores.

alter table public.user_totp enable row level security;

revoke all on table public.user_totp from public;

-- El sistema lee, crea y cambia. No borra: nada se borra en automático.
grant select, insert, update on table public.user_totp to integro_service;

create policy user_totp_service_all on public.user_totp
  for all to integro_service using (true) with check (true);

-- integro_app no tiene ningún permiso: la persona no lee ni su propia fila.
-- Si su Authenticator está activo se lo dice la API, que lo lee como el sistema.
