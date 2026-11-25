/* Íntegro, lógica de la cuenta (sin pantalla)
   -------------------------------------------------------------------
   Decide qué pasa en la ventana de «Iniciar sesión» con cada respuesta de la API y
   qué texto se le muestra a la persona. No toca el documento ni llama a la
   API: eso lo hace cuenta.js. Así se prueba sin navegador, con node.

   La ventana tiene estos pasos:
     "correo"         pide correo y contraseña  (POST /api/v1/auth/login)
     "codigo"         pide el código de 6 dígitos del correo (POST /api/v1/auth/login/verify)
     "authenticator"  solo para quien tiene el Authenticator activo: la sesión quedó abierta pero en espera, y pide el
                      código de su aplicación (POST /api/v1/auth/2fa/verify). Decisión de Sophia del 25 de noviembre de
                      2026, pieza 3.3.
     "dentro"         la sesión sirve y la ventana se cierra

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
    if (status === 200 && cuerpo && cuerpo.status === "session_opened") {
      /* Con el Authenticator activo la sesión nace en espera: falta el código de la aplicación. clave es la clave
         anti-falsificación de esa sesión, que hace falta para mandar el código o para cerrar la sesión. */
      if (cuerpo.second_factor_required === true) {
        return { paso: "authenticator", campo: "totp", aviso: null, clave: cuerpo.csrf_token || null };
      }
      return { paso: "dentro", campo: null, aviso: null };
    }
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

  /* ---------- El código del Authenticator ---------- */

  var TEXTO_DEL_AUTHENTICATOR = "Escribe el código de 6 dígitos que muestra tu aplicación Authenticator.";

  /* Las aplicaciones muestran el código con un espacio en medio («123 456»): se quita antes de mandarlo. */
  function limpiarCodigoDeAuthenticator(escrito) {
    return String(escrito || "").replace(/\s+/g, "");
  }

  function revisarCodigoDeAuthenticator(escrito) {
    var c = limpiarCodigoDeAuthenticator(escrito);
    if (!c) return { campo: "totp", aviso: "Escribe el código de tu aplicación Authenticator." };
    if (!/^[0-9]{6}$/.test(c)) return { campo: "totp", aviso: "El código debe constar de 6 dígitos." };
    return null;
  }

  /* Qué sigue después de mandar el código del Authenticator (POST /auth/2fa/verify). */
  function despuesDelAuthenticator(status, cuerpo) {
    var error = primerError(cuerpo);
    var codigo = error ? error.code : null;
    var aqui = { paso: "authenticator", campo: "totp", aviso: null };
    if (status === 0) { aqui.aviso = SIN_SERVIDOR; return aqui; }
    if (status === 200 && cuerpo && cuerpo.status === "verified") return { paso: "dentro", campo: null, aviso: null };
    /* Ya no tiene el Authenticator activo: no hay nada que comprobar y la sesión sirve. */
    if (status === 409 && codigo === "two_factor_not_active") return { paso: "dentro", campo: null, aviso: null };
    if (status === 400 && codigo === "invalid_code") {
      var quedan = cuerpo.attempts_left;
      aqui.aviso = "El código ingresado no es correcto.";
      if (typeof quedan === "number") aqui.aviso += " Te " + (quedan === 1 ? "queda" : "quedan") + " " + plural(quedan, "intento", "intentos") + ".";
      return aqui;
    }
    if (status === 429 && codigo === "try_later") {
      aqui.aviso = "Se escribieron demasiados códigos incorrectos. Inténtalo nuevamente en " + minutos(cuerpo.retry_after) + ".";
      return aqui;
    }
    /* La sesión en espera venció o se cerró: se empieza de nuevo. */
    if (status === 401) return { paso: "correo", campo: "email", aviso: "Tu sesión venció. Vuelve a iniciar sesión." };
    if (status === 503) { aqui.aviso = "No pudimos comprobar el código en este momento. Inténtalo más tarde."; return aqui; }
    if (status === 422 && error) { aqui.aviso = error.message; return aqui; }
    aqui.aviso = (error && error.message) || RESPUESTA_RARA;
    return aqui;
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
        esAdmin: cuerpo.is_admin === true,
        enEspera: false
      };
    }
    /* La sesión existe pero está en espera del Authenticator: la API no entrega ningún dato de la persona, solo la
       clave para mandar el código. La cabecera es la del visitante, e «Iniciar sesión» lleva directo a ese paso. */
    var error = primerError(cuerpo);
    if (status === 403 && error && error.code === "second_factor_required") {
      return {
        sesion: false, nombre: null, apellidos: "", correo: "", clave: cuerpo.csrf_token || null, servidor: true,
        esAnfitrion: false, esAdmin: false, enEspera: true
      };
    }
    return {
      sesion: false, nombre: null, apellidos: "", correo: "", clave: null, servidor: status !== 0,
      esAnfitrion: false, esAdmin: false, enEspera: false
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

  /* A dónde se puede volver después de iniciar sesión o de crear la cuenta: una página de Íntegro, con su
     dirección completa (por ejemplo, propiedad.html?id=2&llegada=2026-12-01). Viene de la dirección de la página
     (?siguiente=...), o sea, de quien escribió o abrió ese enlace: solo se acepta una página de esta lista, escrita
     sin dirección de otro sitio, sin «javascript:», sin barras ni nada raro. Todo lo demás es null y no se usa.
     Registro y recuperar contraseña no están: volver a ellas no tiene sentido. */
  var PAGINAS_DE_REGRESO = [
    "index.html", "propiedad.html", "como-funciona.html", "anfitriones.html",
    "mi-cuenta.html", "anfitrion.html", "administracion.html", "proximamente.html"
  ];

  function siguienteSeguro(valor) {
    if (typeof valor !== "string" || valor.length === 0 || valor.length > 300) return null;
    var partes = /^([a-z-]+\.html)(\?[A-Za-z0-9_=&%.\-]*)?(#[A-Za-z0-9_\-]*)?$/.exec(valor);
    if (!partes || PAGINAS_DE_REGRESO.indexOf(partes[1]) === -1) return null;
    return valor;
  }

  /* Las páginas cuyo trabajo termina al iniciar sesión: el registro («Tu cuenta está lista») y recuperar la
     contraseña («Tu contraseña cambió»). Quedarse ahí no tiene sentido: se va a la portada. */
  var PAGINAS_QUE_TERMINAN = ["registro.html", "recuperar-contrasena.html"];
  var PORTADA = "index.html";

  function archivoDe(ruta) {
    var archivo = String(ruta || "").split("/").pop();
    return archivo === "" ? PORTADA : archivo;
  }

  /* A dónde va la persona al terminar de iniciar sesión (decisiones de Sophia del 21 de noviembre de 2026):
     - si la dirección trae ?siguiente= con una página permitida (siguienteSeguro), a esa página;
     - si estaba en el registro o en recuperar la contraseña, a la portada;
     - desde cualquier otra página no se mueve: sigue donde estaba, para no perder lo que estaba haciendo.
     ruta es window.location.pathname; siguiente, el valor de ?siguiente=. */
  function destinoTrasIniciarSesion(ruta, siguiente) {
    var seguro = siguienteSeguro(siguiente);
    if (seguro) return { ir: true, destino: seguro };
    if (PAGINAS_QUE_TERMINAN.indexOf(archivoDe(ruta)) !== -1) return { ir: true, destino: PORTADA };
    return { ir: false, destino: null };
  }

  /* El aviso breve que ve quien inicia sesión sin cambiar de página. */
  function avisoDeInicio(nombre) {
    return "Iniciaste sesión como " + nombre + ".";
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
    TEXTO_DEL_AUTHENTICATOR: TEXTO_DEL_AUTHENTICATOR,
    limpiarCodigoDeAuthenticator: limpiarCodigoDeAuthenticator,
    revisarCodigoDeAuthenticator: revisarCodigoDeAuthenticator,
    despuesDelAuthenticator: despuesDelAuthenticator,
    estadoDeCabecera: estadoDeCabecera,
    vistaDe: vistaDe,
    permisoDePagina: permisoDePagina,
    siguienteSeguro: siguienteSeguro,
    destinoTrasIniciarSesion: destinoTrasIniciarSesion,
    avisoDeInicio: avisoDeInicio,
    PAGINAS_QUE_TERMINAN: PAGINAS_QUE_TERMINAN,
    PAGINAS_DE_REGRESO: PAGINAS_DE_REGRESO,
    despuesDeSalir: despuesDeSalir,
    minutos: minutos
  };
});
