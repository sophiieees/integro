/* Íntegro, la pantalla de recuperar la contraseña
   -------------------------------------------------------------------
   recuperar-contrasena.html tiene tres pasos (los de recuperar-logica.js):
   1. El correo. POST /api/v1/auth/password-reset/request envía un código de 6
      dígitos al correo, si la cuenta existe y su correo está comprobado. La API
      contesta lo mismo en todos los casos.
   2. El código y la contraseña nueva. POST /api/v1/auth/password-reset/confirm
      cambia la contraseña y cierra todas las sesiones de la cuenta. «Enviar otro
      código» vuelve a llamar a la primera ruta.
   3. Listo. «Iniciar sesión» abre la ventana de la cabecera (cuenta.js).

   Mientras la persona escribe la contraseña nueva, se califica con
   POST /api/v1/auth/password-strength, igual que en el registro. Esa ruta no
   guarda nada. La contraseña viaja solo a la propia API y no se deja escrita
   en la página cuando ya se mandó.

   Qué hacer con cada respuesta lo decide recuperar-logica.js.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_RECUPERAR;
  var formCorreo = document.getElementById("formulario-correo");
  if (!LOGICA || !formCorreo) return;

  var API = "/api/v1/auth";
  var formCambio = document.getElementById("formulario-cambio");
  var listo = document.getElementById("recuperar-listo");
  var aviso = document.querySelector("[data-aviso]");
  var estado = { enviando: false, correo: "", secuencia: 0, temporizador: null };

  /* ---------- API ---------- */

  function peticion(ruta, cuerpo) {
    return fetch(API + ruta, {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
      credentials: "same-origin"
    }).then(function (respuesta) {
      return respuesta.text().then(function (texto) {
        var datos = null;
        try { datos = texto ? JSON.parse(texto) : null; } catch (e) { datos = null; }
        return { status: respuesta.status, cuerpo: datos };
      });
    }, function () {
      return { status: 0, cuerpo: null };
    });
  }

  /* ---------- Lo que se ve ---------- */

  function mostrarAviso(texto) {
    aviso.textContent = texto || "";
    aviso.hidden = !texto;
  }

  function mostrarNota(texto) {
    var nota = formCambio.querySelector("[data-nota]");
    nota.textContent = texto || "";
    nota.hidden = !texto;
  }

  /* Pone los avisos en sus campos. raiz es el formulario donde están. */
  function mostrarErrores(errores, raiz) {
    Array.prototype.forEach.call(raiz.querySelectorAll("[data-error-de]"), function (zona) {
      var avisos = errores[zona.getAttribute("data-error-de")] || [];
      zona.innerHTML = "";
      avisos.forEach(function (texto) {
        var linea = document.createElement("span");
        linea.textContent = texto;
        zona.appendChild(linea);
      });
      zona.hidden = !avisos.length;
      var contenedor = zona.closest(".campo");
      if (contenedor) contenedor.classList.toggle("con-error", avisos.length > 0);
    });
  }

  function mostrarPaso(paso) {
    formCorreo.hidden = paso !== "correo";
    formCambio.hidden = paso !== "codigo";
    listo.hidden = paso !== "listo";
    /* La introducción es del paso del correo: después estorba. */
    document.querySelector("[data-intro]").hidden = paso !== "correo";
    var visible = paso === "correo" ? formCorreo : paso === "codigo" ? formCambio : listo;
    var titulo = visible.querySelector("h2");
    if (titulo) { titulo.setAttribute("tabindex", "-1"); titulo.focus(); }
  }

  function ocupado(si) {
    estado.enviando = si;
    Array.prototype.forEach.call(document.querySelectorAll(".formulario-tarjeta button, .formulario-tarjeta input"), function (el) {
      el.disabled = si;
    });
  }

  /* ---------- El indicador de la contraseña ---------- */

  var indicador = document.querySelector("[data-fortaleza]");

  function pintarIndicador(vista) {
    indicador.setAttribute("data-nivel", vista.nivel);
    Array.prototype.forEach.call(indicador.querySelectorAll(".fortaleza-barra span"), function (cuadro, i) {
      cuadro.classList.toggle("lleno", i < vista.segmentos);
    });
    indicador.querySelector("[data-fortaleza-nivel]").textContent = vista.etiqueta;
    var lista = indicador.querySelector("[data-fortaleza-consejos]");
    lista.innerHTML = "";
    vista.consejos.forEach(function (texto) {
      var li = document.createElement("li");
      li.textContent = texto;
      lista.appendChild(li);
    });
  }

  function calificar() {
    var contrasena = formCambio.elements.new_password.value;
    var numero = ++estado.secuencia;
    if (!contrasena) { pintarIndicador(LOGICA.vistaDeFortaleza(null, false)); return; }
    peticion("/password-strength", LOGICA.cuerpoDeFortaleza(contrasena, estado.correo)).then(function (r) {
      /* Si ya se escribió otra cosa, esta respuesta llegó tarde. */
      if (numero !== estado.secuencia) return;
      pintarIndicador(LOGICA.vistaDeFortaleza(r.status === 200 ? r.cuerpo : null, true));
    });
  }

  formCambio.elements.new_password.addEventListener("input", function () {
    clearTimeout(estado.temporizador);
    estado.temporizador = setTimeout(calificar, 300);
  });

  /* ---------- Paso 1: el correo ---------- */

  function pasarAlCodigo(siguiente) {
    estado.correo = siguiente.correo;
    formCambio.querySelector("[data-texto]").textContent = siguiente.texto;
    formCambio.elements.code.value = "";
    formCambio.elements.new_password.value = "";
    pintarIndicador(LOGICA.vistaDeFortaleza(null, false));
    mostrarErrores({}, formCambio);
    mostrarNota(null);
    mostrarPaso("codigo");
    formCambio.elements.code.focus();
  }

  formCorreo.addEventListener("submit", function (e) {
    e.preventDefault();
    if (estado.enviando) return;
    mostrarAviso(null);
    var correo = formCorreo.elements.email.value.trim();
    var revision = LOGICA.revisarCorreo(correo);
    if (revision) {
      mostrarErrores({ email: [revision.aviso] }, formCorreo);
      formCorreo.elements.email.focus();
      return;
    }
    mostrarErrores({}, formCorreo);
    ocupado(true);
    peticion("/password-reset/request", { email: correo }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDePedir(r.status, r.cuerpo, correo);
      if (siguiente.paso === "codigo") { pasarAlCodigo(siguiente); return; }
      mostrarErrores(siguiente.errores, formCorreo);
      mostrarAviso(siguiente.aviso);
      formCorreo.elements.email.focus();
    });
  });

  /* ---------- Paso 2: el código y la contraseña nueva ---------- */

  formCambio.addEventListener("submit", function (e) {
    e.preventDefault();
    if (estado.enviando) return;
    mostrarAviso(null);
    var codigo = formCambio.elements.code.value.trim();
    var contrasena = formCambio.elements.new_password.value;
    var errores = LOGICA.revisarCambio(codigo, contrasena);
    mostrarErrores(errores, formCambio);
    if (LOGICA.hayErrores(errores)) {
      formCambio.elements[LOGICA.primerCampoConError(errores)].focus();
      return;
    }
    ocupado(true);
    peticion("/password-reset/confirm", { email: estado.correo, code: codigo, new_password: contrasena }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDeCambiar(r.status, r.cuerpo);
      if (siguiente.paso === "listo") {
        /* La contraseña ya se mandó: no se queda escrita en la página. */
        formCambio.elements.new_password.value = "";
        formCambio.elements.code.value = "";
        pintarIndicador(LOGICA.vistaDeFortaleza(null, false));
        mostrarErrores({}, formCambio);
        mostrarPaso("listo");
        listo.querySelector("[data-iniciar-sesion]").focus();
        return;
      }
      mostrarErrores(siguiente.errores, formCambio);
      mostrarAviso(siguiente.aviso);
      /* Si lo que falló fue el código, la contraseña buena se queda; si fue la contraseña, que la corrija. */
      if (siguiente.errores.new_password) calificar();
      var primero = LOGICA.primerCampoConError(siguiente.errores);
      (primero ? formCambio.elements[primero] : formCambio.elements.code).focus();
      if (siguiente.pedirOtro) formCambio.querySelector("[data-reenviar]").focus();
    });
  });

  formCambio.querySelector("[data-reenviar]").addEventListener("click", function () {
    if (estado.enviando) return;
    mostrarAviso(null);
    mostrarNota(null);
    ocupado(true);
    peticion("/password-reset/request", { email: estado.correo }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDePedir(r.status, r.cuerpo, estado.correo);
      if (siguiente.paso === "codigo") {
        mostrarErrores({}, formCambio);
        mostrarNota(LOGICA.notaDeReenvio());
      } else {
        mostrarAviso(siguiente.aviso);
      }
      formCambio.elements.code.focus();
    });
  });

  formCambio.querySelector("[data-otro-correo]").addEventListener("click", function () {
    if (estado.enviando) return;
    mostrarAviso(null);
    mostrarErrores({}, formCambio);
    formCambio.elements.new_password.value = "";
    pintarIndicador(LOGICA.vistaDeFortaleza(null, false));
    mostrarPaso("correo");
    formCorreo.elements.email.focus();
  });

  /* ---------- Abrir la ventana de iniciar sesión ---------- */

  function abrirSesion(e) {
    if (e) e.preventDefault();
    var entrar = document.querySelector(".cuenta-entrar");
    if (entrar) entrar.click();
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-abrir-sesion]"), function (a) { a.addEventListener("click", abrirSesion); });
  document.querySelector("[data-iniciar-sesion]").addEventListener("click", abrirSesion);

  /* ---------- Con sesión iniciada no hay nada que recuperar ---------- */

  fetch(API + "/me", { credentials: "same-origin", headers: { "Accept": "application/json" } }).then(function (respuesta) {
    if (respuesta.status !== 200) return null;
    return respuesta.json();
  }).then(function (yo) {
    if (!yo || !yo.first_name) return;
    var nota = document.querySelector("[data-ya-con-sesion]");
    nota.textContent = LOGICA.avisoDeSesionIniciada(yo.first_name);
    nota.hidden = false;
    formCorreo.hidden = true;
    document.querySelector("[data-intro]").hidden = true;
  }, function () { /* sin servidor: el formulario avisará al mandarlo */ }).then(function () {
    document.documentElement.setAttribute("data-recuperar-listo", "");
  });
})();
