/* Íntegro, el CAPTCHA en la pantalla
   -------------------------------------------------------------------
   Dibuja el widget de Cloudflare Turnstile y entrega, cuando la pantalla lo pide, el resultado del desafío que la API
   va a comprobar (ADR 0016). Qué acción corresponde a cada pantalla y qué texto decir lo decide captcha-logica.js.

   Cada zona es un div con data-captcha="<acción>" (register, login, password_reset, resend_code o correct_email): la
   acción se declara una sola vez, en el HTML, y es la que el widget le dice a Cloudflare y la API espera en su ruta.

   1. preparar(zona) dibuja el widget en una zona de la pantalla. Pide a la API la llave
      pública (GET /api/v1/auth/captcha) y, solo la primera vez, carga el script de Cloudflare. Se llama cuando la zona
      se vuelve visible, para que el resultado esté listo antes de que la persona termine de escribir.
   2. obtener(zona) devuelve una promesa que siempre se cumple, nunca falla:
        { token: "...", aviso: null }  el resultado del desafío, para mandarlo en X-Captcha-Token
        { token: null, aviso: "..." }  no hubo resultado (no cargó, el desafío falló o se agotó la espera)
        { token: null, aviso: null, sinServidor: true }  la API no contestó: la pantalla dice lo de siempre cuando no hay
                                       servidor, en lugar de decir que falló el CAPTCHA
      Un resultado sirve una sola vez: al entregarlo, el widget se reinicia y ya va por el siguiente.

   La llave pública no es secreta; la secreta solo vive en el servidor. El script de Cloudflare solo se carga en las
   pantallas que piden CAPTCHA, cuando hace falta, y no en cada página del sitio.
*/
(function () {
  "use strict";

  var LOGICA = window.INTEGRO_CAPTCHA_LOGICA;
  if (!LOGICA) return;

  var llave = null;
  var script = null;
  var zonas = [];

  /* ---------- La llave pública y el script de Cloudflare ---------- */

  /* Se pide una sola vez; si falla, la próxima vez se vuelve a intentar. Contesta { valor, red }: la llave (o null) y si
     falló porque la API no contestó (red), que no es lo mismo que contestar que no hay llave (503). */
  function pedirLlave() {
    if (llave) return llave;
    llave = fetch(LOGICA.RUTA_DE_LA_LLAVE, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (respuesta) {
        if (!respuesta.ok) return { valor: null, red: false };
        return respuesta.json().then(function (cuerpo) {
          return { valor: cuerpo && typeof cuerpo.site_key === "string" && cuerpo.site_key ? cuerpo.site_key : null, red: false };
        }, function () { return { valor: null, red: false }; });
      }, function () { return { valor: null, red: true }; })
      .then(function (resultado) { if (!resultado.valor) llave = null; return resultado; });
    return llave;
  }

  function cargarScript() {
    if (window.turnstile) return Promise.resolve(true);
    if (script) return script;
    script = new Promise(function (resolver) {
      var etiqueta = document.createElement("script");
      etiqueta.src = LOGICA.URL_DEL_SCRIPT;
      etiqueta.async = true;
      etiqueta.onload = function () { resolver(Boolean(window.turnstile)); };
      etiqueta.onerror = function () { if (etiqueta.remove) etiqueta.remove(); resolver(false); };
      document.head.appendChild(etiqueta);
    }).then(function (cargo) { if (!cargo) script = null; return cargo; });
    return script;
  }

  /* ---------- Una zona con su widget ---------- */

  function buscar(zona) {
    for (var i = 0; i < zonas.length; i++) if (zonas[i].zona === zona) return zonas[i];
    return null;
  }

  function reiniciar(registro) {
    try { window.turnstile.reset(registro.id); } catch (e) { /* si no se puede, el siguiente intento avisa */ }
  }

  /* Entrega el resultado que hay y pide el siguiente: este ya no sirve para otra petición. */
  function entregar(registro) {
    var token = registro.token;
    registro.token = null;
    reiniciar(registro);
    return { token: token, aviso: null };
  }

  function terminarEsperas(registro, respuesta) {
    var esperas = registro.esperas;
    registro.esperas = [];
    esperas.forEach(function (espera) { clearTimeout(espera.temporizador); espera.resolver(respuesta); });
  }

  function opciones(registro, valorDeLlave) {
    var datos = LOGICA.opcionesDelWidget(valorDeLlave, registro.accion);
    datos.callback = function (token) {
      registro.token = token;
      registro.error = false;
      var espera = registro.esperas.shift();
      if (espera) { clearTimeout(espera.temporizador); espera.resolver(entregar(registro)); }
    };
    datos["error-callback"] = function () {
      registro.token = null;
      registro.error = true;
      terminarEsperas(registro, { token: null, aviso: LOGICA.AVISO });
      return true;
    };
    datos["expired-callback"] = function () { registro.token = null; };
    datos["timeout-callback"] = function () { registro.token = null; };
    return datos;
  }

  /* Dibuja el widget en la zona, una sola vez. Devuelve su registro, con fallo = true si no se pudo. */
  function preparar(zona) {
    var registro = buscar(zona);
    if (!registro) {
      var accion = zona.getAttribute("data-captcha");
      registro = { zona: zona, accion: LOGICA.esAccion(accion) ? accion : null, id: null, token: null, error: false, esperas: [], preparando: null, fallo: false, sinServidor: false };
      zonas.push(registro);
    }
    if (registro.id !== null) return Promise.resolve(registro);
    /* Una zona sin una acción que la API conozca no se dibuja: se avisa, y no se manda nada. */
    if (registro.accion === null) { registro.fallo = true; return Promise.resolve(registro); }
    if (registro.preparando) return registro.preparando;
    registro.preparando = Promise.all([pedirLlave(), cargarScript()]).then(function (resultado) {
      registro.preparando = null;
      var datosDeLaLlave = resultado[0];
      if (!datosDeLaLlave.valor || !resultado[1]) {
        registro.fallo = true;
        registro.sinServidor = datosDeLaLlave.red;
        return registro;
      }
      registro.fallo = false;
      registro.sinServidor = false;
      registro.id = window.turnstile.render(zona, opciones(registro, datosDeLaLlave.valor));
      return registro;
    });
    return registro.preparando;
  }

  /* ---------- El resultado, cuando la pantalla lo pide ---------- */

  function obtener(zona) {
    return preparar(zona).then(function (registro) {
      if (registro.fallo) {
        return registro.sinServidor ? { token: null, aviso: null, sinServidor: true } : { token: null, aviso: LOGICA.AVISO_SIN_CARGAR };
      }
      if (registro.token) return entregar(registro);
      return new Promise(function (resolver) {
        var espera = { resolver: resolver, temporizador: null };
        espera.temporizador = setTimeout(function () {
          var posicion = registro.esperas.indexOf(espera);
          if (posicion !== -1) registro.esperas.splice(posicion, 1);
          resolver({ token: null, aviso: LOGICA.AVISO });
        }, LOGICA.ESPERA_MAXIMA_MS);
        registro.esperas.push(espera);
        /* Si el desafío falló antes, no va a avisar solo: se vuelve a intentar. */
        if (registro.error) { registro.error = false; reiniciar(registro); }
      });
    });
  }

  window.INTEGRO_CAPTCHA = {
    preparar: function (zona) { return preparar(zona).then(function () { return undefined; }); },
    obtener: obtener
  };
})();
