-- Íntegro, base de datos, grupo 1: users, host_profiles, verifications.
--
-- Decisiones que implementa esta migración:
--   1. Nombres de tablas, columnas y valores en inglés. Comentarios en español.
--   2. La llave de una persona es un id generado (UUID), el mismo que le asigna
--      Supabase Auth. No se guarda CURP ni número de identificación.
--   3. El correo y la contraseña viven solo en Supabase Auth (auth.users).
--      Aquí no se repiten.
--   4. Todos los datos del registro son obligatorios: nombre, apellido,
--      teléfono, país y fecha de nacimiento. Sin ellos la cuenta no se crea.
--   5. Hay huéspedes extranjeros: teléfono en formato internacional y país
--      con el código de dos letras (MX, US, ES).
--   6. La plataforma funciona en español e inglés: cada persona guarda su idioma.
--   7. Una persona puede ser huésped y anfitrión: una sola tabla de personas
--      y un perfil de anfitrión aparte.
--   8. De una verificación se guarda el resultado, la fecha y la referencia
--      del proveedor. Nunca el documento.
--   9. Cada persona lee solo sus propios datos. Lo que decide el sistema
--      (estado de identidad, nivel del anfitrión, resultados de verificación)
--      no lo puede escribir el navegador: solo el servidor.

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
  -- Mismo id que auth.users. Sin "on delete cascade": una cuenta con datos
  -- no se borra sola al borrar su acceso.
  id uuid primary key references auth.users (id),
  first_name text not null,
  last_name text not null,
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
-- Alta de la persona al registrarse
-- ---------------------------------------------------------------------------
-- Cuando Supabase Auth crea una cuenta, esta función crea su fila en users
-- con los datos que mandó el formulario de registro. Si falta un dato o no
-- cumple el formato, la fila no se crea y el registro completo se cancela:
-- no puede existir una cuenta sin sus datos.

create function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.users (id, first_name, last_name, phone, country, birth_date, preferred_language)
  values (
    new.id,
    new.raw_user_meta_data ->> 'first_name',
    new.raw_user_meta_data ->> 'last_name',
    new.raw_user_meta_data ->> 'phone',
    new.raw_user_meta_data ->> 'country',
    (new.raw_user_meta_data ->> 'birth_date')::date,
    coalesce(new.raw_user_meta_data ->> 'preferred_language', 'es')
  );
  return new;
end;
$$;

revoke execute on function public.handle_new_auth_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

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
-- anon: visitante sin sesión. authenticated: persona con sesión iniciada.
-- service_role: el servidor de Íntegro (su llave nunca llega al navegador).

alter table public.users enable row level security;
alter table public.host_profiles enable row level security;
alter table public.verifications enable row level security;

revoke all on table public.users from anon, authenticated;
revoke all on table public.host_profiles from anon, authenticated;
revoke all on table public.verifications from anon, authenticated;

grant all on table public.users to service_role;
grant all on table public.host_profiles to service_role;
grant all on table public.verifications to service_role;

-- users: cada persona lee su fila y corrige sus datos de registro.
-- identity_status no está en la lista: no lo puede cambiar.
grant select on table public.users to authenticated;
grant update (first_name, last_name, phone, country, birth_date, preferred_language)
  on table public.users to authenticated;

create policy users_select_own on public.users
  for select to authenticated
  using (id = (select auth.uid()));

create policy users_update_own on public.users
  for update to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

-- host_profiles: el anfitrión lee su perfil. Lo escribe solo el servidor.
grant select on table public.host_profiles to authenticated;

create policy host_profiles_select_own on public.host_profiles
  for select to authenticated
  using (user_id = (select auth.uid()));

-- verifications: la persona lee sus resultados. Los escribe solo el servidor.
grant select on table public.verifications to authenticated;

create policy verifications_select_own on public.verifications
  for select to authenticated
  using (user_id = (select auth.uid()));
