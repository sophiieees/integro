/* Íntegro, la cabecera y el pie de las páginas
   -------------------------------------------------------------------
   La cabecera y el pie viven aquí, en una sola copia. Cada página trae solo
   dos espacios vacíos:

     <header class="cabecera" data-cabecera="portada"></header>
     <footer class="pie" data-pie></footer>

   y este script los llena al cargar. Así un cambio se hace una vez y vale
   para todas las páginas.

   La cabecera depende de dos cosas (docs/diseno/vistas.md):

   - La VISTA de quien mira: visitante, cliente, anfitrión o administrador.
     Cada una lleva sus enlaces. Al cargar se arma la del visitante; cuenta.js
     pregunta a la API quién tiene sesión y vuelve a armarla con la que toca.
   - La PÁGINA (data-cabecera): «anfitriones» cambia «Conviértete en anfitrión»
     por «Publica tu propiedad», porque ya se está ahí.

   Una vista nueva se agrega con una entrada de VISTAS, sin tocar las páginas.
   La cabecera es comodidad, no seguridad: el permiso lo da la API en cada ruta.

   La zona de la cuenta ([data-cuenta]) queda vacía: la pinta cuenta.js, que
   se carga después de este archivo.

   Sin JavaScript la página se ve sin cabecera ni pie (ADR 0008).
   Funciona en el navegador (se monta solo) y en node (module.exports), para
   probarlo sin navegador.
*/
(function (raiz, fabrica) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.INTEGRO_ESTRUCTURA = fabrica();
})(typeof window !== "undefined" ? window : this, function () {
  "use strict";

  var MARCA =
    "<a class=\"marca\" href=\"index.html\" aria-label=\"Íntegro, inicio\">" +
    "<span class=\"marca-punto\" aria-hidden=\"true\"></span>Íntegro</a>";

  /* La barra de navegación del visitante y del cliente (decisión del 20 de noviembre de 2026).
     «Todo» es la portada; «Alojamientos», sus resultados; las otras dos todavía no existen. */
  var PESTANAS = [
    { clave: "todo", texto: "Todo", href: "index.html" },
    { clave: "alojamientos", texto: "Alojamientos", href: "index.html#resultados" },
    { clave: "experiencias", texto: "Experiencias", href: "proximamente.html?seccion=experiencias" },
    { clave: "servicios", texto: "Servicios", href: "proximamente.html?seccion=servicios" }
  ];

  var SER_ANFITRION = { texto: "Conviértete en anfitrión", href: "anfitriones.html", clase: "btn-enlace solo-escritorio" };
  var PUBLICAR = { texto: "Publica tu propiedad", href: "#publicar", clase: "btn btn-azul solo-escritorio" };

  var MI_CUENTA = { texto: "Mi cuenta", href: "mi-cuenta.html" };
  var MIS_RESERVAS = { texto: "Mis reservas", href: "mi-cuenta.html#reservas" };
  var BUSCAR = { texto: "Buscar hospedaje", href: "index.html" };

  /* Cada vista dice qué enlaces lleva junto a la marca (enlaces), qué acciones a la derecha (acciones) y qué
     trae el menú de la cuenta (menu). «Cerrar sesión» lo agrega cuenta.js al final de todos. */
  var VISTAS = {
    visitante: { enlaces: PESTANAS, acciones: [SER_ANFITRION], menu: [] },
    cliente: {
      enlaces: PESTANAS,
      acciones: [SER_ANFITRION],
      menu: [
        MI_CUENTA,
        MIS_RESERVAS,
        { texto: "Mensajes", href: "mi-cuenta.html#mensajes" },
        { texto: "Reseñas", href: "mi-cuenta.html#resenas" },
        { texto: "Comentarios", href: "mi-cuenta.html#comentarios" }
      ]
    },
    anfitrion: {
      enlaces: [
        { texto: "Mis propiedades", href: "anfitrion.html#propiedades" },
        { texto: "Reservas", href: "anfitrion.html#reservas" },
        { texto: "Reseñas", href: "anfitrion.html#resenas" },
        { texto: "Comentarios", href: "anfitrion.html#comentarios" },
        { texto: "Chats con clientes", href: "anfitrion.html#chats" },
        { texto: "Subir publicación", href: "anfitrion.html#publicar" }
      ],
      acciones: [],
      /* Sigue pudiendo reservar como huésped: una sola cuenta es las dos cosas. */
      menu: [MI_CUENTA, MIS_RESERVAS, BUSCAR]
    },
    administrador: {
      enlaces: [
        { texto: "Verificaciones", href: "administracion.html#verificaciones" },
        { texto: "Casos", href: "administracion.html#casos" },
        { texto: "Cargos", href: "administracion.html#cargos" },
        { texto: "Bitácora", href: "administracion.html#bitacora" }
      ],
      acciones: [],
      menu: [MI_CUENTA]
    }
  };
  var VISTA_POR_DEFECTO = "visitante";

  /* Lo que un administrador puede mirar con su propia cuenta. No es actuar como otra persona. */
  var VER_COMO = [
    { clave: "administrador", texto: "Vista de administrador", href: "administracion.html" },
    { clave: "cliente", texto: "Ver como cliente", href: "index.html" },
    { clave: "anfitrion", texto: "Ver como anfitrión", href: "anfitrion.html" }
  ];

  /* Los nombres de página que traen las páginas en data-cabecera. Solo «anfitriones» cambia algo. */
  var PAGINAS = ["portada", "interior", "anfitriones"];
  var PAGINA_POR_DEFECTO = "interior";

  var ENLACES_DEL_PIE = [
    { texto: "Cómo funciona", href: "como-funciona.html" },
    { texto: "Anfitriones", href: "anfitriones.html" },
    { texto: "Términos y condiciones", href: "#" },
    { texto: "Aviso de privacidad", href: "#" }
  ];

  var SECCIONES_PROXIMAS = { experiencias: "Experiencias", servicios: "Servicios" };

  /* La entrada de VISTAS de esa vista; si no existe (o es otra cosa), la del visitante. */
  function datosDeLaVista(vista) {
    return Object.prototype.hasOwnProperty.call(VISTAS, vista) ? VISTAS[vista] : VISTAS[VISTA_POR_DEFECTO];
  }

  function enlace(e, clase, extra) {
    return "<a" + (clase ? " class=\"" + clase + "\"" : "") + (extra || "") + " href=\"" + e.href + "\">" + e.texto + "</a>";
  }

  /* Qué pestaña de la barra es la de esta página, o null si ninguna.
     ruta, busqueda y hash son los de window.location. */
  function pestanaActiva(ruta, busqueda, hash) {
    var archivo = String(ruta || "").split("/").pop() || "index.html";
    if (archivo === "index.html") return hash === "#resultados" ? "alojamientos" : "todo";
    if (archivo === "propiedad.html") return "alojamientos";
    if (archivo === "proximamente.html") {
      var m = /(?:^|[?&])seccion=([a-z]+)(?:&|$)/.exec(String(busqueda || ""));
      return m && tituloDeSeccion(busqueda) ? m[1] : null;
    }
    return null;
  }

  /* El nombre de la sección de proximamente.html?seccion=…, o null si no es una de las que se conocen. */
  function tituloDeSeccion(busqueda) {
    var m = /(?:^|[?&])seccion=([a-z]+)(?:&|$)/.exec(String(busqueda || ""));
    return m && Object.prototype.hasOwnProperty.call(SECCIONES_PROXIMAS, m[1]) ? SECCIONES_PROXIMAS[m[1]] : null;
  }

  /* El HTML de dentro de <header class="cabecera">.
     pagina es el data-cabecera de la página; vista, quién mira; activa, la clave de la pestaña que se marca. */
  function construirCabecera(pagina, vista, activa) {
    var v = datosDeLaVista(vista);
    var enAnfitriones = pagina === "anfitriones";
    var partes = ["<div class=\"contenedor\">", MARCA];
    if (v.enlaces.length) {
      partes.push(
        "<nav class=\"enlaces-cabecera\" aria-label=\"Principal\">" +
          v.enlaces.map(function (e) {
            if (!e.clave) return enlace(e);
            return enlace(e, "", " data-pestana=\"" + e.clave + "\"" + (e.clave === activa ? " aria-current=\"page\"" : ""));
          }).join("") +
        "</nav>"
      );
    }
    var acciones = v.acciones.map(function (a) { return a === SER_ANFITRION && enAnfitriones ? PUBLICAR : a; });
    partes.push(
      "<div class=\"cabecera-acciones\">" +
        acciones.map(function (a) { return enlace(a, a.clase); }).join("") +
        "<span class=\"cuenta\" data-cuenta></span>" +
      "</div>"
    );
    partes.push("</div>");
    return partes.join("\n      ");
  }

  /* Lo que lleva el menú de la cuenta de esa vista. Un administrador, además, puede elegir qué vista mirar. */
  function menuDeLaCuenta(vista, esAdmin) {
    var propio = Object.prototype.hasOwnProperty.call(VISTAS, vista) ? VISTAS[vista].menu : VISTAS.cliente.menu;
    if (!esAdmin) return propio;
    var elegir = VER_COMO.map(function (e) { return { texto: e.texto, href: e.href, verComo: e.clave, actual: e.clave === vista }; });
    return elegir.concat(propio);
  }

  /* El HTML de dentro de <footer class="pie">. */
  function construirPie() {
    return [
      "<div class=\"contenedor\">",
      "<div class=\"pie-fila\">" +
        "<p><strong>Íntegro</strong></p>" +
        "<a class=\"btn btn-reportar\" href=\"#\">Reportar un problema</a>" +
      "</div>",
      "<nav aria-label=\"Pie de página\">" +
        ENLACES_DEL_PIE.map(function (e) { return enlace(e); }).join("") +
      "</nav>",
      "</div>"
    ].join("\n      ");
  }

  function activaEn(ubicacion) {
    return ubicacion ? pestanaActiva(ubicacion.pathname, ubicacion.search, ubicacion.hash) : null;
  }

  /* Vuelve a armar solo la cabecera, con la vista que toca. ubicacion es window.location (o nada). */
  function montarCabecera(documento, vista, ubicacion) {
    Array.prototype.forEach.call(documento.querySelectorAll("[data-cabecera]"), function (el) {
      el.innerHTML = construirCabecera(el.getAttribute("data-cabecera") || PAGINA_POR_DEFECTO, vista, activaEn(ubicacion));
    });
  }

  /* Llena los espacios de la página. documento solo necesita querySelectorAll. */
  function montar(documento, vista, ubicacion) {
    montarCabecera(documento, vista, ubicacion);
    Array.prototype.forEach.call(documento.querySelectorAll("[data-pie]"), function (el) {
      el.innerHTML = construirPie();
    });
  }

  /* Cambia la pestaña marcada sin volver a armar la cabecera (por ejemplo, al dar clic en «Alojamientos» en la portada). */
  function marcarPestana(documento, ubicacion) {
    var activa = activaEn(ubicacion);
    Array.prototype.forEach.call(documento.querySelectorAll("[data-pestana]"), function (el) {
      if (el.getAttribute("data-pestana") === activa) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    });
  }

  if (typeof document !== "undefined") {
    montar(document, VISTA_POR_DEFECTO, window.location);
    window.addEventListener("hashchange", function () { marcarPestana(document, window.location); });
  }

  return {
    PESTANAS: PESTANAS,
    VISTAS: VISTAS,
    VISTA_POR_DEFECTO: VISTA_POR_DEFECTO,
    VER_COMO: VER_COMO,
    PAGINAS: PAGINAS,
    PAGINA_POR_DEFECTO: PAGINA_POR_DEFECTO,
    construirCabecera: construirCabecera,
    construirPie: construirPie,
    menuDeLaCuenta: menuDeLaCuenta,
    pestanaActiva: pestanaActiva,
    tituloDeSeccion: tituloDeSeccion,
    montar: montar,
    montarCabecera: montarCabecera,
    marcarPestana: marcarPestana
  };
});
