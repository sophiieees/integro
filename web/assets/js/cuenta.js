/* Íntegro, la cuenta en la pantalla
   -------------------------------------------------------------------
   1. Al cargar, pregunta a la API quién tiene sesión (GET /auth/me) y pinta
      la cabecera: «Iniciar sesión», o el nombre y «Cerrar sesión».
   2. «Iniciar sesión» abre una ventana sobre la página con los dos pasos del inicio
      de sesión (ADR 0014): correo y contraseña, y luego el código.
   3. Al terminar, la ventana se cierra y la persona sigue en la misma página.
   4. «Cerrar sesión» cierra la sesión (POST /auth/logout) con la clave
      anti-falsificación que la API entrega en /auth/me.

   La llave de sesión viaja en una cookie que este código no puede leer
   (ADR 0015): el navegador la manda solo, con credentials: "same-origin".
   Qué decir en cada caso lo decide cuenta-logica.js.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_CUENTA;
  if (!LOGICA) return;

  var API = "/api/v1/auth";
  var estado = { sesion: false, nombre: null, clave: null, servidor: true, paso: "correo", correo: "", enviando: false };
  var ventana = null;
  var quienAbrio = null;

  /* ---------- API ---------- */

  function peticion(metodo, ruta, cuerpo, clave) {
    var cabeceras = { "Accept": "application/json" };
    if (cuerpo) cabeceras["Content-Type"] = "application/json";
    if (clave) cabeceras["X-CSRF-Token"] = clave;
    return fetch(API + ruta, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
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

  /* ---------- Cabecera ---------- */

  function pintarCabecera() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-cuenta]"), function (zona) {
      zona.innerHTML = "";
      if (estado.sesion) {
        var nombre = document.createElement("span");
        nombre.className = "cuenta-nombre";
        nombre.textContent = estado.nombre;
        var salir = document.createElement("button");
        salir.type = "button";
        salir.className = "btn-enlace cuenta-salir";
        salir.textContent = "Cerrar sesión";
        salir.addEventListener("click", salirDeLaSesion);
        zona.appendChild(nombre);
        zona.appendChild(salir);
      } else {
        var entrar = document.createElement("a");
        entrar.className = "cuenta-entrar";
        entrar.href = "#entrar";
        entrar.textContent = "Iniciar sesión";
        entrar.addEventListener("click", function (e) { e.preventDefault(); abrirVentana(entrar); });
        zona.appendChild(entrar);
      }
    });
  }

  function cargarSesion() {
    return peticion("GET", "/me").then(function (r) {
      var cabecera = LOGICA.estadoDeCabecera(r.status, r.cuerpo);
      estado.sesion = cabecera.sesion;
      estado.nombre = cabecera.nombre;
      estado.clave = cabecera.clave;
      estado.servidor = cabecera.servidor;
      pintarCabecera();
    });
  }

  function salirDeLaSesion() {
    if (estado.enviando) return;
    estado.enviando = true;
    peticion("POST", "/logout", null, estado.clave).then(function (r) {
      estado.enviando = false;
      var resultado = LOGICA.despuesDeSalir(r.status);
      if (!resultado.sesion) {
        estado.sesion = false; estado.nombre = null; estado.clave = null;
        pintarCabecera();
      } else if (r.status === 403) {
        /* La clave ya no es la de esta sesión: se vuelve a pedir y se intenta una vez más. */
        cargarSesion().then(function () {
          if (estado.sesion) peticion("POST", "/logout", null, estado.clave).then(function (otra) {
            if (!LOGICA.despuesDeSalir(otra.status).sesion) { estado.sesion = false; estado.nombre = null; estado.clave = null; pintarCabecera(); }
            else window.alert(resultado.aviso);
          });
        });
      } else {
        window.alert(resultado.aviso);
      }
    });
  }

  /* ---------- La ventana ---------- */

  function crearVentana() {
    var fondo = document.createElement("div");
    fondo.className = "ventana-fondo";
    fondo.id = "ventana-entrar";
    fondo.hidden = true;
    fondo.innerHTML =
      "<div class=\"ventana\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"ventana-entrar-titulo\">" +
        "<h2 id=\"ventana-entrar-titulo\">Iniciar sesión</h2>" +
        "<p class=\"ventana-aviso\" data-aviso role=\"alert\" hidden></p>" +
        "<form data-paso=\"correo\" novalidate>" +
          "<label class=\"campo\"><span>Correo electrónico</span><input type=\"email\" name=\"email\" autocomplete=\"email\" inputmode=\"email\" spellcheck=\"false\"></label>" +
          "<label class=\"campo\"><span>Contraseña</span><input type=\"password\" name=\"password\" autocomplete=\"current-password\"></label>" +
          "<div class=\"ventana-acciones\">" +
            "<button type=\"button\" class=\"btn-enlace\" data-cancelar>Cancelar</button>" +
            "<button type=\"submit\" class=\"btn btn-primario\">Continuar</button>" +
          "</div>" +
        "</form>" +
        "<form data-paso=\"codigo\" novalidate hidden>" +
          "<p class=\"ventana-texto\" data-texto></p>" +
          "<label class=\"campo\"><span>Código</span><input type=\"text\" name=\"code\" autocomplete=\"one-time-code\" inputmode=\"numeric\" maxlength=\"6\" pattern=\"[0-9]*\"></label>" +
          "<div class=\"ventana-acciones\">" +
            "<button type=\"button\" class=\"btn-enlace\" data-volver>Volver</button>" +
            "<button type=\"submit\" class=\"btn btn-primario\">Iniciar sesión</button>" +
          "</div>" +
        "</form>" +
        "<p class=\"ventana-pie\">¿Aún no tienes una cuenta? <a href=\"registro.html\">Regístrate</a></p>" +
      "</div>";
    document.body.appendChild(fondo);

    fondo.addEventListener("click", function (e) { if (e.target === fondo) cerrarVentana(); });
    fondo.querySelector("[data-cancelar]").addEventListener("click", cerrarVentana);
    fondo.querySelector("[data-volver]").addEventListener("click", function () { mostrarPaso("correo", null, "email"); });
    fondo.querySelector("form[data-paso=correo]").addEventListener("submit", enviarCorreo);
    fondo.querySelector("form[data-paso=codigo]").addEventListener("submit", enviarCodigo);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !fondo.hidden) cerrarVentana(); });
    return fondo;
  }

  function formulario(paso) { return ventana.querySelector("form[data-paso=" + paso + "]"); }

  function mostrarAviso(texto) {
    var aviso = ventana.querySelector("[data-aviso]");
    aviso.textContent = texto || "";
    aviso.hidden = !texto;
  }

  function mostrarPaso(paso, aviso, campo) {
    estado.paso = paso;
    formulario("correo").hidden = paso !== "correo";
    formulario("codigo").hidden = paso !== "codigo";
    mostrarAviso(aviso);
    var entrada = campo ? ventana.querySelector("[name=" + campo + "]") : ventana.querySelector("form:not([hidden]) input");
    if (entrada) entrada.focus();
  }

  function ocupado(si) {
    estado.enviando = si;
    Array.prototype.forEach.call(ventana.querySelectorAll("button, input"), function (el) { el.disabled = si; });
  }

  function abrirVentana(desde) {
    if (!ventana) ventana = crearVentana();
    quienAbrio = desde || null;
    ventana.hidden = false;
    document.body.classList.add("con-ventana");
    formulario("correo").reset();
    formulario("codigo").reset();
    mostrarPaso("correo", estado.servidor ? null : LOGICA.SIN_SERVIDOR, "email");
  }

  function cerrarVentana() {
    if (!ventana || ventana.hidden) return;
    ventana.hidden = true;
    document.body.classList.remove("con-ventana");
    formulario("correo").reset();
    formulario("codigo").reset();
    mostrarAviso(null);
    estado.paso = "correo";
    if (quienAbrio && document.body.contains(quienAbrio)) quienAbrio.focus();
    quienAbrio = null;
  }

  function enviarCorreo(e) {
    e.preventDefault();
    if (estado.enviando) return;
    var form = formulario("correo");
    var correo = form.email.value.trim();
    var revision = LOGICA.revisarCorreoYContrasena(correo, form.password.value);
    if (revision) { mostrarPaso("correo", revision.aviso, revision.campo); return; }
    ocupado(true);
    peticion("POST", "/login", { email: correo, password: form.password.value }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDelCorreo(r.status, r.cuerpo, correo);
      estado.servidor = r.status !== 0;
      if (siguiente.paso === "codigo") {
        estado.correo = correo;
        form.password.value = "";
        ventana.querySelector("[data-texto]").textContent = siguiente.texto;
      }
      mostrarPaso(siguiente.paso, siguiente.aviso, siguiente.campo);
    });
  }

  function enviarCodigo(e) {
    e.preventDefault();
    if (estado.enviando) return;
    var form = formulario("codigo");
    var codigo = form.code.value.trim();
    var revision = LOGICA.revisarCodigo(codigo);
    if (revision) { mostrarPaso("codigo", revision.aviso, revision.campo); return; }
    ocupado(true);
    peticion("POST", "/login/verify", { email: estado.correo, code: codigo }).then(function (r) {
      ocupado(false);
      var siguiente = LOGICA.despuesDelCodigo(r.status, r.cuerpo);
      if (siguiente.paso === "dentro") {
        cerrarVentana();
        cargarSesion();
        return;
      }
      if (siguiente.paso === "correo") form.code.value = "";
      mostrarPaso(siguiente.paso, siguiente.aviso, siguiente.campo);
    });
  }

  /* ---------- Arranque ---------- */

  pintarCabecera();
  cargarSesion().then(function () {
    /* Avisa que ya se supo si hay sesión y si hay servidor. Las pruebas de principio a fin esperan esta marca. */
    document.documentElement.setAttribute("data-cuenta-lista", "");
    if (window.location.hash === "#entrar" && !estado.sesion) abrirVentana(document.querySelector(".cuenta-entrar"));
  });
})();
