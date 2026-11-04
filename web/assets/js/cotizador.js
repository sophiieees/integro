/* Íntegro, cotizador de reserva (función del Assignment 2)
   -------------------------------------------------------------------
   Función pura, sin DOM: recibe la propiedad, las fechas y el número de
   personas y devuelve el desglose y el total, o un aviso si no se cumple
   la estancia mínima. En producción vive en el servidor
   (GET /api/v1/properties/:id/quote); aquí corre en el navegador del
   prototipo. Se expone como window.INTEGRO_COTIZAR y, en Node, como
   module.exports, para poder probarla con los casos de la especificación.
*/
(function (raiz) {
  "use strict";

  function fecha(iso) {
    var p = String(iso).split("-");
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
  }

  function iso(d) { return d.toISOString().slice(0, 10); }

  function precioDeLaNoche(propiedad, dia) {
    var temporadas = propiedad.temporadas || [];
    for (var i = 0; i < temporadas.length; i++) {
      var t = temporadas[i];
      if (dia >= t.desde && dia <= t.hasta) return { precio: t.precio, nombre: t.nombre || "Temporada" };
    }
    return { precio: propiedad.precio_noche, nombre: null };
  }

  /* cotizar(propiedad, llegada, salida, huespedes)
     -> { ok: true, noches, lineas: [{ concepto, noches, precio, importe }], limpieza, total }
     -> { ok: false, aviso: "..." } */
  function cotizar(propiedad, llegada, salida, huespedes) {
    if (!propiedad) return { ok: false, aviso: "No hay propiedad seleccionada." };
    if (!llegada || !salida) return { ok: false, aviso: "Elige fecha de llegada y de salida." };
    var a = fecha(llegada), b = fecha(salida);
    if (isNaN(a) || isNaN(b)) return { ok: false, aviso: "Fecha no válida." };
    var noches = Math.round((b - a) / 86400000);
    if (noches < 1) return { ok: false, aviso: "La salida debe ser después de la llegada." };
    var minimo = propiedad.estancia_minima || 1;
    if (noches < minimo) {
      return { ok: false, aviso: "Estancia mínima: " + minimo + " noches. Elegiste " + noches + "." };
    }
    var personas = parseInt(huespedes, 10) || 1;
    if (propiedad.capacidad && personas > propiedad.capacidad) {
      return { ok: false, aviso: "Esta propiedad recibe hasta " + propiedad.capacidad + " huéspedes." };
    }

    var grupos = {};
    var orden = [];
    for (var d = new Date(a); d < b; d.setUTCDate(d.getUTCDate() + 1)) {
      var info = precioDeLaNoche(propiedad, iso(d));
      var clave = (info.nombre || "base") + "@" + info.precio;
      if (!grupos[clave]) {
        grupos[clave] = { concepto: info.nombre ? info.nombre : "Tarifa base", noches: 0, precio: info.precio, importe: 0 };
        orden.push(clave);
      }
      grupos[clave].noches += 1;
      grupos[clave].importe += info.precio;
    }
    var lineas = orden.map(function (k) { return grupos[k]; });
    var subtotal = lineas.reduce(function (s, l) { return s + l.importe; }, 0);
    var limpieza = propiedad.limpieza || 0;
    return { ok: true, noches: noches, lineas: lineas, limpieza: limpieza, subtotal: subtotal, total: subtotal + limpieza };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = cotizar;
  if (raiz) raiz.INTEGRO_COTIZAR = cotizar;
})(typeof window !== "undefined" ? window : null);
