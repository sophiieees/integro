/* Íntegro, la página «Próximamente»
   -------------------------------------------------------------------
   Pone el nombre de la sección (Experiencias o Servicios) como título de la
   página, tomándolo de la dirección: proximamente.html?seccion=experiencias.
   Si la dirección trae otra cosa, la página queda con «Próximamente».
   Qué secciones se conocen lo dice estructura.js (tituloDeSeccion).
*/
(function () {
  "use strict";

  var ESTRUCTURA = window.INTEGRO_ESTRUCTURA;
  if (!ESTRUCTURA) return;

  var titulo = ESTRUCTURA.tituloDeSeccion(window.location.search);
  if (!titulo) return;

  var encabezado = document.querySelector("[data-titulo-de-seccion]");
  if (encabezado) encabezado.textContent = titulo;
  document.title = titulo + " | Íntegro";
})();
