/* Pruebas del grupo 1 de la base de datos: users, user_credentials,
  host_profiles, verifications.
  Corre la migración real sobre un PostgreSQL en memoria (PGlite) y comprueba
  cada regla: datos obligatorios, formatos, duplicados y permisos.
  No se conecta a ninguna base real. Cómo correrlas: tests/database/README.md.
   Cada caso imprime lo esperado, lo obtenido y COINCIDE o NO COINCIDE. */

const fs = require("fs");
const path = require("path");
const { PGlite } = require("@electric-sql/pglite");

const RAIZ = path.join(__dirname, "..", "..");
const MIGRACIONES = path.join(RAIZ, "database", "migrations");

// Papeles de la base de datos (los crea la migración).
const PERSONA = "integro_app"; // la API atendiendo a una persona con sesión
const SISTEMA = "integro_service"; // la API actuando como el sistema

// Personas de prueba (datos ficticios).
const ANA = "11111111-1111-4111-8111-111111111111"; // mexicana
const JOHN = "22222222-2222-4222-8222-222222222222"; // extranjero
const NADIE = "33333333-3333-4333-8333-333333333333"; // id que no existe
const DATOS_ANA = {
  id: ANA, first_name: "Ana", last_name: "Torres", email: "ana@example.com",
  phone: "+525512345678", country: "MX", birth_date: "1995-03-14"
};
const DATOS_JOHN = {
  id: JOHN, first_name: "John", last_name: "Miller", email: "john@example.com",
  phone: "+14155550123", country: "US", birth_date: "1988-11-02", preferred_language: "en"
};
// Contraseña ya convertida, con el formato que produce Argon2id (valor ficticio).
const HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsZGVwcnVlYmE$aGFzaGRlcHJ1ZWJh";

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

// Corre la instrucción con el papel indicado. Para PERSONA se anota antes el
// id de quien tiene la sesión, como hará la API; sin id es alguien sin sesión.
async function como(papel, id, sql, parametros) {
  await db.query("select set_config('app.user_id', $1, false)", [id || ""]);
  await db.exec(`set role ${papel}`);
  try {
    return await ejecutar(sql, parametros);
  } finally {
    await db.exec("reset role");
    await db.query("select set_config('app.user_id', '', false)");
  }
}

const sistema = (sql, parametros) => como(SISTEMA, null, sql, parametros);

// Simula el registro: el sistema guarda a la persona con los datos del formulario.
function registrar(datos) {
  const columnas = Object.keys(datos);
  const marcas = columnas.map((_, i) => `$${i + 1}`);
  return sistema(
    `insert into public.users (${columnas.join(", ")}) values (${marcas.join(", ")})`,
    columnas.map((c) => datos[c])
  );
}

// Lectura directa para comprobar un valor guardado (como dueño de la base).
async function valor(sql, parametros) {
  const r = await db.query(sql, parametros);
  return r.rows.length ? Object.values(r.rows[0]).join(", ") : "sin fila";
}

async function main() {
  db = new PGlite();
  for (const archivo of fs.readdirSync(MIGRACIONES).filter((a) => a.endsWith(".sql")).sort()) {
    await db.exec(fs.readFileSync(path.join(MIGRACIONES, archivo), "utf8"));
    console.log(`Migración aplicada: ${archivo}`);
  }
  console.log("");

  console.log("== Registro ==");
  comparar("Registro completo de una persona mexicana",
    "aceptado, 1 fila(s) afectada(s)", await registrar(DATOS_ANA));
  comparar("Su fila queda sin verificar y en español",
    "Ana, Torres, ana@example.com, +525512345678, MX, unverified, es",
    await valor("select first_name, last_name, email, phone, country, identity_status, preferred_language from public.users where id = $1", [ANA]));
  comparar("Registro completo de una persona extranjera, en inglés",
    "aceptado, 1 fila(s) afectada(s)", await registrar(DATOS_JOHN));
  comparar("Su fila queda con país US e idioma en",
    "US, en", await valor("select country, preferred_language from public.users where id = $1", [JOHN]));

  // Variante válida de Ana con otro correo y teléfono, a la que se le cambia un dato.
  const variante = (cambios) => {
    const datos = { ...DATOS_ANA, email: "otra@example.com", phone: "+525500000002", ...cambios };
    delete datos.id;
    return datos;
  };

  for (const campo of ["first_name", "last_name", "email", "phone", "country", "birth_date"]) {
    const datos = variante({});
    delete datos[campo];
    comparar(`Registro sin ${campo}`, `rechazado 23502 ${campo}`, await registrar(datos));
  }
  comparar("Nombre con puros espacios",
    "rechazado 23514 users_first_name_length", await registrar(variante({ first_name: "   " })));
  comparar("Correo con mayúsculas (Otra@Example.com)",
    "rechazado 23514 users_email_lowercase", await registrar(variante({ email: "Otra@Example.com" })));
  comparar("Correo sin arroba (otraexample.com)",
    "rechazado 23514 users_email_format", await registrar(variante({ email: "otraexample.com" })));
  comparar("Correo que ya usa otra persona",
    "rechazado 23505 users_email_unique", await registrar(variante({ email: DATOS_ANA.email })));
  comparar("Teléfono sin código de país (5512345678)",
    "rechazado 23514 users_phone_e164", await registrar(variante({ phone: "5512345678" })));
  comparar("Teléfono con espacios (+52 55 1234 5678)",
    "rechazado 23514 users_phone_e164", await registrar(variante({ phone: "+52 55 1234 5678" })));
  comparar("Teléfono que ya usa otra persona",
    "rechazado 23505 users_phone_unique", await registrar(variante({ phone: DATOS_ANA.phone })));
  comparar("País en minúsculas (mx)",
    "rechazado 23514 users_country_iso2", await registrar(variante({ country: "mx" })));
  comparar("País con tres letras (MEX)",
    "rechazado 23514 users_country_iso2", await registrar(variante({ country: "MEX" })));
  const manana = await valor("select (current_date + 1)::text");
  comparar("Fecha de nacimiento de mañana",
    "rechazado 23514 users_birth_date_range", await registrar(variante({ birth_date: manana })));
  comparar("Fecha de nacimiento anterior a 1900 (1899-12-31)",
    "rechazado 23514 users_birth_date_range", await registrar(variante({ birth_date: "1899-12-31" })));
  comparar("Fecha de nacimiento que no existe (2000-02-31)",
    "rechazado 22008", await registrar(variante({ birth_date: "2000-02-31" })));
  comparar("Idioma que la plataforma no maneja (fr)",
    "rechazado 23514 users_preferred_language_valid", await registrar(variante({ preferred_language: "fr" })));
  comparar("Después de los rechazos solo existen las dos personas válidas",
    "2", await valor("select count(*) from public.users"));

  console.log("");
  console.log("== Contraseñas (user_credentials) ==");
  comparar("El sistema guarda la contraseña de Ana ya convertida con Argon2id",
    "aceptado, 1 fila(s) afectada(s)", await sistema("insert into public.user_credentials (user_id, password_hash) values ($1, $2)", [ANA, HASH]));
  comparar("Contraseña tal como se escribió, sin convertir (MiClave123)",
    "rechazado 23514 user_credentials_hash_argon2id", await sistema("insert into public.user_credentials (user_id, password_hash) values ($1, 'MiClave123')", [JOHN]));
  comparar("Segunda contraseña para la misma persona",
    "rechazado 23505 user_credentials_user_unique", await sistema("insert into public.user_credentials (user_id, password_hash) values ($1, $2)", [ANA, HASH]));
  comparar("Contraseña para una persona que no existe",
    "rechazado 23503 user_credentials_user_id_fkey", await sistema("insert into public.user_credentials (user_id, password_hash) values ($1, $2)", [NADIE, HASH]));
  comparar("Ana, con sesión, intenta leer la tabla de contraseñas",
    "rechazado 42501", await como(PERSONA, ANA, "select password_hash from public.user_credentials"));
  comparar("Ana intenta cambiar su contraseña directo en la tabla",
    "rechazado 42501", await como(PERSONA, ANA, "update public.user_credentials set password_hash = $2 where user_id = $1", [ANA, HASH]));

  console.log("");
  console.log("== Permisos sobre users ==");
  comparar("Ana, con sesión, lee la tabla y solo ve su fila",
    "1 fila(s)", await como(PERSONA, ANA, "select id from public.users"));
  comparar("Ana busca la fila de John",
    "0 fila(s)", await como(PERSONA, ANA, "select id from public.users where id = $1", [JOHN]));
  comparar("Alguien sin sesión lee la tabla y no ve ninguna fila",
    "0 fila(s)", await como(PERSONA, null, "select id from public.users"));
  comparar("Ana corrige su nombre",
    "aceptado, 1 fila(s) afectada(s)", await como(PERSONA, ANA, "update public.users set first_name = 'Ana María' where id = $1", [ANA]));
  comparar("La fecha de actualización se movió sola",
    "true", await valor("select updated_at > created_at from public.users where id = $1", [ANA]));
  comparar("Ana intenta marcarse como verificada",
    "rechazado 42501", await como(PERSONA, ANA, "update public.users set identity_status = 'verified' where id = $1", [ANA]));
  comparar("Ana intenta cambiar su correo directo en la tabla",
    "rechazado 42501", await como(PERSONA, ANA, "update public.users set email = 'nueva@example.com' where id = $1", [ANA]));
  comparar("Ana intenta cambiar el nombre de John",
    "aceptado, 0 fila(s) afectada(s)", await como(PERSONA, ANA, "update public.users set first_name = 'X' where id = $1", [JOHN]));
  comparar("Ana intenta insertar una fila a mano",
    "rechazado 42501", await como(PERSONA, ANA, "insert into public.users (first_name, last_name, email, phone, country, birth_date) values ('A', 'B', 'ab@example.com', '+525500000003', 'MX', '1990-01-01')"));
  comparar("Ana intenta borrar su fila",
    "rechazado 42501", await como(PERSONA, ANA, "delete from public.users where id = $1", [ANA]));
  comparar("El sistema marca a Ana como verificada",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.users set identity_status = 'verified' where id = $1", [ANA]));
  comparar("El sistema intenta un estado que no existe (approved)",
    "rechazado 23514 users_identity_status_valid", await sistema("update public.users set identity_status = 'approved' where id = $1", [ANA]));
  comparar("El sistema intenta borrar a Ana: no tiene permiso de borrar",
    "rechazado 42501", await sistema("delete from public.users where id = $1", [ANA]));
  comparar("Ni el dueño de la base puede borrar a Ana mientras tenga datos ligados",
    "rechazado 23503 user_credentials_user_id_fkey", await ejecutar("delete from public.users where id = $1", [ANA]));

  console.log("");
  console.log("== host_profiles ==");
  comparar("El sistema crea el perfil de anfitrión de Ana",
    "aceptado, 1 fila(s) afectada(s)", await sistema("insert into public.host_profiles (user_id) values ($1)", [ANA]));
  comparar("El perfil nace en nivel new",
    "new", await valor("select level from public.host_profiles where user_id = $1", [ANA]));
  comparar("Segundo perfil para la misma persona",
    "rechazado 23505 host_profiles_user_unique", await sistema("insert into public.host_profiles (user_id) values ($1)", [ANA]));
  comparar("Perfil para una persona que no existe",
    "rechazado 23503 host_profiles_user_id_fkey", await sistema("insert into public.host_profiles (user_id) values ($1)", [NADIE]));
  comparar("Nivel que no existe (gold)",
    "rechazado 23514 host_profiles_level_valid", await sistema("update public.host_profiles set level = 'gold' where user_id = $1", [ANA]));
  comparar("Últimos dígitos de la CLABE con cinco cifras (12345)",
    "rechazado 23514 host_profiles_clabe_last4_format", await sistema("update public.host_profiles set clabe_last4 = '12345' where user_id = $1", [ANA]));
  comparar("Cuenta de Stripe con formato incorrecto (cuenta123)",
    "rechazado 23514 host_profiles_stripe_account_format", await sistema("update public.host_profiles set stripe_account_id = 'cuenta123' where user_id = $1", [ANA]));
  comparar("Cuenta de Stripe y CLABE con formato correcto",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.host_profiles set stripe_account_id = 'acct_1AbcPrueba', clabe_last4 = '1234' where user_id = $1", [ANA]));
  comparar("La misma cuenta de Stripe para otro anfitrión",
    "rechazado 23505 host_profiles_stripe_account_unique", await sistema("insert into public.host_profiles (user_id, stripe_account_id) values ($1, 'acct_1AbcPrueba')", [JOHN]));
  comparar("Ana lee su perfil de anfitrión",
    "1 fila(s)", await como(PERSONA, ANA, "select id from public.host_profiles"));
  comparar("John no ve el perfil de Ana",
    "0 fila(s)", await como(PERSONA, JOHN, "select id from public.host_profiles"));
  comparar("Ana intenta subirse el nivel",
    "rechazado 42501", await como(PERSONA, ANA, "update public.host_profiles set level = 'verified' where user_id = $1", [ANA]));
  comparar("John intenta crearse un perfil de anfitrión a mano",
    "rechazado 42501", await como(PERSONA, JOHN, "insert into public.host_profiles (user_id) values ($1)", [JOHN]));
  comparar("Alguien sin sesión lee los perfiles y no ve ninguno",
    "0 fila(s)", await como(PERSONA, null, "select id from public.host_profiles"));

  console.log("");
  console.log("== verifications ==");
  comparar("El sistema registra una verificación de identidad pendiente",
    "aceptado, 1 fila(s) afectada(s)", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'identity', 'didit', 'ref-001')", [ANA]));
  comparar("El mismo aviso del proveedor llega dos veces",
    "rechazado 23505 verifications_provider_reference_unique", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'identity', 'didit', 'ref-001')", [ANA]));
  comparar("Tipo de verificación que no existe (passport)",
    "rechazado 23514 verifications_kind_valid", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'passport', 'didit', 'ref-002')", [ANA]));
  comparar("Resultado que no existe (expired)",
    "rechazado 23514 verifications_result_valid", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-003', 'expired', now())", [ANA]));
  comparar("Pendiente pero con fecha de respuesta",
    "rechazado 23514 verifications_resolved_matches_result", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-004', 'pending', now())", [ANA]));
  comparar("Aprobada pero sin fecha de respuesta",
    "rechazado 23514 verifications_resolved_matches_result", await sistema("update public.verifications set result = 'approved' where provider_reference = 'ref-001'"));
  comparar("Aprobada con su fecha de respuesta",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.verifications set result = 'approved', resolved_at = now() where provider_reference = 'ref-001'"));
  comparar("Verificación para una persona que no existe",
    "rechazado 23503 verifications_user_id_fkey", await sistema("insert into public.verifications (user_id, kind, provider, provider_reference) values ($1, 'card', 'stripe', 'ref-005')", [NADIE]));
  comparar("El sistema intenta borrar una verificación: no tiene permiso de borrar",
    "rechazado 42501", await sistema("delete from public.verifications where provider_reference = 'ref-001'"));
  comparar("Ana lee sus verificaciones",
    "1 fila(s)", await como(PERSONA, ANA, "select id from public.verifications"));
  comparar("John no ve las verificaciones de Ana",
    "0 fila(s)", await como(PERSONA, JOHN, "select id from public.verifications"));
  comparar("John intenta registrarse una verificación aprobada",
    "rechazado 42501", await como(PERSONA, JOHN, "insert into public.verifications (user_id, kind, provider, provider_reference, result, resolved_at) values ($1, 'identity', 'didit', 'ref-006', 'approved', now())", [JOHN]));
  comparar("Ana intenta cambiar el resultado de su verificación",
    "rechazado 42501", await como(PERSONA, ANA, "update public.verifications set result = 'rejected' where user_id = $1", [ANA]));
  comparar("Alguien sin sesión lee las verificaciones y no ve ninguna",
    "0 fila(s)", await como(PERSONA, null, "select id from public.verifications"));

  console.log("");
  console.log(`Total: ${numero} casos, ${numero - fallas} coinciden, ${fallas} no coinciden.`);
  await db.close();
  process.exit(fallas === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("La prueba no pudo correr:", e.message);
  process.exit(2);
});
