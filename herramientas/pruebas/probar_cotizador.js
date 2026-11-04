// Corre los casos de prueba de la especificación del cotizador contra los datos de muestra.
// Uso: node herramientas/pruebas/probar_cotizador.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const raiz = path.join(__dirname, "..", "..");
const contexto = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(raiz, "web/assets/js/datos.js"), "utf8"), contexto);
const cotizar = require(path.join(raiz, "web/assets/js/cotizador.js"));
const propiedades = contexto.window.INTEGRO_DATOS.propiedades;
const p1 = propiedades.find((p) => p.id === 1);

const casos = [
  { n: 1, llegada: "2026-11-20", salida: "2026-11-22", huespedes: 2, esperado: "total 5250" },
  { n: 2, llegada: "2026-12-14", salida: "2026-12-17", huespedes: 2, esperado: "total 9250 (1 noche a 2400 y 2 de temporada a 3200)" },
  { n: 3, llegada: "2026-11-20", salida: "2026-11-21", huespedes: 2, esperado: "aviso de estancia mínima 2 noches, sin total" },
];

let fallos = 0;
for (const c of casos) {
  const r = cotizar(p1, c.llegada, c.salida, c.huespedes);
  console.log(`Caso ${c.n}: ${c.llegada} -> ${c.salida}, ${c.huespedes} huéspedes`);
  console.log(`  esperado: ${c.esperado}`);
  console.log(`  obtenido: ${JSON.stringify(r)}`);
  const ok = c.n === 1 ? r.ok && r.total === 5250
    : c.n === 2 ? r.ok && r.total === 9250 && r.lineas.length === 2
    : !r.ok && /Estancia mínima: 2/.test(r.aviso);
  console.log(`  ${ok ? "COINCIDE" : "NO COINCIDE"}`);
  if (!ok) fallos++;
}
process.exit(fallos ? 1 : 0);
