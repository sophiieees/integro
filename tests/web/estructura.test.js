/* Casos del script de la cabecera y el pie (web/assets/js/estructura.js).
   Se corren con node, sin navegador:  node --test tests/web
   La referencia es lo que las páginas traían escrito a mano el 20 de noviembre de 2026, antes de armarlo con
   un script: el script tiene que producir lo mismo, sin cambiar nada de lo que ya estaba aprobado. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const ESTRUCTURA = require(path.join(__dirname, "..", "..", "web", "assets", "js", "estructura.js"));

/* Sin los espacios entre etiquetas, que el navegador ignora. */
const normalizar = (html) => html.replace(/\s+/g, " ").replace(/> </g, "><").trim();

const COMO_ESTABA = {
  "portada": "<div class=\"contenedor\"><a class=\"marca\" href=\"index.html\" aria-label=\"Íntegro, inicio\"><span class=\"marca-punto\" aria-hidden=\"true\"></span>Íntegro</a><nav class=\"enlaces-cabecera\" aria-label=\"Principal\"><a href=\"anfitriones.html\">Conviértete en anfitrión</a></nav><div class=\"cabecera-acciones cuenta\" data-cuenta></div></div>",
  "interior": "<div class=\"contenedor\"><a class=\"marca\" href=\"index.html\" aria-label=\"Íntegro, inicio\"><span class=\"marca-punto\" aria-hidden=\"true\"></span>Íntegro</a><nav class=\"enlaces-cabecera\" aria-label=\"Principal\"><a href=\"index.html\">Buscar hospedaje</a><a href=\"anfitriones.html\">Conviértete en anfitrión</a></nav><div class=\"cabecera-acciones cuenta\" data-cuenta></div></div>",
  "anfitriones": "<div class=\"contenedor\"><a class=\"marca\" href=\"index.html\" aria-label=\"Íntegro, inicio\"><span class=\"marca-punto\" aria-hidden=\"true\"></span>Íntegro</a><div class=\"cabecera-acciones\"><a class=\"btn-enlace\" href=\"index.html\">Buscar hospedaje</a><a class=\"btn btn-azul solo-escritorio\" href=\"#publicar\">Publica tu propiedad</a><span class=\"cuenta\" data-cuenta></span></div></div>",
  "pie": "<div class=\"contenedor\"><div class=\"pie-fila\"><p><strong>Íntegro</strong></p><a class=\"btn btn-reportar\" href=\"#\">Reportar un problema</a></div><nav aria-label=\"Pie de página\"><a href=\"como-funciona.html\">Cómo funciona</a><a href=\"anfitriones.html\">Anfitriones</a><a href=\"#\">Términos y condiciones</a><a href=\"#\">Aviso de privacidad</a></nav></div>"
};

/* --- Lo mismo que antes ---------------------------------------------------- */

test("la cabecera de la portada es la que ya tenía", () => {
  assert.equal(normalizar(ESTRUCTURA.construirCabecera("portada")), COMO_ESTABA.portada);
});

test("la cabecera de las páginas interiores es la que ya tenían", () => {
  assert.equal(normalizar(ESTRUCTURA.construirCabecera("interior")), COMO_ESTABA.interior);
});

test("la cabecera de anfitriones es la que ya tenía", () => {
  assert.equal(normalizar(ESTRUCTURA.construirCabecera("anfitriones")), COMO_ESTABA.anfitriones);
});

test("el pie es el que ya tenía", () => {
  assert.equal(normalizar(ESTRUCTURA.construirPie()), COMO_ESTABA.pie);
});

/* --- Las reglas de cada cabecera -------------------------------------------- */

test("la portada es solo para el huésped: no ofrece «Buscar hospedaje»", () => {
  const portada = ESTRUCTURA.construirCabecera("portada");

  assert.ok(!portada.includes("Buscar hospedaje"));
  assert.ok(portada.includes("Conviértete en anfitrión"));
});

test("las interiores traen «Buscar hospedaje» y «Conviértete en anfitrión», en ese orden", () => {
  const interior = ESTRUCTURA.construirCabecera("interior");

  assert.ok(interior.indexOf("Buscar hospedaje") < interior.indexOf("Conviértete en anfitrión"));
});

test("anfitriones trae el botón «Publica tu propiedad», solo en escritorio, y no «Conviértete en anfitrión»", () => {
  const anfitriones = ESTRUCTURA.construirCabecera("anfitriones");

  assert.ok(anfitriones.includes('class="btn btn-azul solo-escritorio" href="#publicar">Publica tu propiedad</a>'));
  assert.ok(!anfitriones.includes("Conviértete en anfitrión"));
});

test("toda cabecera trae la marca que lleva a la portada y una sola zona para la cuenta, vacía", () => {
  for (const nombre of Object.keys(ESTRUCTURA.VARIANTES)) {
    const cabecera = ESTRUCTURA.construirCabecera(nombre);

    assert.equal(cabecera.split("data-cuenta").length - 1, 1, nombre);
    assert.match(cabecera, /<a class="marca" href="index\.html" aria-label="Íntegro, inicio">/, nombre);
    // Esa zona la pinta cuenta.js: aquí no trae enlaces ni texto.
    assert.match(cabecera, /data-cuenta><\/(div|span)>/, nombre);
  }
});

test("el pie trae «Reportar un problema» y los cuatro enlaces", () => {
  const pie = ESTRUCTURA.construirPie();

  assert.ok(pie.includes('<a class="btn btn-reportar" href="#">Reportar un problema</a>'));
  for (const texto of ["Cómo funciona", "Anfitriones", "Términos y condiciones", "Aviso de privacidad"]) {
    assert.ok(pie.includes(">" + texto + "</a>"), texto);
  }
});

test("una vista que no existe usa la cabecera interior", () => {
  assert.equal(ESTRUCTURA.VARIANTE_POR_DEFECTO, "interior");
  assert.equal(ESTRUCTURA.construirCabecera("no-existe"), ESTRUCTURA.construirCabecera("interior"));
  assert.equal(ESTRUCTURA.construirCabecera(undefined), ESTRUCTURA.construirCabecera("interior"));
  assert.equal(ESTRUCTURA.construirCabecera(null), ESTRUCTURA.construirCabecera("interior"));
});

test("una vista nueva se agrega solo con una entrada de la tabla", () => {
  assert.deepEqual(Object.keys(ESTRUCTURA.VARIANTES).sort(), ["anfitriones", "interior", "portada"]);
  for (const variante of Object.values(ESTRUCTURA.VARIANTES)) {
    assert.ok(Array.isArray(variante.enlaces) && Array.isArray(variante.acciones));
  }
});

/* --- Montar en una página ---------------------------------------------------- */

function paginaFalsa(cabecera, conPie) {
  const elemento = (atributo) => ({ atributo, innerHTML: "", getAttribute(nombre) { return nombre === "data-cabecera" ? atributo : null; } });
  const header = elemento(cabecera);
  const footer = elemento(null);
  return {
    header, footer,
    querySelectorAll(selector) {
      if (selector === "[data-cabecera]") return cabecera === undefined ? [] : [header];
      if (selector === "[data-pie]") return conPie ? [footer] : [];
      return [];
    }
  };
}

test("montar llena el espacio de la cabecera y el del pie", () => {
  const pagina = paginaFalsa("interior", true);

  ESTRUCTURA.montar(pagina);

  assert.equal(normalizar(pagina.header.innerHTML), COMO_ESTABA.interior);
  assert.equal(normalizar(pagina.footer.innerHTML), COMO_ESTABA.pie);
});

test("montar toma la variante del atributo de cada página", () => {
  for (const nombre of ["portada", "interior", "anfitriones"]) {
    const pagina = paginaFalsa(nombre, true);

    ESTRUCTURA.montar(pagina);

    assert.equal(normalizar(pagina.header.innerHTML), COMO_ESTABA[nombre], nombre);
  }
});

test("una página sin espacios no se toca ni da error", () => {
  const pagina = paginaFalsa(undefined, false);

  assert.doesNotThrow(() => ESTRUCTURA.montar(pagina));
  assert.equal(pagina.header.innerHTML, "");
  assert.equal(pagina.footer.innerHTML, "");
});
