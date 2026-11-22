/* Casos de la lógica de la ventana de «Iniciar sesión» (web/assets/js/cuenta-logica.js).
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
  assert.deepEqual(LOGICA.revisarCorreoYContrasena("", "x"), { campo: "email", aviso: "Escribe tu correo electrónico." });
  assert.deepEqual(LOGICA.revisarCorreoYContrasena("   ", "x"), { campo: "email", aviso: "Escribe tu correo electrónico." });
  assert.equal(LOGICA.revisarCorreoYContrasena("ana", "x").campo, "email");
  assert.equal(LOGICA.revisarCorreoYContrasena("@x", "x").campo, "email");
  assert.equal(LOGICA.revisarCorreoYContrasena("ana@", "x").campo, "email");
  assert.deepEqual(LOGICA.revisarCorreoYContrasena(CORREO, ""), { campo: "password", aviso: "Escribe tu contraseña." });
  assert.equal(LOGICA.revisarCorreoYContrasena(CORREO, "Ejemplo-2026"), null);
  assert.equal(LOGICA.revisarCorreoYContrasena("  " + CORREO + " ", "x"), null);
});

test("el código tiene que ser de 6 números", () => {
  assert.equal(LOGICA.revisarCodigo("").campo, "code");
  assert.equal(LOGICA.revisarCodigo("12345").aviso, "El código debe constar de 6 dígitos.");
  assert.equal(LOGICA.revisarCodigo("1234567").aviso, "El código debe constar de 6 dígitos.");
  assert.equal(LOGICA.revisarCodigo("12345a").aviso, "El código debe constar de 6 dígitos.");
  assert.equal(LOGICA.revisarCodigo(" 123456 "), null);
  assert.equal(LOGICA.revisarCodigo("000000"), null);
});

/* --- Caso 1: correo y contraseña correctos ------------------------------ */

test("correctos: pasa al código y dice a qué correo se envió", () => {
  const r = LOGICA.despuesDelCorreo(200, { status: "code_required" }, CORREO);

  assert.equal(r.paso, "codigo");
  assert.equal(r.campo, "code");
  assert.equal(r.aviso, null);
  assert.equal(r.texto, `Te enviamos un código de 6 dígitos a ${CORREO}. Su vigencia es de 5 minutos.`);
});

/* --- Caso 2: contraseña incorrecta -------------------------------------- */

test("contraseña incorrecta o correo sin cuenta: aviso y se queda en el paso 1", () => {
  const r = LOGICA.despuesDelCorreo(401, error("credentials", "invalid_credentials", "El correo electrónico o la contraseña no son correctos."), CORREO);

  assert.deepEqual(r, { paso: "correo", campo: "password", aviso: "El correo electrónico o la contraseña no son correctos." });
});

/* --- Caso 3: correo sin comprobar --------------------------------------- */

test("correo sin comprobar: aviso de comprobarlo", () => {
  const r = LOGICA.despuesDelCorreo(403, error("email", "email_not_verified", "..."), CORREO);

  assert.equal(r.paso, "correo");
  assert.equal(r.campo, "email");
  assert.match(r.aviso, /comprobado tu correo electrónico/);
});

/* --- Caso 4: demasiados intentos ---------------------------------------- */

test("espera por dispositivo: aviso con los minutos que faltan", () => {
  const r = LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 900 }), CORREO);

  assert.equal(r.paso, "correo");
  assert.equal(r.aviso, "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en 15 minutos.");
  assert.equal(LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 61 }), CORREO).aviso,
    "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en 2 minutos.");
  assert.equal(LOGICA.despuesDelCorreo(429, error("credentials", "try_later", "...", { retry_after: 30 }), CORREO).aviso,
    "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en 1 minuto.");
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

  assert.deepEqual(cuatro, { paso: "codigo", campo: "code", aviso: "El código ingresado no es correcto. Te quedan 4 intentos." });
  assert.equal(uno.aviso, "El código ingresado no es correcto. Te queda 1 intento.");
});

test("código incorrecto sin intentos: vuelve al paso 1", () => {
  const r = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "...", { attempts_left: 0 }));

  assert.equal(r.paso, "correo");
  assert.equal(r.aviso, "El código ingresado no es correcto. Ya no te quedan intentos.");
});

test("código incorrecto sin el dato de intentos (sin paso 1 previo): solo el aviso", () => {
  const r = LOGICA.despuesDelCodigo(400, error("code", "invalid_code", "..."));

  assert.deepEqual(r, { paso: "codigo", campo: "code", aviso: "El código ingresado no es correcto." });
});

test("código vencido o agotado: aviso y vuelve al paso 1", () => {
  const vencido = LOGICA.despuesDelCodigo(400, error("code", "code_expired", "..."));
  const agotado = LOGICA.despuesDelCodigo(400, error("code", "too_many_attempts", "..."));

  assert.equal(vencido.paso, "correo");
  assert.match(vencido.aviso, /venció/);
  assert.equal(agotado.paso, "correo");
  assert.match(agotado.aviso, /Se agotaron los intentos/);
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
  const r = LOGICA.estadoDeCabecera(200, { first_name: "Ana", last_name: "Torres", email: CORREO, csrf_token: "clave-de-la-pagina" });

  assert.deepEqual(r, {
    sesion: true, nombre: "Ana", apellidos: "Torres", correo: CORREO, clave: "clave-de-la-pagina", servidor: true,
    esAnfitrion: false, esAdmin: false
  });
});

test("sin sesión la cabecera muestra «Iniciar sesión»", () => {
  assert.deepEqual(LOGICA.estadoDeCabecera(401, { errors: [{ code: "not_authenticated" }] }), {
    sesion: false, nombre: null, apellidos: "", correo: "", clave: null, servidor: true, esAnfitrion: false, esAdmin: false
  });
});

/* --- Caso 8b: las vistas -------------------------------------------------- */

const ME = { first_name: "Ana", last_name: "Torres", email: CORREO, csrf_token: "c" };
const estadoCon = (extra) => LOGICA.estadoDeCabecera(200, Object.assign({}, ME, extra));

test("is_host e is_admin de /auth/me dicen qué vistas tiene la persona", () => {
  assert.deepEqual(
    [estadoCon({}), estadoCon({ is_host: true }), estadoCon({ is_admin: true }), estadoCon({ is_host: true, is_admin: true })]
      .map((e) => [e.esAnfitrion, e.esAdmin]),
    [[false, false], [true, false], [false, true], [true, true]]
  );
});

test("solo un true de verdad cuenta: «true», 1 o un texto no hacen a nadie anfitrión ni administrador", () => {
  for (const raro of ["true", 1, "si", {}, [], null]) {
    const e = estadoCon({ is_host: raro, is_admin: raro });

    assert.deepEqual([e.esAnfitrion, e.esAdmin], [false, false], String(raro));
  }
});

test("la vista: visitante, cliente, anfitrión o administrador", () => {
  assert.equal(LOGICA.vistaDe(LOGICA.estadoDeCabecera(401, null), null), "visitante");
  assert.equal(LOGICA.vistaDe(LOGICA.estadoDeCabecera(0, null), null), "visitante");
  assert.equal(LOGICA.vistaDe(estadoCon({}), null), "cliente");
  assert.equal(LOGICA.vistaDe(estadoCon({ is_host: true }), null), "anfitrion");
  assert.equal(LOGICA.vistaDe(estadoCon({ is_admin: true }), null), "administrador");
  assert.equal(LOGICA.vistaDe(estadoCon({ is_admin: true, is_host: true }), null), "administrador");
});

test("un administrador puede elegir mirar como cliente o como anfitrión; no como otra cosa", () => {
  const admin = estadoCon({ is_admin: true });

  assert.equal(LOGICA.vistaDe(admin, "cliente"), "cliente");
  assert.equal(LOGICA.vistaDe(admin, "anfitrion"), "anfitrion");
  for (const raro of ["administrador", "visitante", "otra", "", undefined, null, "toString"]) {
    assert.equal(LOGICA.vistaDe(admin, raro), "administrador", String(raro));
  }
});

test("lo que alguien dejó elegido no sirve si no es administrador", () => {
  assert.equal(LOGICA.vistaDe(estadoCon({}), "anfitrion"), "cliente");
  assert.equal(LOGICA.vistaDe(estadoCon({ is_host: true }), "cliente"), "anfitrion");
  assert.equal(LOGICA.vistaDe(LOGICA.estadoDeCabecera(401, null), "anfitrion"), "visitante");
});

/* --- Caso 8c: las páginas protegidas -------------------------------------- */

const visitante = LOGICA.estadoDeCabecera(401, null);

test("una página sin data-requiere la ve cualquiera", () => {
  assert.deepEqual(LOGICA.permisoDePagina(null, visitante), { permitido: true });
  assert.deepEqual(LOGICA.permisoDePagina("", visitante), { permitido: true });
});

test("sin sesión, las tres páginas piden iniciar sesión", () => {
  for (const requiere of ["sesion", "anfitrion", "administrador"]) {
    const r = LOGICA.permisoDePagina(requiere, visitante);

    assert.equal(r.permitido, false, requiere);
    assert.equal(r.titulo, "Inicia sesión para continuar", requiere);
    assert.deepEqual(r.accion, { texto: "Iniciar sesión", iniciarSesion: true }, requiere);
  }
});

test("«Mi cuenta» la ve cualquiera con sesión", () => {
  for (const extra of [{}, { is_host: true }, { is_admin: true }]) {
    assert.equal(LOGICA.permisoDePagina("sesion", estadoCon(extra)).permitido, true);
  }
});

test("el espacio del anfitrión lo ven el anfitrión y el equipo; un cliente recibe una explicación y el camino", () => {
  assert.equal(LOGICA.permisoDePagina("anfitrion", estadoCon({ is_host: true })).permitido, true);
  assert.equal(LOGICA.permisoDePagina("anfitrion", estadoCon({ is_admin: true })).permitido, true);
  const cliente = LOGICA.permisoDePagina("anfitrion", estadoCon({}));

  assert.equal(cliente.permitido, false);
  assert.equal(cliente.titulo, "Esta sección es para anfitriones");
  assert.deepEqual(cliente.accion, { texto: "Conviértete en anfitrión", href: "anfitriones.html" });
});

test("la administración la ve solo el equipo; un anfitrión o un cliente reciben una explicación", () => {
  assert.equal(LOGICA.permisoDePagina("administrador", estadoCon({ is_admin: true })).permitido, true);
  for (const extra of [{}, { is_host: true }]) {
    const r = LOGICA.permisoDePagina("administrador", estadoCon(extra));

    assert.equal(r.permitido, false);
    assert.equal(r.titulo, "Esta sección es solo para el equipo de Íntegro");
    assert.deepEqual(r.accion, { texto: "Volver al inicio", href: "index.html" });
  }
});

test("sin servidor no se sabe quién es: la página lo dice y no muestra nada", () => {
  const r = LOGICA.permisoDePagina("administrador", LOGICA.estadoDeCabecera(0, null));

  assert.equal(r.permitido, false);
  assert.equal(r.texto, LOGICA.SIN_SERVIDOR);
  assert.equal(LOGICA.permisoDePagina("sesion", undefined).permitido, false);
});

test("un requiere que no se conoce no abre la página, ni con sesión ni siendo administrador", () => {
  for (const estado of [visitante, estadoCon({}), estadoCon({ is_admin: true })]) {
    assert.equal(LOGICA.permisoDePagina("otra-cosa", estado).permitido, false);
  }
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

/* --- A dónde se va al terminar de iniciar sesión (decisiones de Sophia del 21 de noviembre de 2026) ---------------- */

test("desde el registro y desde recuperar la contraseña se va a la portada", () => {
  assert.deepEqual(LOGICA.destinoTrasIniciarSesion("/registro.html", null), { ir: true, destino: "index.html" });
  assert.deepEqual(LOGICA.destinoTrasIniciarSesion("/recuperar-contrasena.html", ""), { ir: true, destino: "index.html" });
});

test("desde cualquier otra página no se mueve", () => {
  for (const ruta of ["/index.html", "/", "/propiedad.html", "/mi-cuenta.html", "/anfitrion.html", "/administracion.html"]) {
    assert.deepEqual(LOGICA.destinoTrasIniciarSesion(ruta, null), { ir: false, destino: null }, ruta);
  }
});

test("una página de regreso permitida manda sobre lo demás; una que no vale se ignora", () => {
  const permitida = LOGICA.PAGINAS_DE_REGRESO[0];
  assert.deepEqual(LOGICA.destinoTrasIniciarSesion("/registro.html", permitida), { ir: true, destino: permitida });
  assert.deepEqual(LOGICA.destinoTrasIniciarSesion("/registro.html", "https://malo.invalid/"), { ir: true, destino: "index.html" });
  assert.deepEqual(LOGICA.destinoTrasIniciarSesion("/propiedad.html", "//malo.invalid"), { ir: false, destino: null });
});

test("el aviso de inicio dice el nombre", () => {
  assert.equal(LOGICA.avisoDeInicio("Ana"), "Iniciaste sesión como Ana.");
});
