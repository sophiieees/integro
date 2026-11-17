-- Imitación mínima de Supabase para probar las migraciones sin tocar el
-- proyecto real. Solo se usa en las pruebas; nunca se corre en Supabase.
-- Reproduce lo que Supabase ya trae: los tres roles, el esquema auth con su
-- tabla de cuentas, la función auth.uid() y el permiso amplio que Supabase
-- da por defecto a las tablas nuevas de public (por eso la migración lo quita).

create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;

create schema auth;

create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  raw_user_meta_data jsonb
);

-- En Supabase el id de la sesión llega en el token; aquí se simula con un
-- ajuste de la conexión.
create function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

grant usage on schema public to anon, authenticated, service_role;
grant usage on schema auth to anon, authenticated, service_role;

alter default privileges in schema public
  grant all on tables to anon, authenticated, service_role;
