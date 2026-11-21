/* Íntegro, el botón «Reservar» de la ficha de una propiedad
   -------------------------------------------------------------------
   1. Al cargar, si la dirección trae fechas o huéspedes (llegada, salida, huespedes), los pone en el formulario.
      Es lo que hace que, después de iniciar sesión o de crear la cuenta, la persona vuelva a su propiedad con lo
      que había elegido.
   2. Al dar clic en «Reservar», revisa las fechas, guarda lo elegido en la dirección de la página (sin recargarla)
      y:
        - sin sesión, muestra el aviso de iniciar sesión o crear la cuenta; «Crear cuenta» lleva el regreso a esta
          propiedad en ?siguiente=;
        - con sesión, dice que las reservas se abren pronto: todavía no existen.
   3. Si estaba el aviso de iniciar sesión y la persona inicia sesión en la misma página, el aviso cambia.

   No guarda nada en el navegador: todo va en la dirección. Qué se dice lo decide reservar-logica.js.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_RESERVAR;
  var formulario = document.querySelector(".caja-precio form");
  var boton = formulario && formulario.querySelector("button.btn-primario");
  var zona = document.querySelector("[data-reserva-aviso]");
  if (!LOGICA || !formulario || !boton || !zona) return;

  var idDeLaPropiedad = new URLSearchParams(window.location.search).get("id");

  function valores() {
    return {
      llegada: formulario.elements.llegada.value,
      salida: formulario.elements.salida.value,
      huespedes: formulario.elements.huespedes.value
    };
  }

  /* ---------- 1. Lo que trae la dirección ---------- */

  var guardados = LOGICA.valoresDeLaDireccion(window.location.search);
  if (guardados.llegada) formulario.elements.llegada.value = guardados.llegada;
  if (guardados.salida) formulario.elements.salida.value = guardados.salida;
  if (guardados.huespedes) formulario.elements.huespedes.value = guardados.huespedes;

  /* ---------- Lo que se ve ---------- */

  var mostrado = null; /* "sin-sesion", "con-sesion" o null */

  function vaciar() {
    zona.innerHTML = "";
    zona.hidden = true;
    mostrado = null;
  }

  function parrafo(clase, texto) {
    var p = document.createElement("p");
    p.className = clase;
    p.textContent = texto;
    return p;
  }

  function pintar(aviso, acciones, clave) {
    zona.innerHTML = "";
    zona.appendChild(parrafo("reserva-aviso-titulo", aviso.titulo));
    zona.appendChild(parrafo("reserva-aviso-texto", aviso.texto));
    if (acciones) zona.appendChild(acciones);
    zona.hidden = false;
    mostrado = clave;
  }

  function avisoDeFecha(texto) {
    zona.innerHTML = "";
    zona.appendChild(parrafo("reserva-aviso-texto reserva-aviso-error", texto));
    zona.hidden = false;
    mostrado = null;
  }

  function accionesSinSesion(direccion) {
    var contenedor = document.createElement("div");
    contenedor.className = "reserva-aviso-acciones";
    var entrar = document.createElement("button");
    entrar.type = "button";
    entrar.className = "btn btn-primario";
    entrar.setAttribute("data-reserva-entrar", "");
    entrar.textContent = "Iniciar sesión";
    entrar.addEventListener("click", function () {
      var cabecera = document.querySelector(".cuenta-entrar");
      if (cabecera) cabecera.click();
    });
    var crear = document.createElement("a");
    crear.className = "btn btn-secundario";
    crear.setAttribute("data-reserva-crear", "");
    crear.href = LOGICA.enlaceDeRegistro(direccion);
    crear.textContent = "Crear cuenta";
    contenedor.appendChild(entrar);
    contenedor.appendChild(crear);
    return contenedor;
  }

  /* ---------- 2. El clic en «Reservar» ---------- */

  boton.addEventListener("click", function () {
    var actuales = valores();
    var revision = LOGICA.revisarReserva(actuales);
    if (revision) {
      avisoDeFecha(revision.aviso);
      formulario.elements[revision.campo].focus();
      return;
    }
    var direccion = LOGICA.direccionDeLaFicha(idDeLaPropiedad, actuales);
    /* La dirección guarda lo elegido sin recargar la página ni agregar un paso al historial. */
    if (direccion) {
      try { window.history.replaceState(null, "", direccion); } catch (e) { /* sin historial: no se guarda y ya */ }
    }
    var haySesion = !!(window.INTEGRO_SESION && window.INTEGRO_SESION.activa());
    if (haySesion) pintar(LOGICA.avisoDeReserva(true), null, "con-sesion");
    else pintar(LOGICA.avisoDeReserva(false), accionesSinSesion(direccion), "sin-sesion");
  });

  /* Un cambio en el formulario quita un aviso de fecha que ya no aplica. */
  ["llegada", "salida", "huespedes"].forEach(function (nombre) {
    formulario.elements[nombre].addEventListener("change", function () {
      if (mostrado === null) vaciar();
    });
  });

  /* ---------- 3. Inicia sesión en esta misma página ---------- */

  document.addEventListener("integro:sesion", function (e) {
    if (mostrado === "sin-sesion" && e.detail && e.detail.sesion) pintar(LOGICA.avisoTrasIniciarSesion(), null, "con-sesion");
  });
})();
