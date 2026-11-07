/* YAELCORE-OS · Centro de Mando */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const S = {
  estado: null,        // /api/estado
  tareas: [],          // /api/tareas
  vista: "mapa",
  agenteId: null,      // agente abierto
  detalle: null,       // /api/agentes/:id
  filtro: "todos",
  pensando: false,
};

const ETIQUETA_ESTADO = { pendiente: "Pendiente", en_curso: "En curso", revision: "Revisión", hecho: "Hecho" };
const ETIQUETA_TIPO = { contexto: "Contexto", instruccion: "Instrucción", dato: "Dato", recurso: "Recurso", proceso: "Proceso" };
const ETIQUETA_AREA = { frente: "Frente", front: "Front", back: "Back", interfaz: "Interfaz", nucleo: "Núcleo", mkt: "Integrantes MKT" };
const ETIQUETA_ACCION = {
  siguiente: "¿Qué hago primero?",
  automatizar: "¿Qué automatizo?",
  resumen: "Resumen para Yael",
  faltante: "¿Qué info me falta?",
};

// ------------------------------------------------------------------
// Utilidades
// ------------------------------------------------------------------

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(metodo, ruta, datos) {
  const r = await fetch(ruta, {
    method: metodo,
    headers: datos ? { "Content-Type": "application/json" } : {},
    body: datos ? JSON.stringify(datos) : undefined,
    credentials: "same-origin",
  });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && ruta !== "/api/login") { mostrarLogin(); throw new Error(j.error || "Inicia sesión"); }
  if (!r.ok) throw new Error(j.error || `Error ${r.status}`);
  return j;
}

let avisoTimer;
function aviso(texto, mal = false) {
  const el = $("#aviso");
  el.textContent = texto;
  el.classList.toggle("mal", mal);
  el.classList.add("visible");
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => el.classList.remove("visible"), 3200);
}

function hora(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const hoy = new Date();
  const mismaFecha = d.toDateString() === hoy.toDateString();
  return mismaFecha
    ? d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("es", { day: "2-digit", month: "short" }) + " " + d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
}

const plural = (n, palabra) => `${n} ${palabra}${n === 1 ? "" : "s"}`;
const hoyISO = () => new Date().toISOString().slice(0, 10);
const esJefe = () => S.estado?.yo?.rol === "jefe";
const agentePorId = id => S.estado?.agentes.find(a => a.id === id);
const opciones = (lista, etiquetas = {}, sel) =>
  lista.map(v => `<option value="${esc(v)}" ${v === sel ? "selected" : ""}>${esc(etiquetas[v] || v)}</option>`).join("");

function datosForm(form) {
  const d = Object.fromEntries(new FormData(form).entries());
  $$("input[type=checkbox]", form).forEach(c => (d[c.name] = c.checked));
  return d;
}

// ------------------------------------------------------------------
// Acceso
// ------------------------------------------------------------------

let loginNombre = null;

async function mostrarLogin() {
  $("#app").classList.add("oculto");
  $("#login").classList.remove("oculto");
  const miembros = await api("GET", "/api/miembros-publico").catch(() => []);
  $("#login-miembros").innerHTML = miembros.map(m => `
    <button class="login-miembro" style="--c:${esc(m.color)}" data-nombre="${esc(m.nombre)}" data-pin="${m.requiere_pin ? 1 : 0}">
      ${esc(m.nombre)}<small>${esc(m.puesto)}</small>
    </button>`).join("");
}

$("#login-miembros").addEventListener("click", e => {
  const b = e.target.closest(".login-miembro");
  if (!b) return;
  loginNombre = b.dataset.nombre;
  $$(".login-miembro").forEach(x => x.classList.toggle("sel", x === b));
  $("#login-error").textContent = "";
  if (b.dataset.pin === "1") {
    $("#login-nombre").textContent = loginNombre;
    $("#login-form").classList.remove("oculto");
    $("#login-pin").value = "";
    $("#login-pin").focus();
  } else {
    entrar("");
  }
});

$("#login-form").addEventListener("submit", e => { e.preventDefault(); entrar($("#login-pin").value); });

async function entrar(pin) {
  try {
    await api("POST", "/api/login", { nombre: loginNombre, pin });
    $("#login-form").classList.add("oculto");
    await arrancar();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
}

$("#salir").addEventListener("click", async () => {
  await api("POST", "/api/logout").catch(() => {});
  mostrarLogin();
});

// ------------------------------------------------------------------
// Carga y navegación
// ------------------------------------------------------------------

async function cargar() {
  const [estado, tareas] = await Promise.all([api("GET", "/api/estado"), api("GET", "/api/tareas")]);
  S.estado = estado;
  S.tareas = tareas;
  if (S.agenteId && !agentePorId(S.agenteId)) { S.agenteId = null; S.detalle = null; if (S.vista === "agente") S.vista = "mapa"; }
  if (S.agenteId) S.detalle = await api("GET", `/api/agentes/${S.agenteId}`);
}

async function arrancar() {
  await cargar();
  $("#login").classList.add("oculto");
  $("#app").classList.remove("oculto");
  llenarSelects();
  pintar();
}

function irA(vista) {
  S.vista = vista;
  $$("#pestanas button").forEach(b => b.classList.toggle("activa", b.dataset.vista === vista));
  $$(".vista").forEach(v => v.classList.toggle("oculto", v.id !== `vista-${vista}`));
  pintar();
  window.scrollTo({ top: 0 });
}

$("#pestanas").addEventListener("click", e => {
  const b = e.target.closest("button[data-vista]");
  if (b) irA(b.dataset.vista);
});

async function abrirAgente(id) {
  S.agenteId = id;
  S.detalle = await api("GET", `/api/agentes/${id}`);
  irA("agente");
}

function pintar() {
  const { yo, ia } = S.estado;
  $("#yo").innerHTML = `<span class="bolita" style="background:${esc(yo.color)}"></span>${esc(yo.nombre)} · ${esc(yo.puesto || yo.rol)}`;
  $("#ia-estado").innerHTML = ia.length
    ? `<span class="bolita" style="background:var(--verde)"></span>IA: ${esc(ia.join(" + "))}`
    : `<span class="bolita" style="background:var(--rojo)"></span>IA sin conectar`;
  $("#pestana-equipo").classList.toggle("oculto", !esJefe());
  $("#pestana-agente").classList.toggle("oculto", !S.agenteId);
  if (S.detalle) $("#pestana-agente").textContent = S.detalle.agente.nombre;

  if (S.vista === "mapa") pintarMapa();
  if (S.vista === "tareas") pintarKanban();
  if (S.vista === "conocimiento") pintarFichas();
  if (S.vista === "agente") pintarAgente();
  if (S.vista === "equipo") pintarEquipo();
}

function llenarSelects() {
  const c = S.estado.catalogos;
  const agentes = S.estado.agentes;
  const opAgentes = agentes.map(a => `<option value="${a.id}">${esc(a.nombre)} — ${esc(a.operador || "sin operador")}</option>`).join("");

  const filtroPrevio = S.filtro;
  $("#filtro-agente").innerHTML =
    `<option value="todos">Todos los agentes</option>` +
    `<optgroup label="Agentes">${agentes.map(a => `<option value="a:${a.id}">${esc(a.nombre)}</option>`).join("")}</optgroup>` +
    `<optgroup label="Áreas">${c.areas.map(x => `<option value="area:${x}">${esc(ETIQUETA_AREA[x] || x)}</option>`).join("")}</optgroup>` +
    `<optgroup label="Personas">${S.estado.miembros.map(m => `<option value="m:${m.id}">${esc(m.nombre)}</option>`).join("")}</optgroup>`;
  $("#filtro-agente").value = $$("#filtro-agente option").some(o => o.value === filtroPrevio) ? filtroPrevio : "todos";

  const destinoPrevio = $("#ficha-destino").value;
  $("#ficha-destino").innerHTML = (esJefe() ? `<option value="todos">Todos los agentes (información general)</option>` : "") + opAgentes;
  if (destinoPrevio) $("#ficha-destino").value = destinoPrevio;
  $("#ficha-tipo").innerHTML = opciones(c.tipos, ETIQUETA_TIPO);

  $("#tarea-agente").innerHTML = opAgentes;
  $("#tarea-prioridad").innerHTML = opciones(c.prioridades, { baja: "Baja", media: "Media", alta: "Alta" }, "media");
  $("#tarea-estado").innerHTML = opciones(c.estados, ETIQUETA_ESTADO);
  $("#tarea-recurrencia").innerHTML = opciones(c.recurrencias, { ninguna: "No se repite", diaria: "Cada día", semanal: "Cada semana", mensual: "Cada mes" });

  $("#agente-operador").innerHTML = S.estado.miembros.map(m => `<option value="${m.id}">${esc(m.nombre)}</option>`).join("");
  $("#agente-area").innerHTML = opciones(c.areas, ETIQUETA_AREA, "nucleo");
}

// ------------------------------------------------------------------
// Mapa (réplica del diagrama de Yael)
// ------------------------------------------------------------------

const NODOS = {
  frente:   { x: 512, y: 90,  w: 160, t: "Frente",          c: "#e05252", area: "frente" },
  front:    { x: 125, y: 200, w: 150,  t: "front",           c: "#3fa463", area: "front" },
  back:     { x: 875, y: 207, w: 150,  t: "back",            c: "#c9c35a", area: "back" },
  interfaz: { x: 512, y: 262, w: 160, t: "interfaz",        c: "#8a6fd1", area: "interfaz" },
  nucleo:   { x: 512, y: 380, w: 160, t: "núcleo",          c: "#d9913b", area: "nucleo" },
  agIzq:    { x: 157, y: 380, w: 115, t: "agentes",         c: "#4fb3bf", grupo: "agentes" },
  agDer:    { x: 840, y: 380, w: 115, t: "agentes",         c: "#4fb3bf", grupo: "agentes" },
  mkt:      { x: 512, y: 490, w: 185, t: "integrantes mkt", c: "#3fa463", area: "mkt" },
  yael:     { x: 512, y: 590, w: 165, t: "jefe Yael",       c: "#e05252", miembro: "yael" },
  frida:    { x: 245, y: 710, w: 130, t: "Frida",           c: "#d9913b", miembro: "frida" },
  efren:    { x: 512, y: 740, w: 135, t: "Efren",           c: "#b65fd6", miembro: "efren" },
  nova:     { x: 775, y: 710, w: 128, t: "Nova",            c: "#c9c35a", miembro: "nova" },
};
const ALTO = 56;

const ARISTAS = [
  ["frente", "front"], ["frente", "back"], ["frente", "interfaz"], ["frente", "agIzq"], ["frente", "agDer"],
  ["interfaz", "nucleo"], ["nucleo", "agIzq"], ["nucleo", "agDer"], ["interfaz", "agIzq"], ["interfaz", "agDer"],
  ["nucleo", "mkt"], ["nucleo", "frente"], ["mkt", "frente"], ["mkt", "front"], ["mkt", "back"], ["mkt", "yael"],
  ["agIzq", "yael"], ["agDer", "yael"], ["nucleo", "yael"], ["interfaz", "yael"],
  ["agIzq", "frida"], ["agIzq", "efren"], ["agDer", "nova"], ["agDer", "efren"],
  ["yael", "frida"], ["yael", "efren"], ["yael", "nova"], ["frida", "efren"], ["nova", "efren"],
];

function miembroDeNodo(n) {
  return n.miembro && S.estado.miembros.find(m => m.nombre.toLowerCase() === n.miembro);
}

function tareasAbiertas(filtro) {
  return S.tareas.filter(t => t.estado !== "hecho" && filtro(t));
}

function curva(a, b) {
  const dy = b.y - a.y, dx = b.x - a.x;
  const sale = { x: a.x, y: a.y + Math.sign(dy || 1) * ALTO / 2 };
  const llega = { x: b.x, y: b.y - Math.sign(dy || 1) * ALTO / 2 };
  if (Math.abs(dy) < 30) {
    sale.x = a.x + Math.sign(dx) * NODOS_W(a) / 2; sale.y = a.y;
    llega.x = b.x - Math.sign(dx) * NODOS_W(b) / 2; llega.y = b.y;
    return `M${sale.x},${sale.y} C${(sale.x + llega.x) / 2},${sale.y} ${(sale.x + llega.x) / 2},${llega.y} ${llega.x},${llega.y}`;
  }
  const k = Math.abs(dy) * 0.5;
  return `M${sale.x},${sale.y} C${sale.x},${sale.y + Math.sign(dy) * k} ${llega.x},${llega.y - Math.sign(dy) * k} ${llega.x},${llega.y}`;
}
const NODOS_W = n => n.w;

function pintarMapa() {
  const svg = $("#mapa");
  const hoy = hoyISO();
  let html = `<defs><marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a8a8a"/></marker></defs>`;
  html += ARISTAS.map(([a, b]) =>
    `<path class="arista" data-a="${a}" data-b="${b}" d="${curva(NODOS[a], NODOS[b])}" marker-end="url(#flecha)"/>`).join("");

  for (const [id, n] of Object.entries(NODOS)) {
    let info = "", alerta = false;
    const miembro = miembroDeNodo(n);
    if (miembro) {
      const abiertas = tareasAbiertas(t => t.operador_id === miembro.id);
      alerta = abiertas.some(t => t.fecha_limite && t.fecha_limite < hoy);
      info = `${plural(abiertas.length, "tarea")} abierta${abiertas.length === 1 ? "" : "s"}`;
    } else if (n.area) {
      const agentes = S.estado.agentes.filter(a => a.area === n.area);
      const abiertas = tareasAbiertas(t => agentePorId(t.agente_id)?.area === n.area);
      info = n.area === "mkt" ? `${S.estado.miembros.length} personas` : `${plural(agentes.length, "agente")} · ${plural(abiertas.length, "tarea")}`;
    } else if (n.grupo) {
      info = `${plural(S.estado.agentes.filter(a => a.estado !== "pausado").length, "agente")} activos`;
    }
    html += `
      <g class="nodo" data-nodo="${id}" style="--c:${n.c}" tabindex="0" role="button" aria-label="${esc(n.t)}">
        <rect x="${n.x - n.w / 2}" y="${n.y - ALTO / 2}" width="${n.w}" height="${ALTO}" rx="8" stroke="${n.c}"/>
        <text x="${n.x}" y="${n.y - 3}" text-anchor="middle" font-weight="${n.miembro || id === "frente" ? 700 : 400}">${esc(n.t)}</text>
        <text class="contador ${alerta ? "alerta" : ""}" x="${n.x}" y="${n.y + 16}" text-anchor="middle">${esc(info)}${alerta ? " · ¡vencidas!" : ""}</text>
      </g>`;
  }
  svg.innerHTML = html;

  // Resumen
  const r = S.estado.resumen;
  $("#resumen").innerHTML = [
    ["abiertas", "Tareas abiertas", ""], ["hechas", "Completadas", "verde"],
    ["vencidas", "Vencidas", r.vencidas ? "rojo" : ""], ["revision", "Por revisar", ""],
    ["automatizables", "Automatizables", ""], ["recurrentes", "Automáticas (recurrentes)", ""],
    ["fichas", "Fichas de conocimiento", ""], ["agentes", "Agentes", ""],
  ].map(([k, t, cl]) => `<div class="dato ${cl}"><b>${r[k]}</b><span>${t}</span></div>`).join("");

  // Mis agentes
  const yo = S.estado.yo;
  const mios = S.estado.agentes.filter(a => esJefe() || a.operador_id === yo.id);
  $("#mis-agentes").innerHTML = mios.length ? mios.map(itemAgente).join("") : `<p class="vacio">Aún no controlas ningún agente. Pídele uno a Yael.</p>`;

  // Actividad
  $("#actividad").innerHTML = S.estado.actividad.map(a => `
    <li><span class="bolita" style="background:${esc(a.color || "#666")};margin-top:5px"></span>
      <div>${esc(a.texto)}<time>${esc(a.autor || "Sistema")} · ${hora(a.creado)}</time></div></li>`).join("");
}

function itemAgente(a) {
  return `<button class="item-agente" data-agente="${a.id}">
    <span class="bolita" style="background:${esc(a.color || "#666")}"></span>
    <span class="info"><b>${esc(a.nombre)}</b><small>${esc(a.operador || "sin operador")} · ${esc(ETIQUETA_AREA[a.area] || a.area)}${a.estado === "pausado" ? " · pausado" : ""}</small></span>
    <span class="chip">${a.abiertas} abiertas</span>
  </button>`;
}

function iluminar(id, si) {
  $$(`.arista[data-a="${id}"], .arista[data-b="${id}"]`).forEach(p => p.classList.toggle("viva", si));
}

$("#mapa").addEventListener("mouseover", e => { const g = e.target.closest(".nodo"); if (g) iluminar(g.dataset.nodo, true); });
$("#mapa").addEventListener("mouseout", e => { const g = e.target.closest(".nodo"); if (g) iluminar(g.dataset.nodo, false); });
$("#mapa").addEventListener("keydown", e => { if (e.key === "Enter") e.target.closest(".nodo")?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
$("#mapa").addEventListener("click", e => {
  const g = e.target.closest(".nodo");
  if (!g) return;
  const n = NODOS[g.dataset.nodo];
  const miembro = miembroDeNodo(n);
  if (miembro) {
    const suyos = S.estado.agentes.filter(a => a.operador_id === miembro.id);
    if (suyos.length === 1) return abrirAgente(suyos[0].id);
    S.filtro = `m:${miembro.id}`;
    if (!suyos.length && miembro.rol !== "jefe") aviso(`${miembro.nombre} todavía no controla ningún agente.`);
    return irTareasFiltradas();
  }
  if (n.grupo) { $("#mis-agentes").scrollIntoView({ behavior: "smooth" }); return; }
  S.filtro = n.area === "mkt" ? "todos" : `area:${n.area}`;
  irTareasFiltradas();
});

function irTareasFiltradas() {
  llenarSelects();
  irA("tareas");
}

document.addEventListener("click", e => {
  const a = e.target.closest("[data-agente]");
  if (a) abrirAgente(Number(a.dataset.agente));
});

// ------------------------------------------------------------------
// Tareas (kanban)
// ------------------------------------------------------------------

function pasaFiltro(t) {
  const f = S.filtro;
  if ($("#filtro-auto").checked && !t.automatizable) return false;
  if (f === "todos") return true;
  const [tipo, valor] = f.split(":");
  if (tipo === "a") return t.agente_id === Number(valor);
  if (tipo === "m") return t.operador_id === Number(valor);
  if (tipo === "area") return agentePorId(t.agente_id)?.area === valor;
  return true;
}

function tarjetaTarea(t, compacta = false) {
  const a = agentePorId(t.agente_id);
  const vencida = t.estado !== "hecho" && t.fecha_limite && t.fecha_limite < hoyISO();
  const est = S.estado.catalogos.estados;
  const i = est.indexOf(t.estado);
  return `<div class="tarea" draggable="true" data-tarea="${t.id}" style="--c:${esc(a?.color || "#666")}">
    <div class="t">${esc(t.titulo)}</div>
    <div class="etiquetas">
      ${compacta ? `<span class="etq">${esc(ETIQUETA_ESTADO[t.estado])}</span>` : `<span class="etq">${esc(t.agente)}</span>`}
      ${t.prioridad === "alta" ? `<span class="etq alta">alta</span>` : ""}
      ${t.fecha_limite ? `<span class="etq ${vencida ? "vencida" : ""}">${vencida ? "venció" : "vence"} ${esc(t.fecha_limite)}</span>` : ""}
      ${t.automatizable ? `<span class="etq auto">⚙ automatizable</span>` : ""}
      ${t.recurrencia !== "ninguna" ? `<span class="etq auto">↻ ${esc(t.recurrencia)}</span>` : ""}
      ${t.creador ? `<span class="etq">de ${esc(t.creador)}</span>` : ""}
    </div>
    ${compacta ? "" : `<div class="mover">
      ${i > 0 ? `<button class="btn chico" data-mover="${est[i - 1]}">← ${esc(ETIQUETA_ESTADO[est[i - 1]])}</button>` : ""}
      ${i < est.length - 1 ? `<button class="btn chico" data-mover="${est[i + 1]}">${esc(ETIQUETA_ESTADO[est[i + 1]])} →</button>` : ""}
    </div>`}
  </div>`;
}

function pintarKanban() {
  const visibles = S.tareas.filter(pasaFiltro);
  $("#kanban").innerHTML = S.estado.catalogos.estados.map(e => {
    const col = visibles.filter(t => t.estado === e);
    return `<div class="columna" data-columna="${e}">
      <h3>${esc(ETIQUETA_ESTADO[e])} <span>${col.length}</span></h3>
      ${col.map(t => tarjetaTarea(t)).join("") || `<p class="vacio">Nada aquí.</p>`}
    </div>`;
  }).join("");
}

$("#filtro-agente").addEventListener("change", e => { S.filtro = e.target.value; pintarKanban(); });
$("#filtro-auto").addEventListener("change", pintarKanban);

async function moverTarea(id, estado) {
  try {
    const r = await api("PATCH", `/api/tareas/${id}`, { estado });
    if (r.siguiente) aviso(`↻ Automatización: «${r.siguiente.titulo}» reprogramada para ${r.siguiente.fecha_limite}`);
    await refrescar();
  } catch (err) { aviso(err.message, true); }
}

document.addEventListener("click", e => {
  const mover = e.target.closest("[data-mover]");
  if (mover) {
    e.stopPropagation();
    return moverTarea(Number(mover.closest("[data-tarea]").dataset.tarea), mover.dataset.mover);
  }
  const t = e.target.closest(".tarea[data-tarea]");
  if (t) return abrirModalTarea(Number(t.dataset.tarea));
  if (e.target.closest("[data-nueva-tarea]")) {
    const preset = e.target.closest("[data-nueva-tarea]").dataset.nuevaTarea;
    abrirModalTarea(null, preset ? Number(preset) : undefined);
  }
});

// Arrastrar y soltar entre columnas
document.addEventListener("dragstart", e => {
  const t = e.target.closest?.(".tarea[data-tarea]");
  if (t) e.dataTransfer.setData("text/plain", t.dataset.tarea);
});
document.addEventListener("dragover", e => {
  const c = e.target.closest?.("[data-columna]");
  if (c) { e.preventDefault(); c.classList.add("sobre"); }
});
document.addEventListener("dragleave", e => e.target.closest?.("[data-columna]")?.classList.remove("sobre"));
document.addEventListener("drop", e => {
  const c = e.target.closest?.("[data-columna]");
  if (!c) return;
  e.preventDefault();
  c.classList.remove("sobre");
  const id = Number(e.dataTransfer.getData("text/plain"));
  const t = S.tareas.find(x => x.id === id);
  if (t && t.estado !== c.dataset.columna) moverTarea(id, c.dataset.columna);
});

// Modal de tarea
let tareaEditando = null;

function abrirModalTarea(id, agenteId) {
  const f = $("#form-tarea");
  f.reset();
  $("#tarea-error").textContent = "";
  tareaEditando = id ? S.tareas.find(t => t.id === id) : null;
  const t = tareaEditando;
  $("#modal-tarea-titulo").textContent = t ? "Editar tarea" : "Nueva tarea";
  $("#tarea-borrar").classList.toggle("oculto", !t || !(esJefe() || t.creador_id === S.estado.yo.id));
  f.agente_id.disabled = !!t && !esJefe();
  if (t) {
    for (const k of ["agente_id", "titulo", "detalle", "prioridad", "fecha_limite", "estado", "recurrencia", "resultado"]) f[k].value = t[k] ?? "";
    f.automatizable.checked = !!t.automatizable;
  } else {
    const mios = S.estado.agentes.filter(a => a.operador_id === S.estado.yo.id);
    f.agente_id.value = agenteId || S.agenteId || mios[0]?.id || S.estado.agentes[0]?.id || "";
    f.prioridad.value = "media";
    f.estado.value = "pendiente";
    f.recurrencia.value = "ninguna";
  }
  $("#modal-tarea").showModal();
}

$("#tarea-cancelar").addEventListener("click", () => $("#modal-tarea").close());
$("#form-tarea").addEventListener("submit", async e => {
  e.preventDefault();
  const d = datosForm(e.target);
  try {
    if (tareaEditando) {
      if (!esJefe()) delete d.agente_id;
      const r = await api("PATCH", `/api/tareas/${tareaEditando.id}`, d);
      if (r.siguiente) aviso(`↻ Automatización: «${r.siguiente.titulo}» reprogramada para ${r.siguiente.fecha_limite}`);
      else aviso("Tarea actualizada");
    } else {
      const estado = d.estado;
      const nueva = await api("POST", "/api/tareas", d);
      if (estado && estado !== "pendiente") await api("PATCH", `/api/tareas/${nueva.id}`, { estado });
      aviso("Tarea asignada");
    }
    $("#modal-tarea").close();
    await refrescar();
  } catch (err) { $("#tarea-error").textContent = err.message; }
});
$("#tarea-borrar").addEventListener("click", async () => {
  if (!tareaEditando || !confirm(`¿Borrar «${tareaEditando.titulo}»?`)) return;
  try {
    await api("DELETE", `/api/tareas/${tareaEditando.id}`);
    $("#modal-tarea").close();
    aviso("Tarea borrada");
    await refrescar();
  } catch (err) { $("#tarea-error").textContent = err.message; }
});

// ------------------------------------------------------------------
// Conocimiento
// ------------------------------------------------------------------

let fichasCache = [];

async function pintarFichas() {
  // Junta el conocimiento de todos los agentes (sin duplicar el general)
  const vistos = new Map();
  const detalles = await Promise.all(S.estado.agentes.map(a => api("GET", `/api/agentes/${a.id}`).catch(() => null)));
  detalles.filter(Boolean).forEach(d => d.conocimiento.forEach(f => vistos.set(f.id, f)));
  fichasCache = [...vistos.values()].sort((a, b) => b.id - a.id);
  filtrarFichas();
}

function htmlFicha(f) {
  const destino = f.agente_id == null ? "Todos los agentes" : (agentePorId(f.agente_id)?.nombre || "—");
  const puedeBorrar = esJefe() || f.autor_id === S.estado.yo.id;
  return `<article class="ficha">
    <header><b>${esc(f.titulo)}</b><span class="etq">${esc(ETIQUETA_TIPO[f.tipo] || f.tipo)}</span></header>
    <p>${esc(f.contenido)}</p>
    <footer><span>→ ${esc(destino)}</span><span>· ${esc(f.autor || "")}</span><span>· ${hora(f.creado)}</span>
      <span class="espacio"></span>${puedeBorrar ? `<button class="btn chico peligro" data-borrar-ficha="${f.id}">Borrar</button>` : ""}</footer>
  </article>`;
}

function filtrarFichas() {
  const q = $("#buscar-ficha").value.trim().toLowerCase();
  const lista = fichasCache.filter(f => !q || (f.titulo + " " + f.contenido).toLowerCase().includes(q));
  $("#lista-fichas").innerHTML = lista.map(htmlFicha).join("") || `<p class="vacio">Todavía no hay información. Empieza pasándole contexto a un agente.</p>`;
}
$("#buscar-ficha").addEventListener("input", filtrarFichas);

async function guardarFicha(form, agenteForzado) {
  const d = datosForm(form);
  if (agenteForzado) d.agente_id = agenteForzado;
  await api("POST", "/api/conocimiento", d);
  form.reset();
  aviso("Información guardada. El agente ya la puede usar.");
  await refrescar();
}

$("#form-ficha").addEventListener("submit", async e => {
  e.preventDefault();
  try { await guardarFicha(e.target); } catch (err) { aviso(err.message, true); }
});

document.addEventListener("click", async e => {
  const b = e.target.closest("[data-borrar-ficha]");
  if (!b || !confirm("¿Borrar esta información?")) return;
  try { await api("DELETE", `/api/conocimiento/${b.dataset.borrarFicha}`); aviso("Borrada"); await refrescar(); }
  catch (err) { aviso(err.message, true); }
});

// ------------------------------------------------------------------
// Vista de agente: tareas + conocimiento + canal con copiloto IA
// ------------------------------------------------------------------

function pintarAgente() {
  const d = S.detalle;
  if (!d) return irA("mapa");
  const a = d.agente;
  const yo = S.estado.yo;
  const cont = $("#vista-agente");
  const scrollMsgs = $(".mensajes", cont);
  const alFondo = !scrollMsgs || scrollMsgs.scrollHeight - scrollMsgs.scrollTop - scrollMsgs.clientHeight < 60;
  const borrador = $("#msg-texto", cont)?.value || "";
  const fichaBorrador = $("#form-ficha-agente", cont) ? datosForm($("#form-ficha-agente", cont)) : null;
  const foco = document.activeElement?.id;

  const abiertas = d.tareas.filter(t => t.estado !== "hecho");
  const hechas = d.tareas.filter(t => t.estado === "hecho").slice(0, 8);

  cont.innerHTML = `
    <div class="agente-cab" style="--c:${esc(a.color || "#666")}">
      <div class="avatar">${esc(a.nombre.replace(/^agente\s+/i, "").slice(0, 1).toUpperCase())}</div>
      <div class="titulo">
        <h1>${esc(a.nombre)} ${a.estado === "pausado" ? `<span class="chip">pausado</span>` : ""}</h1>
        <div class="tenue">Lo controla <b>${esc(a.operador || "nadie")}</b> · Área ${esc(ETIQUETA_AREA[a.area] || a.area)} · ${a.abiertas} abiertas · ${a.hechas} hechas · ${a.fichas} fichas</div>
        ${d.puede_operar
          ? `<form id="form-mision" class="mision"><textarea name="mision" rows="2" placeholder="Misión del agente">${esc(a.mision)}</textarea><button class="btn">Guardar misión</button></form>`
          : `<p>${esc(a.mision)}</p>`}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn primario" data-nueva-tarea="${a.id}">+ Pasarle una tarea</button>
        ${d.puede_operar ? `<button class="btn" id="pausar">${a.estado === "pausado" ? "Reactivar" : "Pausar"}</button>` : ""}
        ${esJefe() ? `<button class="btn peligro" id="borrar-agente">Eliminar agente</button>` : ""}
      </div>
    </div>

    <div class="tres-columnas">
      <div class="tarjeta">
        <div class="tarjeta-cab"><h2>Tareas abiertas (${abiertas.length})</h2></div>
        <div class="lista-compacta">${abiertas.map(t => tarjetaTarea(t, true)).join("") || `<p class="vacio">Sin tareas abiertas.</p>`}</div>
        ${hechas.length ? `<h2 class="separado">Completadas recientes</h2><div class="lista-compacta">${hechas.map(t => tarjetaTarea(t, true)).join("")}</div>` : ""}
      </div>

      <div class="tarjeta">
        <h2>Pasarle información</h2>
        <form id="form-ficha-agente" class="formulario">
          <select name="tipo">${opciones(S.estado.catalogos.tipos, ETIQUETA_TIPO)}</select>
          <input name="titulo" required maxlength="120" placeholder="Título">
          <textarea name="contenido" rows="4" placeholder="Contexto, procesos, datos, enlaces…"></textarea>
          <button class="btn primario" type="submit">Guardar en su memoria</button>
        </form>
        <h2 class="separado">Lo que sabe (${d.conocimiento.length})</h2>
        <div class="lista-compacta">${d.conocimiento.map(htmlFicha).join("") || `<p class="vacio">Aún no sabe nada. Pásale contexto para que te ayude mejor.</p>`}</div>
      </div>

      <div class="tarjeta chat">
        <div class="tarjeta-cab"><h2>Canal y copiloto IA</h2><span class="tenue">${esc(yo.nombre)}</span></div>
        <div class="atajos">${S.estado.catalogos.acciones_ia.map(k => `<button class="btn chico" data-accion-ia="${k}">⚡ ${esc(ETIQUETA_ACCION[k] || k)}</button>`).join("")}</div>
        <div class="mensajes">${d.mensajes.map(m => `<div class="msg ${m.es_ia ? "ia" : ""} ${m.autor_id === yo.id ? "mio" : ""}"><div class="autor"><span class="bolita" style="background:${esc(m.es_ia ? "#8a6fd1" : (m.color || "#666"))}"></span>${esc(m.es_ia ? "Copiloto IA" : (m.autor || "—"))} · ${hora(m.creado)}</div>${esc(m.texto)}</div>`).join("")
          || `<p class="vacio">Escribe al equipo o pregúntale al copiloto. El copiloto conoce la misión, la información y las tareas de este agente.</p>`}
        </div>
        <div class="pensando">${S.pensando ? "El copiloto está pensando…" : ""}</div>
        <form id="form-msg" class="enviar">
          <textarea id="msg-texto" placeholder="Mensaje para el equipo o pregunta para la IA…"></textarea>
          <button class="btn" type="submit" title="Enviar al canal del equipo">Enviar</button>
          <button class="btn primario" type="button" id="preguntar-ia" title="Preguntar al copiloto IA">IA</button>
        </form>
      </div>
    </div>`;

  // Restaurar lo que el usuario estaba escribiendo
  $("#msg-texto").value = borrador;
  if (fichaBorrador) {
    const f = $("#form-ficha-agente");
    f.tipo.value = fichaBorrador.tipo; f.titulo.value = fichaBorrador.titulo; f.contenido.value = fichaBorrador.contenido;
  }
  if (foco && document.getElementById(foco)) document.getElementById(foco).focus();
  const m = $(".mensajes", cont);
  if (alFondo) m.scrollTop = m.scrollHeight;

  $("#form-mision")?.addEventListener("submit", async e => {
    e.preventDefault();
    try { await api("PATCH", `/api/agentes/${a.id}`, datosForm(e.target)); aviso("Misión guardada"); await refrescar(); }
    catch (err) { aviso(err.message, true); }
  });
  $("#pausar")?.addEventListener("click", async () => {
    try { await api("PATCH", `/api/agentes/${a.id}`, { estado: a.estado === "pausado" ? "activo" : "pausado" }); await refrescar(); }
    catch (err) { aviso(err.message, true); }
  });
  $("#borrar-agente")?.addEventListener("click", async () => {
    if (!confirm(`¿Eliminar ${a.nombre} con todas sus tareas, información y mensajes?`)) return;
    try { await api("DELETE", `/api/agentes/${a.id}`); S.agenteId = null; S.detalle = null; await refrescar(); irA("mapa"); }
    catch (err) { aviso(err.message, true); }
  });
  $("#form-ficha-agente").addEventListener("submit", async e => {
    e.preventDefault();
    try { await guardarFicha(e.target, a.id); } catch (err) { aviso(err.message, true); }
  });
  $("#form-msg").addEventListener("submit", async e => {
    e.preventDefault();
    const texto = $("#msg-texto").value.trim();
    if (!texto) return;
    try { await api("POST", `/api/agentes/${a.id}/mensajes`, { texto }); $("#msg-texto").value = ""; await refrescar(); }
    catch (err) { aviso(err.message, true); }
  });
  $("#msg-texto").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#form-msg").requestSubmit(); }
  });
  $("#preguntar-ia").addEventListener("click", () => {
    const texto = $("#msg-texto").value.trim();
    if (!texto) return aviso("Escribe tu pregunta para la IA", true);
    preguntarIA(a.id, texto, () => ($("#msg-texto").value = ""));
  });
  $$("[data-accion-ia]", cont).forEach(b => b.addEventListener("click", () => preguntarIA(a.id, b.dataset.accionIa)));
}

async function preguntarIA(agenteId, pregunta, alEnviar) {
  if (S.pensando) return;
  if (!S.estado.ia.length) return aviso("No hay IA conectada. Agrega tus claves en el archivo .env", true);
  S.pensando = true;
  alEnviar?.();
  pintar();
  try {
    await api("POST", `/api/agentes/${agenteId}/ia`, { pregunta });
  } catch (err) {
    aviso(err.message, true);
  } finally {
    S.pensando = false;
    await refrescar();
  }
}

// ------------------------------------------------------------------
// Equipo (solo jefe)
// ------------------------------------------------------------------

function pintarEquipo() {
  $("#lista-miembros").innerHTML = S.estado.miembros.map(m => {
    const suyos = S.estado.agentes.filter(a => a.operador_id === m.id);
    return `<div class="item-agente" style="cursor:default">
      <span class="bolita" style="background:${esc(m.color)}"></span>
      <span class="info"><b>${esc(m.nombre)}</b><small>${esc(m.puesto || m.rol)} · controla: ${esc(suyos.map(a => a.nombre).join(", ") || "ningún agente")}</small></span>
    </div>`;
  }).join("") + `<h2 class="separado">Agentes</h2>` + S.estado.agentes.map(itemAgente).join("");
}

$("#form-agente").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const a = await api("POST", "/api/agentes", datosForm(e.target));
    e.target.reset();
    aviso(`${a.nombre} creado`);
    await refrescar();
    llenarSelects();
  } catch (err) { aviso(err.message, true); }
});
$("#form-miembro").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const m = await api("POST", "/api/miembros", datosForm(e.target));
    e.target.reset();
    aviso(`${m.nombre} agregado. Define su PIN en .env: CENTRO_PIN_${m.nombre.toUpperCase()}`);
    await refrescar();
    llenarSelects();
  } catch (err) { aviso(err.message, true); }
});

// ------------------------------------------------------------------
// Refresco en vivo (el equipo trabaja al mismo tiempo)
// ------------------------------------------------------------------

async function refrescar() {
  try {
    const nAgentes = S.estado?.agentes.length;
    const nMiembros = S.estado?.miembros.length;
    await cargar();
    if (S.estado.agentes.length !== nAgentes || S.estado.miembros.length !== nMiembros) llenarSelects();
    // No repintar formularios mientras el usuario escribe en ellos
    const activo = document.activeElement;
    const escribiendo = activo && ["INPUT", "TEXTAREA", "SELECT"].includes(activo.tagName) && !activo.closest("#vista-agente");
    if ($("#modal-tarea").open || (escribiendo && S.vista !== "tareas")) return;
    if (activo?.closest("#form-mision")) return;
    if (S.vista === "conocimiento" && escribiendo) return;
    pintar();
  } catch (_) { /* sin conexión momentánea */ }
}

setInterval(() => { if (!$("#app").classList.contains("oculto") && !document.hidden) refrescar(); }, 6000);

// Inicio
api("GET", "/api/estado").then(arrancar).catch(() => mostrarLogin());
