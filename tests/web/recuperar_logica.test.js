/* Casos de la lógica de recuperar la contraseña (web/assets/js/recuperar-logica.js).
   Se corren con node, sin navegador ni API:  node --test tests/web
   Las respuestas de la API son las que documenta backend/README.md.
   Decisiones de Sophia del 21 de noviembre de 2026: código de 6 dígitos que dura 30 minutos; solo una cuenta con el
   correo comprobado puede recuperar la contraseña. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const JS = path.join(__dirname, "..", "..", "web", "assets", "js");
const LOGICA = require(path.join(JS, "recuperar-logica.js"));
const CUENTA = require(path.join(JS, "cuenta-logica.js"));

const CORREO = "ana@prueba.invalid";
const error = (field, code, message, extra) => Object.assign({ errors: [{ field, code, message }] }, extra);

/* --- Lo escrito antes de mandarlo ------------------------------------------ */

test("el correo vacío o mal escrito se avisa sin llamar a la API", () => {
  assert.deepEqual(LOGICA.revisarCorreo(""), { campo: "email", aviso: "Escribe tu correo electrónico." });
  assert.deepEqual(LOGICA.revisarCorreo("   "), { campo: "email", aviso: "Escribe tu correo electrónico." });
  assert.equal(LOGICA.revisarCorreo(undefined).campo, "email");
  for (const mal of ["ana", "@x", "ana@"]) assert.equal(LOGICA.revisarCorreo(mal).campo, "email", mal);
  assert.equal(LOGICA.revisarCorreo(CORREO), null);
  assert.equal(LOGICA.revisarCorreo("  " + CORREO + " "), null);
});

test("el código tiene que ser de 6 números y la contraseña nueva no puede ir vacía", () => {
  assert.deepEqual(LOGICA.revisarCambio("123456", "Nueva-2026!"), {});
  assert.deepEqual(LOGICA.revisarCambio(" 123456 ", "Nueva-2026!"), {});
  assert.deepEqual(LOGICA.revisarCambio("", "x").code, ["Escribe el código que recibiste."]);
  assert.deepEqual(LOGICA.revisarCambio("12345", "x").code, ["El código debe constar de 6 dígitos."]);
  assert.deepEqual(LOGICA.revisarCambio("12ab56", "x").code, ["El código debe constar de 6 dígitos."]);
  assert.deepEqual(LOGICA.revisarCambio("1234567", "x").code, ["El código debe constar de 6 dígitos."]);
  assert.deepEqual(LOGICA.revisarCambio("123456", "").new_password, ["Escribe tu contraseña nueva."]);
  assert.deepEqual(Object.keys(LOGICA.revisarCambio("", "")), ["code", "new_password"]);
});

test("revisarCambio no revisa las reglas de la contraseña: eso lo dice el indicador y la API", () => {
  assert.deepEqual(LOGICA.revisarCambio("123456", "corta"), {});
});

/* --- Pedir el código --------------------------------------------------------- */

test("pedir el código pasa al paso del código, sin prometer que llegó", () => {
  const r = LOGICA.despuesDePedir(200, { status: "code_requested" }, CORREO);

  assert.equal(r.paso, "codigo");
  assert.equal(r.correo, CORREO);
  assert.match(r.texto, /^Si ana@prueba\.invalid tiene una cuenta con el correo electrónico comprobado, te enviamos un código de 6 dígitos\./);
  assert.match(r.texto, /30 minutos/);
  assert.match(r.texto, /no deseado/);
  assert.doesNotMatch(r.texto, /Te enviamos un código/);
});

test("pedir el código: sin servidor, con un 422 o con una respuesta rara se queda en el correo y avisa", () => {
  assert.deepEqual(LOGICA.despuesDePedir(0, null, CORREO), {
    paso: "correo", errores: {}, aviso: LOGICA.SIN_SERVIDOR, texto: null, correo: CORREO,
  });
  const faltante = LOGICA.despuesDePedir(422, error("email", "required", "Este dato es obligatorio."), CORREO);
  assert.equal(faltante.paso, "correo");
  assert.deepEqual(faltante.errores, { email: ["Este dato es obligatorio."] });
  for (const [status, cuerpo] of [[500, null], [200, { status: "otra-cosa" }], [422, { errors: [] }], [502, "no es json"]]) {
    const r = LOGICA.despuesDePedir(status, cuerpo, CORREO);
    assert.equal(r.paso, "correo", String(status));
    assert.equal(r.aviso, "El servidor respondió de forma inesperada. Inténtalo nuevamente.", String(status));
  }
});

test("el aviso de un campo que la pantalla no tiene va aparte", () => {
  const r = LOGICA.despuesDePedir(422, error("otro", "x", "Algo pasó."), CORREO);

  assert.equal(r.aviso, "Algo pasó.");
  assert.deepEqual(r.errores, {});
});

test("pedir otro código deja una nota que dice la espera y que el anterior deja de servir", () => {
  const nota = LOGICA.notaDeReenvio();

  assert.match(nota, /Si la cuenta existe/);
  assert.match(nota, /un minuto/);
  assert.match(nota, /anterior deja de servir/);
});

/* --- Cambiar la contraseña ------------------------------------------------------- */

test("con 200 la contraseña cambió y se pasa a «listo»", () => {
  const r = LOGICA.despuesDeCambiar(200, { status: "password_changed" });

  assert.equal(r.paso, "listo");
  assert.deepEqual(r.errores, {});
  assert.equal(r.aviso, null);
});

test("código incorrecto: dice cuántos intentos quedan, con singular y plural", () => {
  const con = (quedan) => LOGICA.despuesDeCambiar(400, error("code", "invalid_code", "x", { attempts_left: quedan }));

  assert.deepEqual(con(4).errores.code, ["El código ingresado no es correcto. Te quedan 4 intentos."]);
  assert.deepEqual(con(1).errores.code, ["El código ingresado no es correcto. Te queda 1 intento."]);
  assert.equal(con(4).paso, "codigo");
  assert.equal(con(4).pedirOtro, false);
});

test("sin intentos: se ofrece pedir otro código", () => {
  const r = LOGICA.despuesDeCambiar(400, error("code", "invalid_code", "x", { attempts_left: 0 }));

  assert.match(r.errores.code[0], /Ya no te quedan intentos con este código: pide uno nuevo\.$/);
  assert.equal(r.pedirOtro, true);
});

test("un código incorrecto sin número de intentos (correo sin cuenta) no inventa uno", () => {
  const r = LOGICA.despuesDeCambiar(400, error("code", "invalid_code", "x"));

  assert.deepEqual(r.errores.code, ["El código ingresado no es correcto."]);
  assert.equal(r.pedirOtro, false);
});

test("código vencido o con los intentos agotados: se pide otro", () => {
  const vencido = LOGICA.despuesDeCambiar(400, error("code", "code_expired", "x"));
  const agotado = LOGICA.despuesDeCambiar(400, error("code", "too_many_attempts", "x"));

  assert.deepEqual(vencido.errores.code, ["El código venció. Pide uno nuevo."]);
  assert.deepEqual(agotado.errores.code, ["Se agotaron los intentos con ese código. Pide uno nuevo."]);
  assert.equal(vencido.pedirOtro && agotado.pedirOtro, true);
  assert.equal(vencido.paso, "codigo");
});

test("demasiados intentos desde ese dispositivo: dice cuánto esperar", () => {
  const r = LOGICA.despuesDeCambiar(429, error("credentials", "try_later", "x", { retry_after: 840 }));

  assert.equal(r.aviso, "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en 14 minutos.");
  assert.equal(r.paso, "codigo");
  assert.equal(LOGICA.despuesDeCambiar(429, error("credentials", "try_later", "x", { retry_after: 30 })).aviso.endsWith("en 1 minuto."), true);
  assert.equal(CUENTA.minutos(840), "14 minutos");
});

test("faltas de la contraseña: una sola línea que remite al indicador, para no repetir la lista", () => {
  const cuerpo = { errors: [
    { field: "new_password", code: "too_short", message: "La contraseña debe tener al menos 10 caracteres." },
    { field: "new_password", code: "missing_digit", message: "La contraseña debe tener al menos un número." },
  ] };

  const r = LOGICA.despuesDeCambiar(422, cuerpo);

  assert.deepEqual(r.errores, { new_password: ["Tu contraseña aún no cumple lo que se indica abajo."] });
  assert.equal(r.aviso, null);
});

test("una contraseña muy fácil de adivinar: una línea que remite a los consejos del indicador, sin repetirlos", () => {
  const mensaje = "La contraseña es muy fácil de adivinar. Evita secuencias como 1234, abcd o símbolos en fila del teclado.";

  const r = LOGICA.despuesDeCambiar(422, error("new_password", "too_weak", mensaje));

  assert.deepEqual(r.errores, { new_password: ["Tu contraseña es muy fácil de adivinar. Revisa los consejos de abajo."] });
  assert.doesNotMatch(r.errores.new_password[0], /secuencias/);
});

test("un 422 con otro campo o sin avisos no rompe la pantalla", () => {
  assert.equal(LOGICA.despuesDeCambiar(422, error("otro", "x", "Aviso suelto.")).aviso, "Aviso suelto.");
  assert.equal(LOGICA.despuesDeCambiar(422, { errors: [] }).aviso, "El servidor respondió de forma inesperada. Inténtalo nuevamente.");
  assert.deepEqual(LOGICA.despuesDeCambiar(422, error("code", "required", "Este dato es obligatorio.")).errores, { code: ["Este dato es obligatorio."] });
});

test("sin servidor o con una respuesta rara, el paso del código se queda donde está", () => {
  assert.deepEqual(LOGICA.despuesDeCambiar(0, null), { paso: "codigo", errores: {}, aviso: LOGICA.SIN_SERVIDOR, pedirOtro: false });
  for (const [status, cuerpo] of [[500, null], [200, { status: "otra-cosa" }], [502, "no es json"], [400, { errors: [] }]]) {
    const r = LOGICA.despuesDeCambiar(status, cuerpo);
    assert.equal(r.paso, "codigo", String(status));
    assert.equal(r.aviso, "El servidor respondió de forma inesperada. Inténtalo nuevamente.", String(status));
  }
});

/* --- El resto -------------------------------------------------------------------------- */

test("el primer campo con aviso, en el orden de la pantalla", () => {
  assert.equal(LOGICA.primerCampoConError({ new_password: ["x"], code: ["y"] }), "code");
  assert.equal(LOGICA.primerCampoConError({ new_password: ["x"] }), "new_password");
  assert.equal(LOGICA.primerCampoConError({}), null);
  assert.equal(LOGICA.hayErrores({}), false);
  assert.equal(LOGICA.hayErrores({ code: ["x"] }), true);
});

test("con sesión iniciada la pantalla pide cerrarla primero", () => {
  assert.equal(LOGICA.avisoDeSesionIniciada("Ana"), "Ya iniciaste sesión como Ana. Para recuperar tu contraseña, primero cierra sesión.");
});

test("el indicador es el del registro: califica la contraseña con el correo y se pinta igual", () => {
  const cuerpo = LOGICA.cuerpoDeFortaleza("Nueva-2026!", CORREO);

  assert.equal(cuerpo.password, "Nueva-2026!");
  assert.equal(cuerpo.email, CORREO);
  assert.equal(LOGICA.vistaDeFortaleza({ level: "very_reliable", meets_rules: true, accepted: true }, true).segmentos, 4);
  assert.equal(LOGICA.vistaDeFortaleza(null, false).segmentos, 0);
});

test("los textos están en tono formal de tú, nunca de usted", () => {
  const textos = [
    LOGICA.despuesDePedir(200, { status: "code_requested" }, CORREO).texto,
    LOGICA.notaDeReenvio(),
    LOGICA.avisoDeSesionIniciada("Ana"),
    LOGICA.despuesDeCambiar(400, error("code", "invalid_code", "x", { attempts_left: 2 })).errores.code[0],
    LOGICA.despuesDeCambiar(400, error("code", "code_expired", "x")).errores.code[0],
    LOGICA.despuesDeCambiar(429, error("credentials", "try_later", "x", { retry_after: 60 })).aviso,
    LOGICA.AVISO_CONTRASENA,
  ];

  for (const texto of textos) {
    assert.doesNotMatch(texto, /\b(usted|su contraseña|ingrese|escriba|verifique)\b/i, texto);
  }
});

/* --- «Tu contraseña cambió»: 3 segundos y al inicio de sesión (decisión de Sophia del 21 de noviembre de 2026) ---- */

test("la espera es de 3 segundos y lleva a la portada con la ventana de iniciar sesión", () => {
  assert.equal(LOGICA.SEGUNDOS_DE_ESPERA, 3);
  assert.equal(LOGICA.DESTINO_AL_TERMINAR, "index.html#entrar");
});

test("la cuenta regresiva habla en singular y en plural", () => {
  assert.equal(LOGICA.textoDeEspera(3), "Te llevaremos al inicio de sesión en 3 segundos.");
  assert.equal(LOGICA.textoDeEspera(1), "Te llevaremos al inicio de sesión en 1 segundo.");
});
