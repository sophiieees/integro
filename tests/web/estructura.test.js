/* Casos del script de la cabecera y el pie (web/assets/js/estructura.js).
   Se corren con node, sin navegador:  node --test tests/web
   Decisión de Sophia del 20 de noviembre de 2026: la cabecera cambia según la vista de quien mira (visitante, cliente,
   anfitrión, administrador), con la barra «Todo, Alojamientos, Experiencias, Servicios» para el visitante y el cliente.
   Las páginas siguen trayendo solo un espacio vacío; el script lo llena. El pie no cambió. */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const WEB = path.join(__dirname, "..", "..", "web");
const ESTRUCTURA = require(path.join(WEB, "assets", "js", "estructura.js"));

/* Sin los espacios entre etiquetas, que el navegador ignora. */
const normalizar = (html) => html.replace(/\s+/g, " ").replace(/> </g, "><").trim();

const MARCA = "<a class=\"marca\" href=\"index.html\" aria-label=\"Íntegro, inicio\"><span class=\"marca-punto\" aria-hidden=\"true\"></span>Íntegro</a>";
const PIE = "<div class=\"contenedor\"><div class=\"pie-fila\"><p><strong>Íntegro</strong></p><a class=\"btn btn-reportar\" href=\"#\">Reportar un problema</a></div><nav aria-label=\"Pie de página\"><a href=\"como-funciona.html\">Cómo funciona</a><a href=\"anfitriones.html\">Anfitriones</a><a href=\"#\">Términos y condiciones</a><a href=\"#\">Aviso de privacidad</a></nav></div>";
const SER_ANFITRION = "<a class=\"btn-enlace solo-escritorio\" href=\"anfitriones.html\">Conviértete en anfitrión</a>";
const CUENTA = "<span class=\"cuenta\" data-cuenta></span>";

const VISTAS = ["visitante", "cliente", "anfitrion", "administrador"];
const PAGINAS = ["portada", "interior", "anfitriones"];

/* Los textos de los enlaces de una cabecera, en el orden en que se ven. */
const enlacesDe = (html) => [...html.matchAll(/<a [^>]*>([^<]*)<\/a>/g)].map((m) => m[1]);
const textoDeLaBarra = (html) => enlacesDe((html.match(/<nav class="enlaces-cabecera"[^>]*>(.*?)<\/nav>/s) || ["", ""])[1]);

/* --- Las cuatro vistas -------------------------------------------------------- */

test("el visitante y el cliente ven la barra Todo, Alojamientos, Experiencias y Servicios, y «Conviértete en anfitrión»", () => {
  for (const vista of ["visitante", "cliente"]) {
    const html = normalizar(ESTRUCTURA.construirCabecera("portada", vista, "todo"));

    assert.deepEqual(textoDeLaBarra(html), ["Todo", "Alojamientos", "Experiencias", "Servicios"], vista);
    assert.ok(html.includes(SER_ANFITRION), vista);
    assert.ok(!html.includes("Buscar hospedaje"), vista);
  }
});

test("la cabecera del visitante y la del cliente son la misma: la cuenta la pinta cuenta.js", () => {
  assert.equal(ESTRUCTURA.construirCabecera("interior", "visitante", null), ESTRUCTURA.construirCabecera("interior", "cliente", null));
});

test("la cabecera del visitante, completa", () => {
  assert.equal(
    normalizar(ESTRUCTURA.construirCabecera("portada", "visitante", "todo")),
    "<div class=\"contenedor\">" + MARCA +
      "<nav class=\"enlaces-cabecera\" aria-label=\"Principal\">" +
        "<a data-pestana=\"todo\" aria-current=\"page\" href=\"index.html\">Todo</a>" +
        "<a data-pestana=\"alojamientos\" href=\"index.html#resultados\">Alojamientos</a>" +
        "<a data-pestana=\"experiencias\" href=\"proximamente.html?seccion=experiencias\">Experiencias</a>" +
        "<a data-pestana=\"servicios\" href=\"proximamente.html?seccion=servicios\">Servicios</a>" +
      "</nav>" +
      "<div class=\"cabecera-acciones\">" + SER_ANFITRION + CUENTA + "</div>" +
    "</div>"
  );
});

test("el anfitrión ve sus funciones y ya no ve «Conviértete en anfitrión» ni la barra", () => {
  const html = ESTRUCTURA.construirCabecera("interior", "anfitrion", null);

  assert.deepEqual(textoDeLaBarra(html), ["Mis propiedades", "Reservas", "Reseñas", "Comentarios", "Chats con clientes", "Subir publicación"]);
  for (const ausente of ["Conviértete en anfitrión", "Todo", "Experiencias", "Servicios", "Buscar hospedaje"]) {
    assert.ok(!html.includes(">" + ausente + "<"), ausente);
  }
});

test("el administrador ve verificaciones, casos, cargos y bitácora", () => {
  const html = ESTRUCTURA.construirCabecera("interior", "administrador", null);

  assert.deepEqual(textoDeLaBarra(html), ["Verificaciones", "Casos", "Cargos", "Bitácora"]);
  assert.ok(!html.includes("Conviértete en anfitrión"));
});

test("en la página de anfitriones, «Conviértete en anfitrión» se cambia por «Publica tu propiedad», solo en escritorio", () => {
  for (const vista of ["visitante", "cliente"]) {
    const html = ESTRUCTURA.construirCabecera("anfitriones", vista, null);

    assert.ok(html.includes('<a class="btn btn-azul solo-escritorio" href="#publicar">Publica tu propiedad</a>'), vista);
    assert.ok(!html.includes("Conviértete en anfitrión"), vista);
  }
});

test("en las otras páginas no hay «Publica tu propiedad» en la cabecera", () => {
  for (const pagina of ["portada", "interior"]) {
    assert.ok(!ESTRUCTURA.construirCabecera(pagina, "visitante", null).includes("Publica tu propiedad"), pagina);
  }
});

test("la página de anfitriones no cambia la cabecera del anfitrión ni la del administrador", () => {
  for (const vista of ["anfitrion", "administrador"]) {
    assert.equal(ESTRUCTURA.construirCabecera("anfitriones", vista, null), ESTRUCTURA.construirCabecera("interior", vista, null), vista);
  }
});

test("toda cabecera trae la marca que lleva a la portada y una sola zona para la cuenta, vacía", () => {
  for (const vista of VISTAS) {
    for (const pagina of PAGINAS) {
      const cabecera = ESTRUCTURA.construirCabecera(pagina, vista, null);
      const donde = vista + " / " + pagina;

      assert.equal(cabecera.split("data-cuenta").length - 1, 1, donde);
      assert.match(cabecera, /<a class="marca" href="index\.html" aria-label="Íntegro, inicio">/, donde);
      // Esa zona la pinta cuenta.js: aquí no trae enlaces ni texto.
      assert.match(cabecera, /data-cuenta><\/span>/, donde);
    }
  }
});

test("una vista que no existe usa la del visitante; una página que no existe, la interior", () => {
  assert.equal(ESTRUCTURA.VISTA_POR_DEFECTO, "visitante");
  assert.equal(ESTRUCTURA.PAGINA_POR_DEFECTO, "interior");
  for (const rara of ["no-existe", undefined, null, "toString"]) {
    assert.equal(ESTRUCTURA.construirCabecera("interior", rara), ESTRUCTURA.construirCabecera("interior", "visitante"), String(rara));
  }
  assert.doesNotThrow(() => ESTRUCTURA.construirCabecera("no-existe", "cliente"));
});

test("una vista nueva se agrega solo con una entrada de la tabla", () => {
  assert.deepEqual(Object.keys(ESTRUCTURA.VISTAS).sort(), ["administrador", "anfitrion", "cliente", "visitante"]);
  for (const vista of Object.values(ESTRUCTURA.VISTAS)) {
    assert.ok(Array.isArray(vista.enlaces) && Array.isArray(vista.acciones) && Array.isArray(vista.menu));
  }
});

/* --- La pestaña marcada --------------------------------------------------------- */

test("solo la pestaña activa se marca, con aria-current", () => {
  for (const clave of ["todo", "alojamientos", "experiencias", "servicios"]) {
    const html = ESTRUCTURA.construirCabecera("interior", "visitante", clave);

    assert.equal(html.split("aria-current").length - 1, 1, clave);
    assert.match(html, new RegExp("data-pestana=\"" + clave + "\" aria-current=\"page\""), clave);
  }
  assert.equal(ESTRUCTURA.construirCabecera("interior", "visitante", null).includes("aria-current"), false);
});

test("qué pestaña es la de cada página", () => {
  const activa = ESTRUCTURA.pestanaActiva;

  assert.equal(activa("/", "", ""), "todo");
  assert.equal(activa("/index.html", "", ""), "todo");
  assert.equal(activa("/C:/proyecto/web/index.html", "", ""), "todo");
  assert.equal(activa("/index.html", "", "#resultados"), "alojamientos");
  assert.equal(activa("/propiedad.html", "?id=2", ""), "alojamientos");
  assert.equal(activa("/proximamente.html", "?seccion=experiencias", ""), "experiencias");
  assert.equal(activa("/proximamente.html", "?seccion=servicios", ""), "servicios");
  assert.equal(activa("/proximamente.html", "", ""), null);
  assert.equal(activa("/proximamente.html", "?seccion=otra", ""), null);
  assert.equal(activa("/anfitriones.html", "", ""), null);
  assert.equal(activa("/registro.html", "", ""), null);
  assert.equal(activa(undefined, undefined, undefined), "todo");
});

test("el título de proximamente.html sale de la dirección, y solo de dos secciones conocidas", () => {
  const titulo = ESTRUCTURA.tituloDeSeccion;

  assert.equal(titulo("?seccion=experiencias"), "Experiencias");
  assert.equal(titulo("?seccion=servicios"), "Servicios");
  assert.equal(titulo("?otra=1&seccion=servicios"), "Servicios");
  for (const raro of ["", "?seccion=", "?seccion=otra", "?seccion=__proto__", "?seccion=experiencias2", undefined, null]) {
    assert.equal(titulo(raro), null, String(raro));
  }
});

/* --- El menú de la cuenta ----------------------------------------------------------- */

test("el menú del cliente", () => {
  assert.deepEqual(ESTRUCTURA.menuDeLaCuenta("cliente", false).map((e) => e.texto), ["Mi cuenta", "Mis reservas", "Mensajes", "Reseñas", "Comentarios"]);
});

test("el menú del anfitrión: su cuenta, sus reservas como huésped y buscar hospedaje", () => {
  assert.deepEqual(ESTRUCTURA.menuDeLaCuenta("anfitrion", false).map((e) => e.texto), ["Mi cuenta", "Mis reservas", "Buscar hospedaje"]);
});

test("quien no es administrador no ve cómo cambiar de vista, aunque se lo pida", () => {
  for (const vista of ["cliente", "anfitrion", "administrador", "visitante"]) {
    assert.ok(ESTRUCTURA.menuDeLaCuenta(vista, false).every((e) => !e.verComo), vista);
  }
});

test("el administrador puede mirar su vista, la de cliente y la de anfitrión, y marca la que está viendo", () => {
  for (const vista of ["administrador", "cliente", "anfitrion"]) {
    const menu = ESTRUCTURA.menuDeLaCuenta(vista, true);
    const elegir = menu.filter((e) => e.verComo);

    assert.deepEqual(elegir.map((e) => e.texto), ["Vista de administrador", "Ver como cliente", "Ver como anfitrión"], vista);
    assert.deepEqual(elegir.filter((e) => e.actual).map((e) => e.verComo), [vista], vista);
  }
});

test("el administrador, mirando como cliente, conserva el menú del cliente", () => {
  const propios = ESTRUCTURA.menuDeLaCuenta("cliente", true).filter((e) => !e.verComo).map((e) => e.texto);

  assert.deepEqual(propios, ["Mi cuenta", "Mis reservas", "Mensajes", "Reseñas", "Comentarios"]);
});

/* --- Ningún enlace da 404 ----------------------------------------------------------- */

const existe = (href) => {
  const [archivo, ancla] = href.replace(/\?[^#]*/, "").split("#");
  if (archivo === "") return true; // #publicar y #: dentro de la misma página
  const ruta = path.join(WEB, archivo);
  if (!fs.existsSync(ruta)) return false;
  return !ancla || fs.readFileSync(ruta, "utf8").includes('id="' + ancla + '"');
};

test("todo enlace de toda cabecera, menú y pie lleva a una página (y a un lugar de ella) que existe", () => {
  const hrefs = new Set();
  for (const vista of VISTAS) {
    for (const pagina of PAGINAS) {
      for (const m of ESTRUCTURA.construirCabecera(pagina, vista, null).matchAll(/href="([^"]+)"/g)) hrefs.add(m[1]);
    }
    for (const admin of [false, true]) {
      for (const item of ESTRUCTURA.menuDeLaCuenta(vista, admin)) hrefs.add(item.href);
    }
  }
  for (const m of ESTRUCTURA.construirPie().matchAll(/href="([^"]+)"/g)) hrefs.add(m[1]);

  const rotos = [...hrefs].filter((href) => href !== "#" && !existe(href));

  assert.deepEqual(rotos, []);
  assert.ok(hrefs.size > 20);
});

/* --- El pie --------------------------------------------------------------------------- */

test("el pie es el que ya tenía", () => {
  assert.equal(normalizar(ESTRUCTURA.construirPie()), PIE);
});

test("el pie trae «Reportar un problema» y los cuatro enlaces", () => {
  const pie = ESTRUCTURA.construirPie();

  assert.ok(pie.includes('<a class="btn btn-reportar" href="#">Reportar un problema</a>'));
  for (const texto of ["Cómo funciona", "Anfitriones", "Términos y condiciones", "Aviso de privacidad"]) {
    assert.ok(pie.includes(">" + texto + "</a>"), texto);
  }
});

/* --- Montar en una página --------------------------------------------------------------- */

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

test("montar llena el espacio de la cabecera y el del pie, con la vista y la pestaña de la página", () => {
  const pagina = paginaFalsa("interior", true);

  ESTRUCTURA.montar(pagina, "cliente", { pathname: "/propiedad.html", search: "?id=2", hash: "" });

  assert.equal(normalizar(pagina.header.innerHTML), normalizar(ESTRUCTURA.construirCabecera("interior", "cliente", "alojamientos")));
  assert.match(pagina.header.innerHTML, /data-pestana="alojamientos" aria-current="page"/);
  assert.equal(normalizar(pagina.footer.innerHTML), PIE);
});

test("montar toma la página del atributo de cada página", () => {
  for (const nombre of PAGINAS) {
    const pagina = paginaFalsa(nombre, true);

    ESTRUCTURA.montar(pagina, "visitante");

    assert.equal(normalizar(pagina.header.innerHTML), normalizar(ESTRUCTURA.construirCabecera(nombre, "visitante", null)), nombre);
  }
});

test("montarCabecera vuelve a armar solo la cabecera, con otra vista, y no toca el pie", () => {
  const pagina = paginaFalsa("interior", true);
  ESTRUCTURA.montar(pagina, "visitante");
  pagina.footer.innerHTML = "sin tocar";

  ESTRUCTURA.montarCabecera(pagina, "anfitrion");

  assert.equal(normalizar(pagina.header.innerHTML), normalizar(ESTRUCTURA.construirCabecera("interior", "anfitrion", null)));
  assert.equal(pagina.footer.innerHTML, "sin tocar");
});

test("una página sin espacios no se toca ni da error", () => {
  const pagina = paginaFalsa(undefined, false);

  assert.doesNotThrow(() => ESTRUCTURA.montar(pagina, "visitante"));
  assert.equal(pagina.header.innerHTML, "");
  assert.equal(pagina.footer.innerHTML, "");
});

test("marcarPestana cambia la pestaña marcada sin volver a armar la cabecera", () => {
  const enlaces = ["todo", "alojamientos", "experiencias", "servicios"].map((clave) => {
    const atributos = clave === "todo" ? { "aria-current": "page" } : {};
    return {
      clave, atributos,
      getAttribute(nombre) { return nombre === "data-pestana" ? clave : atributos[nombre] ?? null; },
      setAttribute(nombre, valor) { atributos[nombre] = valor; },
      removeAttribute(nombre) { delete atributos[nombre]; }
    };
  });
  const pagina = { querySelectorAll: (selector) => (selector === "[data-pestana]" ? enlaces : []) };

  ESTRUCTURA.marcarPestana(pagina, { pathname: "/index.html", search: "", hash: "#resultados" });

  assert.deepEqual(enlaces.filter((e) => e.atributos["aria-current"]).map((e) => e.clave), ["alojamientos"]);
});
