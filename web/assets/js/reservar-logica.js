/* Íntegro, lógica de «Reservar» en la ficha de una propiedad (sin pantalla)
   -------------------------------------------------------------------
   Decisión de Sophia del 20 de noviembre de 2026 (docs/diseno/vistas.md): un visitante que da clic en «Reservar»
   sin sesión ve el aviso de iniciar sesión o crear su cuenta y, al terminar, vuelve a la misma propiedad con sus
   fechas y sus huéspedes. Eso se guarda en la dirección de la página, no en el navegador.

   Aquí se decide qué se guarda en la dirección, qué se lee de ella y qué se le dice a la persona. No toca el
   documento: eso lo hace reservar.js. Así se prueba sin navegador, con node.

   La dirección de la ficha es propiedad.html?id=2&llegada=2026-12-01&salida=2026-12-03&huespedes=2. Lo que viene
   en ella lo escribió quien abrió el enlace: cada dato se revisa y lo que no sirve se ignora.

   Funciona en el navegador (window.INTEGRO_RESERVAR) y en node (module.exports).
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = fabrica(require("./cuenta-logica.js"));
  else raiz.INTEGRO_RESERVAR = fabrica(raiz.INTEGRO_CUENTA);
})(typeof window !== "undefined" ? window : this, function (CUENTA) {
  "use strict";

  var HUESPEDES_MAX = 6;
  var ID_MAX = 9999;

  /* Una fecha AAAA-MM-DD que existe (no el 31 de febrero), o "". */
  function fechaValida(texto) {
    if (typeof texto !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(texto)) return "";
    var d = new Date(texto + "T00:00:00Z");
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === texto ? texto : "";
  }

  function huespedesValidos(texto) {
    if (typeof texto !== "string" || !/^[0-9]{1,2}$/.test(texto)) return "";
    var n = parseInt(texto, 10);
    return n >= 1 && n <= HUESPEDES_MAX ? String(n) : "";
  }

  /* El número de la propiedad (?id=), o null si no es uno razonable. */
  function idValido(texto) {
    if (typeof texto !== "string" || !/^[0-9]{1,4}$/.test(texto)) return null;
    var n = parseInt(texto, 10);
    return n >= 1 && n <= ID_MAX ? n : null;
  }

  /* Lo que la dirección trae de las fechas y los huéspedes. busqueda es window.location.search.
     Cada dato que no sirve queda vacío; nunca falla. */
  function valoresDeLaDireccion(busqueda) {
    var params = new URLSearchParams(typeof busqueda === "string" ? busqueda : "");
    return {
      llegada: fechaValida(params.get("llegada")),
      salida: fechaValida(params.get("salida")),
      huespedes: huespedesValidos(params.get("huespedes"))
    };
  }

  /* Revisa lo que la persona escribió antes de guardarlo. Devuelve el aviso, o null si está bien.
     No exige las fechas: se guardan las que haya. Solo avisa de las que no pueden ser. */
  function revisarReserva(valores) {
    var llegada = valores.llegada || "";
    var salida = valores.salida || "";
    if (llegada && !fechaValida(llegada)) return { campo: "llegada", aviso: "La fecha de llegada no es válida." };
    if (salida && !fechaValida(salida)) return { campo: "salida", aviso: "La fecha de salida no es válida." };
    if (llegada && salida && salida <= llegada) {
      return { campo: "salida", aviso: "La fecha de salida debe ser posterior a la de llegada." };
    }
    return null;
  }

  /* La dirección de la ficha con lo que la persona eligió, o null si la propiedad no es una válida. */
  function direccionDeLaFicha(id, valores) {
    var numero = idValido(String(id));
    if (numero === null) return null;
    var partes = ["id=" + numero];
    var llegada = fechaValida(valores.llegada);
    var salida = fechaValida(valores.salida);
    var huespedes = huespedesValidos(String(valores.huespedes || ""));
    if (llegada) partes.push("llegada=" + llegada);
    if (salida) partes.push("salida=" + salida);
    if (huespedes) partes.push("huespedes=" + huespedes);
    return "propiedad.html?" + partes.join("&");
  }

  /* El enlace de «Crear cuenta» desde la ficha: lleva a la persona de vuelta a esta propiedad al terminar.
     Si la dirección no es una de las que se permiten, el enlace es el de siempre. */
  function enlaceDeRegistro(direccion) {
    var segura = CUENTA.siguienteSeguro(direccion);
    return segura ? "registro.html?siguiente=" + encodeURIComponent(segura) : "registro.html";
  }

  var SIN_SESION = {
    titulo: "Para reservar necesitas una cuenta",
    texto: "Inicia sesión o crea tu cuenta. Volverás a esta propiedad con tus fechas y tus huéspedes."
  };
  var CON_SESION = {
    titulo: "Las reservas se abren pronto",
    texto: "Todavía no se puede reservar. Tus fechas y tus huéspedes quedaron guardados en la dirección de esta página."
  };
  var RECIEN_INICIADA = {
    titulo: "Ya iniciaste sesión",
    texto: "Las reservas se abren pronto. Tus fechas y tus huéspedes siguen aquí."
  };

  /* Qué se le dice a la persona al dar clic en «Reservar». */
  function avisoDeReserva(haySesion) {
    return haySesion ? CON_SESION : SIN_SESION;
  }

  /* Qué se le dice cuando estaba viendo el aviso de iniciar sesión y la inicia en la misma página. */
  function avisoTrasIniciarSesion() {
    return RECIEN_INICIADA;
  }

  return {
    HUESPEDES_MAX: HUESPEDES_MAX,
    fechaValida: fechaValida,
    huespedesValidos: huespedesValidos,
    idValido: idValido,
    valoresDeLaDireccion: valoresDeLaDireccion,
    revisarReserva: revisarReserva,
    direccionDeLaFicha: direccionDeLaFicha,
    enlaceDeRegistro: enlaceDeRegistro,
    avisoDeReserva: avisoDeReserva,
    avisoTrasIniciarSesion: avisoTrasIniciarSesion
  };
});
