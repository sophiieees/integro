/* Íntegro, lógica de recuperar la contraseña (sin pantalla)
   -------------------------------------------------------------------
   Decide qué se dice y qué sigue con cada respuesta de la API en la pantalla de
   recuperar la contraseña. No toca el documento ni llama a la API: eso lo hace
   recuperar.js. Así se prueba sin navegador, con node.

   La pantalla tiene tres pasos:
     "correo"  pide el correo         (POST /api/v1/auth/password-reset/request)
     "codigo"  pide el código de 6 dígitos y la contraseña nueva
                                      (POST /api/v1/auth/password-reset/confirm)
     "listo"   la contraseña cambió; hay que iniciar sesión de nuevo

   Decisiones de Sophia del 21 de noviembre de 2026: código de 6 dígitos que
   dura 30 minutos, y solo una cuenta con el correo comprobado puede recuperar
   la contraseña.

   El indicador de la contraseña es el del registro (registro-logica.js).
   Funciona en el navegador (window.INTEGRO_RECUPERAR) y en node (module.exports).
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = fabrica(require("./cuenta-logica.js"), require("./registro-logica.js"));
  } else {
    raiz.INTEGRO_RECUPERAR = fabrica(raiz.INTEGRO_CUENTA, raiz.INTEGRO_REGISTRO);
  }
})(typeof window !== "undefined" ? window : this, function (CUENTA, REGISTRO) {
  "use strict";

  var SIN_SERVIDOR = CUENTA.SIN_SERVIDOR;
  var RESPUESTA_RARA = "El servidor respondió de forma inesperada. Inténtalo nuevamente.";
  var CAMPOS = ["email", "code", "new_password"];
  var AVISO_CONTRASENA = "Tu contraseña aún no cumple lo que se indica abajo.";
  var AVISO_CONTRASENA_FACIL = "Tu contraseña es muy fácil de adivinar. Revisa los consejos de abajo.";

  function plural(n, uno, varios) { return n + " " + (n === 1 ? uno : varios); }

  function primerError(cuerpo) {
    return cuerpo && cuerpo.errors && cuerpo.errors.length ? cuerpo.errors[0] : null;
  }

  function hayErrores(errores) { return Object.keys(errores).length > 0; }

  /* El primer campo con aviso, en el orden de la pantalla, o null. */
  function primerCampoConError(errores) {
    for (var i = 0; i < CAMPOS.length; i++) if (errores[CAMPOS[i]]) return CAMPOS[i];
    return null;
  }

  /* Agrupa los avisos de la API por campo; los que la pantalla no tiene van aparte, en aviso. */
  function avisosPorCampo(cuerpo) {
    var errores = {};
    var sueltos = [];
    ((cuerpo && cuerpo.errors) || []).forEach(function (e) {
      if (CAMPOS.indexOf(e.field) !== -1) (errores[e.field] = errores[e.field] || []).push(e);
      else sueltos.push(e.message);
    });
    return { errores: errores, aviso: sueltos.length ? sueltos.join(" ") : null };
  }

  /* ---------- Lo escrito antes de mandarlo ---------- */

  function revisarCorreo(correo) {
    var c = (correo || "").trim();
    if (!c) return { campo: "email", aviso: "Escribe tu correo electrónico." };
    if (c.indexOf("@") < 1 || c.indexOf("@") === c.length - 1) {
      return { campo: "email", aviso: "El correo electrónico no tiene un formato válido." };
    }
    return null;
  }

  /* Devuelve los avisos por campo ({ campo: [texto] }); vacío si todo está bien. */
  function revisarCambio(codigo, contrasena) {
    var errores = {};
    var c = (codigo || "").trim();
    if (!c) errores.code = ["Escribe el código que recibiste."];
    else if (!/^[0-9]{6}$/.test(c)) errores.code = ["El código debe constar de 6 dígitos."];
    if (!contrasena) errores.new_password = ["Escribe tu contraseña nueva."];
    return errores;
  }

  /* ---------- Con cada respuesta de la API ---------- */

  function textoDelCodigo(correo) {
    return "Si " + correo + " tiene una cuenta con el correo electrónico comprobado, te enviamos un código de 6 dígitos. " +
      "Su vigencia es de 30 minutos. Si no llega, revisa tu carpeta de correo no deseado.";
  }

  /* Qué sigue después de pedir el código (y después de pedir otro). La API contesta lo mismo tenga o no
     cuenta ese correo; por eso el texto no promete que llegó. */
  function despuesDePedir(status, cuerpo, correo) {
    var base = { paso: "correo", errores: {}, aviso: null, texto: null, correo: correo };
    if (status === 0) { base.aviso = SIN_SERVIDOR; return base; }
    if (status === 200 && cuerpo && cuerpo.status === "code_requested") {
      base.paso = "codigo";
      base.texto = textoDelCodigo(correo);
      return base;
    }
    if (status === 422) {
      var avisos = avisosPorCampo(cuerpo);
      Object.keys(avisos.errores).forEach(function (campo) {
        base.errores[campo] = avisos.errores[campo].map(function (e) { return e.message; });
      });
      base.aviso = avisos.aviso;
      if (!hayErrores(base.errores) && !base.aviso) base.aviso = RESPUESTA_RARA;
      return base;
    }
    base.aviso = RESPUESTA_RARA;
    return base;
  }

  /* El aviso al pedir otro código estando ya en el paso del código. */
  function notaDeReenvio() {
    return "Si la cuenta existe, enviamos otro código. Debes esperar un minuto entre un envío y otro, y el código anterior deja de servir.";
  }

  /* Qué sigue después de mandar el código y la contraseña nueva. */
  function despuesDeCambiar(status, cuerpo) {
    var base = { paso: "codigo", errores: {}, aviso: null, pedirOtro: false };
    var error = primerError(cuerpo);
    var codigo = error ? error.code : null;
    if (status === 0) { base.aviso = SIN_SERVIDOR; return base; }
    if (status === 200 && cuerpo && cuerpo.status === "password_changed") { base.paso = "listo"; return base; }
    if (status === 400 && codigo === "invalid_code") {
      var quedan = cuerpo.attempts_left;
      var texto = "El código ingresado no es correcto.";
      if (typeof quedan === "number") {
        texto += quedan === 0
          ? " Ya no te quedan intentos con este código: pide uno nuevo."
          : " Te " + (quedan === 1 ? "queda" : "quedan") + " " + plural(quedan, "intento", "intentos") + ".";
        base.pedirOtro = quedan === 0;
      }
      base.errores.code = [texto];
      return base;
    }
    if (status === 400 && codigo === "code_expired") {
      base.errores.code = ["El código venció. Pide uno nuevo."];
      base.pedirOtro = true;
      return base;
    }
    if (status === 400 && codigo === "too_many_attempts") {
      base.errores.code = ["Se agotaron los intentos con ese código. Pide uno nuevo."];
      base.pedirOtro = true;
      return base;
    }
    if (status === 429 && codigo === "try_later") {
      base.aviso = "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en " + CUENTA.minutos(cuerpo.retry_after) + ".";
      return base;
    }
    if (status === 422) {
      var avisos = avisosPorCampo(cuerpo);
      Object.keys(avisos.errores).forEach(function (campo) {
        var lista = avisos.errores[campo];
        /* Lo que le falta a la contraseña, y los consejos para que no sea fácil de adivinar, los dice el
           indicador: en el campo va una sola línea que remite a él, no la misma lista dos veces. */
        if (campo === "new_password") {
          base.errores[campo] = [lista.some(function (e) { return e.code === "too_weak"; }) ? AVISO_CONTRASENA_FACIL : AVISO_CONTRASENA];
        } else {
          base.errores[campo] = lista.map(function (e) { return e.message; });
        }
      });
      base.aviso = avisos.aviso;
      if (!hayErrores(base.errores) && !base.aviso) base.aviso = RESPUESTA_RARA;
      return base;
    }
    base.aviso = (error && error.message) || RESPUESTA_RARA;
    return base;
  }

  /* La pantalla cuando ya hay una sesión iniciada. */
  function avisoDeSesionIniciada(nombre) {
    return "Ya iniciaste sesión como " + nombre + ". Para recuperar tu contraseña, primero cierra sesión.";
  }

  return {
    CAMPOS: CAMPOS,
    SIN_SERVIDOR: SIN_SERVIDOR,
    AVISO_CONTRASENA: AVISO_CONTRASENA,
    AVISO_CONTRASENA_FACIL: AVISO_CONTRASENA_FACIL,
    revisarCorreo: revisarCorreo,
    revisarCambio: revisarCambio,
    hayErrores: hayErrores,
    primerCampoConError: primerCampoConError,
    despuesDePedir: despuesDePedir,
    notaDeReenvio: notaDeReenvio,
    despuesDeCambiar: despuesDeCambiar,
    avisoDeSesionIniciada: avisoDeSesionIniciada,
    /* El indicador es el del registro. */
    cuerpoDeFortaleza: function (contrasena, correo) {
      return REGISTRO.cuerpoDeFortaleza({ password: contrasena, email: correo });
    },
    vistaDeFortaleza: REGISTRO.vistaDeFortaleza
  };
});
