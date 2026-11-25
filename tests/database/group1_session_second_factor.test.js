/* Pruebas de la columna sessions.second_factor_at (grupo 1): cuándo pasó cada sesión el Authenticator.
  Migración: database/migrations/20261125000007_session_second_factor.sql

  Especificación aceptada por Sophia el 25 de noviembre de 2026 (pieza 3.3, parte de la base):
     1. Una sesión nueva nace sin esa fecha: todavía no pasa el Authenticator.
     2. El sistema anota la fecha cuando la sesión lo pasa, y la vuelve a anotar más adelante: aceptado.
     3. Una fecha anterior a la creación de la sesión: rechazado 23514.
     4. El sistema puede dejarla vacía otra vez: aceptado.
     5. La persona no lee esa columna, ni de sus propias sesiones, y no la cambia: rechazado 42501. Sigue leyendo las
        demás columnas de sus sesiones, como antes.
     6. Las reglas de antes de la tabla sessions siguen valiendo.

  Corre todas las migraciones sobre un PostgreSQL en memoria (PGlite). No se conecta a ninguna base real.
  Cómo correrlas: tests/database/README.md. Cada caso imprime lo esperado, lo obtenido y COINCIDE o NO COINCIDE. */

const fs = require("fs");
const path = require("path");
const { PGlite } = require("@electric-sql/pglite");

const RAIZ = path.join(__dirname, "..", "..");
const MIGRACIONES = path.join(RAIZ, "database", "migrations");

const PERSONA = "integro_app";
const SISTEMA = "integro_service";

const ANA = "11111111-1111-4111-8111-111111111111";
const JOHN = "22222222-2222-4222-8222-222222222222";
// Huellas de llaves de sesión con la forma de un SHA-256 (valores ficticios).
const HUELLA_ANA = "a".repeat(64);
const HUELLA_JOHN = "b".repeat(64);

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

async function ejecutar(sql, parametros) {
  try {
    const r = await db.query(sql, parametros);
    if (r.fields && r.fields.length > 0) return `${r.rows.length} fila(s)`;
    return `aceptado, ${r.affectedRows} fila(s) afectada(s)`;
  } catch (e) {
    return `rechazado ${e.code} ${e.constraint || e.column || ""}`.trim();
  }
}

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

async function valor(sql, parametros) {
  const r = await db.query(sql, parametros);
  return r.rows.length ? Object.values(r.rows[0]).join(", ") : "sin fila";
}

async function registrar(id, nombre, correo, telefono) {
  await db.exec("begin");
  await db.exec(`set local role ${SISTEMA}`);
  await db.query(
    "insert into public.users (id, first_name, last_name, email, country, birth_date) values ($1, $2, 'Prueba', $3, 'MX', '1995-03-14')",
    [id, nombre, correo]
  );
  await db.query("insert into public.user_phones (user_id, phone, is_primary) values ($1, $2, true)", [id, telefono]);
  await db.exec("commit");
}

const ABRIR = "insert into public.sessions (user_id, token_hash, expires_at) values ($1, $2, now() + interval '7 days')";

async function main() {
  db = new PGlite();
  for (const archivo of fs.readdirSync(MIGRACIONES).filter((a) => a.endsWith(".sql")).sort()) {
    await db.exec(fs.readFileSync(path.join(MIGRACIONES, archivo), "utf8"));
    console.log(`Migración aplicada: ${archivo}`);
  }
  await registrar(ANA, "Ana", "ana@example.com", "+525512345678");
  await registrar(JOHN, "John", "john@example.com", "+14155550123");
  console.log("");

  console.log("== 1. Una sesión nueva ==");
  comparar("El sistema abre una sesión de Ana",
    "aceptado, 1 fila(s) afectada(s)", await sistema(ABRIR, [ANA, HUELLA_ANA]));
  comparar("La sesión nace sin haber pasado el Authenticator",
    "true", await valor("select second_factor_at is null as sin_fecha from public.sessions where token_hash = $1", [HUELLA_ANA]));

  console.log("");
  console.log("== 2. La sesión pasa el Authenticator ==");
  comparar("El sistema anota que la sesión pasó el Authenticator",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.sessions set second_factor_at = now() where token_hash = $1", [HUELLA_ANA]));
  comparar("La fecha queda guardada",
    "true", await valor("select second_factor_at is not null as con_fecha from public.sessions where token_hash = $1", [HUELLA_ANA]));
  comparar("A los 30 días lo vuelve a pasar y la fecha se actualiza",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.sessions set second_factor_at = created_at + interval '30 days' where token_hash = $1", [HUELLA_ANA]));
  comparar("El sistema abre una sesión que ya lo pasó desde el principio",
    "aceptado, 1 fila(s) afectada(s)",
    await sistema("insert into public.sessions (user_id, token_hash, expires_at, second_factor_at) values ($1, $2, now() + interval '7 days', now())", [JOHN, HUELLA_JOHN]));

  console.log("");
  console.log("== 3. La fecha no puede ser anterior a la sesión ==");
  comparar("Una fecha un segundo antes de que la sesión existiera",
    "rechazado 23514 sessions_second_factor_after_created",
    await sistema("update public.sessions set second_factor_at = created_at - interval '1 second' where token_hash = $1", [HUELLA_ANA]));
  comparar("La misma fecha en que se creó la sesión",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.sessions set second_factor_at = created_at where token_hash = $1", [HUELLA_ANA]));

  console.log("");
  console.log("== 4. Dejarla vacía otra vez ==");
  comparar("El sistema vuelve a dejar la sesión en espera",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.sessions set second_factor_at = null where token_hash = $1", [HUELLA_ANA]));
  comparar("Queda vacía",
    "true", await valor("select second_factor_at is null as sin_fecha from public.sessions where token_hash = $1", [HUELLA_ANA]));

  console.log("");
  console.log("== 5. La persona no ve ni toca esa columna ==");
  comparar("Ana lee la fecha de su propia sesión",
    "rechazado 42501", await como(PERSONA, ANA, "select second_factor_at from public.sessions"));
  comparar("Ana pide todas las columnas de sus sesiones",
    "rechazado 42501", await como(PERSONA, ANA, "select * from public.sessions"));
  comparar("Ana sigue leyendo las columnas de siempre de sus sesiones",
    "1 fila(s)", await como(PERSONA, ANA, "select id, user_id, expires_at, revoked_at, last_used_at, ip_address, user_agent, created_at from public.sessions"));
  comparar("Ana se anota que ya pasó el Authenticator",
    "rechazado 42501", await como(PERSONA, ANA, "update public.sessions set second_factor_at = now() where user_id = $1", [ANA]));
  comparar("John no ve las sesiones de Ana",
    "1 fila(s)", await como(PERSONA, JOHN, "select id from public.sessions"));
  comparar("Alguien sin sesión no ve ninguna",
    "0 fila(s)", await como(PERSONA, null, "select id from public.sessions"));

  console.log("");
  console.log("== 6. Las reglas de antes siguen valiendo ==");
  comparar("La huella de la llave sigue sin poder leerla la persona",
    "rechazado 42501", await como(PERSONA, ANA, "select token_hash from public.sessions"));
  comparar("Una sesión que vence antes de crearse",
    "rechazado 23514 sessions_expires_after_created",
    await sistema("insert into public.sessions (user_id, token_hash, expires_at) values ($1, $2, now() - interval '1 day')", [ANA, "c".repeat(64)]));
  comparar("El sistema sigue sin poder borrar una sesión",
    "rechazado 42501", await sistema("delete from public.sessions where token_hash = $1", [HUELLA_ANA]));
  comparar("El sistema cierra la sesión como siempre",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.sessions set revoked_at = now() where token_hash = $1", [HUELLA_ANA]));

  console.log("");
  console.log(`Total: ${numero} casos, ${numero - fallas} coinciden, ${fallas} no coinciden.`);
  await db.close();
  process.exit(fallas === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("La prueba no pudo correr:", e.message);
  process.exit(2);
});
