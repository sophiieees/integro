/* Íntegro, lógica del CAPTCHA (sin pantalla)
   -------------------------------------------------------------------
   Decisiones de Sophia del 22 de noviembre de 2026 (ADR 0016): Cloudflare Turnstile, siempre activo, en cinco
   acciones. Este archivo guarda lo que no toca el documento: cuál es la acción de cada pantalla, cómo se pide el
   widget y qué se le dice a la persona cuando no se pudo comprobar. captcha.js dibuja el widget y espera el
   resultado; cada pantalla (cuenta.js, registro.js, recuperar.js) manda ese resultado a la API en el encabezado
   X-Captcha-Token. Así se prueba sin navegador, con node.

   Funciona en el navegador (window.INTEGRO_CAPTCHA_LOGICA) y en node (module.exports).
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.INTEGRO_CAPTCHA_LOGICA = fabrica();
})(typeof window !== "undefined" ? window : this, function () {
  "use strict";

  /* La acción que declara el widget de cada pantalla. La API espera la suya en cada ruta (app/modules/accounts/router.py)
     y rechaza un resultado hecho para otra. */
  var ACCIONES = {
    registrar: "register",
    iniciarSesion: "login",
    recuperar: "password_reset",
    reenviar: "resend_code",
    corregirCorreo: "correct_email"
  };

  /* La zona de cada pantalla declara su acción en el HTML (data-captcha="register"): es la única fuente. */
  function esAccion(valor) {
    return Object.keys(ACCIONES).some(function (nombre) { return ACCIONES[nombre] === valor; });
  }

  var RUTA_DE_LA_LLAVE = "/api/v1/auth/captcha";
  var URL_DEL_SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  var ENCABEZADO = "X-Captcha-Token";
  /* Lo más que se espera un resultado antes de rendirse: el desafío casi siempre se resuelve solo en un instante. */
  var ESPERA_MAXIMA_MS = 20000;

  var AVISO = "No pudimos comprobar que eres una persona. Inténtalo de nuevo.";
  var AVISO_SIN_CARGAR = "No pudimos cargar la comprobación de que eres una persona. Revisa tu conexión e inténtalo de nuevo.";

  /* Cómo se pide el widget. «interaction-only» lo deja escondido y solo aparece si Cloudflare necesita que la persona
     haga algo (Sophia quiere que casi nunca estorbe). */
  function opcionesDelWidget(llave, accion) {
    return { sitekey: llave, action: accion, appearance: "interaction-only", theme: "light", language: "es" };
  }

  /* El aviso de una respuesta de la API que fue por el CAPTCHA, o null si fue por otra cosa. La API contesta 400
     (no lo resolvió, venció o ya se usó) o 503 (no se pudo comprobar con Cloudflare) con el campo «captcha». */
  function avisoDeCaptcha(status, cuerpo) {
    if (status !== 400 && status !== 503) return null;
    var errores = cuerpo && cuerpo.errors;
    if (!errores || !errores.length || errores[0].field !== "captcha") return null;
    return AVISO;
  }

  /* Cuando no hubo resultado que mandar (el widget falló, o se agotó la espera), se contesta con la misma forma que la
     API, para que cada pantalla lo trate en un solo lugar. */
  function respuestaSinResultado(aviso) {
    return {
      status: 400,
      cuerpo: { errors: [{ field: "captcha", code: "captcha_failed", message: aviso || AVISO }], aviso: aviso || AVISO }
    };
  }

  /* El aviso que se muestra, venga de la API o de que no hubo resultado que mandar. */
  function avisoDe(status, cuerpo) {
    var aviso = avisoDeCaptcha(status, cuerpo);
    if (!aviso) return null;
    return (cuerpo && cuerpo.aviso) || aviso;
  }

  return {
    ACCIONES: ACCIONES,
    esAccion: esAccion,
    RUTA_DE_LA_LLAVE: RUTA_DE_LA_LLAVE,
    URL_DEL_SCRIPT: URL_DEL_SCRIPT,
    ENCABEZADO: ENCABEZADO,
    ESPERA_MAXIMA_MS: ESPERA_MAXIMA_MS,
    AVISO: AVISO,
    AVISO_SIN_CARGAR: AVISO_SIN_CARGAR,
    opcionesDelWidget: opcionesDelWidget,
    avisoDeCaptcha: avisoDeCaptcha,
    respuestaSinResultado: respuestaSinResultado,
    avisoDe: avisoDe
  };
});
