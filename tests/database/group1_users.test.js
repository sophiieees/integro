/* Pruebas del grupo 1 de la base de datos: users, host_profiles, verifications.
   Corre la migración real sobre un PostgreSQL en memoria (PGlite) y comprueba
   cada regla: datos obligatorios, formatos, duplicados y permisos.
   No se conecta a Supabase. Cómo correrlas: tests/database/README.md.
   Cada caso imprime lo esperado, lo obtenido y COINCIDE o NO COINCIDE. */

const fs = require("fs");
const path = require("path");
const { PGlite } = require("@electric-sql/pglite");

const RAIZ = path.join(__dirname, "..", "..");
const MIGRACIONES = path.join(RAIZ, "supabase", "migrations");

// Personas de prueba (datos ficticios).
const ANA = "11111111-1111-4111-8111-111111111111"; // mexicana
const JOHN = "22222222-2222-4222-8222-222222222222"; // extranjero
const DATOS_ANA = {
  first_name: "Ana", last_name: "Torres", phone: "+525512345678",
  country: "MX", birth_date: "1995-03-14"
};
const DATOS_JOHN = {
  first_name: "John", last_name: "Miller", phone: "+14155550123",
  country: "US", birth_date: "1988-11-02", preferred_language: "en"
};

let db;
let numero = 0;
let fallas = 0;

function comparar(nombre, esperado, obtenido) {
  numero += 1;
  const coincide = esperado === obtenido;
  if (!coincide) fallas += 1;
  console.log(`Caso ${numero}. ${nombre}`);
  console.log(`  esperado: ${esperado}`);
  console.log(`  obtenido: ${obtenido}`);
  console.log(`  ${coincide ? "COINCIDE" : "NO COINCIDE"}`);
}

// Ejecuta una instrucción y describe qué pasó: filas leídas, filas afectadas
// o el rechazo con el código de PostgreSQL y la regla que lo causó.
async function ejecutar(sql, parametros) {
  try {
    const r = await db.query(sql, parametros);
    if (r.fields && r.fields.length > 0) return `${r.rows.length} fila(s)`;
    return `aceptado, ${r.affectedRows} fila(s) afectada(s)`;
  } catch (e) {
    return `rechazado ${e.code} ${e.constraint || e.column || ""}`.trim();
  }
}

// Corre la instrucción con el papel indicado: "anon" (visitante),
// "authenticated" (persona con sesión, con su id) o el servidor (por defecto).
async function como(rol, id, sql, parametros) {
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [id || ""]);
  await db.exec(`set role ${rol}`);
  try {
    return await ejecutar(sql, parametros);
  } finally {
    await db.exec("reset role");
    await db.query("select set_config('request.jwt.claim.sub', '', false)");
  }
}

// Simula el registro: Supabase Auth crea la cuenta con los datos del formulario.
// Si no se indica id, se genera uno, como hace Supabase.
function registrar(id, correo, datos) {
  return ejecutar(
    "insert into auth.users (id, email, raw_user_meta_data) values (coalesce($1::uuid, gen_random_uuid()), $2, $3)",
    [id || null, correo, JSON.stringify(datos)]
  );
}

async function valor(sql, parametros) {
  const r = await db.query(sql, parametros);
  return r.rows.length ? Object.values(r.rows[0]).join(", ") : "sin fila";
}

async function main() {
  db = new PGlite();
  await db.exec(fs.readFileSync(path.join(__dirname, "supabase_stub.sql"), "utf8"));
  for (const archivo of fs.readdirSync(MIGRACIONES).filter((a) => a.endsWith(".sql")).sort()) {
    await db.exec(fs.readFileSync(path.join(MIGRACIONES, archivo), "utf8"));
    console.log(`Migración aplicada: ${archivo}`);
  }
  console.log("");

  console.log("== Registro ==");
  comparar("Registro completo de una persona mexicana",
    "aceptado, 1 fila(s) afectada(s)", await registrar(ANA, "ana@example.com", DATOS_ANA));
  comparar("Su fila queda sin verificar y en español",
    "Ana, Torres, +525512345678, MX, unverified, es",
    await valor("select first_name, last_name, phone, country, identity_status, preferred_language from public.users where id = $1", [ANA]));
  comparar("Registro completo de una persona extranjera, en inglés",
    "aceptado, 1 fila(s) afectada(s)", await registrar(JOHN, "john@example.com", DATOS_JOHN));
  comparar("Su fila queda con país US e idioma en",
    "US, en", await valor("select country, preferred_language from public.users where id = $1", [JOHN]));

  for (const campo of ["first_name", "last_name", "phone", "country", "birth_date"]) {
    const datos = { ...DATOS_ANA, phone: "+525500000001" };
    delete datos[campo];
    comparar(`Registro sin ${campo}`,
      `rechazado 23502 ${campo}`, await registrar(undefined, `sin-${campo}@example.com`, datos));
  }
  comparar("Los cinco registros rechazados no dejaron cuenta creada",
    "0", await valor("select count(*) from auth.users where email like 'sin-%'"));

  const variante = (cambios) => ({ ...DATOS_ANA, phone: "+525500000002", ...cambios });
  comparar("Nombre con puros espacios",
    "rechazado 23514 users_first_name_length", await registrar(undefined, "v1@example.com", variante({ first_name: "   " })));
  comparar("Teléfono sin código de país (5512345678)",
    "rechazado 23514 users_phone_e164", await registrar(undefined, "v2@example.com", variante({ phone: "5512345678" })));
  comparar("Teléfono con espacios (+52 55 1234 5678)",
    "rechazado 23514 users_phone_e164", await registrar(undefined, "v3@example.com", variante({ phone: "+52 55 1234 5678" })));
  comparar("Teléfono que ya usa otra persona",
    "rechazado 23505 users_phone_unique", await registrar(undefined, "v4@example.com", variante({ phone: DATOS_ANA.phone })));
  comparar("País en minúsculas (mx)",
    "rechazado 23514 users_country_iso2", await registrar(undefined, "v5@example.com", variante({ country: "mx" })));
  comparar("País con tres letras (MEX)",
    "rechazado 23514 users_country_iso2", await registrar(undefined, "v6@example.com", variante({ country: "MEX" })));
  const manana = await valor("select (current_date + 1)::text");
  comparar("Fecha de nacimiento de mañana",
    "rechazado 23514 users_birth_date_range", await registrar(undefined, "v7@example.com", variante({ birth_date: manana })));
  comparar("Fecha de nacimiento anterior a 1900 (1899-12-31)",
    "rechazado 23514 users_birth_date_range", await registrar(undefined, "v8@example.com", variante({ birth_date: "1899-12-31" })));
  comparar("Fecha de nacimiento que no existe (2000-02-31)",
    "rechazado 22008", await registrar(undefined, "v9@example.com", variante({ birth_date: "2000-02-31" })));
  comparar("Idioma que la plataforma no maneja (fr)",
    "rechazado 23514 users_preferred_language_valid", await registrar(undefined, "v10@example.com", variante({ preferred_language: "fr" })));

  console.log("");
  console.log("== Permisos sobre users ==");
  comparar("Ana, con sesión, lee la tabla y solo ve su fila",
    "1 fila(s)", await como("authenticated", ANA, "select id from public.users"));
  comparar("Ana busca la fila de John",
    "0 fila(s)", await como("authenticated", ANA, "select id from public.users where id = $1", [JOHN]));
  comparar("Un visitante sin sesión lee la tabla",
    "rechazado 42501", await como("anon", null, "select id from public.users"));
  comparar("Ana corrige su nombre",
    "aceptado, 1 fila(s) afectada(s)", await como("authenticated", ANA, "update public.users set first_name = 'Ana María' where id = $1", [ANA]));
  comparar("La fecha de actualización se movió sola",
    "true", await valor("select updated_at > created_at from public.users where id = $1", [ANA]));
  comparar("Ana intenta marcarse como verificada",
    "rechazado 42501", await como("authenticated", ANA, "update public.users set identity_status = 'verified' where id = $1", [ANA]));
  comparar("Ana intenta cambiar el nombre de John",
    "aceptado, 0 fila(s) afectada(s)", await como("authenticated", ANA, "update public.users set first_name = 'X' where id = $1", [JOHN]));
  comparar("Ana intenta insertar una fila a mano",
    "rechazado 42501", await como("authenticated", ANA, "insert into public.users (id, first_name, last_name, phone, country, birth_date) values ($1, 'A', 'B', '+525500000003', 'MX', '1990-01-01')", [ANA]));
  comparar("Ana intenta borrar su fila",
    "rechazado 42501", await como("authenticated", ANA, "delete from public.users where id = $1", [ANA]));
  comparar("El servidor marca a Ana como verificada",
    "aceptado, 1 fila(s) afectada(s)", await ejecutar("update public.users set identity_status = 'verified' where id = $1", [ANA]));
  comparar("El servidor intenta un estado que no existe (approved)",
    "rechazado 23514 users_identity_status_valid", await ejecutar("update public.users set identity_status = 'approved' where id = $1", [ANA]));
  comparar("Borrar el acceso de Ana no borra sus datos: se rechaza",
    "rechazado 23503 users_id_fkey", await ejecutar("delete from auth.users where id = $1", [ANA]));

  console.log("");
  console.log("== host_profiles ==");
  comparar("El servidor crea el perfil de anfitrión de Ana",
    "aceptado, 1 fila(s) afectada(s)", await ejecutar("insert into public.host_profiles (user_id) values ($1)", [ANA]));
  comparar("El perfil nace en nivel new",
    "new", await valor("select level from public.host_profiles where user_id = $1", [ANA]));
  comparar("Segundo perfil para la misma persona",
    "rechazado 23505 host_profiles_user_unique", await ejecutar("insert into public.host_profiles (user_id) values ($1)", [ANA]));
  comparar("Perfil para una persona que no existe",
    "rechazado 23503 host_profiles_user_id_fkey", await ejecutar("insert into public.host_profiles (user_id) values ('33333333-3333-4333-8333-333333333333')"));
  comparar("Nivel que no existe (gold)",
    "rechazado 23514 host_profiles_level_valid", await ejecutar("update public.host_profiles set level = 'gold' where user_id = $1", [ANA]));
  comparar("Últimos dígitos de la CLABE con cinco cifras (12345)",
    "rechazado 23514 host_profiles_clabe_last4_format", await ejecutar("update public.host_profiles set clabe_last4 = '12345' where user_id = $1", [ANA]));
  comparar("Cuenta de Stripe con formato incorrecto (cuenta123)",
    "rechazado 23514 host_profiles_stripe_account_format", await ejecutar("update public.host_profiles set stripe_account_id = 'cuenta123' where user_id = $1", [ANA]));
  comparar("Cuenta de Stripe y CLABE con formato correcto",
    "aceptado, 1 fila(s) afectada(s)", await ejecutar("update public.host_profiles set stripe_account_id = 'acct_1AbcPrueba', clabe_last4 = '1234' where user_id = $1", [ANA]));
  comparar("La misma cuenta de Stripe para otro anfitrión",
    "rechazado 23505 host_profiles_stripe_account_unique", await ejecutar("insert into public.host_profiles (user_id, stripe_account_id) values ($1, 'acct_1AbcPrueba')", [JOHN]));
  comparar("Ana lee su perfil de anfitrión",
    "1 fila(s)", await como("authenticated", ANA, "select id from public.host_profiles"));
  comparar("John no ve el perfil de Ana",
    "0 fila(s)", await como("authenticated", JOHN, "select id from public.host_profiles"));
  comparar("Ana intenta subirse el nivel",
    "rechazado 42501", await como("authenticated", ANA, "update public.host_profiles set level = 'verified' where user_id = $1", [ANA]));
  comparar("John intenta crearse un perfil de anfitrión a mano",
    "rechazado 42501", await como("authenticated", JOHN, "insert into public.host_profiles (user_id) values ($1)", [JOHN]));
  comparar("Un visitante sin sesión lee los perfiles",
    "rechazado 42501", await como("anon", null, "select id from public.host_profiles"));

  console.log("");
  console.log("== verifications ==");
  comparar("El servidor registra una verificación de identidad pendiente",
    "aceptado, 1 fila(s) afectada(s)", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'identity', 'didit', 'ref-001')", [ANA]));
  comparar("El mismo aviso del proveedor llega dos veces",
    "rechazado 23505 verifications_provider_reference_unique", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'identity', 'didit', 'ref-001')", [ANA]));
  comparar("Tipo de verificación que no existe (passport)",
    "rechazado 23514 verifications_kind_valid", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'passport', 'didit', 'ref-002')", [ANA]));
  comparar("Resultado que no existe (expired)",
    "rechazado 23514 verifications_result_valid", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-003', 'expired', now())", [ANA]));
  comparar("Pendiente pero con fecha de respuesta",
    "rechazado 23514 verifications_resolved_matches_result", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-004', 'pending', now())", [ANA]));
  comparar("Aprobada pero sin fecha de respuesta",
    "rechazado 23514 verifications_resolved_matches_result", await ejecutar("update public.verifications set result = 'approved' where provider_reference = 'ref-001'"));
  comparar("Aprobada con su fecha de respuesta",
    "aceptado, 1 fila(s) afectada(s)", await ejecutar("update public.verifications set result = 'approved', resolved_at = now() where provider_reference = 'ref-001'"));
  comparar("Verificación para una persona que no existe",
    "rechazado 23503 verifications_user_id_fkey", await ejecutar("insert into public.verifications (user_id, kind, provider, provider_reference) values ('33333333-3333-4333-8333-333333333333', 'card', 'stripe', 'ref-005')"));
  comparar("Ana lee sus verificaciones",
    "1 fila(s)", await como("authenticated", ANA, "select id from public.verifications"));
  comparar("John no ve las verificaciones de Ana",
    "0 fila(s)", await como("authenticated", JOHN, "select id from public.verifications"));
  comparar("John intenta registrarse una verificación aprobada",
    "rechazado 42501", await como("authenticated", JOHN, "insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-006', 'approved', now())", [JOHN]));
  comparar("Ana intenta cambiar el resultado de su verificación",
    "rechazado 42501", await como("authenticated", ANA, "update public.verifications set result = 'rejected' where user_id = $1", [ANA]));
  comparar("Un visitante sin sesión lee las verificaciones",
    "rechazado 42501", await como("anon", null, "select id from public.verifications"));

  console.log("");
  console.log(`Total: ${numero} casos, ${numero - fallas} coinciden, ${fallas} no coinciden.`);
  await db.close();
  process.exit(fallas === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("La prueba no pudo correr:", e.message);
  process.exit(2);
});
