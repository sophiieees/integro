// Genera los diagramas entidad-relación de Íntegro en notación de Chen.
// Entidad: rectángulo (débil: doble). Relación: rombo (de identificación: doble).
// Atributo: óvalo (clave: subrayado; clave parcial: subrayado punteado;
// multivalor: doble; derivado: punteado; compuesto: óvalo con óvalos hijos).
// Participación total: línea doble. Cardinalidad: 1, N, M sobre cada línea.
//
// El modelo conceptual vive en este archivo: ENTIDADES, RELACIONES y DIAGRAMAS.
// Si cambia el modelo, se cambia aquí y se regeneran las imágenes.
//
// Cómo usarlo (la librería se instala fuera del repositorio):
//   mkdir ~/er-diagram && cd ~/er-diagram && npm init -y && npm install @viz-js/viz
//   NODE_PATH=~/er-diagram/node_modules node tools/er-diagram/generate.mjs docs/database/img
//   bash tools/er-diagram/to-png.sh docs/database/img
// El primer paso escribe los SVG; el segundo los convierte a PNG con Microsoft Edge.
import { createRequire } from "node:module";
const { instance } = createRequire(import.meta.url)("@viz-js/viz");
import fs from "node:fs";
import path from "node:path";

const AZUL = "#0E0E55";
const salida = process.argv[2] || ".";

// k: clave, p: clave parcial, m: multivalor, d: derivado, c: compuesto (partes)
const a = (n, o = {}) => ({ n, ...o });
const ENTIDADES = {
  User: { attrs: [a("id", { k: 1 }), a("name", { c: ["first_name", "last_name"] }), a("email"), a("phone", { m: 1 }), a("country"), a("birth_date"), a("age", { d: 1 }), a("preferred_language"), a("identity_status")] },
  UserCredential: { debil: 1, attrs: [a("password_hash")] },
  Session: { attrs: [a("id", { k: 1 }), a("token_hash"), a("expires_at"), a("revoked_at")] },
  PasswordReset: { attrs: [a("id", { k: 1 }), a("token_hash"), a("expires_at"), a("used_at")] },
  Admin: { debil: 1, attrs: [a("created_at")] },
  HostProfile: { debil: 1, attrs: [a("level"), a("stripe_account_id"), a("clabe_last4")] },
  Verification: { attrs: [a("id", { k: 1 }), a("kind"), a("provider"), a("provider_reference"), a("result"), a("resolved_at")] },
  AuditLog: { attrs: [a("id", { k: 1 }), a("action"), a("entity_type"), a("entity_id")] },
  Property: { attrs: [a("id", { k: 1 }), a("title"), a("description"), a("property_type"), a("capacity"), a("bedrooms"), a("beds"), a("bathrooms"), a("house_rules", { m: 1 }), a("location", { c: ["city", "zone", "exact_address", "approximate_location"] }), a("cancellation_policy"), a("status"), a("average_rating", { d: 1 })] },
  PropertyPhoto: { debil: 1, attrs: [a("position", { p: 1 }), a("file_path")] },
  Rate: { debil: 1, attrs: [a("nightly_price_cents"), a("cleaning_fee_cents"), a("minimum_nights")] },
  SeasonalRate: { debil: 1, attrs: [a("start_date", { p: 1 }), a("end_date"), a("name"), a("nightly_price_cents")] },
  Amenity: { attrs: [a("id", { k: 1 }), a("code"), a("name", { c: ["name_es", "name_en"] })] },
  CalendarBlock: { debil: 1, attrs: [a("start_date", { p: 1 }), a("end_date"), a("source")] },
  Booking: { attrs: [a("id", { k: 1 }), a("check_in"), a("check_out"), a("nights", { d: 1 }), a("guests_count"), a("total_cents"), a("status")] },
  Payment: { attrs: [a("id", { k: 1 }), a("amount_cents"), a("status"), a("reason"), a("stripe_reference"), a("idempotency_key")] },
  StripeEvent: { attrs: [a("id", { k: 1 }), a("stripe_event_id"), a("event_type"), a("received_at"), a("processed_at")] },
  Membership: { debil: 1, attrs: [a("plan"), a("status"), a("period", { c: ["period_start", "period_end"] }), a("failed_attempts")] },
  MembershipCharge: { attrs: [a("id", { k: 1 }), a("amount_cents"), a("status"), a("stripe_reference"), a("invoice_reference")] },
  Conversation: { attrs: [a("id", { k: 1 })] },
  Message: { attrs: [a("id", { k: 1 }), a("body"), a("status"), a("sent_at"), a("read_at")] },
  Report: { attrs: [a("id", { k: 1 }), a("reason"), a("description"), a("status"), a("resolution")] },
};

// lados: [entidad, cardinalidad, participación total]
const r = (id, verbo, l1, l2, o = {}) => ({ id, verbo, lados: [l1, l2], ...o });
const RELACIONES = [
  r("has_credential", "has", ["User", "1", 0], ["UserCredential", "1", 1], { ident: 1 }),
  r("opens", "opens", ["User", "1", 0], ["Session", "N", 1]),
  r("requests", "requests", ["User", "1", 0], ["PasswordReset", "N", 1]),
  r("is_admin", "is", ["User", "1", 0], ["Admin", "1", 1], { ident: 1 }),
  r("acts_as", "acts as", ["User", "1", 0], ["HostProfile", "1", 1], { ident: 1 }),
  r("undergoes", "undergoes", ["User", "1", 0], ["Verification", "N", 1]),
  r("covers", "covers", ["Verification", "N", 0], ["Property", "1", 0]),
  r("performs", "performs", ["User", "1", 0], ["AuditLog", "N", 0]),
  r("owns", "owns", ["HostProfile", "1", 0], ["Property", "N", 1]),
  r("co_hosts", "co-hosts", ["HostProfile", "M", 0], ["Property", "N", 0], { attrs: [a("since")] }),
  r("shows", "shows", ["Property", "1", 0], ["PropertyPhoto", "N", 1], { ident: 1 }),
  r("charges", "charges", ["Property", "1", 0], ["Rate", "1", 1], { ident: 1 }),
  r("has_season", "has season", ["Property", "1", 0], ["SeasonalRate", "N", 1], { ident: 1 }),
  r("offers", "offers", ["Property", "M", 0], ["Amenity", "N", 0]),
  r("blocked_by", "is blocked by", ["Property", "1", 0], ["CalendarBlock", "N", 1], { ident: 1 }),
  r("occupies", "occupies", ["Booking", "1", 0], ["CalendarBlock", "1", 0]),
  r("books", "books", ["User", "1", 0], ["Booking", "N", 1]),
  r("receives", "receives", ["Property", "1", 0], ["Booking", "N", 1]),
  r("paid_by", "is paid by", ["Booking", "1", 0], ["Payment", "N", 1]),
  r("pays", "pays", ["HostProfile", "1", 0], ["Membership", "1", 1], { ident: 1 }),
  r("generates", "generates", ["Membership", "1", 0], ["MembershipCharge", "N", 1]),
  r("is_about", "is about", ["Conversation", "N", 1], ["Property", "1", 0]),
  r("starts", "starts", ["User", "1", 0], ["Conversation", "N", 1]),
  r("refers_to", "refers to", ["Conversation", "N", 0], ["Booking", "1", 0]),
  r("contains", "contains", ["Conversation", "1", 0], ["Message", "N", 1]),
  r("sends", "sends", ["User", "1", 0], ["Message", "N", 1]),
  r("reviews", "reviews", ["User", "M", 0], ["Booking", "N", 0], { attrs: [a("rating"), a("body")] }),
  r("files", "files", ["User", "1", 0], ["Report", "N", 1]),
  r("concerns_booking", "concerns", ["Report", "N", 0], ["Booking", "1", 0]),
  r("concerns_property", "concerns", ["Report", "N", 0], ["Property", "1", 0]),
];

// Diagramas de detalle: posición de cada entidad en pulgadas (x a la derecha, y hacia arriba).
// rel: posición fija del rombo cuando el punto medio no sirve. lado: hacia dónde van los
// atributos de una relación.
const DIAGRAMAS = [
  { archivo: "chen-people-access",
    pos: { User: [0, 0], Session: [-8.6, 4.4], AuditLog: [-8.6, 0], PasswordReset: [-8.6, -4.4],
           UserCredential: [8.6, 6.3], Admin: [8.6, 2.1], HostProfile: [8.6, -2.1], Verification: [8.6, -6.3], Property: [14.4, -6.3] },
    detalle: ["User", "UserCredential", "Session", "PasswordReset", "Admin", "HostProfile", "Verification", "AuditLog"],
    relaciones: ["has_credential", "opens", "requests", "is_admin", "acts_as", "undergoes", "covers", "performs"] },
  { archivo: "chen-properties",
    pos: { Property: [0, 0], HostProfile: [-10.4, 0], PropertyPhoto: [11.6, 5.4], Rate: [11.6, 1.8], SeasonalRate: [11.6, -1.8], Amenity: [11.6, -5.6] },
    rel: { owns: [-5.6, 1.2], co_hosts: [-5.6, -1.2] }, lado: { co_hosts: [0, -1.1] },
    detalle: ["Property", "PropertyPhoto", "Rate", "SeasonalRate", "Amenity"],
    relaciones: ["owns", "co_hosts", "shows", "charges", "has_season", "offers"] },
  { archivo: "chen-bookings-payments",
    pos: { Booking: [0, 0], User: [-7.2, 4.6], Property: [7.6, 4.6], CalendarBlock: [7.6, 0], Payment: [-7.6, 0], StripeEvent: [0, -5.4] },
    detalle: ["Booking", "CalendarBlock", "Payment", "StripeEvent"],
    relaciones: ["blocked_by", "occupies", "books", "receives", "paid_by"] },
  { archivo: "chen-memberships",
    pos: { HostProfile: [-6.4, 0], Membership: [0, 0], MembershipCharge: [7.2, 0] },
    detalle: ["Membership", "MembershipCharge"], relaciones: ["pays", "generates"] },
  { archivo: "chen-messages-reports",
    pos: { User: [0, 5.2], Message: [-11, 5.2], Conversation: [-5.6, 0], Booking: [5.6, 0], Report: [11, 5.2], Property: [11.6, -4.6] },
    lado: { reviews: [1.15, 0.85] },
    detalle: ["Conversation", "Message", "Report"],
    relaciones: ["is_about", "starts", "refers_to", "contains", "sends", "reviews", "files", "concerns_booking", "concerns_property"] },
];

const q = (s) => `"${s}"`;
const grados = (dx, dy) => ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
const rad = (g) => (g * Math.PI) / 180;

// Reparte los atributos alrededor de un centro, evitando las direcciones ocupadas
// por las líneas hacia los rombos. Devuelve la posición de cada óvalo.
function repartir(centro, attrs, ocupadas, ventana = 15) {
  const k = attrs.length;
  const peso = attrs.map((at) => (at.c ? 1.6 + 0.45 * at.c.length : 1));
  const total = peso.reduce((s, x) => s + x, 0);
  const b = [...ocupadas].sort((x, y) => x - y);
  let arcos = [];
  if (b.length === 0) arcos = [[90, 450]];
  else for (let i = 0; i < b.length; i++) {
    const ini = b[i] + ventana;
    let fin = (i + 1 < b.length ? b[i + 1] : b[0] + 360) - ventana;
    if (fin - ini > 6) arcos.push([ini, fin]);
  }
  const largo = arcos.reduce((s, [i, f]) => s + (f - i), 0);
  const escalonar = k > 5;
  const rx = k > 9 ? 1.6 + 0.11 * k : 1.75 + 0.07 * k, ry = k > 9 ? 1.1 + 0.075 * k : 1.2 + 0.055 * k;
  const posiciones = [];
  let acum = 0, anillo = 1;
  attrs.forEach((at, i) => {
    let t = ((acum + peso[i] / 2) / total) * largo;
    acum += peso[i];
    let ang = 0;
    for (const [ini, fin] of arcos) { if (t <= fin - ini) { ang = ini + t; break; } t -= fin - ini; }
    anillo = !escalonar ? 1 : at.c ? 1.42 : anillo === 1 ? 1.42 : 1;
    const x = centro[0] + anillo * rx * Math.cos(rad(ang));
    const y = centro[1] + anillo * ry * Math.sin(rad(ang));
    const partes = (at.c || []).map((parte, j) => {
      const muchas = at.c.length > 2;
      const fi = ang + (j - (at.c.length - 1) / 2) * (muchas ? 36 : 44);
      const lejos = muchas && j % 2 === 1 ? 1.75 : 1;
      return { n: parte, x: x + lejos * 1.45 * Math.cos(rad(fi)), y: y + lejos * 0.95 * Math.sin(rad(fi)) };
    });
    posiciones.push({ at, x, y, partes });
  });
  return posiciones;
}

function ovalo(L, id, at, x, y, dueno) {
  let etiqueta = q(at.n), extra = "";
  if (at.k || at.p) etiqueta = `<<U>${at.n}</U>>`;
  if (at.p) extra += `, class="parcial"`;
  if (at.m) extra += `, peripheries=2`;
  if (at.d) extra += `, style="filled,dashed"`;
  L.push(`  ${q(id)} [shape=ellipse, fontsize=11, margin="0.06,0.03", fillcolor=white, label=${etiqueta}${extra}, pos="${x.toFixed(2)},${y.toFixed(2)}!"];`);
  L.push(`  ${q(dueno)} -- ${q(id)};`);
}

function cabecera(L, fijo) {
  L.push("graph ER {");
  L.push(fijo ? `  layout=neato; overlap=true; splines=false; outputorder=edgesfirst; bgcolor=white; pad=0.3;`
              : `  layout=neato; overlap=false; splines=true; sep="+10"; outputorder=edgesfirst; bgcolor=white; pad=0.3;`);
  L.push(`  node [fontname="Arial", color="${AZUL}", fontcolor="${AZUL}", style=filled, penwidth=1.2];`);
  L.push(`  edge [fontname="Arial", color="${AZUL}", fontcolor="${AZUL}", fontsize=13, penwidth=1.1];`);
}

const cajaEntidad = (e, pos) => `  ${q(e)} [shape=box, fontsize=14, margin="0.18,0.10", fillcolor="#E3E6F6", label=<<B>${e}</B>>${ENTIDADES[e].debil ? ", peripheries=2" : ""}${pos ? `, pos="${pos[0]},${pos[1]}!"` : ""}];`;
const rombo = (x, pos) => `  ${q(x.id)} [shape=diamond, fontsize=12, margin="0.02,0.02", fillcolor="#FFFFFF", label=${q(x.verbo)}${x.ident ? ", peripheries=2" : ""}${pos ? `, pos="${pos[0].toFixed(2)},${pos[1].toFixed(2)}!"` : ""}];`;
const linea = (e, x, card, total, largo) => `  ${q(e)} -- ${q(x.id)} [label=" ${card} "${largo ? `, len=${largo}` : ""}${total ? `, color="${AZUL}:white:${AZUL}", penwidth=1.3` : ""}];`;

function dotDetalle(d) {
  const rels = RELACIONES.filter((x) => d.relaciones.includes(x.id));
  const L = [];
  cabecera(L, true);
  const posRel = {};
  for (const x of rels) {
    const [p1, p2] = x.lados.map(([e]) => d.pos[e]);
    posRel[x.id] = (d.rel && d.rel[x.id]) || [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2];
  }
  for (const e of Object.keys(d.pos)) {
    L.push(cajaEntidad(e, d.pos[e]));
    if (!d.detalle.includes(e)) continue;
    const ocupadas = rels.filter((x) => x.lados.some(([n]) => n === e))
      .map((x) => grados(posRel[x.id][0] - d.pos[e][0], posRel[x.id][1] - d.pos[e][1]));
    for (const o of repartir(d.pos[e], ENTIDADES[e].attrs, ocupadas, ocupadas.length <= 4 ? 21 : 15)) {
      const id = `${e}.${o.at.n}`;
      ovalo(L, id, o.at, o.x, o.y, e);
      for (const parte of o.partes) ovalo(L, `${id}.${parte.n}`, { n: parte.n }, parte.x, parte.y, id);
    }
  }
  for (const x of rels) {
    L.push(rombo(x, posRel[x.id]));
    for (const [e, card, total] of x.lados) L.push(linea(e, x, card, total));
    const lado = (d.lado && d.lado[x.id]) || [0, 1.1];
    (x.attrs || []).forEach((at, i) => {
      const corrimiento = (i - ((x.attrs.length - 1) / 2)) * 1.5;
      ovalo(L, `${x.id}.${at.n}`, at, posRel[x.id][0] + lado[0] + corrimiento * Math.abs(lado[1]) / 1.1, posRel[x.id][1] + lado[1] - corrimiento * lado[0] / 1.4, x.id);
    });
  }
  L.push("}");
  return L.join("\n");
}

function dotGeneral(semilla) {
  const L = [];
  cabecera(L, false);
  L.push(`  start=${semilla};`);
  for (const e of Object.keys(ENTIDADES)) L.push(cajaEntidad(e));
  for (const x of RELACIONES) {
    L.push(rombo(x));
    for (const [e, card, total] of x.lados) L.push(linea(e, x, card, total, 1.5));
  }
  L.push("}");
  return L.join("\n");
}

// Simbología: un ejemplo de cada figura con su nombre.
function dotSimbologia() {
  const L = [];
  cabecera(L, true);
  const ov = 'shape=ellipse, fontsize=11, margin="0.08,0.04", fillcolor=white';
  L.push(`  e1 [shape=box, fontsize=12, margin="0.18,0.10", fillcolor="#E3E6F6", label="Entidad fuerte", pos="0,0!"];`);
  L.push(`  e2 [shape=box, fontsize=12, margin="0.18,0.10", fillcolor="#E3E6F6", peripheries=2, label="Entidad débil", pos="2.7,0!"];`);
  L.push(`  r1 [shape=diamond, fontsize=11, fillcolor=white, label="Relación", pos="5.4,0!"];`);
  L.push(`  r2 [shape=diamond, fontsize=11, fillcolor=white, peripheries=2, label="Relación de identificación", pos="8.9,0!"];`);
  L.push(`  a1 [${ov}, label="Atributo", pos="0,-1.5!"];`);
  L.push(`  a2 [${ov}, label=<<U>Atributo clave</U>>, pos="2.2,-1.5!"];`);
  L.push(`  a3 [${ov}, label=<<U>Clave parcial</U>>, class="parcial", pos="4.5,-1.5!"];`);
  L.push(`  a4 [${ov}, peripheries=2, label="Atributo multivalor", pos="6.9,-1.5!"];`);
  L.push(`  a5 [${ov}, style="filled,dashed", label="Atributo derivado", pos="9.4,-1.5!"];`);
  L.push(`  c [${ov}, label="Atributo compuesto", pos="1.1,-3.0!"];`);
  L.push(`  p1 [${ov}, label="parte", pos="0.1,-4.0!"]; p2 [${ov}, label="parte", pos="2.1,-4.0!"]; c -- p1; c -- p2;`);
  L.push(`  t1 [shape=box, fontsize=12, margin="0.18,0.10", fillcolor="#E3E6F6", label="Entidad", pos="4.6,-3.3!"];`);
  L.push(`  t2 [shape=diamond, fontsize=11, fillcolor=white, label="Relación", pos="7.2,-3.3!"];`);
  L.push(`  t3 [shape=box, fontsize=12, margin="0.18,0.10", fillcolor="#E3E6F6", label="Entidad", pos="9.8,-3.3!"];`);
  L.push(`  t1 -- t2 [label=" N ", color="${AZUL}:white:${AZUL}", penwidth=1.3]; t2 -- t3 [label=" 1 "];`);
  L.push(`  n1 [shape=plaintext, fontsize=10, fillcolor=white, label="Línea doble: participación total (obligatoria)", pos="5.9,-4.0!"];`);
  L.push(`  n2 [shape=plaintext, fontsize=10, fillcolor=white, label="1, N, M: cardinalidad", pos="8.9,-4.0!"];`);
  L.push('}');
  return L.join(String.fromCharCode(10));
}

// La clave parcial lleva subrayado punteado: Graphviz no lo dibuja, así que se
// cambia el subrayado continuo por una línea punteada debajo del texto.
function subrayadoPunteado(svg) {
  return svg.replace(/<g id="[^"]*" class="node parcial">[\s\S]*?<\/g>/g, (grupo) =>
    grupo.replace(/<text([^>]*)>([^<]*)<\/text>/, (m, attrs, texto) => {
      const x = parseFloat(/ x="([-\d.]+)"/.exec(attrs)[1]);
      const y = parseFloat(/ y="([-\d.]+)"/.exec(attrs)[1]);
      const ancho = texto.length * 11 * 0.5;
      const x1 = / text-anchor="start"/.test(attrs) ? x : x - ancho / 2;
      const limpio = attrs.replace(' text-decoration="underline"', "");
      return `<text${limpio}>${texto}</text><line x1="${x1.toFixed(1)}" y1="${(y + 2.6).toFixed(1)}" x2="${(x1 + ancho).toFixed(1)}" y2="${(y + 2.6).toFixed(1)}" stroke="${AZUL}" stroke-width="1" stroke-dasharray="3,2"/>`;
    }));
}

// Cuenta cruces de líneas en un acomodo automático, para elegir el más limpio.
function cruces(viz, fuente) {
  const g = JSON.parse(viz.renderString(fuente.replace("splines=true", "splines=false"), { format: "json" }));
  const p = {};
  for (const o of g.objects) { const [x, y] = o.pos.split(",").map(Number); p[o._gvid] = [x, y]; }
  const seg = g.edges.map((e) => [e.tail, e.head]);
  const ccw = (A, B, C) => (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0]);
  let n = 0;
  for (let i = 0; i < seg.length; i++) for (let j = i + 1; j < seg.length; j++) {
    const [a1, a2] = seg[i], [b1, b2] = seg[j];
    if (a1 === b1 || a1 === b2 || a2 === b1 || a2 === b2) continue;
    const A = p[a1], B = p[a2], C = p[b1], D = p[b2];
    if (ccw(A, C, D) !== ccw(B, C, D) && ccw(A, B, C) !== ccw(A, B, D)) n++;
  }
  return n;
}

function guardar(nombre, svg, extra = "") {
  fs.writeFileSync(path.join(salida, `${nombre}.svg`), subrayadoPunteado(svg));
  const m = /<svg width="(\d+)pt" height="(\d+)pt"/.exec(svg);
  console.log(nombre, m ? `${m[1]}x${m[2]} pt` : "?", (svg.match(/class="node/g) || []).length, "nodos", extra);
}

const viz = await instance();
let mejor = null;
for (let semilla = 1; semilla <= 80; semilla++) {
  const fuente = dotGeneral(semilla);
  const n = cruces(viz, fuente);
  if (!mejor || n < mejor.n) mejor = { n, fuente, semilla };
}
guardar("chen-general", viz.renderString(mejor.fuente, { format: "svg" }), `(acomodo ${mejor.semilla}, ${mejor.n} cruces)`);
for (const d of DIAGRAMAS) guardar(d.archivo, viz.renderString(dotDetalle(d), { format: "svg" }));
guardar("chen-legend", viz.renderString(dotSimbologia(), { format: "svg" }));
