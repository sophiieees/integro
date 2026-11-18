-- Íntegro, base de datos, grupo 1: teléfono multivalor.
--
-- Decisión del 17 de noviembre de 2026: una persona puede registrar varios
-- teléfonos y un solo correo. Si pierde, cambia o le roban un teléfono,
-- conserva otro. El correo sigue en users porque con él inicia sesión.
--
-- Qué cambia:
--   1. Tabla nueva user_phones: un teléfono por fila.
--   2. La columna users.phone desaparece; los teléfonos que ya existan pasan
--      a user_phones como teléfono principal.
--   3. Toda persona tiene exactamente un teléfono principal. Se revisa al
--      cerrar la transacción, para que el registro pueda guardar primero a la
--      persona y enseguida su teléfono.
--   4. Un teléfono cuenta como comprobado solo cuando el sistema anota la
--      fecha en verified_at, después de que la persona escribió el código que
--      se le envió.

-- ---------------------------------------------------------------------------
-- user_phones: los teléfonos de cada persona
-- ---------------------------------------------------------------------------

create table public.user_phones (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  -- Formato internacional E.164: signo de más, código de país y número.
  phone text not null,
  is_primary boolean not null default false,
  -- Vacía mientras la persona no haya comprobado el teléfono con un código.
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Un teléfono no se repite en toda la plataforma.
  constraint user_phones_phone_unique unique (phone),
  constraint user_phones_phone_e164 check (phone ~ '^\+[1-9][0-9]{7,14}$')
);

-- A lo más un teléfono principal por persona.
create unique index user_phones_one_primary on public.user_phones (user_id) where is_primary;

create index user_phones_user_id_idx on public.user_phones (user_id);

create trigger user_phones_set_updated_at
  before update on public.user_phones
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- El teléfono sale de users
-- ---------------------------------------------------------------------------

insert into public.user_phones (user_id, phone, is_primary)
select id, phone, true from public.users;

alter table public.users drop column phone;

-- ---------------------------------------------------------------------------
-- Toda persona tiene un teléfono principal
-- ---------------------------------------------------------------------------
-- Con el índice de arriba no puede haber dos principales; esta regla impide
-- que no haya ninguno. Se revisa al final de la transacción.

create function public.require_primary_phone()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_user_id uuid;
begin
  if tg_table_name = 'users' then
    v_user_id := new.id;
  else
    v_user_id := old.user_id;
  end if;

  if exists (select 1 from public.users where id = v_user_id)
     and not exists (select 1 from public.user_phones where user_id = v_user_id and is_primary) then
    raise exception 'La persona % debe tener un teléfono principal', v_user_id
      using errcode = '23514', constraint = 'users_primary_phone_required';
  end if;
  return null;
end;
$$;

create constraint trigger users_primary_phone_required
  after insert on public.users
  deferrable initially deferred
  for each row execute function public.require_primary_phone();

create constraint trigger user_phones_primary_phone_required
  after update or delete on public.user_phones
  deferrable initially deferred
  for each row execute function public.require_primary_phone();

-- ---------------------------------------------------------------------------
-- Permisos
-- ---------------------------------------------------------------------------
-- La persona lee sus teléfonos. Los escribe solo el sistema, porque agregar,
-- comprobar o cambiar un teléfono exige antes verificar un código.
-- El sistema sí puede borrar un teléfono: es la baja que pide la persona
-- cuando lo pierde o lo cambia. La regla de arriba impide dejarla sin principal.

alter table public.user_phones enable row level security;

revoke all on table public.user_phones from public;

grant select, insert, update, delete on table public.user_phones to integro_service;

create policy user_phones_service_all on public.user_phones
  for all to integro_service using (true) with check (true);

grant select on table public.user_phones to integro_app;

create policy user_phones_select_own on public.user_phones
  for select to integro_app
  using (user_id = (select public.current_user_id()));
