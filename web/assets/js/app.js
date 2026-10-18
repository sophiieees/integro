/* Íntegro · lógica del prototipo
   -------------------------------------------------------------------
   Hace tres cosas y nada más:
     1. Pinta las tarjetas de propiedades desde los datos de muestra.
     2. Filtra por ciudad (o zona) y número de huéspedes al enviar el buscador.
     3. Pinta la ficha de una propiedad según el parámetro ?id= de la URL.
   No cotiza, no reserva y no llama a ninguna API. Todo eso vive en el
   backend (docs/arquitectura.md). La cotización real es una de las
   funciones candidatas del Assignment 2 (PROMPT_LOG.md).
*/
(function () {
  "use strict";

  var DATOS = window.INTEGRO_DATOS || { propiedades: [], ciudades: [], ciudadPorDefecto: "" };
  var MXN = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });

  function dinero(n) { return MXN.format(n); }

  function normalizar(texto) {
    return (texto || "").toString().normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  function escapar(texto) {
    return String(texto).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }

  function fechaCorta(iso) {
    if (!iso) return "";
    var d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("es-MX", { day: "numeric", month: "short" });
  }

  /* ---------- Tarjetas ---------- */

  function insignias(p) {
    var html = p.anfitrion.nivel === "verificado"
      ? "<span class=\"insignia\">Anfitrión verificado</span>"
      : "<span class=\"insignia insignia-nuevo\">Anfitrión nuevo</span>";
    if (p.chapa) html += "<span class=\"insignia insignia-chapa\">Chapa inteligente</span>";
    return html;
  }

  function tarjeta(p) {
    return (
      "<a class=\"tarjeta revelar\" href=\"propiedad.html?id=" + p.id + "\">" +
        "<div class=\"tarjeta-foto tono-" + escapar(p.tono) + "\">" +
          "<div class=\"marcador-foto\">Foto: " + escapar(p.titulo) + "</div>" +
          /* La foto real se carga si existe assets/img/propiedad-<id>-1.jpg; si no, se quita y queda el marcador. */
          "<img src=\"assets/img/propiedad-" + p.id + "-1.jpg\" alt=\"\" loading=\"lazy\" onerror=\"this.remove()\">" +
          insignias(p) +
        "</div>" +
        "<div class=\"tarjeta-cuerpo\">" +
          "<div class=\"tarjeta-titulo\">" + escapar(p.titulo) + "</div>" +
          "<div class=\"tarjeta-meta\">" + escapar(p.zona) + ", " + escapar(p.ciudad) + " · " + escapar(p.tipo) + " · " + p.capacidad + " huéspedes</div>" +
          "<div class=\"tarjeta-calif\">" + p.calificacion.toFixed(2) + " · " + p.resenas + " reseñas verificadas</div>" +
          "<div class=\"tarjeta-precio\"><strong>" + dinero(p.precio_noche) + "</strong> <span class=\"texto-suave\">por noche</span>" +
            "<div class=\"tarjeta-total\">Total 2 noches " + dinero(p.total_2_noches) + " · sin cargos de servicio</div>" +
          "</div>" +
        "</div>" +
      "</a>"
    );
  }

  function pintarTarjetas(lista) {
    var contenedor = document.getElementById("tarjetas");
    if (!contenedor) return;
    var vacio = document.getElementById("aviso-vacio");
    var conteo = document.querySelector("[data-conteo]");
    contenedor.innerHTML = lista.map(tarjeta).join("");
    if (vacio) vacio.hidden = lista.length > 0;
    if (conteo) conteo.textContent = lista.length === 1 ? "1 propiedad verificada" : lista.length + " propiedades verificadas";
    registrarRevelado();
  }

  function filtrar(ciudad, huespedes) {
    var c = normalizar(ciudad);
    return DATOS.propiedades.filter(function (p) {
      var coincideLugar = !c || normalizar(p.ciudad).indexOf(c) !== -1 || normalizar(p.zona).indexOf(c) !== -1;
      var cabe = !huespedes || p.capacidad >= huespedes;
      return coincideLugar && cabe;
    });
  }

  function iniciarBuscador() {
    var form = document.getElementById("buscador");
    if (!form) return;
    var hoy = new Date().toISOString().slice(0, 10);
    Array.prototype.forEach.call(form.querySelectorAll("input[type=date]"), function (i) { i.min = hoy; });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var destino = form.destino.value.trim();
      var huespedes = parseInt(form.huespedes.value, 10) || 0;
      var titulo = document.querySelector("[data-ciudad]");
      var periodo = document.querySelector("[data-periodo]");
      if (titulo) titulo.textContent = destino || "todas las ciudades";
      if (periodo) {
        periodo.textContent = (form.llegada.value && form.salida.value)
          ? "del " + fechaCorta(form.llegada.value) + " al " + fechaCorta(form.salida.value)
          : "este fin de semana";
      }
      pintarTarjetas(filtrar(destino, huespedes));
      var seccion = document.getElementById("resultados");
      if (seccion) seccion.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  /* ---------- Ficha ---------- */

  var POLITICAS = {
    Flexible: "Reembolso completo hasta 24 horas antes de la llegada.",
    Moderada: "Reembolso completo hasta 5 días antes de la llegada; 50 % después.",
    Estricta: "Reembolso del 50 % hasta 7 días antes de la llegada; sin reembolso después."
  };
  var ETIQUETAS_FOTO = ["fachada", "sala", "recámara", "cocina", "baño"];

  function pintarFicha() {
    var raiz = document.getElementById("ficha");
    if (!raiz) return;
    var id = parseInt(new URLSearchParams(window.location.search).get("id"), 10);
    var p = DATOS.propiedades.filter(function (x) { return x.id === id; })[0] || DATOS.propiedades[0];
    if (!p) return;

    document.title = p.titulo + " · Íntegro";

    var campos = {
      "titulo": p.titulo,
      "ciudad": p.ciudad,
      "zona": p.zona + ", " + p.ciudad,
      "zona-corta": p.zona,
      "tipo": p.tipo,
      "capacidad": p.capacidad + " huéspedes · " + p.recamaras + " recámaras · " + p.camas + " camas · " + p.banos + " baños",
      "calif": p.calificacion.toFixed(2) + " · " + p.resenas + " reseñas verificadas",
      "anfitrion-nombre": p.anfitrion.nombre,
      "anfitrion-inicial": p.anfitrion.nombre.charAt(0),
      "responde": "Responde " + p.anfitrion.responde,
      "descripcion": p.descripcion,
      "cancelacion": p.cancelacion,
      "cancelacion-detalle": POLITICAS[p.cancelacion] || "",
      "precio-noche": dinero(p.precio_noche),
      "limpieza": dinero(p.limpieza),
      "subtotal": dinero(p.total_2_noches - p.limpieza),
      "total": dinero(p.total_2_noches),
      "pago-anfitrion": p.anfitrion.nivel === "verificado"
        ? "Anfitrión verificado: recibe el pago al confirmar tu reserva."
        : "Anfitrión nuevo: recibe el pago 24 horas después de tu llegada. Si algo no coincide con lo publicado, tu reporte congela el depósito."
    };
    Object.keys(campos).forEach(function (clave) {
      Array.prototype.forEach.call(raiz.querySelectorAll("[data-campo=\"" + clave + "\"]"), function (el) {
        el.textContent = campos[clave];
      });
    });

    var nivel = raiz.querySelector("[data-nivel]");
    if (nivel) {
      nivel.textContent = p.anfitrion.nivel === "verificado" ? "Anfitrión verificado" : "Anfitrión nuevo";
      nivel.classList.toggle("pastilla-nuevo", p.anfitrion.nivel !== "verificado");
    }
    var chapa = raiz.querySelector("[data-chapa]");
    if (chapa) chapa.hidden = !p.chapa;
    var cajaChapa = raiz.querySelector("[data-caja-chapa]");
    if (cajaChapa) cajaChapa.hidden = !p.chapa;

    var servicios = raiz.querySelector("[data-lista=servicios]");
    if (servicios) servicios.innerHTML = p.servicios.map(function (s) { return "<li>" + escapar(s) + "</li>"; }).join("");
    var reglas = raiz.querySelector("[data-lista=reglas]");
    if (reglas) reglas.innerHTML = p.reglas.map(function (r) { return "<li>" + escapar(r) + "</li>"; }).join("");

    Array.prototype.forEach.call(raiz.querySelectorAll("[data-foto]"), function (el, i) {
      el.classList.add("tono-" + p.tono);
      var marcador = el.querySelector(".marcador-foto");
      if (marcador) marcador.textContent = "Foto " + (i + 1) + ": " + (ETIQUETAS_FOTO[i] || "detalle");
      /* Foto real si existe assets/img/propiedad-<id>-<n>.jpg; si no, queda el marcador. */
      var img = document.createElement("img");
      img.alt = "";
      img.addEventListener("error", function () { img.remove(); });
      img.src = "assets/img/propiedad-" + p.id + "-" + (i + 1) + ".jpg";
      el.appendChild(img);
    });

    var hoy = new Date().toISOString().slice(0, 10);
    Array.prototype.forEach.call(raiz.querySelectorAll("input[type=date]"), function (i) { i.min = hoy; });
  }

  /* ---------- Revelado al entrar en pantalla (una sola vez) ----------
     Comprobación directa de posición al cargar, al hacer scroll y al cambiar
     de tamaño. Se eligió sobre IntersectionObserver porque el contenido no
     debe depender de que el observador avise: si algo falla, el elemento
     se revela igual en cuanto asoma en pantalla. */

  var pendientesDeRevelar = [];

  function registrarRevelado() {
    pendientesDeRevelar = Array.prototype.slice.call(document.querySelectorAll(".revelar:not(.visible)"));
    revelarVisibles();
  }

  function revelarVisibles() {
    if (!pendientesDeRevelar.length) return;
    var alto = window.innerHeight || document.documentElement.clientHeight;
    pendientesDeRevelar = pendientesDeRevelar.filter(function (el) {
      var r = el.getBoundingClientRect();
      var asoma = r.top < alto * 0.94 && r.bottom > 0;
      if (asoma) el.classList.add("visible");
      return !asoma;
    });
  }

  var revisionProgramada = false;
  function programarRevision() {
    if (revisionProgramada) return;
    revisionProgramada = true;
    window.requestAnimationFrame(function () {
      revisionProgramada = false;
      revelarVisibles();
    });
  }
  window.addEventListener("scroll", programarRevision, { passive: true });
  window.addEventListener("resize", programarRevision);
  window.addEventListener("load", programarRevision);

  /* ---------- Arranque ---------- */

  document.addEventListener("DOMContentLoaded", function () {
    var lista = document.getElementById("datalist-ciudades");
    if (lista) lista.innerHTML = DATOS.ciudades.map(function (c) { return "<option value=\"" + escapar(c) + "\">"; }).join("");
    iniciarBuscador();
    if (document.getElementById("tarjetas")) pintarTarjetas(filtrar(DATOS.ciudadPorDefecto, 0));
    pintarFicha();
    registrarRevelado();
  });
})();
