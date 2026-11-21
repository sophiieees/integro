/* Íntegro, la cuenta en la pantalla
   -------------------------------------------------------------------
   1. Al cargar, pregunta a la API quién tiene sesión (GET /auth/me), decide la
      vista de la persona (visitante, cliente, anfitrión o administrador; ver
      docs/diseno/vistas.md), arma la cabecera de esa vista (estructura.js) y
      pinta la cuenta: «Iniciar sesión» y «Crear cuenta», o el nombre con su
      menú, que termina en «Cerrar sesión».
   2. «Iniciar sesión» abre una ventana sobre la página con los dos pasos del inicio
      de sesión (ADR 0014): correo y contraseña, y luego el código.
   3. Al terminar, la ventana se cierra y la persona sigue en la misma página.
   4. «Cerrar sesión» cierra la sesión (POST /auth/logout) con la clave
      anti-falsificación que la API entrega en /auth/me.
   5. Una página protegida (data-requiere en el body) muestra su contenido solo a
      quien puede verlo; a los demás, una explicación y a dónde ir.
   6. Un administrador puede elegir mirar la vista de cliente o la de anfitrión con
      su propia cuenta; lo elegido se recuerda solo en esa pestaña del navegador.

   La cabecera es comodidad, no seguridad: el permiso lo da la API en cada ruta.
   La llave de sesión viaja en una cookie que este código no puede leer
   (ADR 0015): el navegador la manda solo, con credentials: "same-origin".
   Qué decir en cada caso lo decide cuenta-logica.js.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_CUENTA;
  if (!LOGICA) return;
  var ESTRUCTURA = window.INTEGRO_ESTRUCTURA || null;

  var API = "/api/v1/auth";
  var VER_COMO = "integro_view_as";
  /* correo es el que se escribe en la ventana de inicio de sesión; correoDeLaCuenta, el de la persona con sesión. */
  var estado = {
    sesion: false, nombre: null, apellidos: "", correoDeLaCuenta: "", clave: null, servidor: true,
    esAnfitrion: false, esAdmin: false, paso: "correo", correo: "", enviando: false
  };
  var vistaPintada = "visitante";
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

  /* ---------- La vista elegida por un administrador ---------- */

  /* sessionStorage puede no estar (ventana privada, datos bloqueados): sin él, el administrador ve su vista. */
  function leerVerComo() {
    try { return window.sessionStorage.getItem(VER_COMO); } catch (e) { return null; }
  }

  function guardarVerComo(vista) {
    try {
      if (vista === "cliente" || vista === "anfitrion") window.sessionStorage.setItem(VER_COMO, vista);
      else window.sessionStorage.removeItem(VER_COMO);
    } catch (e) { /* no se recuerda y ya */ }
  }

  /* ---------- Cabecera ---------- */

  function menuDeLaCuenta(vista) {
    var items = ESTRUCTURA ? ESTRUCTURA.menuDeLaCuenta(vista, estado.esAdmin) : [];
    var lista = document.createElement("ul");
    lista.className = "cuenta-lista";
    lista.id = "menu-cuenta";
    lista.hidden = true;
    var anterior = null;
    items.forEach(function (item) {
      var fila = document.createElement("li");
      /* Una línea separa lo que el administrador puede mirar de lo propio de la vista. */
      if (anterior && !!anterior.verComo !== !!item.verComo) fila.className = "cuenta-separada";
      var a = document.createElement("a");
      a.href = item.href;
      a.textContent = item.texto;
      if (item.verComo) {
        a.setAttribute("data-ver-como", item.verComo);
        if (item.actual) a.setAttribute("aria-current", "true");
        a.addEventListener("click", function () { guardarVerComo(item.verComo); });
      }
      fila.appendChild(a);
      lista.appendChild(fila);
      anterior = item;
    });
    var ultima = document.createElement("li");
    if (items.length) ultima.className = "cuenta-separada";
    var salir = document.createElement("button");
    salir.type = "button";
    salir.className = "cuenta-salir";
    salir.textContent = "Cerrar sesión";
    salir.addEventListener("click", salirDeLaSesion);
    ultima.appendChild(salir);
    lista.appendChild(ultima);
    return lista;
  }

  function alternarMenu(zona, abrir) {
    var boton = zona.querySelector(".cuenta-nombre");
    var lista = zona.querySelector(".cuenta-lista");
    if (!boton || !lista) return;
    lista.hidden = !abrir;
    boton.setAttribute("aria-expanded", abrir ? "true" : "false");
  }

  function cerrarMenus(devolverFoco) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-cuenta]"), function (zona) {
      var lista = zona.querySelector(".cuenta-lista");
      if (!lista || lista.hidden) return;
      alternarMenu(zona, false);
      if (devolverFoco) zona.querySelector(".cuenta-nombre").focus();
    });
  }

  function pintarSesion(zona, vista) {
    var contenedor = document.createElement("div");
    contenedor.className = "cuenta-menu";
    if (estado.esAdmin && vista !== "administrador") {
      var nota = document.createElement("span");
      nota.className = "cuenta-nota solo-escritorio";
      nota.textContent = vista === "cliente" ? "Viendo como cliente" : "Viendo como anfitrión";
      contenedor.appendChild(nota);
    }
    var nombre = document.createElement("button");
    nombre.type = "button";
    nombre.className = "cuenta-nombre";
    nombre.setAttribute("aria-expanded", "false");
    nombre.setAttribute("aria-controls", "menu-cuenta");
    nombre.textContent = estado.nombre;
    nombre.addEventListener("click", function (e) {
      e.stopPropagation();
      var lista = zona.querySelector(".cuenta-lista");
      var abrir = lista.hidden;
      cerrarMenus(false);
      alternarMenu(zona, abrir);
    });
    contenedor.appendChild(nombre);
    contenedor.appendChild(menuDeLaCuenta(vista));
    zona.appendChild(contenedor);
  }

  function pintarVisitante(zona) {
    var entrar = document.createElement("a");
    entrar.className = "cuenta-entrar";
    entrar.href = "#entrar";
    entrar.textContent = "Iniciar sesión";
    entrar.addEventListener("click", function (e) { e.preventDefault(); abrirVentana(entrar); });
    var crear = document.createElement("a");
    crear.className = "cuenta-crear";
    crear.href = "registro.html";
    crear.textContent = "Crear cuenta";
    zona.appendChild(entrar);
    zona.appendChild(crear);
  }

  function pintarCabecera() {
    var vista = LOGICA.vistaDe(estado, leerVerComo());
    /* La cabecera se vuelve a armar solo si cambió la vista: la del visitante ya la armó estructura.js. */
    if (ESTRUCTURA && vista !== vistaPintada) {
      ESTRUCTURA.montarCabecera(document, vista, window.location);
      vistaPintada = vista;
    }
    Array.prototype.forEach.call(document.querySelectorAll("[data-cuenta]"), function (zona) {
      zona.innerHTML = "";
      if (estado.sesion) pintarSesion(zona, vista);
      else pintarVisitante(zona);
    });
  }

  /* ---------- Páginas protegidas ---------- */

  /* Pone los datos de la persona en la página; sin sesión (o al cerrarla) los borra, para que no queden en la página. */
  function llenarDatos(vacios) {
    var datos = { nombre: (estado.nombre + " " + estado.apellidos).trim(), correo: estado.correoDeLaCuenta };
    Array.prototype.forEach.call(document.querySelectorAll("[data-dato]"), function (el) {
      var valor = vacios ? "" : datos[el.getAttribute("data-dato")];
      if (typeof valor === "string") el.textContent = valor;
    });
  }

  /* El contenido estaba oculto cuando la página cargó, así que el navegador no pudo ir al ancla de la dirección
     (anfitrion.html#resenas). Se va ahí cuando el contenido ya se muestra. */
  function irAlAncla() {
    var destino = null;
    try { destino = window.location.hash ? document.getElementById(decodeURIComponent(window.location.hash.slice(1))) : null; }
    catch (e) { destino = null; }
    if (destino) destino.scrollIntoView();
  }

  function aplicarAcceso() {
    var requiere = document.body.getAttribute("data-requiere");
    var aviso = document.querySelector("[data-acceso]");
    var contenido = document.querySelector("[data-contenido]");
    if (!requiere || !aviso || !contenido) return;
    var permiso = LOGICA.permisoDePagina(requiere, estado);
    contenido.hidden = !permiso.permitido;
    aviso.hidden = permiso.permitido;
    if (permiso.permitido) { llenarDatos(false); irAlAncla(); return; }
    llenarDatos(true);
    aviso.querySelector("[data-acceso-titulo]").textContent = permiso.titulo;
    aviso.querySelector("[data-acceso-texto]").textContent = permiso.texto;
    var enlace = aviso.querySelector("[data-acceso-enlace]");
    enlace.textContent = permiso.accion.texto;
    enlace.hidden = false;
    enlace.href = permiso.accion.href || "#entrar";
    enlace.onclick = permiso.accion.iniciarSesion ? function (e) { e.preventDefault(); abrirVentana(enlace); } : null;
  }

  /* ---------- La sesión ---------- */

  function cargarSesion() {
    return peticion("GET", "/me").then(function (r) {
      var cabecera = LOGICA.estadoDeCabecera(r.status, r.cuerpo);
      estado.sesion = cabecera.sesion;
      estado.nombre = cabecera.nombre;
      estado.apellidos = cabecera.apellidos;
      estado.correoDeLaCuenta = cabecera.correo;
      estado.clave = cabecera.clave;
      estado.servidor = cabecera.servidor;
      estado.esAnfitrion = cabecera.esAnfitrion;
      estado.esAdmin = cabecera.esAdmin;
      /* Lo que se elige mirar solo vale para un administrador; si ya no lo es, se olvida. */
      if (!estado.esAdmin && leerVerComo()) guardarVerComo(null);
      pintarCabecera();
      aplicarAcceso();
    });
  }

  function sinSesion() {
    estado.sesion = false; estado.nombre = null; estado.apellidos = ""; estado.correoDeLaCuenta = ""; estado.clave = null;
    estado.esAnfitrion = false; estado.esAdmin = false;
    guardarVerComo(null);
    pintarCabecera();
    aplicarAcceso();
  }

  function salirDeLaSesion() {
    if (estado.enviando) return;
    estado.enviando = true;
    peticion("POST", "/logout", null, estado.clave).then(function (r) {
      estado.enviando = false;
      var resultado = LOGICA.despuesDeSalir(r.status);
      if (!resultado.sesion) {
        sinSesion();
      } else if (r.status === 403) {
        /* La clave ya no es la de esta sesión: se vuelve a pedir y se intenta una vez más. */
        cargarSesion().then(function () {
          if (estado.sesion) peticion("POST", "/logout", null, estado.clave).then(function (otra) {
            if (!LOGICA.despuesDeSalir(otra.status).sesion) sinSesion();
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
          "<p class=\"ventana-olvido\"><a href=\"recuperar-contrasena.html\">¿Olvidaste tu contraseña?</a></p>" +
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

  /* El menú de la cuenta se cierra al dar clic en otra parte o con Escape (el foco vuelve al nombre). */
  document.addEventListener("click", function (e) {
    if (!e.target.closest || !e.target.closest(".cuenta-menu")) cerrarMenus(false);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") cerrarMenus(true); });

  pintarCabecera();
  cargarSesion().then(function () {
    /* Avisa que ya se supo si hay sesión y si hay servidor. Las pruebas de principio a fin esperan esta marca. */
    document.documentElement.setAttribute("data-cuenta-lista", "");
    if (window.location.hash === "#entrar" && !estado.sesion) abrirVentana(document.querySelector(".cuenta-entrar"));
  });
})();
