/* Íntegro, la cabecera y el pie de las páginas
   -------------------------------------------------------------------
   La cabecera y el pie viven aquí, en una sola copia. Cada página trae solo
   dos espacios vacíos:

     <header class="cabecera" data-cabecera="portada"></header>
     <footer class="pie" data-pie></footer>

   y este script los llena al cargar. Así un cambio se hace una vez y vale
   para todas las páginas.

   La cabecera cambia según la vista de la página (VARIANTES). Hoy hay tres,
   las mismas que ya tenían las páginas. Las vistas del huésped, del anfitrión
   y del administrador se definen cuando se organicen; cada una será una
   variante nueva en esta tabla, sin tocar las páginas.

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

  var BUSCAR = { texto: "Buscar hospedaje", href: "index.html" };
  var SER_ANFITRION = { texto: "Conviértete en anfitrión", href: "anfitriones.html" };

  /* Cada variante dice qué enlaces lleva junto a la marca (enlaces) o, si la
     cabecera trae acciones a la derecha (acciones), cuáles y con qué clase. */
  var VARIANTES = {
    /* La portada es solo para el huésped: no ofrece «Buscar hospedaje», ya está en él. */
    portada: { enlaces: [SER_ANFITRION], acciones: [] },
    interior: { enlaces: [BUSCAR, SER_ANFITRION], acciones: [] },
    anfitriones: {
      enlaces: [],
      acciones: [
        { texto: BUSCAR.texto, href: BUSCAR.href, clase: "btn-enlace" },
        { texto: "Publica tu propiedad", href: "#publicar", clase: "btn btn-azul solo-escritorio" }
      ]
    }
  };
  var VARIANTE_POR_DEFECTO = "interior";

  var ENLACES_DEL_PIE = [
    { texto: "Cómo funciona", href: "como-funciona.html" },
    { texto: "Anfitriones", href: "anfitriones.html" },
    { texto: "Términos y condiciones", href: "#" },
    { texto: "Aviso de privacidad", href: "#" }
  ];

  function enlace(e, clase) {
    return "<a" + (clase ? " class=\"" + clase + "\"" : "") + " href=\"" + e.href + "\">" + e.texto + "</a>";
  }

  /* El HTML de dentro de <header class="cabecera">. */
  function construirCabecera(nombre) {
    var variante = VARIANTES[nombre] || VARIANTES[VARIANTE_POR_DEFECTO];
    var partes = ["<div class=\"contenedor\">", MARCA];
    if (variante.enlaces.length) {
      partes.push(
        "<nav class=\"enlaces-cabecera\" aria-label=\"Principal\">" +
          variante.enlaces.map(function (e) { return enlace(e); }).join("") +
        "</nav>"
      );
    }
    if (variante.acciones.length) {
      partes.push(
        "<div class=\"cabecera-acciones\">" +
          variante.acciones.map(function (a) { return enlace(a, a.clase); }).join("") +
          "<span class=\"cuenta\" data-cuenta></span>" +
        "</div>"
      );
    } else {
      partes.push("<div class=\"cabecera-acciones cuenta\" data-cuenta></div>");
    }
    partes.push("</div>");
    return partes.join("\n      ");
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

  /* Llena los espacios de la página. documento solo necesita querySelectorAll. */
  function montar(documento) {
    Array.prototype.forEach.call(documento.querySelectorAll("[data-cabecera]"), function (el) {
      el.innerHTML = construirCabecera(el.getAttribute("data-cabecera"));
    });
    Array.prototype.forEach.call(documento.querySelectorAll("[data-pie]"), function (el) {
      el.innerHTML = construirPie();
    });
  }

  if (typeof document !== "undefined") montar(document);

  return {
    VARIANTES: VARIANTES,
    VARIANTE_POR_DEFECTO: VARIANTE_POR_DEFECTO,
    construirCabecera: construirCabecera,
    construirPie: construirPie,
    montar: montar
  };
});
