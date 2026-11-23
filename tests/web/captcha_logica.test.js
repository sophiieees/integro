/* Casos de la lógica del CAPTCHA (web/assets/js/captcha-logica.js).
   Se corren con node, sin navegador ni API:  node --test tests/web
   Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016): Cloudflare Turnstile, siempre activo, en cinco acciones.
   Las respuestas de la API son las que documenta backend/README.md. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const WEB = path.join(__dirname, "..", "..", "web");
const LOGICA = require(path.join(WEB, "assets", "js", "captcha-logica.js"));

const captcha = (code) => ({ errors: [{ field: "captcha", code, message: "No pudimos comprobar que eres una persona. Inténtalo de nuevo." }] });

/* --- Las cinco acciones ------------------------------------------------- */

test("hay cinco acciones, distintas y con los caracteres que Cloudflare permite", () => {
  const acciones = Object.values(LOGICA.ACCIONES);
  assert.equal(acciones.length, 5);
  assert.equal(new Set(acciones).size, 5);
  for (const accion of acciones) assert.match(accion, /^[A-Za-z0-9_-]{1,32}$/, accion);
});

test("son las acciones que la API espera en cada ruta", () => {
  /* Las lee del archivo de la API: si allá cambia una, esta prueba lo dice. */
  const router = fs.readFileSync(path.join(WEB, "..", "backend", "app", "modules", "accounts", "router.py"), "utf-8");
  const enLaApi = [...router.matchAll(/require_captcha\("([a-z_]+)"\)/g)].map((m) => m[1]).sort();
  assert.deepEqual(Object.values(LOGICA.ACCIONES).sort(), enLaApi);
});

/* --- El widget ---------------------------------------------------------- */

test("el widget se pide escondido, con la llave, la acción y el idioma", () => {
  assert.deepEqual(LOGICA.opcionesDelWidget("0xLLAVE", "login"), {
    sitekey: "0xLLAVE", action: "login", appearance: "interaction-only", theme: "light", language: "es"
  });
});

test("el script es el de Cloudflare, por HTTPS, y el resultado viaja en el encabezado que la API lee", () => {
  assert.equal(LOGICA.URL_DEL_SCRIPT, "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit");
  assert.equal(LOGICA.ENCABEZADO, "X-Captcha-Token");
  assert.equal(LOGICA.RUTA_DE_LA_LLAVE, "/api/v1/auth/captcha");
});

test("la espera máxima del resultado es de unos segundos, no de minutos", () => {
  assert.ok(LOGICA.ESPERA_MAXIMA_MS >= 10000 && LOGICA.ESPERA_MAXIMA_MS <= 30000);
});

/* --- Qué se dice cuando falla ------------------------------------------- */

test("una respuesta de la API por el CAPTCHA, 400 o 503, tiene su aviso", () => {
  assert.equal(LOGICA.avisoDeCaptcha(400, captcha("captcha_failed")), LOGICA.AVISO);
  assert.equal(LOGICA.avisoDeCaptcha(503, captcha("captcha_unavailable")), LOGICA.AVISO);
});

test("lo que no fue por el CAPTCHA no se confunde con él", () => {
  assert.equal(LOGICA.avisoDeCaptcha(200, { status: "sent" }), null);
  assert.equal(LOGICA.avisoDeCaptcha(422, captcha("captcha_failed")), null);
  assert.equal(LOGICA.avisoDeCaptcha(429, captcha("captcha_failed")), null);
  assert.equal(LOGICA.avisoDeCaptcha(0, null), null);
  assert.equal(LOGICA.avisoDeCaptcha(400, null), null);
  assert.equal(LOGICA.avisoDeCaptcha(400, {}), null);
  assert.equal(LOGICA.avisoDeCaptcha(400, { errors: [] }), null);
  /* Un 400 de otro campo, por ejemplo el código del correo, no es del CAPTCHA. */
  assert.equal(LOGICA.avisoDeCaptcha(400, { errors: [{ field: "code", code: "invalid_code", message: "x" }] }), null);
  assert.equal(LOGICA.avisoDeCaptcha(503, { errors: [{ field: "database", code: "x", message: "x" }] }), null);
});

test("sin resultado que mandar se contesta con la misma forma que la API, con el aviso que toca", () => {
  const sinCargar = LOGICA.respuestaSinResultado(LOGICA.AVISO_SIN_CARGAR);
  assert.equal(sinCargar.status, 400);
  assert.equal(sinCargar.cuerpo.errors[0].field, "captcha");
  assert.equal(LOGICA.avisoDe(sinCargar.status, sinCargar.cuerpo), LOGICA.AVISO_SIN_CARGAR);

  const sinAviso = LOGICA.respuestaSinResultado();
  assert.equal(LOGICA.avisoDe(sinAviso.status, sinAviso.cuerpo), LOGICA.AVISO);
});

test("el aviso de una respuesta de la API es el de siempre y lo que no es del CAPTCHA no tiene aviso", () => {
  assert.equal(LOGICA.avisoDe(400, captcha("captcha_failed")), LOGICA.AVISO);
  assert.equal(LOGICA.avisoDe(503, captcha("captcha_unavailable")), LOGICA.AVISO);
  assert.equal(LOGICA.avisoDe(200, { status: "sent" }), null);
});

test("los textos están en tono formal de tú, nunca de usted, y dicen qué hacer", () => {
  for (const texto of [LOGICA.AVISO, LOGICA.AVISO_SIN_CARGAR]) {
    assert.doesNotMatch(texto, /\busted(es)?\b|\bIntente|\bRevise|\bsu (conexión|cuenta)\b/i, texto);
    assert.match(texto, /[Ii]nténtalo de nuevo\.$/);
  }
  assert.match(LOGICA.AVISO_SIN_CARGAR, /conexión/);
});

test("el aviso coincide, palabra por palabra, con el que contesta la API", () => {
  const api = fs.readFileSync(path.join(WEB, "..", "backend", "app", "api", "captcha.py"), "utf-8");
  assert.ok(api.includes('MESSAGE = "' + LOGICA.AVISO + '"'));
});
