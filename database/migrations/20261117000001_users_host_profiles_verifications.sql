-- Íntegro, base de datos, grupo 1: users, user_credentials, host_profiles,
-- verifications.
--
-- PostgreSQL puro: corre igual en una computadora y en cualquier nube con
-- PostgreSQL. No depende de ningún servicio externo de autenticación.
--
-- Decisiones que implementa esta migración:
--   1. Nombres de tablas, columnas y valores en inglés. Comentarios en español.
--   2. La llave de una persona es un id generado (UUID). No se guarda CURP ni
--      número de identificación.
--   3. La autenticación es propia: el correo vive en users y la contraseña,
--      ya convertida con Argon2id por la API, en user_credentials. La base
--      nunca recibe la contraseña escrita por la persona.
--   4. Todos los datos del registro son obligatorios: nombre, apellido, correo,
--      teléfono, país y fecha de nacimiento.
--   5. Hay huéspedes extranjeros: teléfono en formato internacional y país
--      con el código de dos letras (MX, US, ES).
--   6. La plataforma funciona en español e inglés: cada persona guarda su idioma.
--   7. Una persona puede ser huésped y anfitrión: una sola tabla de personas
--      y un perfil de anfitrión aparte.
--   8. De una verificación se guarda el resultado, la fecha y la referencia
--      del proveedor. Nunca el documento.
--   9. Cada persona lee solo sus propios datos. Lo que decide el sistema
--      (correo, contraseña, estado de identidad, nivel del anfitrión,
--      resultados de verificación) solo lo escribe el servidor.

-- ---------------------------------------------------------------------------
-- Papeles de la base de datos
-- ---------------------------------------------------------------------------
-- integro_app: la API cuando atiende a una persona con sesión iniciada.
--   Solo ve y cambia lo que le pertenece a esa persona.
-- integro_service: la API cuando actúa como el sistema (registro, avisos del
--   proveedor de verificación o de pagos).
-- Ninguno puede iniciar sesión ni tiene contraseña aquí: el usuario de
-- conexión se crea aparte, fuera del repositorio, y se le asignan estos papeles.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'integro_app') then
    create role integro_app nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'integro_service') then
    create role integro_service nologin;
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- Quién es la persona de la petición
-- ---------------------------------------------------------------------------
-- La API valida la sesión y, al abrir cada transacción, anota el id de la
-- persona en el ajuste app.user_id. Las reglas de permisos leen ese id de aquí.
-- Si no hay persona identificada devuelve vacío y no se ve ninguna fila.

create function public.current_user_id()
returns uuid
language sql
stable
set search_path = ''
as $$
  select nullif(current_setting('app.user_id', true), '')::uuid
$$;

-- ---------------------------------------------------------------------------
-- Fecha de actualización automática
-- ---------------------------------------------------------------------------

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- users: toda persona con cuenta, sea huésped, anfitrión o las dos cosas
-- ---------------------------------------------------------------------------

create table public.users (
  id uuid primary key default gen_random_uuid(),
  first_name text not null,
  last_name text not null,
  -- Siempre en minúsculas, para que Ana@correo.com y ana@correo.com sean la
  -- misma cuenta. Lo cambia solo el servidor.
  email text not null,
  -- Formato internacional E.164: signo de más, código de país y número.
  phone text not null,
  -- País de residencia, ISO 3166-1 de dos letras en mayúsculas.
  country text not null,
  -- Se guarda la fecha, no la edad: la edad cambia cada año.
  birth_date date not null,
  preferred_language text not null default 'es',
  -- Lo cambia solo el servidor cuando el proveedor de identidad responde.
  identity_status text not null default 'unverified',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint users_first_name_length check (char_length(btrim(first_name)) between 1 and 80),
  constraint users_last_name_length check (char_length(btrim(last_name)) between 1 and 80),
  constraint users_email_unique unique (email),
  constraint users_email_lowercase check (email = lower(email)),
  constraint users_email_format check (char_length(email) <= 254 and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
  constraint users_phone_unique unique (phone),
  constraint users_phone_e164 check (phone ~ '^\+[1-9][0-9]{7,14}$'),
  constraint users_country_iso2 check (country ~ '^[A-Z]{2}$'),
  constraint users_birth_date_range check (birth_date >= date '1900-01-01' and birth_date <= current_date),
  constraint users_preferred_language_valid check (preferred_language in ('es', 'en')),
  constraint users_identity_status_valid check (identity_status in ('unverified', 'pending', 'verified', 'rejected'))
);

create trigger users_set_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- user_credentials: la contraseña de cada persona, ya convertida
-- ---------------------------------------------------------------------------
-- Va en su propia tabla para que nunca viaje junto con los datos del perfil.
-- La API convierte la contraseña con Argon2id antes de guardarla; aquí solo
-- se acepta un valor con ese formato.

create table public.user_credentials (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  password_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint user_credentials_user_unique unique (user_id),
  constraint user_credentials_hash_argon2id check (password_hash like '$argon2id$%')
);

create trigger user_credentials_set_updated_at
  before update on public.user_credentials
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- host_profiles: lo que solo tiene quien es anfitrión
-- ---------------------------------------------------------------------------

create table public.host_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  level text not null default 'new',
  -- Cuenta conectada de Stripe donde el anfitrión recibe su dinero.
  stripe_account_id text,
  -- Solo los últimos cuatro dígitos de la CLABE, para mostrarlos. La CLABE
  -- completa la guarda el procesador de pagos.
  clabe_last4 text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint host_profiles_user_unique unique (user_id),
  constraint host_profiles_level_valid check (level in ('new', 'verified', 'suspended')),
  constraint host_profiles_stripe_account_unique unique (stripe_account_id),
  constraint host_profiles_stripe_account_format check (stripe_account_id ~ '^acct_[A-Za-z0-9]+$'),
  constraint host_profiles_clabe_last4_format check (clabe_last4 ~ '^[0-9]{4}$')
);

create trigger host_profiles_set_updated_at
  before update on public.host_profiles
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- verifications: resultado de cada verificación de una persona
-- ---------------------------------------------------------------------------
-- La verificación de propiedades se agrega en el grupo 2, cuando exista la
-- tabla properties.

create table public.verifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  -- identity: documento y rostro. bank_account: CLABE a su nombre.
  -- card: tarjeta a su nombre.
  kind text not null,
  provider text not null,
  -- Identificador de la verificación en el sistema del proveedor.
  provider_reference text not null,
  result text not null default 'pending',
  -- Fecha en que el proveedor respondió. Vacía mientras está pendiente.
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint verifications_kind_valid check (kind in ('identity', 'bank_account', 'card')),
  constraint verifications_provider_not_blank check (char_length(btrim(provider)) between 1 and 40),
  constraint verifications_reference_not_blank check (char_length(btrim(provider_reference)) between 1 and 200),
  -- El mismo aviso del proveedor no se registra dos veces.
  constraint verifications_provider_reference_unique unique (provider, provider_reference),
  constraint verifications_result_valid check (result in ('pending', 'approved', 'rejected')),
  -- Pendiente no tiene fecha de respuesta; aprobada o rechazada sí.
  constraint verifications_resolved_matches_result check ((result = 'pending') = (resolved_at is null))
);

create index verifications_user_id_idx on public.verifications (user_id);

create trigger verifications_set_updated_at
  before update on public.verifications
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Permisos: quién puede leer y escribir cada tabla
-- ---------------------------------------------------------------------------
-- Nadie tiene permiso por defecto. Con la seguridad por fila encendida, cada
-- papel solo alcanza las filas que su regla le permite.

alter table public.users enable row level security;
alter table public.user_credentials enable row level security;
alter table public.host_profiles enable row level security;
alter table public.verifications enable row level security;

revoke all on table public.users from public;
revoke all on table public.user_credentials from public;
revoke all on table public.host_profiles from public;
revoke all on table public.verifications from public;

-- El sistema: lee y escribe todo, pero no borra (nada se borra en automático).
grant select, insert, update on table public.users to integro_service;
grant select, insert, update on table public.user_credentials to integro_service;
grant select, insert, update on table public.host_profiles to integro_service;
grant select, insert, update on table public.verifications to integro_service;

create policy users_service_all on public.users
  for all to integro_service using (true) with check (true);
create policy user_credentials_service_all on public.user_credentials
  for all to integro_service using (true) with check (true);
create policy host_profiles_service_all on public.host_profiles
  for all to integro_service using (true) with check (true);
create policy verifications_service_all on public.verifications
  for all to integro_service using (true) with check (true);

-- users: cada persona lee su fila y corrige sus datos de registro.
-- email e identity_status no están en la lista: no los puede cambiar.
grant select on table public.users to integro_app;
grant update (first_name, last_name, phone, country, birth_date, preferred_language)
  on table public.users to integro_app;

create policy users_select_own on public.users
  for select to integro_app
  using (id = (select public.current_user_id()));

create policy users_update_own on public.users
  for update to integro_app
  using (id = (select public.current_user_id()))
  with check (id = (select public.current_user_id()));

-- user_credentials: integro_app no tiene ningún permiso. La contraseña solo
-- la toca el sistema.

-- host_profiles: el anfitrión lee su perfil. Lo escribe solo el sistema.
grant select on table public.host_profiles to integro_app;

create policy host_profiles_select_own on public.host_profiles
  for select to integro_app
  using (user_id = (select public.current_user_id()));

-- verifications: la persona lee sus resultados. Los escribe solo el sistema.
grant select on table public.verifications to integro_app;

create policy verifications_select_own on public.verifications
  for select to integro_app
  using (user_id = (select public.current_user_id()));
