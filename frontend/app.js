// Dashboard logic (dependency-free)

const $ = (sel) => document.querySelector(sel);
const state = { sensors: {}, scenario: null, llm: false, lastReport: null };
const feedEvents = new Map();   // event id -> DOM element
const cards = new Map();        // sensor id -> { el, canvas, refs }
const actions = new Map();      // sensor id -> action item

// Helper functions
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function sevWord(hint) {
  return ({ normal: "Low", low: "Low", moderate: "Moderate", critical: "Critical" }[hint] || "Low");
}
function sevClass(sev) {
  return ({ Critical: "crit", Moderate: "mod", Low: "low" }[sev] || "low");
}
function fmt(v, d = 2) {
  return (v === null || v === undefined || isNaN(v)) ? "–" : Number(v).toFixed(d);
}

function mdToHtml(md) {
  const lines = (md || "").split("\n");
  const out = [];
  let inList = false;
  const inline = (t) => escapeHtml(t)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { if (inList) { out.push("</ul>"); inList = false; } continue; }
    if (line.startsWith("### ")) { if (inList) { out.push("</ul>"); inList = false; } out.push("<h3>" + inline(line.slice(4)) + "</h3>"); }
    else if (line.startsWith("## ")) { if (inList) { out.push("</ul>"); inList = false; } out.push("<h2>" + inline(line.slice(3)) + "</h2>"); }
    else if (line.startsWith("# ")) { if (inList) { out.push("</ul>"); inList = false; } out.push("<h1>" + inline(line.slice(2)) + "</h1>"); }
    else if (/^\s*([-*]|\d+\.)\s+/.test(line)) { if (!inList) { out.push("<ul>"); inList = true; } out.push("<li>" + inline(line.replace(/^\s*([-*]|\d+\.)\s+/, "")) + "</li>"); }
    else { if (inList) { out.push("</ul>"); inList = false; } out.push("<p>" + inline(line) + "</p>"); }
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

// WebSocket connection handler
let ws = null;
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => setConn(true);
  ws.onclose = () => { setConn(false); setTimeout(connect, 1500); };
  ws.onerror = () => ws.close();
  ws.onmessage = (e) => handle(JSON.parse(e.data));
}
function setConn(on) {
  $("#connDot").className = "dot " + (on ? "on" : "off");
  $("#connText").textContent = on ? "live" : "reconnecting…";
}

function handle(msg) {
  switch (msg.type) {
    case "hello": onHello(msg); break;
    case "snapshot": onSnapshot(msg); break;
    case "event": renderEvent(msg.event, true); break;
    case "event_narrated": onNarrated(msg.event); break;
    case "resolved": break; // visual clears on next snapshot
  }
}

// Hello/initial state lifecycle handlers
function onHello(msg) {
  state.llm = msg.llm_enabled;
  const badge = $("#llmBadge");
  if (badge) {
    if (msg.llm_enabled) {
      badge.className = "badge-status live";
      badge.textContent = `Claude Active (${msg.narration_model || 'Agent'})`;
    } else {
      badge.className = "badge-status offline";
      badge.textContent = "Deterministic Rules Engine";
    }
  }
  buildScenarios(msg.scenarios, msg.scenario);
  if (msg.snapshot) onSnapshot(msg.snapshot);

  // Seed feed + queue with any existing events/actions.
  feedEvents.clear();
  $("#feed").innerHTML = "";
  (msg.events || []).forEach((ev) => renderEvent(ev, false));
  if (!(msg.events || []).length) $("#feed").innerHTML = '<div class="empty">Watching the fleet… anomalies will appear here, narrated.</div>';
  actions.clear();
  (msg.actions || []).forEach((a) => actions.set(a.sensor_id, a));
  renderQueue();
}

function buildScenarios(list, active) {
  const wrap = $("#scnButtons");
  wrap.innerHTML = "";
  state.scenarioList = list || [];
  (list || []).forEach((s) => {
    const b = document.createElement("button");
    b.className = "scn-btn" + (s.name === active ? " active" : "");
    b.textContent = s.title;
    b.dataset.name = s.name;
    b.onclick = () => switchScenario(s.name);
    wrap.appendChild(b);
  });
  setScenarioDesc(active);
}
function setScenarioDesc(name) {
  const s = (state.scenarioList || []).find((x) => x.name === name);
  $("#scnDesc").textContent = s ? s.description : "";
}
async function switchScenario(name) {
  document.querySelectorAll(".scn-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.name === name));
  setScenarioDesc(name);
  state.scenario = name;
  try { await fetch("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: name }) }); }
  catch (e) { /* ignore */ }
}

// Snapshot rendering
function onSnapshot(msg) {
  state.scenario = msg.scenario;
  renderKpis(msg.kpis || {});
  (msg.sensors || []).forEach(updateCard);
}

function renderKpis(k) {
  const tiles = [
    { n: k.total ?? "–", l: "Sensors", cls: "" },
    { n: k.anomalous ?? 0, l: "Anomalous", cls: (k.anomalous > 0 ? "alert" : "good") },
    { n: k.malfunction ?? 0, l: "Sensor faults", cls: (k.malfunction > 0 ? "warn" : "good") },
    { n: Math.round((k.avg_confidence ?? 1) * 100) + "%", l: "Avg confidence", cls: "" },
    { n: k.open_actions ?? 0, l: "Open actions", cls: (k.open_actions > 0 ? "alert" : "good") },
  ];
  $("#kpis").innerHTML = tiles.map((t) =>
    `<div class="kpi ${t.cls}"><div class="n">${t.n}</div><div class="l">${t.l}</div></div>`).join("");
}

// Sensor card updating and sparkline drawing
function updateCard(s) {
  state.sensors[s.sensor_id] = s;
  let entry = cards.get(s.sensor_id);
  if (!entry) {
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <div class="card-head">
        <div><div class="card-id"></div><div class="card-loc"></div></div>
        <div class="card-val"><span class="v"></span><span class="u"></span></div>
      </div>
      <canvas class="spark"></canvas>
      <div class="card-foot"><span class="pill"></span><span class="ztag"></span></div>`;
    $("#sensorGrid").appendChild(el);
    entry = {
      el, canvas: el.querySelector(".spark"),
      id: el.querySelector(".card-id"), loc: el.querySelector(".card-loc"),
      v: el.querySelector(".v"), u: el.querySelector(".u"),
      pill: el.querySelector(".pill"), z: el.querySelector(".ztag"),
    };
    cards.set(s.sensor_id, entry);
  }
  const an = s.anomaly || {};
  const q = s.quality || {};
  entry.id.textContent = s.sensor_id;
  entry.loc.textContent = s.location || "";
  entry.v.textContent = fmt(s.value);
  entry.u.textContent = " " + (s.unit || "");
  entry.el.className = "card" + (an.is_anomaly ? " anom" : (q.status === "malfunction" ? " malf" : ""));

  // Status pill: anomaly severity takes precedence over data-quality status.
  if (an.is_anomaly) {
    const sev = sevWord(an.severity_hint);
    entry.pill.className = "pill " + sevClass(sev);
    entry.pill.textContent = sev + " anomaly";
  } else {
    entry.pill.className = "pill " + (q.status || "healthy");
    entry.pill.textContent = q.status || "healthy";
  }
  const methods = (an.methods || []).map((m) => m.split("-")[0]).join("·");
  entry.z.textContent = `z ${fmt(an.z_score, 1)}${methods ? " · " + methods : ""}`;
  drawSpark(entry.canvas, s);
}

function drawSpark(canvas, s) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.offsetWidth || 260;
  const h = canvas.clientHeight || 64;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const series = s.series || [];
  const vals = series.filter((v) => v !== null && v !== undefined && isFinite(v));
  if (vals.length < 2) return;
  const an = s.anomaly || {};
  let lo = Math.min(...vals), hi = Math.max(...vals);
  [an.iqr_low, an.iqr_high, an.baseline_mean].forEach((x) => {
    if (typeof x === "number" && isFinite(x)) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
  });
  if (hi - lo < 1e-6) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
  const n = series.length;
  const X = (i) => (i / (n - 1)) * (w - 4) + 2;
  const Y = (v) => h - ((v - lo) / (hi - lo)) * (h - 6) - 3;

  if (isFinite(an.iqr_low) && isFinite(an.iqr_high)) {
    const yH = Y(an.iqr_high), yL = Y(an.iqr_low);
    ctx.fillStyle = "rgba(56,189,248,0.07)";
    ctx.fillRect(2, yH, w - 4, Math.max(1, yL - yH));
  }
  if (isFinite(an.baseline_mean)) {
    ctx.strokeStyle = "rgba(148,163,184,0.40)";
    ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(2, Y(an.baseline_mean)); ctx.lineTo(w - 2, Y(an.baseline_mean)); ctx.stroke();
    ctx.setLineDash([]);
  }
  const color = an.is_anomaly ? "#f87171" : ((s.quality && s.quality.status !== "healthy") ? "#fbbf24" : "#38bdf8");
  ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.lineJoin = "round";
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < n; i++) {
    const v = series[i];
    if (v === null || v === undefined || !isFinite(v)) { started = false; continue; }
    const x = X(i), y = Y(v);
    if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
  }
  ctx.stroke();
  for (let i = n - 1; i >= 0; i--) {
    if (series[i] !== null && series[i] !== undefined && isFinite(series[i])) {
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(X(i), Y(series[i]), 3, 0, Math.PI * 2); ctx.fill();
      break;
    }
  }
}

// Anomaly feed updating and rendering
function currentSev(ev) { return ev.severity || sevWord(ev.severity_hint); }

function eventInner(ev) {
  const sev = currentSev(ev);
  const kindTag = ev.kind === "malfunction" ? "SENSOR FAULT" : "anomaly";
  let body;
  let src = "";
  if (ev.narration) {
    src = ev.used_llm
      ? '<span class="src ai">Claude</span>'
      : '<span class="src local">Rules</span>';
    const nr = ev.narration;
    body = `<div class="ev-summary">${escapeHtml(nr.summary)}</div>
      <div class="ev-detail"><b>Likely cause:</b> ${escapeHtml(nr.root_cause)}</div>
      <div class="ev-detail"><b>Action:</b> ${escapeHtml(nr.recommended_action)}</div>
      <div class="ev-detail" style="color:var(--faint)">${escapeHtml(nr.confidence_note)}</div>`;
  } else {
    body = `<div class="ev-summary">${escapeHtml(ev.sensor_type)} deviation on ${escapeHtml(ev.sensor_id)} (z ${fmt(ev.z_score, 1)}).</div>
      <div class="ev-pending"><span class="spinner"></span> Analyzing…</div>`;
  }
  return `<div class="ev-head">
      <span class="pill ${sevClass(sev)}">${sev}</span>
      <span class="sid">${escapeHtml(ev.sensor_id)}</span>
      <span style="color:var(--faint);font-size:11.5px">${escapeHtml(ev.location || "")} · ${kindTag}</span>
      ${src}<span class="time">${escapeHtml(ev.ts_iso || "")}</span>
    </div>${body}`;
}

function renderEvent(ev, prepend) {
  const feed = $("#feed");
  const empty = feed.querySelector(".empty");
  if (empty) empty.remove();
  let el = feedEvents.get(ev.id);
  if (!el) {
    el = document.createElement("div");
    feedEvents.set(ev.id, el);
    if (prepend && feed.firstChild) feed.insertBefore(el, feed.firstChild);
    else feed.appendChild(el);
  }
  el.className = "event " + sevClass(currentSev(ev));
  el.innerHTML = eventInner(ev);
  // Trim very long feeds.
  while (feed.children.length > 40) feed.removeChild(feed.lastChild);
}

function onNarrated(ev) {
  renderEvent(ev, false);
  if (ev.narration) {
    actions.set(ev.sensor_id, {
      sensor_id: ev.sensor_id, severity: ev.severity || "Low",
      action: ev.narration.recommended_action, status: "open",
    });
    renderQueue();
  }
}

function renderQueue() {
  const q = $("#queue");
  const items = [...actions.values()];
  if (!items.length) { q.innerHTML = '<div class="empty">No open actions.</div>'; return; }
  const order = { Critical: 0, Moderate: 1, Low: 2 };
  items.sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3));
  q.innerHTML = items.map((a) =>
    `<div class="qitem"><span class="pill ${sevClass(a.severity)}">${a.severity}</span>
      <span class="qtext"><span class="qsid">${escapeHtml(a.sensor_id)}</span> – ${escapeHtml(a.action)}</span></div>`).join("");
}

// Investigation modal and API actions
const modal = $("#modal");
$("#btnInvestigate").onclick = runInvestigation;
$("#modalClose").onclick = () => (modal.hidden = true);
modal.addEventListener("click", (e) => { if (e.target === modal) modal.hidden = true; });

async function runInvestigation() {
  modal.hidden = false;
  $("#modalSteps").innerHTML = "";
  $("#modalBody").innerHTML =
    `<div class="loading-row"><span class="spinner"></span> Investigating the fleet…</div>`;
  try {
    const res = await fetch("/api/investigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    const data = await res.json();
    state.lastReport = data;
    $("#modalSteps").innerHTML = (data.steps || []).map((s) => {
      const arg = s.input && Object.keys(s.input).length ? " " + escapeHtml(JSON.stringify(s.input)) : "";
      return `<span class="step"><b>${escapeHtml(s.tool)}</b>${arg}</span>`;
    }).join("") || '<span class="step">direct analysis</span>';
    $("#modalBody").innerHTML = mdToHtml(data.report_markdown);
    const badge = $("#modalEngine");
    if (badge) {
        badge.className = "badge-status " + (data.used_llm ? "live" : "offline");
        badge.textContent = data.used_llm ? `Claude (${data.model || 'Agent'})` : "Deterministic Mode";
    }
  } catch (e) {
    $("#modalBody").innerHTML = `<p style="color:var(--crit)">Investigation failed: ${escapeHtml(e.message)}</p>`;
  }
}

// Incident report download and compilation
$("#btnReport").onclick = () => window.open("/api/report.html", "_blank");
$("#btnDownloadReport").onclick = async () => {
  const r = state.lastReport || {};
  try {
    const res = await fetch("/api/report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_markdown: r.report_markdown || null, used_llm: !!r.used_llm, model: r.model || null }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "incident_report.html"; a.click();
    URL.revokeObjectURL(url);
  } catch (e) { alert("Report download failed: " + e.message); }
};

// Boot/Initialization
connect();
window.addEventListener("resize", () => {
  for (const s of Object.values(state.sensors)) {
    const entry = cards.get(s.sensor_id);
    if (entry) drawSpark(entry.canvas, s);
  }
});

// Tabs logic
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.hidden = true);
    btn.classList.add("active");
    $("#" + btn.dataset.target).hidden = false;
    // Trigger resize to redraw sparklines if needed
    window.dispatchEvent(new Event("resize"));
  });
});
