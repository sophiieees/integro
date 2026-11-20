/* Casos de la lógica de la pantalla de registro (web/assets/js/registro-logica.js).
   Se corren con node, sin navegador ni API:  node --test tests/web
   Las respuestas de la API son las que documenta backend/README.md. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const JS = path.join(__dirname, "..", "..", "web", "assets", "js");
const REGISTRO = require(path.join(JS, "registro-logica.js"));
const PAISES = require(path.join(JS, "paises.js"));

const CORREO = "ana@prueba.invalid";
const error = (field, code, message, extra) => Object.assign({ errors: [{ field, code, message }] }, extra);
const valores = (cambios) => Object.assign({
  first_name: "Ana", last_name: "Torres López", email: CORREO, password: "Ejemplo-2026",
  marcacion: "52", numero: "55 1234 5678", country: "MX", birth_date: "1995-03-14", terminos: true,
}, cambios);

/* --- Los países y el teléfono -------------------------------------------- */

test("hay 247 países, todos con su código de dos letras, y solo cinco sin código de marcación", () => {
  assert.equal(PAISES.PAISES.length, 247);
  assert.ok(PAISES.PAISES.every(([codigo]) => /^[A-Z]{2}$/.test(codigo)));
  assert.equal(new Set(PAISES.PAISES.map(([codigo]) => codigo)).size, 247);
  assert.deepEqual(PAISES.PAISES.filter(([, marcacion]) => marcacion === 0).map(([codigo]) => codigo), ["AQ", "GS", "PN", "TF", "UM"]);
  assert.equal(PAISES.PRIMERO, "MX");
});

test("la lista de países da el nombre en español, con México primero y los demás en orden alfabético", () => {
  const lista = REGISTRO.listaDePaises(Intl.DisplayNames, "es");

  assert.equal(lista.length, 247);
  assert.deepEqual(lista[0], { codigo: "MX", nombre: "México", marcacion: 52 });
  const resto = lista.slice(1).map((pais) => pais.nombre);
  assert.deepEqual(resto, [...resto].sort((a, b) => a.localeCompare(b, "es")));
  assert.equal(lista.find((pais) => pais.codigo === "US").nombre, "Estados Unidos");
  assert.equal(lista.find((pais) => pais.codigo === "ES").nombre, "España");
});

test("sin Intl.DisplayNames el nombre es el código, y la lista sigue sirviendo", () => {
  const lista = REGISTRO.listaDePaises(null, "es");

  assert.equal(lista.length, 247);
  assert.equal(lista[0].codigo, "MX");
  assert.equal(lista.find((pais) => pais.codigo === "US").nombre, "US");
});

test("la lista del teléfono deja fuera los países sin código de marcación", () => {
  const lista = REGISTRO.paisesConMarcacion(REGISTRO.listaDePaises(Intl.DisplayNames, "es"));

  assert.equal(lista.length, 242);
  assert.ok(lista.every((pais) => pais.marcacion > 0));
  assert.equal(lista[0].codigo, "MX");
  assert.ok(!lista.some((pais) => pais.codigo === "AQ"));
});

test("al elegir el país de residencia, el código del teléfono pasa a ser el de ese país", () => {
  const lista = REGISTRO.listaDePaises(Intl.DisplayNames, "es");

  assert.equal(REGISTRO.marcacionParaElPais("ES", lista), "ES");
  assert.equal(REGISTRO.marcacionParaElPais("MX", lista), "MX");
  // Un país sin código de marcación no cambia el del teléfono.
  assert.equal(REGISTRO.marcacionParaElPais("AQ", lista), null);
  assert.equal(REGISTRO.marcacionParaElPais("ZZ", lista), null);
});

test("el teléfono se arma en formato internacional con el código y lo escrito", () => {
  assert.deepEqual(REGISTRO.telefono("52", "55 1234 5678"), { telefono: "+525512345678" });
  assert.deepEqual(REGISTRO.telefono(52, "(55) 1234-5678"), { telefono: "+525512345678" });
  assert.deepEqual(REGISTRO.telefono("1", "212.555.0100"), { telefono: "+12125550100" });
  assert.deepEqual(REGISTRO.telefono("34", "612345678"), { telefono: "+34612345678" });
  assert.deepEqual(REGISTRO.telefono("52", "  5512345678  "), { telefono: "+525512345678" });
});

test("el teléfono vacío, con letras, con + o de largo imposible se avisa", () => {
  assert.equal(REGISTRO.telefono("52", "").error, "Escribe tu número de teléfono.");
  assert.equal(REGISTRO.telefono("52", "   ").error, "Escribe tu número de teléfono.");
  assert.equal(REGISTRO.telefono("52", "55 abcd 5678").error, "El teléfono solo puede llevar números, espacios, guiones y paréntesis.");
  assert.equal(REGISTRO.telefono("52", "+52 55 1234 5678").error, "Escribe el número sin el código del país; el código se elige en la lista.");
  assert.equal(REGISTRO.telefono("", "5512345678").error, "Elige el código de marcación de tu país.");
  assert.equal(REGISTRO.telefono("0", "5512345678").error, "Elige el código de marcación de tu país.");
  assert.equal(REGISTRO.telefono("52", "12345").error, "El teléfono no tiene un formato válido.");
  assert.equal(REGISTRO.telefono("52", "1234567890123456").error, "El teléfono no tiene un formato válido.");
});

test("el largo del teléfono: de 8 a 15 dígitos contando el código, como la API", () => {
  // +52 más 6 dígitos son 8 en total; con 5 son 7.
  assert.equal(REGISTRO.telefono("52", "123456").telefono, "+52123456");
  assert.ok(REGISTRO.telefono("52", "12345").error);
  // +52 más 13 dígitos son 15 en total; con 14 son 16.
  assert.equal(REGISTRO.telefono("52", "1234567890123").telefono, "+521234567890123");
  assert.ok(REGISTRO.telefono("52", "12345678901234").error);
});

/* --- Antes de mandar ------------------------------------------------------- */

test("un formulario completo no tiene avisos y sus datos van listos para la API", () => {
  const r = REGISTRO.revisarDatos(valores({ first_name: "  Ana ", email: ` ${CORREO} ` }));

  assert.deepEqual(r.errores, {});
  assert.deepEqual(r.datos, {
    first_name: "Ana", last_name: "Torres López", email: CORREO, password: "Ejemplo-2026",
    phone: "+525512345678", country: "MX", birth_date: "1995-03-14", preferred_language: "es",
  });
});

test("cada dato vacío se avisa en su campo", () => {
  const r = REGISTRO.revisarDatos({ first_name: "", last_name: "  ", email: "", password: "", marcacion: "52", numero: "", country: "", birth_date: "", terminos: false });

  assert.deepEqual(r.errores, {
    first_name: ["Escribe tu nombre."],
    last_name: ["Escribe tus apellidos."],
    email: ["Escribe tu correo electrónico."],
    password: ["Escribe tu contraseña."],
    phone: ["Escribe tu número de teléfono."],
    country: ["Elige tu país de residencia."],
    birth_date: ["Escribe tu fecha de nacimiento."],
    terms: ["Para crear tu cuenta, acepta los términos y condiciones y el aviso de privacidad."],
  });
  assert.equal(REGISTRO.hayErrores(r.errores), true);
});

test("la contraseña no se recorta: los espacios los avisa la API", () => {
  assert.equal(REGISTRO.revisarDatos(valores({ password: " Ejemplo-26 " })).datos.password, " Ejemplo-26 ");
});

test("el correo mal escrito, los nombres larguísimos y la fecha rara se avisan", () => {
  for (const malo of ["ana", "ana@", "@x.com", "ana@x", "ana @x.com", "a".repeat(250) + "@x.com"]) {
    assert.deepEqual(REGISTRO.revisarDatos(valores({ email: malo })).errores.email, ["El correo electrónico no tiene un formato válido."], malo);
  }
  assert.deepEqual(REGISTRO.revisarDatos(valores({ first_name: "a".repeat(81) })).errores.first_name, ["El nombre admite hasta 80 caracteres."]);
  assert.deepEqual(REGISTRO.revisarDatos(valores({ last_name: "a".repeat(81) })).errores.last_name, ["Los apellidos admiten hasta 80 caracteres."]);
  assert.deepEqual(REGISTRO.revisarDatos(valores({ first_name: "a".repeat(80) })).errores, {});
  assert.deepEqual(REGISTRO.revisarDatos(valores({ birth_date: "14/03/1995" })).errores.birth_date, ["La fecha de nacimiento no es válida."]);
});

test("sin aceptar los términos no se manda, y la casilla no viaja a la API", () => {
  const sin = REGISTRO.revisarDatos(valores({ terminos: false }));
  const con = REGISTRO.revisarDatos(valores({ terminos: true }));

  assert.deepEqual(sin.errores, { terms: ["Para crear tu cuenta, acepta los términos y condiciones y el aviso de privacidad."] });
  assert.deepEqual(con.errores, {});
  // La API no recibe nada de la casilla: todavía no hay texto legal que registrar.
  assert.ok(!("terminos" in con.datos) && !("terms" in con.datos));
  assert.equal(REGISTRO.revisarDatos(valores({ terminos: undefined })).errores.terms.length, 1);
});

test("la casilla es lo último que se ve: el primer campo con aviso lo deja para el final", () => {
  assert.equal(REGISTRO.primerCampoConError({ terms: ["x"], birth_date: ["x"] }), "birth_date");
  assert.equal(REGISTRO.primerCampoConError({ terms: ["x"] }), "terms");
});

test("un aviso de la API para un campo «terms» no existe: sale arriba", () => {
  const r = REGISTRO.despuesDeRegistrar(422, error("terms", "invalid", "x"), CORREO);

  assert.deepEqual(r.errores, {});
  assert.equal(r.aviso, "x");
});

test("el primer campo con aviso es el primero que se ve en la pantalla", () => {
  assert.equal(REGISTRO.primerCampoConError({ birth_date: ["x"], email: ["x"] }), "email");
  assert.equal(REGISTRO.primerCampoConError({ phone: ["x"], country: ["x"] }), "phone");
  assert.equal(REGISTRO.primerCampoConError({}), null);
});

/* --- El indicador de la contraseña ---------------------------------------- */

const fortaleza = (cambios) => Object.assign({
  level: "medium", label: "Medio", weaknesses: [], hints: [], strengths: [], raise_hints: [],
  meets_rules: true, accepted: true, errors: [],
}, cambios);

test("lo que se manda a la API para calificar lleva el nombre y el correo", () => {
  assert.deepEqual(REGISTRO.cuerpoDeFortaleza(valores({ first_name: " Ana " })),
    { password: "Ejemplo-2026", first_name: "Ana", last_name: "Torres López", email: CORREO });
});

test("cada nivel llena sus cuadros: bajo 1, medio 2, confiable 3 y muy confiable 4", () => {
  const niveles = [["low", "Bajo", 1, "bajo"], ["medium", "Medio", 2, "medio"], ["reliable", "Confiable", 3, "confiable"], ["very_reliable", "Muy confiable", 4, "muy-confiable"]];
  for (const [level, label, segmentos, nivel] of niveles) {
    const vista = REGISTRO.vistaDeFortaleza(fortaleza({ level, label }), true);

    assert.deepEqual([vista.segmentos, vista.nivel, vista.etiqueta], [segmentos, nivel, label], level);
  }
});

test("sin contraseña, o sin respuesta de la API, el indicador queda vacío", () => {
  const vacio = { segmentos: 0, nivel: "", etiqueta: "", consejos: [], aceptada: false };

  assert.deepEqual(REGISTRO.vistaDeFortaleza(fortaleza(), false), vacio);
  assert.deepEqual(REGISTRO.vistaDeFortaleza(null, true), vacio);
  assert.deepEqual(REGISTRO.vistaDeFortaleza({ level: "inventado" }, true), vacio);
});

test("los consejos son primero lo que resta y después lo que suma", () => {
  const vista = REGISTRO.vistaDeFortaleza(fortaleza({
    hints: ["Evita repetir el mismo carácter tres veces seguidas."], raise_hints: ["Usa dos símbolos distintos para subir un nivel."],
  }), true);

  assert.deepEqual(vista.consejos, ["Evita repetir el mismo carácter tres veces seguidas.", "Usa dos símbolos distintos para subir un nivel."]);
  assert.equal(vista.aceptada, true);
});

test("si no cumple las reglas, los consejos son las reglas que faltan y no se acepta", () => {
  const vista = REGISTRO.vistaDeFortaleza(fortaleza({
    level: "low", label: "Bajo", meets_rules: false, accepted: false,
    errors: [{ field: "password", code: "too_short", message: "La contraseña debe tener al menos 10 caracteres." },
             { field: "password", code: "missing_digit", message: "La contraseña debe tener al menos un número." }],
    hints: ["no debe salir"],
  }), true);

  assert.deepEqual(vista.consejos, ["La contraseña debe tener al menos 10 caracteres.", "La contraseña debe tener al menos un número."]);
  assert.equal(vista.aceptada, false);
  assert.equal(vista.segmentos, 1);
});

test("una contraseña de nivel bajo que cumple las reglas no se acepta y dice por qué", () => {
  const vista = REGISTRO.vistaDeFortaleza(fortaleza({
    level: "low", label: "Bajo", accepted: false, hints: ["Evita secuencias como 1234, abcd o símbolos en fila del teclado."],
  }), true);

  assert.equal(vista.aceptada, false);
  assert.deepEqual(vista.consejos, ["Evita secuencias como 1234, abcd o símbolos en fila del teclado."]);
});

/* --- Después de mandar el formulario ------------------------------------------ */

test("cuenta creada: pasa al código y dice a qué correo se envió", () => {
  const r = REGISTRO.despuesDeRegistrar(201, { status: "verification_required", email: CORREO }, "ANA@prueba.invalid");

  assert.equal(r.paso, "codigo");
  assert.equal(r.correo, CORREO);
  assert.equal(r.texto, `Te enviamos un código de 6 dígitos a ${CORREO}. Escríbelo aquí para comprobar tu correo electrónico. Su vigencia es de 5 minutos.`);
  assert.deepEqual(r.errores, {});
  assert.equal(r.aviso, null);
});

test("datos que la API rechaza: cada aviso va en su campo, y los de contraseña pueden ser varios", () => {
  const r = REGISTRO.despuesDeRegistrar(422, { errors: [
    { field: "password", code: "too_short", message: "La contraseña debe tener al menos 10 caracteres." },
    { field: "password", code: "missing_digit", message: "La contraseña debe tener al menos un número." },
    { field: "birth_date", code: "under_age", message: "Hay que tener 18 años cumplidos para crear una cuenta." },
  ] }, CORREO);

  assert.equal(r.paso, "datos");
  assert.deepEqual(r.errores, {
    password: ["La contraseña debe tener al menos 10 caracteres.", "La contraseña debe tener al menos un número."],
    birth_date: ["Hay que tener 18 años cumplidos para crear una cuenta."],
  });
  assert.equal(r.aviso, null);
  assert.equal(r.yaTieneCuenta, false);
});

test("un aviso de un campo que la pantalla no tiene sale arriba", () => {
  const r = REGISTRO.despuesDeRegistrar(422, error("preferred_language", "invalid", "El idioma debe ser es o en."), CORREO);

  assert.deepEqual(r.errores, {});
  assert.equal(r.aviso, "El idioma debe ser es o en.");
});

test("correo o teléfono que ya tienen cuenta: aviso en su campo, y con el correo se ofrece iniciar sesión", () => {
  const correo = REGISTRO.despuesDeRegistrar(409, error("email", "already_registered", "Ya existe una cuenta con este correo."), CORREO);
  const telefono = REGISTRO.despuesDeRegistrar(409, error("phone", "already_registered", "Ya existe una cuenta con este teléfono."), CORREO);

  assert.deepEqual(correo.errores, { email: ["Ya existe una cuenta con este correo."] });
  assert.equal(correo.yaTieneCuenta, true);
  assert.deepEqual(telefono.errores, { phone: ["Ya existe una cuenta con este teléfono."] });
  assert.equal(telefono.yaTieneCuenta, false);
});

test("sin servidor, o con una respuesta rara, se avisa y se queda en el formulario", () => {
  assert.equal(REGISTRO.despuesDeRegistrar(0, null, CORREO).aviso, REGISTRO.SIN_SERVIDOR);
  assert.equal(REGISTRO.despuesDeRegistrar(500, null, CORREO).paso, "datos");
  assert.equal(REGISTRO.despuesDeRegistrar(500, null, CORREO).aviso, "El servidor respondió de forma inesperada. Inténtalo nuevamente.");
  assert.equal(REGISTRO.despuesDeRegistrar(422, { errors: [] }, CORREO).aviso, "El servidor respondió de forma inesperada. Inténtalo nuevamente.");
  assert.equal(REGISTRO.despuesDeRegistrar(201, { status: "otra-cosa" }, CORREO).paso, "datos");
});

/* --- El código del correo ------------------------------------------------------ */

test("código correcto: el correo queda comprobado", () => {
  assert.deepEqual(REGISTRO.despuesDeComprobar(200, { status: "verified" }), { paso: "listo", aviso: null, nota: null });
});

test("un correo que ya estaba comprobado también termina bien, con su nota", () => {
  const r = REGISTRO.despuesDeComprobar(409, error("email", "already_verified", "Este correo ya estaba comprobado."));

  assert.equal(r.paso, "listo");
  assert.equal(r.nota, "Tu correo electrónico ya estaba comprobado.");
});

test("código incorrecto: dice cuántos intentos quedan", () => {
  const cuatro = REGISTRO.despuesDeComprobar(400, error("code", "invalid_code", "...", { attempts_left: 4 }));
  const uno = REGISTRO.despuesDeComprobar(400, error("code", "invalid_code", "...", { attempts_left: 1 }));
  const cero = REGISTRO.despuesDeComprobar(400, error("code", "invalid_code", "...", { attempts_left: 0 }));

  assert.deepEqual(cuatro, { paso: "codigo", aviso: "El código ingresado no es correcto. Te quedan 4 intentos.", nota: null });
  assert.equal(uno.aviso, "El código ingresado no es correcto. Te queda 1 intento.");
  assert.equal(cero.aviso, "El código ingresado no es correcto. Ya no te quedan intentos. Solicita un código nuevo con «Enviar otro código».");
});

test("código vencido o agotado: se pide uno nuevo", () => {
  const vencido = REGISTRO.despuesDeComprobar(400, error("code", "code_expired", "..."));
  const agotado = REGISTRO.despuesDeComprobar(400, error("code", "too_many_attempts", "..."));

  assert.equal(vencido.paso, "codigo");
  assert.equal(vencido.aviso, "El código venció. Solicita uno nuevo con «Enviar otro código».");
  assert.equal(agotado.aviso, "Se agotaron los intentos con ese código. Solicita uno nuevo con «Enviar otro código».");
});

test("el código tiene que ser de 6 números antes de mandarse", () => {
  assert.equal(REGISTRO.revisarCodigo("").aviso, "Escribe el código que recibiste.");
  assert.equal(REGISTRO.revisarCodigo("12ab").aviso, "El código debe constar de 6 dígitos.");
  assert.equal(REGISTRO.revisarCodigo(" 123456 "), null);
});

test("sin servidor o con una respuesta rara, el paso del código se queda donde está", () => {
  assert.deepEqual(REGISTRO.despuesDeComprobar(0, null), { paso: "codigo", aviso: REGISTRO.SIN_SERVIDOR, nota: null });
  assert.equal(REGISTRO.despuesDeComprobar(500, null).paso, "codigo");
  assert.equal(REGISTRO.despuesDeComprobar(200, null).paso, "codigo");
});

/* --- Pedir otro código ----------------------------------------------------------- */

test("otro código enviado: se avisa a qué correo", () => {
  assert.deepEqual(REGISTRO.despuesDeReenviar(200, { status: "sent" }, CORREO),
    { enviado: true, aviso: null, nota: `Te enviamos un código nuevo a ${CORREO}.` });
});

test("otro código antes de un minuto: se dice cuántos segundos faltan", () => {
  assert.equal(REGISTRO.despuesDeReenviar(429, error("email", "wait", "...", { retry_after: 42 }), CORREO).aviso, "Espera 42 segundos para solicitar otro código.");
  assert.equal(REGISTRO.despuesDeReenviar(429, error("email", "wait", "...", { retry_after: 1 }), CORREO).aviso, "Espera 1 segundo para solicitar otro código.");
  assert.equal(REGISTRO.despuesDeReenviar(429, error("email", "wait", "..."), CORREO).aviso, "Espera 60 segundos para solicitar otro código.");
});

test("cinco códigos en una hora, sin servidor o con una respuesta rara", () => {
  assert.equal(REGISTRO.despuesDeReenviar(429, error("email", "hourly_limit", "..."), CORREO).aviso, "Has solicitado demasiados códigos. Inténtalo nuevamente más tarde.");
  assert.equal(REGISTRO.despuesDeReenviar(0, null, CORREO).aviso, REGISTRO.SIN_SERVIDOR);
  assert.equal(REGISTRO.despuesDeReenviar(500, null, CORREO).enviado, false);
});

/* --- El aviso de la contraseña no repite el indicador ---------------------------------- */

test("si la API rechaza la contraseña, en el campo va una sola línea que remite al indicador", () => {
  const errores = { password: ["La contraseña debe tener al menos 10 caracteres.", "La contraseña debe tener al menos un número."],
                    birth_date: ["Hay que tener 18 años cumplidos para crear una cuenta."] };

  const resumen = REGISTRO.resumirAvisos(errores);

  assert.deepEqual(resumen, { password: ["Tu contraseña aún no cumple lo que se indica abajo."], birth_date: errores.birth_date });
  assert.equal(REGISTRO.AVISO_CONTRASENA, "Tu contraseña aún no cumple lo que se indica abajo.");
  // No toca lo que recibió.
  assert.equal(errores.password.length, 2);
});

test("sin avisos de contraseña, los demás pasan tal cual", () => {
  assert.deepEqual(REGISTRO.resumirAvisos({ email: ["Ya existe una cuenta con este correo."] }), { email: ["Ya existe una cuenta con este correo."] });
  assert.deepEqual(REGISTRO.resumirAvisos({}), {});
});

/* --- Con sesión iniciada ----------------------------------------------------------- */

test("con sesión iniciada la pantalla lo dice con el nombre", () => {
  assert.equal(REGISTRO.avisoDeSesionIniciada("Ana"), "Ya iniciaste sesión como Ana. Para crear otra cuenta, primero cierra sesión.");
});
