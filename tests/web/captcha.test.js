/* Casos de captcha.js, el que dibuja el widget de Cloudflare Turnstile y entrega su resultado.
   Se corren con node, sin navegador:  node --test tests/web
   Un navegador de mentira (window, document y fetch) deja ver lo que cuesta ver en una pantalla: que el resultado sirva
   una sola vez, el tiempo agotado, la llave que no llega o el script de Cloudflare que no carga. La pantalla de verdad se
   prueba en tests/e2e/test_captcha_e2e.py. Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016). */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const JS = path.join(__dirname, "..", "..", "web", "assets", "js");
const LOGICA = require(path.join(JS, "captcha-logica.js"));
const RUTA = path.join(JS, "captcha.js");

const pasar = () => new Promise((resolver) => setImmediate(resolver));
const unaVezMas = async (veces = 5) => { for (let i = 0; i < veces; i++) await pasar(); };

/* Arma un navegador de mentira y carga captcha.js en él. opciones:
     llave        lo que contesta GET /captcha: "ok" (por defecto), 503 o "red" (la petición falla)
     turnstile    "puesto" (por defecto: ya está en la página), "carga" (se carga al pedirlo) o "falla" (no carga) */
function navegador(opciones = {}) {
  const registro = { fetch: [], renders: [], resets: [], scripts: [] };
  const ventana = {};
  let widgets = 0;
  const turnstile = {
    render(zona, datos) { const id = "w" + (++widgets); registro.renders.push({ id, zona, datos }); return id; },
    reset(id) { registro.resets.push(id); }
  };
  const modo = opciones.turnstile || "puesto";
  if (modo === "puesto") ventana.turnstile = turnstile;
  ventana.INTEGRO_CAPTCHA_LOGICA = LOGICA;
  global.window = ventana;
  global.document = {
    createElement: (nombre) => ({ nombre, remove() { this.quitado = true; } }),
    head: {
      appendChild(etiqueta) {
        registro.scripts.push(etiqueta);
        setImmediate(() => {
          if (modo === "carga") { ventana.turnstile = turnstile; etiqueta.onload(); } else etiqueta.onerror();
        });
      }
    }
  };
  let intento = 0;
  global.fetch = (ruta, datos) => {
    registro.fetch.push({ ruta, datos });
    intento += 1;
    const llave = Array.isArray(opciones.llave) ? opciones.llave[Math.min(intento, opciones.llave.length) - 1] : opciones.llave;
    if (llave === "red") return Promise.reject(new TypeError("sin red"));
    if (llave === 503) return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({ errors: [] }) });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ site_key: "0xLLAVE-PUBLICA" }) });
  };
  delete require.cache[require.resolve(RUTA)];
  require(RUTA);
  return { ventana, registro, captcha: ventana.INTEGRO_CAPTCHA };
}

/* Una zona como la del HTML: un div con data-captcha="<acción>". */
const zona = (accion) => ({ accion, getAttribute: (nombre) => (nombre === "data-captcha" ? accion : null) });

/* --- Dibujar el widget -------------------------------------------------- */

test("dibuja el widget con la llave que da la API, la acción y el modo escondido", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("register");

  await captcha.preparar(aqui);

  assert.equal(registro.fetch.length, 1);
  assert.equal(registro.fetch[0].ruta, "/api/v1/auth/captcha");
  assert.equal(registro.fetch[0].datos.credentials, "same-origin");
  assert.equal(registro.renders.length, 1);
  assert.equal(registro.renders[0].zona, aqui);
  const { datos } = registro.renders[0];
  assert.equal(datos.sitekey, "0xLLAVE-PUBLICA");
  assert.equal(datos.action, "register");
  assert.equal(datos.appearance, "interaction-only");
  assert.equal(typeof datos.callback, "function");
  assert.equal(typeof datos["error-callback"], "function");
});

test("una zona se dibuja una sola vez, aunque se prepare muchas veces", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("register");

  await Promise.all([captcha.preparar(aqui), captcha.preparar(aqui)]);
  await captcha.preparar(aqui);

  assert.equal(registro.renders.length, 1);
  assert.equal(registro.fetch.length, 1);
});

test("dos zonas comparten la llave y el script: se piden una sola vez", async () => {
  const { captcha, registro } = navegador({ turnstile: "carga" });

  await Promise.all([captcha.preparar(zona("resend_code")), captcha.preparar(zona("correct_email"))]);

  assert.equal(registro.fetch.length, 1);
  assert.equal(registro.scripts.length, 1);
  assert.equal(registro.renders.length, 2);
  assert.deepEqual(registro.renders.map((r) => r.datos.action), ["resend_code", "correct_email"]);
});

test("si Cloudflare ya está en la página no se vuelve a cargar su script", async () => {
  const { captcha, registro } = navegador({ turnstile: "puesto" });

  await captcha.preparar(zona("resend_code"));

  assert.equal(registro.scripts.length, 0);
});

test("una zona sin una acción que la API conozca no se dibuja y se avisa que no cargó", async () => {
  const { captcha, registro } = navegador();

  for (const accion of [null, "", "otra_cosa", "REGISTER"]) {
    assert.deepEqual(await captcha.obtener(zona(accion)), { token: null, aviso: LOGICA.AVISO_SIN_CARGAR }, String(accion));
  }
  assert.equal(registro.renders.length, 0);
  assert.equal(registro.fetch.length, 0, "ni siquiera se pide la llave");
});

test("la acción del widget es la que declara su zona, para cada una de las cinco", async () => {
  const { captcha, registro } = navegador();
  const acciones = Object.values(LOGICA.ACCIONES);

  await Promise.all(acciones.map((accion) => captcha.preparar(zona(accion))));

  assert.deepEqual(registro.renders.map((r) => r.datos.action).sort(), [...acciones].sort());
});

test("el script de Cloudflare se carga de su dirección, de forma asíncrona, cuando hace falta", async () => {
  const { captcha, registro } = navegador({ turnstile: "carga" });

  await captcha.preparar(zona("resend_code"));

  assert.equal(registro.scripts.length, 1);
  assert.equal(registro.scripts[0].src, "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit");
  assert.equal(registro.scripts[0].async, true);
  assert.equal(registro.renders.length, 1);
});

/* --- Entregar el resultado ---------------------------------------------- */

test("espera el resultado del desafío y lo entrega", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  assert.equal(respuesta, null, "todavía no hay resultado");

  registro.renders[0].datos.callback("RESULTADO-1");
  await unaVezMas();

  assert.deepEqual(respuesta, { token: "RESULTADO-1", aviso: null });
});

test("si el resultado ya está, se entrega al momento", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);
  registro.renders[0].datos.callback("LISTO");

  assert.deepEqual(await captcha.obtener(aqui), { token: "LISTO", aviso: null });
});

test("un resultado sirve una sola vez: al entregarlo se reinicia el widget y el siguiente es otro", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);
  registro.renders[0].datos.callback("UNO");

  const primero = await captcha.obtener(aqui);
  assert.equal(primero.token, "UNO");
  assert.deepEqual(registro.resets, ["w1"]);

  let segundo = null;
  captcha.obtener(aqui).then((r) => { segundo = r; });
  await unaVezMas();
  assert.equal(segundo, null, "el mismo resultado no se entrega dos veces");

  registro.renders[0].datos.callback("DOS");
  await unaVezMas();
  assert.equal(segundo.token, "DOS");
  assert.deepEqual(registro.resets, ["w1", "w1"]);
});

test("obtener dibuja el widget si nadie lo había preparado", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("register");

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  registro.renders[0].datos.callback("TARDE");
  await unaVezMas();

  assert.equal(respuesta.token, "TARDE");
  assert.equal(registro.renders[0].datos.action, "register");
});

test("un resultado vencido ya no se entrega", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);
  registro.renders[0].datos.callback("VIEJO");
  registro.renders[0].datos["expired-callback"]();

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  assert.equal(respuesta, null);

  registro.renders[0].datos.callback("NUEVO");
  await unaVezMas();
  assert.equal(respuesta.token, "NUEVO");
});

test("cada zona entrega solo sus resultados", async () => {
  const { captcha, registro } = navegador();
  const a = zona("resend_code");
  const b = zona("correct_email");
  await Promise.all([captcha.preparar(a), captcha.preparar(b)]);
  registro.renders[0].datos.callback("DE-A");
  registro.renders[1].datos.callback("DE-B");

  assert.equal((await captcha.obtener(b)).token, "DE-B");
  assert.equal((await captcha.obtener(a)).token, "DE-A");
});

/* --- Cuando algo sale mal ----------------------------------------------- */

test("si el desafío falla, se avisa y no se manda nada; el siguiente intento lo vuelve a empezar", async () => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  registro.renders[0].datos["error-callback"]("300030");
  await unaVezMas();
  assert.deepEqual(respuesta, { token: null, aviso: LOGICA.AVISO });

  const reiniciosAntes = registro.resets.length;
  let otra = null;
  captcha.obtener(aqui).then((r) => { otra = r; });
  await unaVezMas();
  assert.equal(registro.resets.length, reiniciosAntes + 1, "se reinició el widget para intentar otra vez");
  registro.renders[0].datos.callback("YA-SI");
  await unaVezMas();
  assert.equal(otra.token, "YA-SI");
});

test("el error de Cloudflare devuelve verdadero, para que el navegador no llene la consola", async () => {
  const { captcha, registro } = navegador();
  await captcha.preparar(zona("resend_code"));

  assert.equal(registro.renders[0].datos["error-callback"](), true);
});

test("si el resultado no llega en el tiempo máximo, se rinde con un aviso y deja de esperar", async (t) => {
  const { captcha, registro } = navegador();
  const aqui = zona("login");
  await captcha.preparar(aqui);
  t.mock.timers.enable({ apis: ["setTimeout"] });

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  t.mock.timers.tick(LOGICA.ESPERA_MAXIMA_MS - 1);
  await unaVezMas();
  assert.equal(respuesta, null);
  t.mock.timers.tick(1);
  await unaVezMas();

  assert.deepEqual(respuesta, { token: null, aviso: LOGICA.AVISO });
  /* Un resultado que llega después no se entrega a nadie: queda para la próxima petición. */
  registro.renders[0].datos.callback("TARDE");
  assert.deepEqual(await captcha.obtener(aqui), { token: "TARDE", aviso: null });
});

test("si la API no da la llave, se avisa que no cargó la comprobación; después vuelve a intentarlo", async () => {
  const { captcha, registro } = navegador({ llave: [503, "ok"] });
  const aqui = zona("register");

  const primera = await captcha.obtener(aqui);
  assert.deepEqual(primera, { token: null, aviso: LOGICA.AVISO_SIN_CARGAR });
  assert.equal(registro.renders.length, 0);

  let segunda = null;
  captcha.obtener(aqui).then((r) => { segunda = r; });
  await unaVezMas();
  assert.equal(registro.fetch.length, 2, "la llave se pidió otra vez");
  registro.renders[0].datos.callback("YA");
  await unaVezMas();
  assert.equal(segunda.token, "YA");
});

test("si la API no contesta, no se manda nada y se dice que no hay servidor, no que falló el CAPTCHA", async () => {
  const { captcha, registro } = navegador({ llave: "red" });

  assert.deepEqual(await captcha.obtener(zona("resend_code")), { token: null, aviso: null, sinServidor: true });
  assert.equal(registro.renders.length, 0);
});

test("cuando vuelve la red, la llave se pide otra vez y todo funciona", async () => {
  const { captcha, registro } = navegador({ llave: ["red", "ok"] });
  const aqui = zona("login");

  assert.equal((await captcha.obtener(aqui)).sinServidor, true);

  let respuesta = null;
  captcha.obtener(aqui).then((r) => { respuesta = r; });
  await unaVezMas();
  registro.renders[0].datos.callback("YA-HAY-RED");
  await unaVezMas();

  assert.deepEqual(respuesta, { token: "YA-HAY-RED", aviso: null });
});

test("que la API conteste 503 no es no tener servidor: es que el CAPTCHA no cargó", async () => {
  const { captcha } = navegador({ llave: 503 });

  assert.deepEqual(await captcha.obtener(zona("login")), { token: null, aviso: LOGICA.AVISO_SIN_CARGAR });
});

test("si el script de Cloudflare no carga, se avisa y se quita; después se vuelve a cargar", async () => {
  const { captcha, registro } = navegador({ turnstile: "falla" });

  assert.deepEqual(await captcha.obtener(zona("resend_code")), { token: null, aviso: LOGICA.AVISO_SIN_CARGAR });
  assert.equal(registro.scripts[0].quitado, true);
  assert.equal(registro.renders.length, 0);

  await captcha.obtener(zona("resend_code"));
  assert.equal(registro.scripts.length, 2, "se intentó cargar otra vez");
});

test("una llave que no es un texto no sirve", async () => {
  navegador();
  global.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ site_key: 123 }) });
  delete require.cache[require.resolve(RUTA)];
  require(RUTA);
  const captcha = global.window.INTEGRO_CAPTCHA;

  assert.deepEqual(await captcha.obtener(zona("resend_code")), { token: null, aviso: LOGICA.AVISO_SIN_CARGAR });
});

test("la promesa nunca falla: siempre se cumple, con resultado o con aviso", async () => {
  const { captcha } = navegador({ llave: "red" });

  await assert.doesNotReject(captcha.obtener(zona("resend_code")));
  await assert.doesNotReject(captcha.preparar(zona("correct_email")));
});

test("sin la lógica no se hace nada", () => {
  global.window = {};
  delete require.cache[require.resolve(RUTA)];
  require(RUTA);

  assert.equal(global.window.INTEGRO_CAPTCHA, undefined);
});
