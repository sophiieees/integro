/* Íntegro, lógica de la cuenta (sin pantalla)
   -------------------------------------------------------------------
   Decide qué pasa en la ventana de «Entrar» con cada respuesta de la API y
   qué texto se le muestra a la persona. No toca el documento ni llama a la
   API: eso lo hace cuenta.js. Así se prueba sin navegador, con node.

   La ventana tiene tres pasos:
     "correo"  pide correo y contraseña  (POST /api/v1/auth/login)
     "codigo"  pide el código de 6 dígitos (POST /api/v1/auth/login/verify)
     "dentro"  la sesión quedó abierta y la ventana se cierra

   Funciona en el navegador (window.INTEGRO_CUENTA) y en node (module.exports).
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.INTEGRO_CUENTA = fabrica();
})(typeof window !== "undefined" ? window : this, function () {
  "use strict";

  var SIN_SERVIDOR = "No hay conexión con la API de Íntegro. Arranca el servidor y abre la página desde http://127.0.0.1:8000/.";
  var RESPUESTA_RARA = "La API respondió algo inesperado. Intenta de nuevo.";

  function plural(n, uno, varios) { return n + " " + (n === 1 ? uno : varios); }

  function minutos(segundos) {
    var m = Math.ceil((segundos || 0) / 60);
    return m <= 1 ? "1 minuto" : m + " minutos";
  }

  /* El primer aviso de la respuesta de la API, o null. */
  function primerError(cuerpo) {
    return cuerpo && cuerpo.errors && cuerpo.errors.length ? cuerpo.errors[0] : null;
  }

  /* Revisa lo escrito antes de mandarlo. Devuelve el aviso, o null si está bien. */
  function revisarCorreoYContrasena(correo, contrasena) {
    var c = (correo || "").trim();
    if (!c) return { campo: "email", aviso: "Escribe tu correo." };
    if (c.indexOf("@") < 1 || c.indexOf("@") === c.length - 1) return { campo: "email", aviso: "El correo no tiene un formato válido." };
    if (!contrasena) return { campo: "password", aviso: "Escribe tu contraseña." };
    return null;
  }

  function revisarCodigo(codigo) {
    var c = (codigo || "").trim();
    if (!c) return { campo: "code", aviso: "Escribe el código que te llegó." };
    if (!/^[0-9]{6}$/.test(c)) return { campo: "code", aviso: "El código son 6 números." };
    return null;
  }

  /* Qué sigue después del paso del correo y la contraseña.
     status es el código HTTP (0 si no hubo conexión) y cuerpo la respuesta ya leída. */
  function despuesDelCorreo(status, cuerpo, correo) {
    var error = primerError(cuerpo);
    var codigo = error ? error.code : null;
    if (status === 0) return { paso: "correo", campo: null, aviso: SIN_SERVIDOR };
    if (status === 200 && cuerpo && cuerpo.status === "code_required") {
      return { paso: "codigo", campo: "code", aviso: null, texto: "Te enviamos un código de 6 dígitos a " + correo + ". Vence en 5 minutos." };
    }
    if (status === 401) return { paso: "correo", campo: "password", aviso: "El correo o la contraseña no son correctos." };
    if (status === 403 && codigo === "email_not_verified") {
      return { paso: "correo", campo: "email", aviso: "Todavía no has comprobado tu correo. Busca el código que te enviamos al registrarte." };
    }
    if (status === 429 && codigo === "try_later") {
      return { paso: "correo", campo: null, aviso: "Demasiados intentos desde este dispositivo. Intenta de nuevo en " + minutos(cuerpo.retry_after) + "." };
    }
    if (status === 429 && codigo === "wait") {
      /* Ya hay un código vigente, enviado hace menos de un minuto: se pide ese. */
      return { paso: "codigo", campo: "code", aviso: null, texto: "Ya te enviamos un código a " + correo + " hace menos de un minuto. Escríbelo aquí." };
    }
    if (status === 429 && codigo === "hourly_limit") {
      return { paso: "correo", campo: null, aviso: "Ya pediste demasiados códigos en una hora. Intenta más tarde." };
    }
    if (status === 422 && error) return { paso: "correo", campo: error.field, aviso: error.message };
    return { paso: "correo", campo: null, aviso: (error && error.message) || RESPUESTA_RARA };
  }

  /* Qué sigue después del paso del código. */
  function despuesDelCodigo(status, cuerpo) {
    var error = primerError(cuerpo);
    var codigo = error ? error.code : null;
    if (status === 0) return { paso: "codigo", campo: null, aviso: SIN_SERVIDOR };
    if (status === 200 && cuerpo && cuerpo.status === "session_opened") return { paso: "dentro", campo: null, aviso: null };
    if (status === 400 && codigo === "invalid_code") {
      var quedan = cuerpo.attempts_left;
      var aviso = "El código no es correcto.";
      if (typeof quedan === "number") aviso += quedan === 0 ? " Ya no te quedan intentos." : " Te " + (quedan === 1 ? "queda" : "quedan") + " " + plural(quedan, "intento", "intentos") + ".";
      return { paso: quedan === 0 ? "correo" : "codigo", campo: quedan === 0 ? "email" : "code", aviso: aviso };
    }
    if (status === 400 && codigo === "code_expired") return { paso: "correo", campo: "email", aviso: "El código venció. Vuelve a escribir tu correo y tu contraseña para recibir otro." };
    if (status === 400 && codigo === "too_many_attempts") return { paso: "correo", campo: "email", aviso: "Demasiados intentos con ese código. Vuelve a escribir tu correo y tu contraseña para recibir otro." };
    if (status === 422 && error) return { paso: "codigo", campo: "code", aviso: error.message };
    return { paso: "codigo", campo: null, aviso: (error && error.message) || RESPUESTA_RARA };
  }

  /* Qué muestra la cabecera según la respuesta de GET /auth/me. */
  function estadoDeCabecera(status, cuerpo) {
    if (status === 200 && cuerpo && cuerpo.first_name) {
      return { sesion: true, nombre: cuerpo.first_name, clave: cuerpo.csrf_token || null, servidor: true };
    }
    return { sesion: false, nombre: null, clave: null, servidor: status !== 0 };
  }

  /* Qué sigue después de pedir cerrar sesión. */
  function despuesDeSalir(status) {
    if (status === 200 || status === 401) return { sesion: false, aviso: null };
    if (status === 0) return { sesion: true, aviso: SIN_SERVIDOR };
    if (status === 403) return { sesion: true, aviso: "No se pudo cerrar la sesión. Recarga la página e inténtalo de nuevo." };
    return { sesion: true, aviso: RESPUESTA_RARA };
  }

  return {
    SIN_SERVIDOR: SIN_SERVIDOR,
    revisarCorreoYContrasena: revisarCorreoYContrasena,
    revisarCodigo: revisarCodigo,
    despuesDelCorreo: despuesDelCorreo,
    despuesDelCodigo: despuesDelCodigo,
    estadoDeCabecera: estadoDeCabecera,
    despuesDeSalir: despuesDeSalir,
    minutos: minutos
  };
});
