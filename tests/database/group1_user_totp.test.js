/* Pruebas de la tabla user_totp (grupo 1): la clave del Authenticator de cada persona.
  Migración: database/migrations/20261124000006_user_totp.sql

  Especificación aceptada por Sophia el 24 de noviembre de 2026 (pieza 3.2, parte de la tabla):
     1. El sistema guarda la clave cifrada de una persona: aceptado. Queda pendiente (sin fecha de comprobación),
        con la versión 1 de la llave, sin periodo usado, cero intentos fallidos y sin espera.
     2. Una segunda fila para la misma persona: rechazado 23505. Para una persona que no existe: rechazado 23503.
     3. Sin la clave cifrada: rechazado 23502. Con algo que no es base64, demasiado corto o demasiado largo:
        rechazado 23514.
     4. Versión de la llave en cero, intentos negativos o periodo negativo: rechazado 23514.
     5. Marcarla como comprobada sin anotar el periodo del código: rechazado 23514. Con el periodo: aceptado.
     6. El sistema la cambia (intentos, espera, clave nueva): aceptado, y la fecha de actualización cambia sola.
     7. El sistema intenta borrarla: rechazado 42501. Nada se borra.
     8. La persona no lee, crea, cambia ni borra nada, ni su propia fila: rechazado 42501. Tampoco alguien sin sesión.

  Corre todas las migraciones sobre un PostgreSQL en memoria (PGlite). No se conecta a ninguna base real.
  Cómo correrlas: tests/database/README.md. Cada caso imprime lo esperado, lo obtenido y COINCIDE o NO COINCIDE. */

const fs = require("fs");
const path = require("path");
const { PGlite } = require("@electric-sql/pglite");

const RAIZ = path.join(__dirname, "..", "..");
const MIGRACIONES = path.join(RAIZ, "database", "migrations");

const PERSONA = "integro_app"; // la API atendiendo a una persona con sesión
const SISTEMA = "integro_service"; // la API actuando como el sistema

// Personas de prueba (datos ficticios).
const ANA = "11111111-1111-4111-8111-111111111111";
const JOHN = "22222222-2222-4222-8222-222222222222";
const NADIE = "33333333-3333-4333-8333-333333333333";

// Así se ve una clave cifrada: 48 bytes (12 + 20 + 16) en base64 son 64 caracteres. Valores ficticios.
const CIFRADA = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5YWJjZGVmZ2hpamts";
const OTRA_CIFRADA = "bW5vcHFyc3R1dnd4eXpBQkNERUZHSElKS0xNTk9QUVJTVFVWV1hZWjAxMjM0NTY3";

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

// Corre la instrucción con el papel indicado. Para PERSONA se anota antes el id de quien tiene la sesión.
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

// Lectura directa para comprobar un valor guardado (como dueño de la base).
async function valor(sql, parametros) {
  const r = await db.query(sql, parametros);
  return r.rows.length ? Object.values(r.rows[0]).join(", ") : "sin fila";
}

// Registra a una persona como lo hace el sistema: su fila y su teléfono principal, en una sola operación.
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

const INSERTAR = "insert into public.user_totp (user_id, secret_ciphertext) values ($1, $2)";

async function main() {
  db = new PGlite();
  for (const archivo of fs.readdirSync(MIGRACIONES).filter((a) => a.endsWith(".sql")).sort()) {
    await db.exec(fs.readFileSync(path.join(MIGRACIONES, archivo), "utf8"));
    console.log(`Migración aplicada: ${archivo}`);
  }
  await registrar(ANA, "Ana", "ana@example.com", "+525512345678");
  await registrar(JOHN, "John", "john@example.com", "+14155550123");
  console.log("");

  console.log("== 1. El sistema guarda la clave cifrada ==");
  comparar("El sistema guarda la clave cifrada de Ana",
    "aceptado, 1 fila(s) afectada(s)", await sistema(INSERTAR, [ANA, CIFRADA]));
  comparar("Queda pendiente: sin fecha de comprobación, versión 1, sin periodo usado, cero intentos y sin espera",
    "true, 1, true, 0, true",
    await valor("select confirmed_at is null as pendiente, key_version, last_used_step is null as sin_periodo, failed_attempts, locked_until is null as sin_espera from public.user_totp where user_id = $1", [ANA]));
  comparar("La clave se guarda tal como llegó, ya cifrada",
    CIFRADA, await valor("select secret_ciphertext from public.user_totp where user_id = $1", [ANA]));

  console.log("");
  console.log("== 2. Una fila por persona, y solo de personas que existen ==");
  comparar("Una segunda fila para Ana",
    "rechazado 23505 user_totp_user_unique", await sistema(INSERTAR, [ANA, OTRA_CIFRADA]));
  comparar("Una fila para una persona que no existe",
    "rechazado 23503 user_totp_user_id_fkey", await sistema(INSERTAR, [NADIE, CIFRADA]));
  comparar("Una fila sin persona",
    "rechazado 23502 user_id", await sistema("insert into public.user_totp (secret_ciphertext) values ($1)", [CIFRADA]));

  console.log("");
  console.log("== 3. La clave cifrada ==");
  comparar("Sin la clave cifrada",
    "rechazado 23502 secret_ciphertext", await sistema("insert into public.user_totp (user_id) values ($1)", [JOHN]));
  comparar("Una clave en claro, como la escribiría la aplicación (base32, 32 caracteres)",
    "rechazado 23514 user_totp_ciphertext_format", await sistema(INSERTAR, [JOHN, "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"]));
  comparar("Algo que no es base64",
    "rechazado 23514 user_totp_ciphertext_format", await sistema(INSERTAR, [JOHN, "no es base64 ".repeat(6)]));
  comparar("Un texto vacío",
    "rechazado 23514 user_totp_ciphertext_format", await sistema(INSERTAR, [JOHN, ""]));
  comparar("Base64 de 63 caracteres: uno menos que el mínimo",
    "rechazado 23514 user_totp_ciphertext_format", await sistema(INSERTAR, [JOHN, CIFRADA.slice(0, 63)]));
  comparar("Base64 de 257 caracteres: uno más que el máximo",
    "rechazado 23514 user_totp_ciphertext_format", await sistema(INSERTAR, [JOHN, "A".repeat(257)]));
  comparar("Base64 de 256 caracteres: el máximo",
    "aceptado, 1 fila(s) afectada(s)", await sistema(INSERTAR, [JOHN, "A".repeat(256)]));

  console.log("");
  console.log("== 4. Los números ==");
  comparar("Versión de la llave en cero",
    "rechazado 23514 user_totp_key_version_positive", await sistema("update public.user_totp set key_version = 0 where user_id = $1", [ANA]));
  comparar("Intentos fallidos negativos",
    "rechazado 23514 user_totp_failed_attempts_not_negative", await sistema("update public.user_totp set failed_attempts = -1 where user_id = $1", [ANA]));
  comparar("Periodo usado negativo",
    "rechazado 23514 user_totp_last_used_step_not_negative", await sistema("update public.user_totp set last_used_step = -1 where user_id = $1", [ANA]));
  comparar("Versión 2 de la llave",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.user_totp set key_version = 2 where user_id = $1", [ANA]));

  console.log("");
  console.log("== 5. Comprobarla ==");
  comparar("Marcarla como comprobada sin anotar el periodo del código",
    "rechazado 23514 user_totp_confirmed_has_step", await sistema("update public.user_totp set confirmed_at = now() where user_id = $1", [ANA]));
  comparar("Marcarla como comprobada con el periodo del código",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.user_totp set confirmed_at = now(), last_used_step = 58800000 where user_id = $1", [ANA]));
  comparar("Queda activa, con su periodo",
    "true, 58800000",
    await valor("select confirmed_at is not null, last_used_step from public.user_totp where user_id = $1", [ANA]));
  comparar("Quitarle el periodo a una clave ya comprobada",
    "rechazado 23514 user_totp_confirmed_has_step", await sistema("update public.user_totp set last_used_step = null where user_id = $1", [ANA]));

  console.log("");
  console.log("== 6. El sistema la cambia ==");
  await db.query("update public.user_totp set updated_at = now() - interval '1 hour' where user_id = $1", [ANA]);
  comparar("Anota tres intentos fallidos y una espera de 15 minutos",
    "aceptado, 1 fila(s) afectada(s)", await sistema("update public.user_totp set failed_attempts = 3, locked_until = now() + interval '15 minutes' where user_id = $1", [ANA]));
  comparar("La fecha de actualización cambió sola",
    "true", await valor("select updated_at > now() - interval '1 minute' from public.user_totp where user_id = $1", [ANA]));
  comparar("Guarda una clave nueva en la misma fila y la deja pendiente otra vez",
    "aceptado, 1 fila(s) afectada(s)",
    await sistema("update public.user_totp set secret_ciphertext = $2, confirmed_at = null, last_used_step = null, failed_attempts = 0, locked_until = null where user_id = $1", [ANA, OTRA_CIFRADA]));
  comparar("Sigue habiendo una sola fila de Ana",
    "1", await valor("select count(*) from public.user_totp where user_id = $1", [ANA]));
  comparar("El sistema lee todas las filas",
    "2 fila(s)", await sistema("select id from public.user_totp"));

  console.log("");
  console.log("== 7. Nada se borra ==");
  comparar("El sistema intenta borrar la clave de Ana",
    "rechazado 42501", await sistema("delete from public.user_totp where user_id = $1", [ANA]));
  comparar("El sistema intenta vaciar la tabla",
    "rechazado 42501", await sistema("truncate public.user_totp"));
  comparar("Borrar a una persona que tiene clave",
    "rechazado 42501", await sistema("delete from public.users where id = $1", [ANA]));

  console.log("");
  console.log("== 8. La persona no ve ni toca nada ==");
  comparar("Ana lee su propia clave",
    "rechazado 42501", await como(PERSONA, ANA, "select secret_ciphertext from public.user_totp where user_id = $1", [ANA]));
  comparar("Ana pregunta si tiene fila, sin pedir la clave",
    "rechazado 42501", await como(PERSONA, ANA, "select confirmed_at from public.user_totp where user_id = $1", [ANA]));
  comparar("Ana cuenta las filas",
    "rechazado 42501", await como(PERSONA, ANA, "select count(*) from public.user_totp"));
  comparar("Ana se pone una clave",
    "rechazado 42501", await como(PERSONA, ANA, INSERTAR, [ANA, CIFRADA]));
  comparar("Ana se marca la clave como comprobada",
    "rechazado 42501", await como(PERSONA, ANA, "update public.user_totp set confirmed_at = now(), last_used_step = 1 where user_id = $1", [ANA]));
  comparar("Ana se quita la espera",
    "rechazado 42501", await como(PERSONA, ANA, "update public.user_totp set failed_attempts = 0, locked_until = null where user_id = $1", [ANA]));
  comparar("Ana borra su clave",
    "rechazado 42501", await como(PERSONA, ANA, "delete from public.user_totp where user_id = $1", [ANA]));
  comparar("John lee la clave de Ana",
    "rechazado 42501", await como(PERSONA, JOHN, "select secret_ciphertext from public.user_totp where user_id = $1", [ANA]));
  comparar("Alguien sin sesión lee la tabla",
    "rechazado 42501", await como(PERSONA, null, "select id from public.user_totp"));
  comparar("Después de todo, la clave de Ana sigue siendo la que guardó el sistema",
    OTRA_CIFRADA, await valor("select secret_ciphertext from public.user_totp where user_id = $1", [ANA]));

  console.log("");
  console.log(`Total: ${numero} casos, ${numero - fallas} coinciden, ${fallas} no coinciden.`);
  await db.close();
  process.exit(fallas === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("La prueba no pudo correr:", e.message);
  process.exit(2);
});
