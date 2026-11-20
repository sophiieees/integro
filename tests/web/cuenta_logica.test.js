/* Casos de la lógica de la ventana de «Entrar» (web/assets/js/cuenta-logica.js).
   Se corren con node, sin navegador ni API:  node --test tests/web
   Las respuestas de la API son las que documenta backend/README.md. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const LOGICA = require(path.join(__dirname, "..", "..", "web", "assets", "js", "cuenta-logica.js"));

const CORREO = "ana@prueba.invalid";
const error = (field, code, message, extra) => Object.assign({ errors: [{ field, code, message }] }, extra);

/* --- Lo escrito antes de mandarlo --------------------------------------- */

test("correo y contraseña vacíos o mal escritos se avisan sin llamar a la API", () => {
  assert.deepEqual(LOGICA.revisarCorreoYContrasena("", "x"), { campo: "email", aviso: "Escribe tu correo." });
  assert.deepEqual(LOGICA.revisarCorreoYContrasena("   ", "x"), { campo: "email", aviso: "Escribe tu correo." });
  assert.equal(LOGICA.revisarCorreoYContrasena("ana", "x").campo, "email");
  assert.equal(LOGICA.revisarCorreoYContrasena("@x", "x").campo, "email");
  assert.equal(LOGICA.revisarCorreoYContrasena("ana@", "x").campo, "email");
  assert.deepEqual(LOGICA.revisarCorreoYContrasena(CORREO, ""), { campo: "password", aviso: "Escribe tu contraseña." });
  assert.equal(LOGICA.revisarCorreoYContrasena(CORREO, "Ejemplo-2026"), null);
  assert.equal(LOGICA.revisarCorreoYContrasena("  " + CORREO + " ", "x"), null);
});

test("el código tiene que ser de 6 números", () => {
  assert.equal(LOGICA.revisarCodigo("").campo, "code");
  assert.equal(LOGICA.revisarCodigo("12345").aviso, "El código son 6 números.");
  assert.equal(LOGICA.revisarCodigo("1234567").aviso, "El código son 6 números.");
  assert.equal(LOGICA.revisarCodigo("12345a").aviso, "El código son 6 números.");
  assert.equal(LOGICA.revisarCodigo(" 123456 "), null);
  assert.equal(LOGICA.revisarCodigo("000000"), null);
});

/* --- Caso 1: correo y contraseña correctos ------------------------------ */

test("correctos: pasa al código y dice a qué correo se envió", () => {
  const r = LOGICA.despuesDelCorreo(200, { status: "code_required" }, CORREO);

  assert.equal(r.paso, "codigo");
  assert.equal(r.campo, "code");
  assert.equal(r.aviso, null);
  assert.equal(r.texto, `Te enviamos un código de 6 dígitos a ${CORREO}. Vence en 5 minutos.`);
});

/* --- Caso 2: contraseña incorrecta -------------------------------------- */

test("contraseña incorrecta o correo sin cuenta: aviso y se queda en el paso 1", () => {
  const r = LOGICA.despuesDelCorreo(401, error("credentials", "invalid_credentials", "El correo o la contraseña no son correctos."), CORREO);

  assert.deepEqual(r, { paso: "correo", campo: "password", aviso: "El correo o la contraseña no son correctos." });
});

/* --- Caso 3: correo sin comprobar --------------------------------------- */

test("correo sin comprobar: aviso de comprobarlo", () => {
  const r = LOGICA.despuesDelCorreo(403, error("email", "email_not_verified", "..."), CORREO);

  assert.equal(r.paso, "correo");
  assert.equal(r.campo, "email");
  assert.match(r.aviso, /comprobado tu correo/);
});

/* --- Caso 4: demasiados intentos ---------------------------------------- */

test("espera por dispositivo: aviso con los minutos que faltan", () => {
  const r = LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 900 }), CORREO);

  assert.equal(r.paso, "correo");
  assert.equal(r.aviso, "Demasiados intentos desde este dispositivo. Intenta de nuevo en 15 minutos.");
  assert.equal(LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 61 }), CORREO).aviso,
    "Demasiados intentos desde este dispositivo. Intenta de nuevo en 2 minutos.");
  assert.equal(LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 30 }), CORREO).aviso,
    "Demasiados intentos desde este dispositivo. Intenta de nuevo en 1 minuto.");
});

test("minutos: se redondea hacia arriba y nunca es cero", () => {
  assert.equal(LOGICA.minutos(0), "1 minuto");
  assert.equal(LOGICA.minutos(60), "1 minuto");
  assert.equal(LOGICA.minutos(61), "2 minutos");
  assert.equal(LOGICA.minutos(900), "15 minutos");
  assert.equal(LOGICA.minutos(undefined), "1 minuto");
});

test("ya hay un código vigente (menos de un minuto): se pide ese código", () => {
  const r = LOGICA.despuesDelCorreo(429, error("email", "wait", "...", { retry_after: 42 }), CORREO);

  assert.equal(r.paso, "codigo");
  assert.match(r.texto, /hace menos de un minuto/);
  assert.equal(r.aviso, null);
});

test("cinco códigos en una hora: aviso y se queda en el paso 1", () => {
  const r = LOGICA.despuesDelCorreo(429, error("email", "hourly_limit", "..."), CORREO);

  assert.equal(r.paso, "correo");
  assert.match(r.aviso, /demasiados códigos/);
});

test("dato faltante según la API: el aviso va en su campo", () => {
  const r = LOGICA.despuesDelCorreo(422, error("email", "required", "Este dato es obligatorio."), CORREO);

  assert.deepEqual(r, { paso: "correo", campo: "email", aviso: "Este dato es obligatorio." });
});

/* --- Caso 5: código correcto -------------------------------------------- */

test("código correcto: dentro, sin aviso", () => {
  assert.deepEqual(LOGICA.despuesDelCodigo(200, { status: "session_opened", expires_at: "2026-12-19T00:00:00Z", csrf_token: "x" }),
    { paso: "dentro", campo: null, aviso: null });
});

/* --- Caso 6: código incorrecto, vencido o agotado ----------------------- */

test("código incorrecto: aviso con los intentos que quedan y sigue en el código", () => {
  const cuatro = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "...", { attempts_left: 4 }));
  const uno = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "...", { attempts_left: 1 }));

  assert.deepEqual(cuatro, { paso: "codigo", campo: "code", aviso: "El código no es correcto. Te quedan 4 intentos." });
  assert.equal(uno.aviso, "El código no es correcto. Te queda 1 intento.");
});

test("código incorrecto sin intentos: vuelve al paso 1", () => {
  const r = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "...", { attempts_left: 0 }));

  assert.equal(r.paso, "correo");
  assert.equal(r.aviso, "El código no es correcto. Ya no te quedan intentos.");
});

test("código incorrecto sin el dato de intentos (sin paso 1 previo): solo el aviso", () => {
  const r = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "..."));

  assert.deepEqual(r, { paso: "codigo", campo: "code", aviso: "El código no es correcto." });
});

test("código vencido o agotado: aviso y vuelve al paso 1", () => {
  const vencido = LOGICA.despuesDelCodigo(400, error("code", "code_expired", "..."));
  const agotado = LOGICA.despuesDelCodigo(400, error("code", "too_many_attempts", "..."));

  assert.equal(vencido.paso, "correo");
  assert.match(vencido.aviso, /venció/);
  assert.equal(agotado.paso, "correo");
  assert.match(agotado.aviso, /Demasiados intentos/);
});

/* --- Caso 7: salir ------------------------------------------------------ */

test("salir: con 200 o 401 la sesión queda cerrada; con 403 o sin servidor sigue", () => {
  assert.deepEqual(LOGICA.despuesDeSalir(200), { sesion: false, aviso: null });
  assert.deepEqual(LOGICA.despuesDeSalir(401), { sesion: false, aviso: null });
  assert.equal(LOGICA.despuesDeSalir(403).sesion, true);
  assert.match(LOGICA.despuesDeSalir(403).aviso, /Recarga la página/);
  assert.equal(LOGICA.despuesDeSalir(0).aviso, LOGICA.SIN_SERVIDOR);
  assert.equal(LOGICA.despuesDeSalir(500).sesion, true);
});

/* --- Caso 8: la cabecera al cargar -------------------------------------- */

test("con sesión la cabecera muestra el nombre y guarda la clave de la página", () => {
  const r = LOGICA.estadoDeCabecera(200, { first_name: "Ana", last_name: "Torres", csrf_token: "clave-de-la-pagina" });

  assert.deepEqual(r, { sesion: true, nombre: "Ana", clave: "clave-de-la-pagina", servidor: true });
});

test("sin sesión la cabecera muestra «Entrar»", () => {
  assert.deepEqual(LOGICA.estadoDeCabecera(401, { errors: [{ code: "not_authenticated" }] }),
    { sesion: false, nombre: null, clave: null, servidor: true });
});

/* --- Caso 9: sin API ---------------------------------------------------- */

test("sin servidor: la cabecera lo sabe y cada paso avisa que hace falta el servidor", () => {
  assert.equal(LOGICA.estadoDeCabecera(0, null).servidor, false);
  assert.equal(LOGICA.despuesDelCorreo(0, null, CORREO).aviso, LOGICA.SIN_SERVIDOR);
  assert.equal(LOGICA.despuesDelCorreo(0, null, CORREO).paso, "correo");
  assert.equal(LOGICA.despuesDelCodigo(0, null).aviso, LOGICA.SIN_SERVIDOR);
  assert.match(LOGICA.SIN_SERVIDOR, /127\.0\.0\.1:8000/);
});

/* --- Respuestas que no se esperan --------------------------------------- */

test("una respuesta rara no rompe la ventana", () => {
  assert.equal(LOGICA.despuesDelCorreo(500, null, CORREO).paso, "correo");
  assert.equal(LOGICA.despuesDelCorreo(200, { status: "otra-cosa" }, CORREO).paso, "correo");
  assert.equal(LOGICA.despuesDelCorreo(502, "no es json", CORREO).paso, "correo");
  assert.equal(LOGICA.despuesDelCodigo(200, null).paso, "codigo");
  assert.equal(LOGICA.despuesDelCodigo(500, { errors: [] }).paso, "codigo");
  assert.equal(LOGICA.estadoDeCabecera(200, {}).sesion, false);
});
