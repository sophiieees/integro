-- Íntegro, base de datos, grupo 1: código para recuperar la contraseña.
-- Cambia one_time_codes.
--
-- PostgreSQL puro, igual que las migraciones anteriores.
--
-- Decisión de Sophia del 21 de noviembre de 2026 que implementa esta migración:
--   Recuperar la contraseña se hace con un código de 6 dígitos que llega al
--   correo, no con un enlace. one_time_codes ya guarda huellas de códigos de un
--   solo uso, con intentos y vencimiento; solo le falta admitir un uso más:
--
--     password_reset  recuperar la contraseña  email
--
--   La tabla password_resets no sirve para esto: pide una huella única por
--   fila, y con un código de 6 dígitos (un millón de combinaciones) se
--   repetiría entre personas. password_resets se queda sin usar, como lo
--   anticipa la decisión 17 de docs/database/data-model.md.
--
-- Esta migración la corre el dueño de la base (en pgAdmin, con el Query Tool).
-- No cambia ningún dato: solo cambia dos reglas de la tabla.

begin;

alter table public.one_time_codes drop constraint one_time_codes_purpose_valid;
alter table public.one_time_codes add constraint one_time_codes_purpose_valid
  check (purpose in ('login', 'verify_email', 'verify_phone', 'password_reset'));

-- El código de recuperar la contraseña, igual que el del correo, solo va por correo.
alter table public.one_time_codes drop constraint one_time_codes_channel_matches_purpose;
alter table public.one_time_codes add constraint one_time_codes_channel_matches_purpose
  check (
    (purpose <> 'verify_email' or channel = 'email')
    and (purpose <> 'password_reset' or channel = 'email')
    and (purpose <> 'verify_phone' or channel in ('sms', 'whatsapp'))
  );

commit;
