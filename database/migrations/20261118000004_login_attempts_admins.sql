-- Íntegro, base de datos, grupo 1: intentos de inicio de sesión y administradores.
-- login_attempts y admins.
--
-- PostgreSQL puro, igual que las migraciones anteriores.
--
-- Decisiones del 18 de noviembre de 2026 que implementa esta migración:
--   1. La cuenta nunca se bloquea por contraseñas incorrectas. A los 3 fallos
--      se avisa al dueño y a los 6 quien está intentando espera 15 minutos,
--      por dispositivo y dirección (ADR 0014). Para contar hay que guardar
--      cada intento: eso es login_attempts.
--   2. Los administradores se dan de alta solo a mano, por el dueño de la
--      base. La API nunca puede crear ni quitar administradores, ni siquiera
--      actuando como el sistema: si alguien toma el control de la API no puede
--      hacerse administrador.

-- ---------------------------------------------------------------------------
-- login_attempts: cada vez que alguien escribe un correo y una contraseña
-- ---------------------------------------------------------------------------
-- Se anotan los fallidos y los correctos, para contar los fallos seguidos:
-- un intento correcto reinicia la cuenta. Solo se agregan filas; nunca se
-- cambian ni se borran.
-- La dirección IP y el navegador son datos personales, igual que en sessions:
-- van en el aviso de privacidad.

create table public.login_attempts (
  id uuid primary key default gen_random_uuid(),
  -- El correo que se escribió, en minúsculas. Vacío si lo escrito no tenía
  -- forma de correo: el intento se anota de todos modos, por quien lo hizo.
  email text,
  -- La persona dueña de ese correo, si existe. Vacío si el correo no tiene cuenta.
  user_id uuid references public.users (id),
  succeeded boolean not null,
  -- Quién está intentando: desde qué dirección y con qué navegador.
  ip_address inet,
  user_agent text,
  created_at timestamptz not null default now(),

  constraint login_attempts_email_format check (
    char_length(email) <= 254
    and email = lower(email)
    and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
  ),
  constraint login_attempts_user_agent_length check (char_length(user_agent) <= 500),
  -- Un intento correcto siempre es de una persona que existe.
  constraint login_attempts_success_has_user check (not succeeded or user_id is not null)
);

-- Para contar los intentos recientes de una cuenta y los de quien intenta.
create index login_attempts_user_created_idx on public.login_attempts (user_id, created_at desc);
create index login_attempts_ip_created_idx on public.login_attempts (ip_address, created_at desc);

-- ---------------------------------------------------------------------------
-- admins: las personas que administran la plataforma
-- ---------------------------------------------------------------------------
-- Una fila por persona administradora. La persona sigue siendo una fila de
-- users, con su correo y su contraseña: aquí solo se anota que administra.

create table public.admins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint admins_user_unique unique (user_id)
);

create trigger admins_set_updated_at
  before update on public.admins
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Permisos
-- ---------------------------------------------------------------------------
-- Nadie tiene permiso por defecto, igual que en las tablas anteriores.

alter table public.login_attempts enable row level security;
alter table public.admins enable row level security;

revoke all on table public.login_attempts from public;
revoke all on table public.admins from public;

-- login_attempts: el sistema lee y agrega. No cambia ni borra: es un registro.
-- integro_app no tiene ningún permiso.
grant select, insert on table public.login_attempts to integro_service;

create policy login_attempts_service_select on public.login_attempts
  for select to integro_service using (true);
create policy login_attempts_service_insert on public.login_attempts
  for insert to integro_service with check (true);

-- admins: el sistema solo lee, para saber quién administra. No hay permiso de
-- crear, cambiar ni borrar para ningún papel de la API: las altas y las bajas
-- las hace el dueño de la base, a mano.
grant select on table public.admins to integro_service;

create policy admins_service_select on public.admins
  for select to integro_service using (true);

-- La persona puede saber si ella misma es administradora. No ve a las demás.
grant select on table public.admins to integro_app;

create policy admins_select_own on public.admins
  for select to integro_app
  using (user_id = (select public.current_user_id()));
