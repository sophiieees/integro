/* Íntegro, lógica de la pantalla de registro (sin pantalla)
   -------------------------------------------------------------------
   Decide qué datos se mandan a la API, qué pasa con cada respuesta y qué se
   le dice a la persona. No toca el documento ni llama a la API: eso lo hace
   registro.js. Así se prueba sin navegador, con node.

   La pantalla tiene tres pasos:
     "datos"   el formulario                    (POST /api/v1/auth/register)
     "codigo"  el código que llegó al correo    (POST /api/v1/auth/verify-email)
     "listo"   el correo quedó comprobado

   Los textos van en tono formal pero de tú (decisión del 20 de noviembre de 2026).
   Funciona en el navegador (window.INTEGRO_REGISTRO) y en node (module.exports).
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = fabrica(require("./cuenta-logica.js"), require("./paises.js"));
  } else {
    raiz.INTEGRO_REGISTRO = fabrica(raiz.INTEGRO_CUENTA, raiz.INTEGRO_PAISES);
  }
})(typeof window !== "undefined" ? window : this, function (CUENTA, PAISES) {
  "use strict";

  var SIN_SERVIDOR = CUENTA.SIN_SERVIDOR;
  var RESPUESTA_RARA = "El servidor respondió de forma inesperada. Inténtalo nuevamente.";
  var CAMPOS = ["first_name", "last_name", "email", "password", "phone", "country", "birth_date", "terms"];
  /* Los que existen en la API; «terms» es solo de la pantalla. */
  var CAMPOS_DE_LA_API = ["first_name", "last_name", "email", "password", "phone", "country", "birth_date"];

  /* Los mismos límites que la API (backend/app/modules/accounts/validation.py). */
  var NOMBRE_MAX = 80;
  var CORREO_MAX = 254;
  var CORREO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var FECHA = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
  var TELEFONO_MIN = 8;
  var TELEFONO_MAX = 15;

  function plural(n, uno, varios) { return n + " " + (n === 1 ? uno : varios); }

  /* La fecha de hoy, AAAA-MM-DD, donde está la persona: la del reloj de su navegador. toISOString da la de UTC, que
     pasadas las 18:00 en México ya es la de mañana y dejaría escribir un nacimiento en el futuro. */
  function fechaDeHoy(ahora) {
    var mes = ahora.getMonth() + 1;
    var dia = ahora.getDate();
    return ahora.getFullYear() + "-" + (mes < 10 ? "0" : "") + mes + "-" + (dia < 10 ? "0" : "") + dia;
  }

  /* ---------- Países y teléfono ---------- */

  /* La lista de países para elegir, con su nombre en español: México primero y
     los demás por orden alfabético. DisplayNames es Intl.DisplayNames; sin él
     el nombre es el código de dos letras. */
  function listaDePaises(DisplayNames, idioma) {
    var nombres = null;
    try { nombres = DisplayNames ? new DisplayNames([idioma || "es"], { type: "region" }) : null; } catch (e) { nombres = null; }
    var lista = PAISES.PAISES.map(function (par) {
      var nombre = par[0];
      try { if (nombres) nombre = nombres.of(par[0]) || par[0]; } catch (e) { nombre = par[0]; }
      return { codigo: par[0], nombre: nombre, marcacion: par[1] };
    });
    lista.sort(function (a, b) {
      if (a.codigo === PAISES.PRIMERO) return -1;
      if (b.codigo === PAISES.PRIMERO) return 1;
      return a.nombre.localeCompare(b.nombre, idioma || "es");
    });
    return lista;
  }

  /* Los países que tienen código de marcación, para la lista del teléfono. */
  function paisesConMarcacion(lista) {
    return lista.filter(function (pais) { return pais.marcacion > 0; });
  }

  /* Al cambiar el país de residencia, el código del teléfono pasa a ser el de ese país,
     si tiene uno. Devuelve el país del código que debe quedar elegido, o null si no cambia. */
  function marcacionParaElPais(codigoDePais, lista) {
    var pais = lista.filter(function (p) { return p.codigo === codigoDePais; })[0];
    return pais && pais.marcacion > 0 ? pais.codigo : null;
  }

  /* El teléfono en formato internacional, +521234567890, a partir del código de marcación y de lo escrito.
     Devuelve { telefono } o { error }. */
  function telefono(marcacion, texto) {
    var codigo = parseInt(marcacion, 10);
    var escrito = (texto || "").trim();
    if (!escrito) return { error: "Escribe tu número de teléfono." };
    if (!(codigo > 0)) return { error: "Elige el código de marcación de tu país." };
    if (escrito.indexOf("+") !== -1) return { error: "Escribe el número sin el código del país; el código se elige en la lista." };
    if (/[^0-9\s().-]/.test(escrito)) return { error: "El teléfono solo puede llevar números, espacios, guiones y paréntesis." };
    var digitos = escrito.replace(/[^0-9]/g, "");
    var total = String(codigo).length + digitos.length;
    if (total < TELEFONO_MIN || total > TELEFONO_MAX) return { error: "El teléfono no tiene un formato válido." };
    return { telefono: "+" + codigo + digitos };
  }

  /* ---------- Antes de mandar ---------- */

  /* Revisa lo escrito. Solo lo evidente: lo demás lo decide la API, que es la que manda.
     valores: first_name, last_name, email, password, marcacion, numero, country, birth_date, terminos.
     Devuelve { errores: { campo: [avisos] }, datos } con los datos listos para la API. */
  function revisarDatos(valores) {
    var errores = {};
    function falla(campo, aviso) { (errores[campo] = errores[campo] || []).push(aviso); }

    var nombre = (valores.first_name || "").trim();
    var apellidos = (valores.last_name || "").trim();
    var correo = (valores.email || "").trim();
    var contrasena = valores.password || "";
    var pais = (valores.country || "").trim();
    var nacimiento = (valores.birth_date || "").trim();

    if (!nombre) falla("first_name", "Escribe tu nombre.");
    else if (nombre.length > NOMBRE_MAX) falla("first_name", "El nombre admite hasta " + NOMBRE_MAX + " caracteres.");
    if (!apellidos) falla("last_name", "Escribe tus apellidos.");
    else if (apellidos.length > NOMBRE_MAX) falla("last_name", "Los apellidos admiten hasta " + NOMBRE_MAX + " caracteres.");
    if (!correo) falla("email", "Escribe tu correo electrónico.");
    else if (correo.length > CORREO_MAX || !CORREO.test(correo)) falla("email", "El correo electrónico no tiene un formato válido.");
    if (!contrasena) falla("password", "Escribe tu contraseña.");
    var marcado = telefono(valores.marcacion, valores.numero);
    if (marcado.error) falla("phone", marcado.error);
    if (!pais) falla("country", "Elige tu país de residencia.");
    if (!nacimiento) falla("birth_date", "Escribe tu fecha de nacimiento.");
    else if (!FECHA.test(nacimiento)) falla("birth_date", "La fecha de nacimiento no es válida.");
    /* La casilla solo se pide en la pantalla: todavía no hay texto legal que registrar (revisión pendiente). */
    if (!valores.terminos) falla("terms", "Para crear tu cuenta, acepta los términos y condiciones y el aviso de privacidad.");

    return {
      errores: errores,
      datos: {
        first_name: nombre,
        last_name: apellidos,
        email: correo,
        password: contrasena,
        phone: marcado.telefono || "",
        country: pais,
        birth_date: nacimiento,
        preferred_language: "es"
      }
    };
  }

  function hayErrores(errores) { return Object.keys(errores).length > 0; }

  /* El primer campo con aviso, en el orden en que se ven, para llevar el cursor ahí. */
  function primerCampoConError(errores) {
    for (var i = 0; i < CAMPOS.length; i++) if (errores[CAMPOS[i]]) return CAMPOS[i];
    return null;
  }

  /* ---------- El indicador de la contraseña ---------- */

  var NIVELES = {
    low: { segmentos: 1, nivel: "bajo", etiqueta: "Bajo" },
    medium: { segmentos: 2, nivel: "medio", etiqueta: "Medio" },
    reliable: { segmentos: 3, nivel: "confiable", etiqueta: "Confiable" },
    very_reliable: { segmentos: 4, nivel: "muy-confiable", etiqueta: "Muy confiable" }
  };

  /* Lo que se manda a POST /auth/password-strength mientras la persona escribe. */
  function cuerpoDeFortaleza(valores) {
    return {
      password: valores.password || "",
      first_name: (valores.first_name || "").trim(),
      last_name: (valores.last_name || "").trim(),
      email: (valores.email || "").trim()
    };
  }

  /* Lo que muestra el indicador: cuántos cuadros se llenan, el nivel y los consejos.
     respuesta es el cuerpo que contesta la API, o null si no hubo respuesta. */
  function vistaDeFortaleza(respuesta, hayContrasena) {
    var vacia = { segmentos: 0, nivel: "", etiqueta: "", consejos: [], aceptada: false };
    if (!hayContrasena || !respuesta || !NIVELES[respuesta.level]) return vacia;
    var nivel = NIVELES[respuesta.level];
    var consejos;
    if (respuesta.meets_rules === false) {
      /* No cumple las reglas: primero lo que falta. */
      consejos = (respuesta.errors || []).map(function (e) { return e.message; });
    } else {
      consejos = (respuesta.hints || []).concat(respuesta.raise_hints || []);
    }
    return {
      segmentos: nivel.segmentos,
      nivel: nivel.nivel,
      etiqueta: respuesta.label || nivel.etiqueta,
      consejos: consejos,
      aceptada: respuesta.accepted === true
    };
  }

  /* ---------- Con cada respuesta de la API ---------- */

  /* Agrupa los avisos de la API por campo. Los de un campo que la pantalla no tiene van aparte, en aviso. */
  function avisosPorCampo(cuerpo) {
    var errores = {};
    var sueltos = [];
    ((cuerpo && cuerpo.errors) || []).forEach(function (e) {
      if (CAMPOS_DE_LA_API.indexOf(e.field) !== -1) (errores[e.field] = errores[e.field] || []).push(e.message);
      else sueltos.push(e.message);
    });
    return { errores: errores, aviso: sueltos.length ? sueltos.join(" ") : null };
  }

  /* Qué sigue después de mandar el formulario. */
  function despuesDeRegistrar(status, cuerpo, correo) {
    var base = { paso: "datos", errores: {}, aviso: null, texto: null, yaTieneCuenta: false };
    if (status === 0) { base.aviso = SIN_SERVIDOR; return base; }
    if (status === 201 && cuerpo && cuerpo.status === "verification_required") {
      var enviado = cuerpo.email || correo;
      base.paso = "codigo";
      base.correo = enviado;
      base.texto = "Te enviamos un código de 6 dígitos a " + enviado + ". Escríbelo aquí para comprobar tu correo electrónico. Su vigencia es de 5 minutos.";
      return base;
    }
    if (status === 422 || status === 409) {
      var avisos = avisosPorCampo(cuerpo);
      base.errores = avisos.errores;
      base.aviso = avisos.aviso;
      base.yaTieneCuenta = status === 409 && !!avisos.errores.email;
      if (!hayErrores(base.errores) && !base.aviso) base.aviso = RESPUESTA_RARA;
      return base;
    }
    base.aviso = RESPUESTA_RARA;
    return base;
  }

  /* Qué sigue después de escribir el código del correo. */
  function despuesDeComprobar(status, cuerpo) {
    var error = cuerpo && cuerpo.errors && cuerpo.errors.length ? cuerpo.errors[0] : null;
    var codigo = error ? error.code : null;
    if (status === 0) return { paso: "codigo", aviso: SIN_SERVIDOR, nota: null };
    if (status === 200 && cuerpo && cuerpo.status === "verified") return { paso: "listo", aviso: null, nota: null };
    if (status === 409 && codigo === "already_verified") return { paso: "listo", aviso: null, nota: "Tu correo electrónico ya estaba comprobado." };
    if (status === 400 && codigo === "invalid_code") {
      var quedan = cuerpo.attempts_left;
      var aviso = "El código ingresado no es correcto.";
      if (typeof quedan === "number") {
        aviso += quedan === 0
          ? " Ya no te quedan intentos. Solicita un código nuevo con «Enviar otro código»."
          : " Te " + (quedan === 1 ? "queda" : "quedan") + " " + plural(quedan, "intento", "intentos") + ".";
      }
      return { paso: "codigo", aviso: aviso, nota: null };
    }
    if (status === 400 && codigo === "code_expired") return { paso: "codigo", aviso: "El código venció. Solicita uno nuevo con «Enviar otro código».", nota: null };
    if (status === 400 && codigo === "too_many_attempts") return { paso: "codigo", aviso: "Se agotaron los intentos con ese código. Solicita uno nuevo con «Enviar otro código».", nota: null };
    if (status === 422 && error) return { paso: "codigo", aviso: error.message, nota: null };
    return { paso: "codigo", aviso: (error && error.message) || RESPUESTA_RARA, nota: null };
  }

  /* Qué sigue después de pedir otro código. */
  function despuesDeReenviar(status, cuerpo, correo) {
    var error = cuerpo && cuerpo.errors && cuerpo.errors.length ? cuerpo.errors[0] : null;
    var codigo = error ? error.code : null;
    if (status === 0) return { enviado: false, aviso: SIN_SERVIDOR, nota: null };
    if (status === 200 && cuerpo && cuerpo.status === "sent") return { enviado: true, aviso: null, nota: "Te enviamos un código nuevo a " + correo + "." };
    if (status === 429 && codigo === "wait") {
      var segundos = typeof cuerpo.retry_after === "number" ? cuerpo.retry_after : 60;
      return { enviado: false, aviso: "Espera " + plural(segundos, "segundo", "segundos") + " para solicitar otro código.", nota: null };
    }
    if (status === 429 && codigo === "hourly_limit") return { enviado: false, aviso: "Has solicitado demasiados códigos. Inténtalo nuevamente más tarde.", nota: null };
    return { enviado: false, aviso: (error && error.message) || RESPUESTA_RARA, nota: null };
  }

  /* ---------- Corregir el correo de una cuenta sin comprobar ---------- */

  /* Revisa lo evidente: los dos datos y la forma del correo. Devuelve { errores, datos }. */
  function revisarCorreccion(valores) {
    var errores = {};
    var nuevo = (valores.new_email || "").trim();
    if (!nuevo) errores.new_email = ["Escribe el correo electrónico correcto."];
    else if (nuevo.length > CORREO_MAX || !CORREO.test(nuevo)) errores.new_email = ["El correo electrónico no tiene un formato válido."];
    if (!valores.password) errores.password = ["Escribe tu contraseña."];
    return { errores: errores, datos: { email: (valores.email || "").trim(), password: valores.password || "", new_email: nuevo } };
  }

  /* Qué sigue después de pedir la corrección. */
  function despuesDeCorregir(status, cuerpo) {
    var error = cuerpo && cuerpo.errors && cuerpo.errors.length ? cuerpo.errors[0] : null;
    var codigo = error ? error.code : null;
    var base = { paso: "correccion", errores: {}, aviso: null, correo: null, texto: null, nota: null };
    if (status === 0) { base.aviso = SIN_SERVIDOR; return base; }
    if (status === 200 && cuerpo && cuerpo.status === "verification_required") {
      base.paso = "codigo";
      base.correo = cuerpo.email;
      base.texto = "Te enviamos un código de 6 dígitos a " + cuerpo.email + ". Escríbelo aquí para comprobar tu correo electrónico. Su vigencia es de 5 minutos.";
      base.nota = "Corregimos tu correo electrónico. El código anterior ya no sirve.";
      return base;
    }
    if (status === 401) { base.aviso = "La contraseña no es correcta."; return base; }
    if (status === 409 && codigo === "already_verified") { base.paso = "listo"; base.nota = "Tu correo electrónico ya estaba comprobado."; return base; }
    if ((status === 409 || status === 422) && error && error.field === "new_email") { base.errores.new_email = [error.message]; return base; }
    if (status === 422 && error && (error.field === "email" || error.field === "password")) { base.errores[error.field === "email" ? "new_email" : "password"] = [error.message]; return base; }
    if (status === 429 && codigo === "try_later") {
      base.aviso = "Se recibieron demasiados intentos desde este dispositivo. Inténtalo nuevamente en " + CUENTA.minutos(cuerpo.retry_after) + ".";
      return base;
    }
    if (status === 429 && codigo === "hourly_limit") { base.aviso = "Has solicitado demasiados códigos. Inténtalo nuevamente más tarde."; return base; }
    base.aviso = (error && error.message) || RESPUESTA_RARA;
    return base;
  }

  /* Cuando la API rechaza la contraseña, lo que falta ya lo dice el indicador de debajo: en el campo va una sola
     línea que remite a él, no la misma lista dos veces. */
  var AVISO_CONTRASENA = "Tu contraseña aún no cumple lo que se indica abajo.";

  function resumirAvisos(errores) {
    var resumen = {};
    Object.keys(errores).forEach(function (campo) {
      resumen[campo] = campo === "password" ? [AVISO_CONTRASENA] : errores[campo];
    });
    return resumen;
  }

  /* La pantalla cuando ya hay una sesión iniciada. */
  function avisoDeSesionIniciada(nombre) {
    return "Ya iniciaste sesión como " + nombre + ". Para crear otra cuenta, primero cierra sesión.";
  }

  return {
    CAMPOS: CAMPOS,
    SIN_SERVIDOR: SIN_SERVIDOR,
    fechaDeHoy: fechaDeHoy,
    listaDePaises: listaDePaises,
    paisesConMarcacion: paisesConMarcacion,
    marcacionParaElPais: marcacionParaElPais,
    telefono: telefono,
    revisarDatos: revisarDatos,
    hayErrores: hayErrores,
    primerCampoConError: primerCampoConError,
    cuerpoDeFortaleza: cuerpoDeFortaleza,
    vistaDeFortaleza: vistaDeFortaleza,
    despuesDeRegistrar: despuesDeRegistrar,
    despuesDeComprobar: despuesDeComprobar,
    despuesDeReenviar: despuesDeReenviar,
    revisarCorreccion: revisarCorreccion,
    despuesDeCorregir: despuesDeCorregir,
    AVISO_CONTRASENA: AVISO_CONTRASENA,
    resumirAvisos: resumirAvisos,
    avisoDeSesionIniciada: avisoDeSesionIniciada,
    revisarCodigo: CUENTA.revisarCodigo
  };
});
