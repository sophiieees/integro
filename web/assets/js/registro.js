/* Íntegro, la pantalla de registro
   -------------------------------------------------------------------
   registro.html tiene tres pasos (los de registro-logica.js):
   1. El formulario. Al mandarlo, POST /api/v1/auth/register crea la cuenta y la
      API envía un código al correo.
   2. El código. POST /api/v1/auth/verify-email comprueba el correo; «Enviar otro
      código» llama a POST /api/v1/auth/resend-code.
   3. Listo. «Iniciar sesión» abre la ventana de la cabecera (cuenta.js).

   Mientras la persona escribe, la contraseña se califica con
   POST /api/v1/auth/password-strength y se muestra el indicador de cuatro niveles.
   Esa ruta no guarda nada. La contraseña viaja solo a la propia API.

   Qué hacer con cada respuesta lo decide registro-logica.js.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_REGISTRO;
  var form = document.getElementById("formulario-registro");
  if (!LOGICA || !form) return;

  var API = "/api/v1/auth";
  var formCodigo = document.getElementById("formulario-codigo");
  var listo = document.getElementById("registro-listo");
  var aviso = document.querySelector("[data-aviso]");
  var estado = { enviando: false, correo: "", telefonoCambiado: false, secuencia: 0, temporizador: null };

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

  function campo(nombre) { return form.elements[nombre]; }

  function mostrarErrores(errores) {
    Array.prototype.forEach.call(form.querySelectorAll("[data-error-de]"), function (zona) {
      var nombre = zona.getAttribute("data-error-de");
      var avisos = errores[nombre] || [];
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

  function enfocar(nombre) {
    /* Los avisos del teléfono y de los términos van en campos que en el formulario se llaman distinto. */
    var destino = nombre === "phone" ? campo("numero") : nombre === "terms" ? campo("terminos") : campo(nombre);
    if (destino) destino.focus();
  }

  function mostrarPaso(paso) {
    form.hidden = paso !== "datos";
    formCodigo.hidden = paso !== "codigo";
    listo.hidden = paso !== "listo";
    /* La introducción es de los datos: en el código y en listo estorba. */
    document.querySelector("[data-intro]").hidden = paso !== "datos";
    var visible = paso === "datos" ? form : paso === "codigo" ? formCodigo : listo;
    var titulo = visible.querySelector("h2");
    if (titulo) { titulo.setAttribute("tabindex", "-1"); titulo.focus(); }
  }

  function ocupado(si) {
    estado.enviando = si;
    Array.prototype.forEach.call(document.querySelectorAll(".formulario-tarjeta button, .formulario-tarjeta input, .formulario-tarjeta select"), function (el) {
      el.disabled = si;
    });
  }

  function valores() {
    return {
      first_name: campo("first_name").value,
      last_name: campo("last_name").value,
      email: campo("email").value,
      password: campo("password").value,
      marcacion: marcacionElegida(),
      numero: campo("numero").value,
      country: campo("country").value,
      birth_date: campo("birth_date").value,
      terminos: campo("terminos").checked
    };
  }

  /* ---------- Países y teléfono ---------- */

  var paises = LOGICA.listaDePaises(window.Intl && window.Intl.DisplayNames, "es");
  var conMarcacion = LOGICA.paisesConMarcacion(paises);

  function opcion(valor, texto) {
    var o = document.createElement("option");
    o.value = valor;
    o.textContent = texto;
    return o;
  }

  paises.forEach(function (pais) { campo("country").appendChild(opcion(pais.codigo, pais.nombre)); });
  conMarcacion.forEach(function (pais) {
    var o = opcion(pais.codigo, "+" + pais.marcacion + " " + pais.nombre);
    o.setAttribute("data-marcacion", pais.marcacion);
    campo("marcacion").appendChild(o);
  });
  campo("country").value = "MX";
  campo("marcacion").value = "MX";

  function marcacionElegida() {
    var o = campo("marcacion").selectedOptions[0];
    return o ? o.getAttribute("data-marcacion") : "";
  }

  campo("marcacion").addEventListener("change", function () { estado.telefonoCambiado = true; });
  campo("country").addEventListener("change", function () {
    if (estado.telefonoCambiado) return;
    var codigo = LOGICA.marcacionParaElPais(campo("country").value, paises);
    if (codigo) campo("marcacion").value = codigo;
  });

  /* Nadie nace en el futuro. */
  campo("birth_date").max = new Date().toISOString().slice(0, 10);

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
    var actuales = valores();
    var numero = ++estado.secuencia;
    if (!actuales.password) { pintarIndicador(LOGICA.vistaDeFortaleza(null, false)); return; }
    peticion("/password-strength", LOGICA.cuerpoDeFortaleza(actuales)).then(function (r) {
      /* Si ya se escribió otra cosa, esta respuesta llegó tarde. */
      if (numero !== estado.secuencia) return;
      pintarIndicador(LOGICA.vistaDeFortaleza(r.status === 200 ? r.cuerpo : null, true));
    });
  }

  function programarCalificacion() {
    clearTimeout(estado.temporizador);
    estado.temporizador = setTimeout(calificar, 300);
  }

  ["password", "first_name", "last_name", "email"].forEach(function (nombre) {
    campo(nombre).addEventListener("input", programarCalificacion);
  });

  /* ---------- Paso 1: el formulario ---------- */

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (estado.enviando) return;
    mostrarAviso(null);
    var revision = LOGICA.revisarDatos(valores());
    mostrarErrores(revision.errores);
    if (LOGICA.hayErrores(revision.errores)) { enfocar(LOGICA.primerCampoConError(revision.errores)); return; }
    ocupado(true);
    peticion("/register", revision.datos).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDeRegistrar(r.status, r.cuerpo, revision.datos.email);
      if (siguiente.paso === "codigo") {
        estado.correo = siguiente.correo;
        formCodigo.querySelector("[data-texto]").textContent = siguiente.texto;
        /* La contraseña ya se mandó: no se queda escrita en la página. */
        campo("password").value = "";
        pintarIndicador(LOGICA.vistaDeFortaleza(null, false));
        mostrarPaso("codigo");
        formCodigo.elements.code.focus();
        return;
      }
      mostrarErrores(LOGICA.resumirAvisos(siguiente.errores));
      /* Lo que le falta a la contraseña lo muestra el indicador: se actualiza ya, sin esperar a que la persona escriba. */
      if (siguiente.errores.password) calificar();
      mostrarAviso(siguiente.aviso);
      agregarEnlaceDeSesion(siguiente.yaTieneCuenta);
      var primero = LOGICA.primerCampoConError(siguiente.errores);
      if (primero) enfocar(primero);
    });
  });

  /* Si el correo ya tiene cuenta, el aviso del campo ofrece iniciar sesión. */
  function agregarEnlaceDeSesion(si) {
    var zona = form.querySelector("[data-error-de=email]");
    var anterior = zona.querySelector("[data-enlace-sesion]");
    if (anterior) anterior.remove();
    if (!si) return;
    var enlace = document.createElement("a");
    enlace.href = "#entrar";
    enlace.setAttribute("data-enlace-sesion", "");
    enlace.textContent = "Inicia sesión";
    enlace.addEventListener("click", abrirSesion);
    zona.appendChild(document.createTextNode(" "));
    zona.appendChild(enlace);
  }

  function abrirSesion(e) {
    if (e) e.preventDefault();
    var entrar = document.querySelector(".cuenta-entrar");
    if (entrar) entrar.click();
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-abrir-sesion]"), function (a) { a.addEventListener("click", abrirSesion); });
  document.querySelector("[data-iniciar-sesion]").addEventListener("click", abrirSesion);

  /* ---------- Paso 2: el código ---------- */

  function mostrarNota(texto) {
    var nota = formCodigo.querySelector("[data-nota]");
    nota.textContent = texto || "";
    nota.hidden = !texto;
  }

  formCodigo.addEventListener("submit", function (e) {
    e.preventDefault();
    if (estado.enviando) return;
    mostrarAviso(null);
    var codigo = formCodigo.elements.code.value.trim();
    var revision = LOGICA.revisarCodigo(codigo);
    if (revision) { mostrarAviso(revision.aviso); formCodigo.elements.code.focus(); return; }
    ocupado(true);
    peticion("/verify-email", { email: estado.correo, code: codigo }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDeComprobar(r.status, r.cuerpo);
      mostrarAviso(siguiente.aviso);
      if (siguiente.paso === "listo") {
        var nota = listo.querySelector("[data-nota-final]");
        nota.textContent = siguiente.nota || "";
        nota.hidden = !siguiente.nota;
        mostrarPaso("listo");
        listo.querySelector("[data-iniciar-sesion]").focus();
        return;
      }
      formCodigo.elements.code.focus();
    });
  });

  formCodigo.querySelector("[data-reenviar]").addEventListener("click", function () {
    if (estado.enviando) return;
    mostrarAviso(null);
    mostrarNota(null);
    ocupado(true);
    peticion("/resend-code", { email: estado.correo }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDeReenviar(r.status, r.cuerpo, estado.correo);
      mostrarAviso(siguiente.aviso);
      mostrarNota(siguiente.nota);
      formCodigo.elements.code.focus();
    });
  });

  /* ---------- Con sesión iniciada no hay a quién registrar ---------- */

  fetch(API + "/me", { credentials: "same-origin", headers: { "Accept": "application/json" } }).then(function (respuesta) {
    if (respuesta.status !== 200) return null;
    return respuesta.json();
  }).then(function (yo) {
    if (!yo || !yo.first_name) return;
    var nota = document.querySelector("[data-ya-con-sesion]");
    nota.textContent = LOGICA.avisoDeSesionIniciada(yo.first_name);
    nota.hidden = false;
    form.hidden = true;
  }, function () { /* sin servidor: el formulario avisará al mandarlo */ }).then(function () {
    document.documentElement.setAttribute("data-registro-listo", "");
  });
})();
