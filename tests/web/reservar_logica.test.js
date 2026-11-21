/* Casos de la lógica de «Reservar» (web/assets/js/reservar-logica.js) y del regreso seguro de cuenta-logica.js.
   Se corren con node, sin navegador:  node --test tests/web
   Decisión de Sophia del 20 de noviembre de 2026: un visitante que da clic en «Reservar» sin sesión ve el aviso de
   iniciar sesión o crear la cuenta y, al terminar, vuelve a la misma propiedad con sus fechas y sus huéspedes,
   guardados en la dirección de la página. Para quien ya tiene sesión, por ahora, las reservas «se abren pronto». */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const WEB = path.join(__dirname, "..", "..", "web");
const JS = path.join(WEB, "assets", "js");
const RESERVAR = require(path.join(JS, "reservar-logica.js"));
const CUENTA = require(path.join(JS, "cuenta-logica.js"));

/* --- A dónde se puede volver después de iniciar sesión ------------------------------------ */

test("se vuelve a una página de Íntegro con su dirección completa", () => {
  for (const bien of [
    "propiedad.html?id=2",
    "propiedad.html?id=2&llegada=2026-12-01&salida=2026-12-03&huespedes=2",
    "index.html",
    "index.html#resultados",
    "mi-cuenta.html#reservas",
    "anfitriones.html",
    "proximamente.html?seccion=servicios",
  ]) {
    assert.equal(CUENTA.siguienteSeguro(bien), bien, bien);
  }
});

test("lo que apunta a otro sitio, a un código o a algo raro no se usa nunca", () => {
  for (const mal of [
    "https://evil.example/propiedad.html", "http://evil.example", "//evil.example/propiedad.html", "///evil.example",
    "javascript:alert(1)", "JAVASCRIPT:alert(1)", "data:text/html,<b>", "vbscript:x", "\\\\evil.example\\propiedad.html",
    "/propiedad.html", "../propiedad.html", "./propiedad.html", "web/propiedad.html", "propiedad.html/../../x",
    "propiedad.html?next=https://evil.example", "propiedad.html?x=<script>", "propiedad.html?x=\"onload=",
    "propiedad.html?x=a b", "propiedad.html\nSet-Cookie: a=b", "propiedad.html\r\n", " propiedad.html",
    "propiedad.html ", "propiedad.html#<b>", "propiedad.html:80", "propiedad.html?a=1;b=2", "propiedad.html?a=1'",
  ]) {
    assert.equal(CUENTA.siguienteSeguro(mal), null, JSON.stringify(mal));
  }
});

test("solo valen las páginas de la lista: no el registro, ni recuperar la contraseña, ni archivos que no existen", () => {
  for (const mal of ["registro.html", "recuperar-contrasena.html", "otra.html", "propiedad.htm", "propiedad", "PROPIEDAD.HTML", "propiedad.html.js", "assets/js/cuenta.js"]) {
    assert.equal(CUENTA.siguienteSeguro(mal), null, mal);
  }
  assert.equal(CUENTA.PAGINAS_DE_REGRESO.includes("registro.html"), false);
  assert.ok(CUENTA.PAGINAS_DE_REGRESO.includes("propiedad.html"));
});

test("lo que no es un texto, o es vacío o larguísimo, no se usa", () => {
  for (const raro of [undefined, null, 0, 5, true, {}, [], ["propiedad.html"], "", "x".repeat(301)]) {
    assert.equal(CUENTA.siguienteSeguro(raro), null, String(raro));
  }
  assert.notEqual(CUENTA.siguienteSeguro("propiedad.html?id=" + "1".repeat(250)), null);
  assert.equal(CUENTA.siguienteSeguro("propiedad.html?id=" + "1".repeat(300)), null);
});

test("todas las páginas de la lista existen en web/", () => {
  for (const pagina of CUENTA.PAGINAS_DE_REGRESO) assert.ok(fs.existsSync(path.join(WEB, pagina)), pagina);
});

/* --- La dirección de la ficha --------------------------------------------------------------- */

test("la dirección guarda la propiedad, las fechas y los huéspedes", () => {
  assert.equal(
    RESERVAR.direccionDeLaFicha(2, { llegada: "2026-12-01", salida: "2026-12-03", huespedes: "2" }),
    "propiedad.html?id=2&llegada=2026-12-01&salida=2026-12-03&huespedes=2"
  );
});

test("lo que la persona no eligió no se guarda", () => {
  assert.equal(RESERVAR.direccionDeLaFicha("2", { llegada: "", salida: "", huespedes: "" }), "propiedad.html?id=2");
  assert.equal(RESERVAR.direccionDeLaFicha(2, { llegada: "2026-12-01", salida: "", huespedes: "3" }), "propiedad.html?id=2&llegada=2026-12-01&huespedes=3");
  assert.equal(RESERVAR.direccionDeLaFicha(2, {}), "propiedad.html?id=2");
});

test("un dato que no sirve no se guarda, aunque el resto sí", () => {
  assert.equal(RESERVAR.direccionDeLaFicha(2, { llegada: "2026-02-31", salida: "mañana", huespedes: "99" }), "propiedad.html?id=2");
  assert.equal(RESERVAR.direccionDeLaFicha(2, { llegada: "<b>", salida: "2026-12-03", huespedes: "2" }), "propiedad.html?id=2&salida=2026-12-03&huespedes=2");
});

test("sin una propiedad válida no hay dirección", () => {
  for (const id of [null, undefined, "", "0", "-1", "abc", "2; drop", "10000", "1e3", "2.5", " 2", "<b>"]) {
    assert.equal(RESERVAR.direccionDeLaFicha(id, { llegada: "2026-12-01" }), null, String(id));
  }
});

test("la dirección que se arma siempre es una de las que se permiten volver", () => {
  const direccion = RESERVAR.direccionDeLaFicha(2, { llegada: "2026-12-01", salida: "2026-12-03", huespedes: "2" });

  assert.equal(CUENTA.siguienteSeguro(direccion), direccion);
});

/* --- Lo que trae la dirección --------------------------------------------------------------------- */

test("se leen las fechas y los huéspedes de la dirección", () => {
  assert.deepEqual(
    RESERVAR.valoresDeLaDireccion("?id=2&llegada=2026-12-01&salida=2026-12-03&huespedes=4"),
    { llegada: "2026-12-01", salida: "2026-12-03", huespedes: "4" }
  );
});

test("lo que no sirve se ignora sin fallar", () => {
  const vacio = { llegada: "", salida: "", huespedes: "" };

  assert.deepEqual(RESERVAR.valoresDeLaDireccion(""), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion(undefined), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion(null), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion("?id=2"), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion("?llegada=2026-02-30&salida=2026-13-01&huespedes=0"), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion("?llegada=<script>&salida=26-12-03&huespedes=-2"), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion("?huespedes=7"), vacio);
  assert.deepEqual(RESERVAR.valoresDeLaDireccion("?huespedes=1e1"), vacio);
  assert.equal(RESERVAR.valoresDeLaDireccion("?llegada=2026-12-01&llegada=2026-12-09").llegada, "2026-12-01");
  assert.equal(RESERVAR.valoresDeLaDireccion("?huespedes=02").huespedes, "2");
});

test("un año bisiesto sí tiene 29 de febrero; uno que no, no", () => {
  assert.equal(RESERVAR.fechaValida("2028-02-29"), "2028-02-29");
  assert.equal(RESERVAR.fechaValida("2027-02-29"), "");
  assert.equal(RESERVAR.fechaValida("2026-12-31"), "2026-12-31");
  assert.equal(RESERVAR.fechaValida("2026-12-32"), "");
  assert.equal(RESERVAR.fechaValida(20261201), "");
});

test("los huéspedes van de 1 a 6", () => {
  for (const bien of ["1", "2", "6"]) assert.equal(RESERVAR.huespedesValidos(bien), bien);
  for (const mal of ["0", "7", "", "dos", "1.5", "-1", undefined, 3]) assert.equal(RESERVAR.huespedesValidos(mal), "", String(mal));
});

/* --- Revisar lo escrito --------------------------------------------------------------------------------- */

test("las fechas no son obligatorias: se guardan las que haya", () => {
  assert.equal(RESERVAR.revisarReserva({ llegada: "", salida: "", huespedes: "2" }), null);
  assert.equal(RESERVAR.revisarReserva({ llegada: "2026-12-01", salida: "", huespedes: "2" }), null);
  assert.equal(RESERVAR.revisarReserva({ llegada: "", salida: "2026-12-03" }), null);
});

test("una salida igual o anterior a la llegada se avisa", () => {
  const aviso = { campo: "salida", aviso: "La fecha de salida debe ser posterior a la de llegada." };

  assert.deepEqual(RESERVAR.revisarReserva({ llegada: "2026-12-03", salida: "2026-12-01" }), aviso);
  assert.deepEqual(RESERVAR.revisarReserva({ llegada: "2026-12-03", salida: "2026-12-03" }), aviso);
  assert.equal(RESERVAR.revisarReserva({ llegada: "2026-12-03", salida: "2026-12-04" }), null);
  assert.equal(RESERVAR.revisarReserva({ llegada: "2026-12-31", salida: "2027-01-01" }), null);
});

test("una fecha que no existe se avisa en su campo", () => {
  assert.deepEqual(RESERVAR.revisarReserva({ llegada: "2026-02-31", salida: "" }), { campo: "llegada", aviso: "La fecha de llegada no es válida." });
  assert.deepEqual(RESERVAR.revisarReserva({ llegada: "", salida: "x" }), { campo: "salida", aviso: "La fecha de salida no es válida." });
});

/* --- El enlace de «Crear cuenta» ----------------------------------------------------------------------------- */

test("«Crear cuenta» lleva el regreso a esta propiedad, bien escrito en la dirección", () => {
  const direccion = "propiedad.html?id=2&llegada=2026-12-01&salida=2026-12-03&huespedes=2";

  const enlace = RESERVAR.enlaceDeRegistro(direccion);

  assert.equal(enlace, "registro.html?siguiente=propiedad.html%3Fid%3D2%26llegada%3D2026-12-01%26salida%3D2026-12-03%26huespedes%3D2");
  // Y la página de registro lo lee y recupera la misma dirección.
  const leida = new URLSearchParams(enlace.split("?")[1]).get("siguiente");
  assert.equal(leida, direccion);
  assert.equal(CUENTA.siguienteSeguro(leida), direccion);
});

test("si la dirección no es una de las permitidas, «Crear cuenta» es el de siempre", () => {
  for (const mala of [null, undefined, "", "https://evil.example", "javascript:alert(1)", "registro.html", "//evil.example"]) {
    assert.equal(RESERVAR.enlaceDeRegistro(mala), "registro.html", String(mala));
  }
});

/* --- Lo que se le dice a la persona --------------------------------------------------------------------------------- */

test("sin sesión: se pide iniciar sesión o crear la cuenta y se promete volver a la propiedad", () => {
  const aviso = RESERVAR.avisoDeReserva(false);

  assert.equal(aviso.titulo, "Para reservar necesitas una cuenta");
  assert.match(aviso.texto, /Inicia sesión o crea tu cuenta\./);
  assert.match(aviso.texto, /Volverás a esta propiedad con tus fechas y tus huéspedes\./);
});

test("con sesión: las reservas todavía no existen y se dice sin prometer lo que no hay", () => {
  const aviso = RESERVAR.avisoDeReserva(true);

  assert.equal(aviso.titulo, "Las reservas se abren pronto");
  assert.match(aviso.texto, /Todavía no se puede reservar\./);
  assert.doesNotMatch(aviso.texto, /reservaste|confirmad|pago/i);
});

test("al iniciar sesión en la misma página, el aviso cambia y dice que las fechas siguen ahí", () => {
  const aviso = RESERVAR.avisoTrasIniciarSesion();

  assert.equal(aviso.titulo, "Ya iniciaste sesión");
  assert.match(aviso.texto, /Las reservas se abren pronto\./);
  assert.match(aviso.texto, /siguen aquí/);
});

test("los textos están en tono formal de tú, nunca de usted", () => {
  const todos = [RESERVAR.avisoDeReserva(true), RESERVAR.avisoDeReserva(false), RESERVAR.avisoTrasIniciarSesion()]
    .flatMap((a) => [a.titulo, a.texto])
    .concat(RESERVAR.revisarReserva({ llegada: "2026-12-03", salida: "2026-12-01" }).aviso);

  for (const texto of todos) assert.doesNotMatch(texto, /\b(usted|su cuenta|inicie|cree su|ingrese)\b/i, texto);
});
