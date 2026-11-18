-- Íntegro, base de datos, grupo 1: acceso a la cuenta.
-- sessions, password_resets, one_time_codes y users.email_verified_at.
--
-- PostgreSQL puro, igual que las migraciones anteriores.
--
-- Decisiones del 17 de noviembre de 2026 que implementa esta migración:
--   1. La sesión se guarda en la base (tabla sessions), no en un pase firmado
--      (JWT). Cerrar sesión la revoca y la llave deja de servir en ese instante.
--   2. De cada sesión se guarda desde dónde se abrió: dirección IP, navegador
--      y último uso. Son datos personales; van en el aviso de privacidad.
--   3. Los códigos de un solo uso (iniciar sesión, comprobar el correo,
--      comprobar un teléfono) van en su propia tabla, one_time_codes. La
--      recuperación de contraseña sigue en password_resets, como se diseñó.
--   4. La base sabe si la persona comprobó su correo: users.email_verified_at.
--   5. Nunca se guarda una llave ni un código: se guarda su huella, igual que
--      con las contraseñas (data-model.md, decisión 6).
--   6. La persona lee sus propias sesiones, sin la huella. Todo lo demás de
--      estas tablas lo lee y lo escribe solo el sistema.
--
-- La huella es un SHA-256 escrito en hexadecimal: 64 caracteres. La calcula
-- la API; aquí solo se acepta un valor con ese formato.

-- ---------------------------------------------------------------------------
-- users: fecha en que la persona comprobó su correo
-- ---------------------------------------------------------------------------
-- Vacía hasta que la persona escriba el código que se le envió. La escribe
-- solo el sistema: no está en la lista de columnas que integro_app puede
-- cambiar. La persona sí puede leerla, como el resto de su fila.

alter table public.users add column email_verified_at timestamptz;

-- ---------------------------------------------------------------------------
-- sessions: cada inicio de sesión de una persona
-- ---------------------------------------------------------------------------
-- Una persona puede tener varias sesiones abiertas (celular y computadora).
-- Una sesión sirve mientras no haya vencido y revoked_at siga vacía.

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  -- Huella de la llave que recibe la persona. La llave nunca se guarda.
  token_hash text not null,
  expires_at timestamptz not null,
  -- Fecha en que se cerró la sesión. Vacía mientras está abierta.
  revoked_at timestamptz,
  last_used_at timestamptz not null default now(),
  -- Desde dónde se abrió. Pueden quedar vacías si no se conocen.
  ip_address inet,
  user_agent text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint sessions_token_hash_unique unique (token_hash),
  constraint sessions_token_hash_sha256 check (token_hash ~ '^[0-9a-f]{64}$'),
  constraint sessions_expires_after_created check (expires_at > created_at),
  constraint sessions_revoked_after_created check (revoked_at >= created_at),
  constraint sessions_last_used_after_created check (last_used_at >= created_at),
  constraint sessions_user_agent_length check (char_length(user_agent) <= 500)
);

create index sessions_user_id_idx on public.sessions (user_id);

create trigger sessions_set_updated_at
  before update on public.sessions
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- password_resets: cada vez que una persona pide recuperar su contraseña
-- ---------------------------------------------------------------------------
-- Sirve una sola vez: al usarla se anota la fecha en used_at.

create table public.password_resets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  -- Huella de la llave que va en el enlace de recuperación.
  token_hash text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint password_resets_token_hash_unique unique (token_hash),
  constraint password_resets_token_hash_sha256 check (token_hash ~ '^[0-9a-f]{64}$'),
  constraint password_resets_expires_after_created check (expires_at > created_at),
  constraint password_resets_used_after_created check (used_at >= created_at)
);

create index password_resets_user_id_idx on public.password_resets (user_id);

create trigger password_resets_set_updated_at
  before update on public.password_resets
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- one_time_codes: códigos cortos de un solo uso
-- ---------------------------------------------------------------------------
-- Para qué sirve cada código (purpose) y por dónde salió (channel):
--   login         iniciar sesión          email, sms o whatsapp
--   verify_email  comprobar el correo     email
--   verify_phone  comprobar un teléfono   sms o whatsapp
-- destination guarda a qué correo o teléfono se envió, porque una persona
-- puede tener varios teléfonos.

create table public.one_time_codes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  purpose text not null,
  channel text not null,
  destination text not null,
  -- Huella del código. El código nunca se guarda.
  code_hash text not null,
  expires_at timestamptz not null,
  -- Intentos fallidos. El máximo permitido lo decide la API.
  attempts integer not null default 0,
  used_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint one_time_codes_purpose_valid check (purpose in ('login', 'verify_email', 'verify_phone')),
  constraint one_time_codes_channel_valid check (channel in ('email', 'sms', 'whatsapp')),
  -- El correo se comprueba por correo y el teléfono por SMS o WhatsApp.
  constraint one_time_codes_channel_matches_purpose check (
    (purpose <> 'verify_email' or channel = 'email')
    and (purpose <> 'verify_phone' or channel in ('sms', 'whatsapp'))
  ),
  -- Por correo, el destino es un correo en minúsculas; por SMS o WhatsApp,
  -- un teléfono en formato internacional E.164. Mismas reglas que users.email
  -- y user_phones.phone.
  constraint one_time_codes_destination_matches_channel check (
    (channel = 'email'
      and char_length(destination) <= 254
      and destination = lower(destination)
      and destination ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')
    or (channel in ('sms', 'whatsapp') and destination ~ '^\+[1-9][0-9]{7,14}$')
  ),
  constraint one_time_codes_code_hash_sha256 check (code_hash ~ '^[0-9a-f]{64}$'),
  constraint one_time_codes_expires_after_created check (expires_at > created_at),
  constraint one_time_codes_attempts_not_negative check (attempts >= 0),
  constraint one_time_codes_used_after_created check (used_at >= created_at)
);

create index one_time_codes_user_purpose_idx on public.one_time_codes (user_id, purpose);

create trigger one_time_codes_set_updated_at
  before update on public.one_time_codes
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Permisos
-- ---------------------------------------------------------------------------
-- Nadie tiene permiso por defecto, igual que en las tablas anteriores.

alter table public.sessions enable row level security;
alter table public.password_resets enable row level security;
alter table public.one_time_codes enable row level security;

revoke all on table public.sessions from public;
revoke all on table public.password_resets from public;
revoke all on table public.one_time_codes from public;

-- El sistema: lee y escribe las tres tablas, pero no borra. Una sesión se
-- cierra con revoked_at; un código o una recuperación se gastan con used_at.
grant select, insert, update on table public.sessions to integro_service;
grant select, insert, update on table public.password_resets to integro_service;
grant select, insert, update on table public.one_time_codes to integro_service;

create policy sessions_service_all on public.sessions
  for all to integro_service using (true) with check (true);
create policy password_resets_service_all on public.password_resets
  for all to integro_service using (true) with check (true);
create policy one_time_codes_service_all on public.one_time_codes
  for all to integro_service using (true) with check (true);

-- sessions: la persona lee sus propias sesiones, para ver dónde tiene sesión
-- iniciada. token_hash no está en la lista: no puede leer la huella. No puede
-- crear, cambiar ni borrar; cerrar una sesión lo hace el sistema.
grant select (id, user_id, expires_at, revoked_at, last_used_at, ip_address, user_agent, created_at)
  on table public.sessions to integro_app;

create policy sessions_select_own on public.sessions
  for select to integro_app
  using (user_id = (select public.current_user_id()));

-- password_resets y one_time_codes: integro_app no tiene ningún permiso.
