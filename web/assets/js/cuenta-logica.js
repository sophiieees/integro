/* Íntegro, lógica de la cuenta (sin pantalla)
   -------------------------------------------------------------------
   Decide qué pasa en la ventana de «Iniciar sesión» con cada respuesta de la API y
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

  var SIN_SERVIDOR = "No fue posible comunicarse con el servidor de Íntegro. Inícialo y abre la página desde http://127.0.0.1:8000/.";
  var RESPUESTA_RARA = "El servidor respondió de forma inesperada. Inténtalo nuevamente.";

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
    if (!c) return { campo: "email", aviso: "Escribe tu correo electrónico." };
    if (c.indexOf("@") < 1 || c.indexOf("@") === c.length - 1) return { campo: "email", aviso: "El correo electrónico no tiene un formato válido." };
    if (!contrasena) return { campo: "password", aviso: "Escribe tu contraseña." };
    return null;
  }

  function revisarCodigo(codigo) {
    var c = (codigo || "").trim();
    if (!c) return { campo: "code", aviso: "Escribe el código que recibiste." };
    if (!/^[0-9]{6}$/.test(c)) return { campo: "code", aviso: "El código debe constar de 6 dígitos." };
    return null;
  }

  /* Qué sigue después del paso del correo y la contraseña.
     status es el código HTTP (0 si no hubo conexión) y cuerpo la respuesta ya leída. */
  function despuesDelCorreo(status, cuerpo, correo) {
    var error = primerError(cuerpo);
    var codigo = error ? error.code : null;
    if (status === 0) return { paso: "correo", campo: null, aviso: SIN_SERVIDOR };
    if (status === 200 && cuerpo && cuerpo.status === "code_required") {
      return { paso: "codigo", campo: "code", aviso: null, texto: "Te enviamos un código de 6 dígitos a " + correo + ". Su vigencia es de 5 minutos." };
    }
    if (status === 401) return { paso: "correo", campo: "password", aviso: "El correo electrónico o la contraseña no son correctos." };
    if (status === 403 && codigo === "email_not_verified") {
      return { paso: "correo", campo: "email", aviso: "Aún no has comprobado tu correo electrónico. Revisa el código que te enviamos al registrarte." };
    }
    if (status === 429 && codigo === "try_later") {
      return { paso: "correo", campo: null, aviso: "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en " + minutos(cuerpo.retry_after) + "." };
    }
    if (status === 429 && codigo === "wait") {
      /* Ya hay un código vigente, enviado hace menos de un minuto: se pide ese. */
      return { paso: "codigo", campo: "code", aviso: null, texto: "Ya te enviamos un código a " + correo + " hace menos de un minuto. Por favor, escríbelo aquí." };
    }
    if (status === 429 && codigo === "hourly_limit") {
      return { paso: "correo", campo: null, aviso: "Has solicitado demasiados códigos en una hora. Inténtalo nuevamente más tarde." };
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
      var aviso = "El código ingresado no es correcto.";
      if (typeof quedan === "number") aviso += quedan === 0 ? " Ya no te quedan intentos." : " Te " + (quedan === 1 ? "queda" : "quedan") + " " + plural(quedan, "intento", "intentos") + ".";
      return { paso: quedan === 0 ? "correo" : "codigo", campo: quedan === 0 ? "email" : "code", aviso: aviso };
    }
    if (status === 400 && codigo === "code_expired") return { paso: "correo", campo: "email", aviso: "El código venció. Vuelve a escribir tu correo electrónico y tu contraseña para recibir uno nuevo." };
    if (status === 400 && codigo === "too_many_attempts") return { paso: "correo", campo: "email", aviso: "Se agotaron los intentos con ese código. Vuelve a escribir tu correo electrónico y tu contraseña para recibir uno nuevo." };
    if (status === 422 && error) return { paso: "codigo", campo: "code", aviso: error.message };
    return { paso: "codigo", campo: null, aviso: (error && error.message) || RESPUESTA_RARA };
  }

  /* Qué muestra la cabecera según la respuesta de GET /auth/me.
     esAnfitrion y esAdmin salen de is_host e is_admin: dicen qué vistas tiene la persona. */
  function estadoDeCabecera(status, cuerpo) {
    if (status === 200 && cuerpo && cuerpo.first_name) {
      return {
        sesion: true,
        nombre: cuerpo.first_name,
        apellidos: cuerpo.last_name || "",
        correo: cuerpo.email || "",
        clave: cuerpo.csrf_token || null,
        servidor: true,
        esAnfitrion: cuerpo.is_host === true,
        esAdmin: cuerpo.is_admin === true
      };
    }
    return {
      sesion: false, nombre: null, apellidos: "", correo: "", clave: null, servidor: status !== 0,
      esAnfitrion: false, esAdmin: false
    };
  }

  /* En qué vista está la persona (docs/diseno/vistas.md). Un administrador puede elegir mirar la de cliente o la
     de anfitrión con su propia cuenta (verComo); para cualquier otra persona, verComo no cambia nada. */
  function vistaDe(estado, verComo) {
    if (!estado || !estado.sesion) return "visitante";
    if (estado.esAdmin) return verComo === "cliente" || verComo === "anfitrion" ? verComo : "administrador";
    return estado.esAnfitrion ? "anfitrion" : "cliente";
  }

  var SIN_SESION = {
    titulo: "Inicia sesión para continuar",
    texto: "Esta sección es para personas con una cuenta de Íntegro.",
    accion: { texto: "Iniciar sesión", iniciarSesion: true }
  };

  /* Si la persona puede ver una página protegida. requiere es el data-requiere de la página:
     "sesion", "anfitrion" o "administrador". Un administrador puede ver las páginas del anfitrión: es la manera
     de probar la plataforma con su propio usuario. La página explica el motivo; no es un error de la API. */
  function permisoDePagina(requiere, estado) {
    if (!requiere) return { permitido: true };
    if (!estado || !estado.servidor) {
      return {
        permitido: false,
        titulo: "No fue posible comprobar tu sesión",
        texto: SIN_SERVIDOR,
        accion: { texto: "Volver al inicio", href: "index.html" }
      };
    }
    if (!estado.sesion) return Object.assign({ permitido: false }, SIN_SESION);
    if (requiere === "anfitrion" && !estado.esAnfitrion && !estado.esAdmin) {
      return {
        permitido: false,
        titulo: "Esta sección es para anfitriones",
        texto: "Tu cuenta todavía no tiene un perfil de anfitrión. Conoce cómo convertirte en anfitrión.",
        accion: { texto: "Conviértete en anfitrión", href: "anfitriones.html" }
      };
    }
    if (requiere === "administrador" && !estado.esAdmin) {
      return {
        permitido: false,
        titulo: "Esta sección es solo para el equipo de Íntegro",
        texto: "Tu cuenta no tiene acceso a esta sección.",
        accion: { texto: "Volver al inicio", href: "index.html" }
      };
    }
    /* Un requiere que no se conoce (un error al escribir la página) no abre nada. */
    if (requiere !== "sesion" && requiere !== "anfitrion" && requiere !== "administrador") {
      return {
        permitido: false,
        titulo: "Esta sección no está disponible",
        texto: "No fue posible comprobar quién puede verla.",
        accion: { texto: "Volver al inicio", href: "index.html" }
      };
    }
    return { permitido: true };
  }

  /* Qué sigue después de pedir cerrar sesión. */
  function despuesDeSalir(status) {
    if (status === 200 || status === 401) return { sesion: false, aviso: null };
    if (status === 0) return { sesion: true, aviso: SIN_SERVIDOR };
    if (status === 403) return { sesion: true, aviso: "No fue posible cerrar la sesión. Recarga la página e inténtalo nuevamente." };
    return { sesion: true, aviso: RESPUESTA_RARA };
  }

  return {
    SIN_SERVIDOR: SIN_SERVIDOR,
    revisarCorreoYContrasena: revisarCorreoYContrasena,
    revisarCodigo: revisarCodigo,
    despuesDelCorreo: despuesDelCorreo,
    despuesDelCodigo: despuesDelCodigo,
    estadoDeCabecera: estadoDeCabecera,
    vistaDe: vistaDe,
    permisoDePagina: permisoDePagina,
    despuesDeSalir: despuesDeSalir,
    minutos: minutos
  };
});
