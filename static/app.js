"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (x, d = 2) => (x == null || isNaN(x)) ? "–" : Number(x).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 1, sign = true) => (x == null || isNaN(x)) ? "–" : (sign && x > 0 ? "+" : "") + (x * 100).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }) + "%";
const pts = (x, d = 1) => (x == null || isNaN(x)) ? "–" : (x > 0 ? "+" : "") + (x * 100).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }) + " punti";
const cls = (x) => x > 0 ? "pos" : x < 0 ? "neg" : "";
const sigKey = (s) => !s ? "NESSUN" : s.startsWith("COMPRA") ? "COMPRA" : s.startsWith("ACCUMULA") ? "ACCUMULA" : s.startsWith("ALLEGG") ? "VENDI" : "NESSUN";
const chip = (s) => `<span class="chip s-${sigKey(s)}">${esc(s || "non analizzato")}</span>`;
const big = (x) => x == null ? "–" : x >= 1e12 ? num(x / 1e12, 2) + " T" : x >= 1e9 ? num(x / 1e9, 1) + " Mld" : x >= 1e6 ? num(x / 1e6, 1) + " Mln" : num(x, 0);
const kv = (k, v) => `<div><span>${k}</span><b>${v}</b></div>`;
const ok = (b) => b ? `<span class="ok">✓</span>` : `<span class="ko">✗</span>`;
const stChip = (s) => {
  const k = s === "attivo" || s === "attiva" ? "COMPRA" : (s || "").startsWith("in raccolta") ? "ACCUMULA" : "NESSUN";
  return `<span class="chip s-${k}">${esc(s || "–")}</span>`;
};

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const js = await r.json().catch(() => ({ error: "Risposta non valida dal server" }));
  if (!r.ok) throw Object.assign(new Error(js.error || "Errore"), { data: js });
  return js;
}

/* ---------------- disclaimer ---------------- */
const DISCLAIMER = `
<p><b>Strumento di studio e analisi quantitativa a uso esclusivamente personale.</b></p>
<p>Le previsioni sono stime statistiche basate su dati storici e modelli matematici. I mercati
non sono prevedibili con certezza: le probabilità indicate possono essere sbagliate, anche di molto,
e i rendimenti passati non sono indicativi di quelli futuri. Anche quando il banco di prova dà esito
positivo, una precisione realistica è del 52-55%.</p>
<p>Nulla di quanto mostrato costituisce consulenza in materia di investimenti, raccomandazione
personalizzata, sollecitazione all'acquisto o alla vendita di strumenti finanziari, né ricerca
in materia di investimenti ai sensi della normativa MiFID II / TUF. I segnali non tengono conto
della situazione finanziaria, degli obiettivi e della tolleranza al rischio di nessuno.</p>
<p>I dati provengono da fonti gratuite (Yahoo Finance) e possono essere incompleti, in ritardo o
errati. I fondamentali possono non essere aggiornati. Verifica sempre su fonti ufficiali.</p>
<p>Ogni decisione d'investimento resta sotto la tua esclusiva responsabilità. Non usare questo
strumento per prendere decisioni per conto di clienti terzi.</p>`;

function initDisclaimer() {
  $("#discText").innerHTML = DISCLAIMER;
  $("#discFull").innerHTML = DISCLAIMER;
  let seen = false;
  try { seen = localStorage.getItem("oracolo_disc_v1") === "1"; } catch (e) {}
  if (!seen) $("#discModal").classList.remove("hidden");
  $("#discOk").onclick = () => {
    try { localStorage.setItem("oracolo_disc_v1", "1"); } catch (e) {}
    $("#discModal").classList.add("hidden");
  };
}

/* ---------------- tema e tab ---------------- */
function initTheme() {
  let t = null;
  try { t = localStorage.getItem("oracolo_theme"); } catch (e) {}
  if (t) document.documentElement.dataset.theme = t;
  $("#themeBtn").onclick = () => {
    const cur = document.documentElement.dataset.theme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const nx = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nx;
    try { localStorage.setItem("oracolo_theme", nx); } catch (e) {}
  };
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + name));
  document.querySelectorAll("nav.bottom button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  window.scrollTo(0, 0);
  if (name === "home") loadHome();
  if (name === "scan") loadSignals();
  if (name === "pf") loadPortfolio();
  if (name === "lab") loadLab();
  if (name === "method") loadAgentsDoc();
}

/* ---------------- MERCATI ---------------- */
let scanTimer = null;
async function loadHome() {
  const o = await api("/api/overview");
  $("#demoBanner").classList.toggle("hidden", !o.demo);
  const lab = o.lab || {};
  const lb = $("#labBanner");
  if (lab.stocks !== "attivo") {
    lb.classList.remove("hidden");
    lb.innerHTML = lab.stocks === "non addestrato"
      ? `<b>Il banco di prova non è ancora stato eseguito.</b> <span class="tiny">Finché i test non danno esito positivo nessun titolo riceve segnali. Apri il Laboratorio ›</span>`
      : `<b>Modello azioni spento dal Laboratorio.</b> <span class="tiny">I test fuori campione non sono stati superati: tutti i titoli mostrano NESSUN SEGNALE. È un esito onesto. Dettagli ›</span>`;
  } else lb.classList.add("hidden");
  $("#indices").innerHTML = o.indices.map((i) => `
    <div class="tile" data-t="${esc(i.ticker)}">
      <div class="t-name">${esc(i.name)}</div>
      ${i.signal ? `
        <div class="t-big ${cls(i.exp_return)}">${pct(i.exp_return)}</div>
        <div class="t-small">rialzo ${pct(i.p_up, 0, false)} · rif. ${pct(i.ref ?? i.base_rate, 0, false)}</div>
        <div style="margin-top:6px">${chip(i.signal)}</div>` :
        `<div class="t-small" style="margin-top:8px">Tocca per analizzare</div>`}
    </div>`).join("");
  const row = (s) => `
    <div class="item" data-t="${esc(s.ticker)}">
      <div class="l"><b>${esc(s.name)}</b><span>${esc(s.ticker)} · ${esc(s.market)}</span></div>
      <div class="r">${chip(s.signal)}<div class="tiny ${cls(s.exp_return)}">${pct(s.exp_return)} · rialzo ${pct(s.p_up, 0, false)}</div></div>
    </div>`;
  $("#topBuy").innerHTML = o.top_buy.length ? o.top_buy.map(row).join("") : `<div class="muted tiny">Nessun segnale d'acquisto nell'ultima scansione${o.n_signals ? "" : " (avvia la prima scansione)"}.</div>`;
  $("#topSell").innerHTML = o.top_sell.length ? o.top_sell.map(row).join("") : `<div class="muted tiny">Nessun segnale di vendita.</div>`;
  renderScan(o.scan, o.last_scan, o.n_signals, o.n_universe);
  if (o.scan.running && !scanTimer) pollScan();
}

function renderScan(st, last, n, tot) {
  const p = $("#scanProg");
  if (st.running) {
    p.classList.remove("hidden");
    p.firstElementChild.style.width = (100 * st.done / Math.max(st.total, 1)) + "%";
    $("#scanInfo").textContent = `Scansione in corso: ${st.done}/${st.total} — ${st.current || ""}`;
    $("#scanBtn").disabled = true;
  } else {
    p.classList.add("hidden");
    $("#scanBtn").disabled = false;
    const when = last ? new Date(last.ts * 1000).toLocaleString("it-IT") : "mai";
    $("#scanInfo").textContent = `Ultima scansione: ${when}${last ? " (" + last.detail + ")" : ""}. Titoli analizzati: ${n ?? "–"} su ${tot ?? "–"}.`;
  }
}

function pollScan() {
  scanTimer = setInterval(async () => {
    const s = await api("/api/scan/status");
    renderScan(s.state, s.last);
    if (!s.state.running) { clearInterval(scanTimer); scanTimer = null; loadHome(); }
  }, 3000);
}

/* ---------------- ANALIZZA ---------------- */
async function analyze(t) {
  showTab("analyze");
  $("#q").value = t;
  $("#suggest").innerHTML = "";
  $("#result").innerHTML = `<div class="loading"><span class="spin"></span>Analizzo ${esc(t)}…<br><span class="tiny">Misure di oggi, modello panel, opzioni e 10.000 simulazioni</span></div>`;
  try {
    const o = await api("/api/analyze?t=" + encodeURIComponent(t));
    renderResult(o);
  } catch (e) {
    const sug = e.data && e.data.suggestions || [];
    $("#result").innerHTML = `<div class="card">${esc(e.message)}${sug.length ? "<p>Forse cercavi:</p>" : ""}</div>`;
    $("#suggest").innerHTML = sug.map((s) => `<div class="item" data-t="${esc(s.symbol)}"><div class="l"><b>${esc(s.name || s.symbol)}</b><span>${esc(s.symbol)} · ${esc(s.exchange || "")}</span></div></div>`).join("");
  }
}

function fanChart(o) {
  const H = o.history, h = o.horizon_days, e = o.ensemble;
  const n = Math.min(H.close.length, 130);
  const hist = H.close.slice(-n);
  const p0 = hist[hist.length - 1];
  const steps = 30;
  const cone = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps, m = e.mu * f, s = e.sigma * Math.sqrt(f);
    cone.push({ x: n - 1 + f * h, q05: p0 * Math.exp(m - 1.645 * s), q25: p0 * Math.exp(m - 0.674 * s),
      q50: p0 * Math.exp(m), q75: p0 * Math.exp(m + 0.674 * s), q95: p0 * Math.exp(m + 1.645 * s) });
  }
  const W = 640, Ht = 260, pl = 8, pr = 64, pt = 10, pb = 22;
  const all = hist.concat(cone.map((c) => c.q05), cone.map((c) => c.q95));
  const lo = Math.min(...all), hi = Math.max(...all);
  const X = (x) => pl + (x / (n - 1 + h)) * (W - pl - pr);
  const Y = (y) => pt + (1 - (y - lo) / (hi - lo)) * (Ht - pt - pb);
  const band = (a, b) => cone.map((c) => `${X(c.x)},${Y(c[a])}`).join(" ") + " " + cone.slice().reverse().map((c) => `${X(c.x)},${Y(c[b])}`).join(" ");
  const line = hist.map((v, i) => `${X(i)},${Y(v)}`).join(" ");
  const med = cone.map((c) => `${X(c.x)},${Y(c.q50)}`).join(" ");
  const last = cone[cone.length - 1];
  const lab = (v, txt) => `<text x="${W - pr + 6}" y="${Y(v) + 4}" font-size="11" fill="currentColor" opacity=".75">${txt}</text>`;
  const pl_ = o.plan;
  const lvl = [];
  if (pl_.use) {
    const P = pl_.use === "market" ? pl_.plan_market : pl_.plan_limit;
    [["entry", "var(--accent)"], ["stop", "var(--sell)"], ["target", "var(--buy)"]].forEach(([k, c]) => {
      if (P[k] > lo && P[k] < hi) lvl.push(`<line x1="${X(n - 1)}" x2="${W - pr}" y1="${Y(P[k])}" y2="${Y(P[k])}" stroke="${c}" stroke-dasharray="4 3" stroke-width="1.2"/>`);
    });
  }
  return `<svg class="chart" viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Previsione a ventaglio">
    <polygon points="${band("q95", "q05")}" fill="var(--fan1)"/>
    <polygon points="${band("q75", "q25")}" fill="var(--fan2)"/>
    <polyline points="${line}" fill="none" stroke="var(--line)" stroke-width="1.6"/>
    <polyline points="${med}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="5 4"/>
    ${lvl.join("")}
    <line x1="${X(n - 1)}" x2="${X(n - 1)}" y1="${pt}" y2="${Ht - pb}" stroke="currentColor" opacity=".25"/>
    ${lab(last.q95, num(last.q95, 0))}${lab(last.q50, num(last.q50, 0))}${lab(last.q05, num(last.q05, 0))}
    <text x="${X(0)}" y="${Ht - 6}" font-size="11" fill="currentColor" opacity=".6">${esc(H.dates[H.dates.length - n])}</text>
    <text x="${X(n - 1)}" y="${Ht - 6}" font-size="11" fill="currentColor" opacity=".6" text-anchor="middle">oggi</text>
    <text x="${W - pr}" y="${Ht - 6}" font-size="11" fill="currentColor" opacity=".6" text-anchor="end">+${esc(o.horizon_label)}</text>
  </svg>
  <div class="legend"><span><i style="background:var(--fan2)"></i>50% degli scenari</span><span><i style="background:var(--fan1)"></i>90% degli scenari</span>
  <span><i style="background:var(--accent)"></i>mediana</span>${pl_.use ? '<span><i style="background:var(--buy)"></i>obiettivo</span><span><i style="background:var(--sell)"></i>stop</span>' : ""}</div>`;
}

function rankBar(r) {
  if (r == null) return "";
  const w = Math.round((r + 0.5) * 100);
  return `<div class="bar mini"><div style="width:${w}%"></div><span class="mark" style="left:50%"></span></div>`;
}

function pricedBlock(o) {
  const mk = o.priced || {}, e = o.ensemble, p = o.plan, pn = o.panel || {};
  const rd = mk.rdcf || null, vx = mk.vix || null;
  const days = mk.calendar_days || (o.is_index ? 91 : 45);
  const market = `
    <div class="pblock"><h4>Cosa prezza il mercato</h4>
      <div class="kv">
        ${kv("Probabilità di rialzo implicita", pct(mk.p_market, 0, false))}
        ${kv(`Movimento atteso in ${days} giorni`, mk.move != null ? "±" + pct(mk.move, 1, false) : "–")}
        ${kv("Volatilità implicita", mk.iv != null ? pct(mk.iv, 0, false) + " annua" : "non disponibile")}
        ${kv("Volatilità prevista da noi", pct(mk.sigma_ours_ann, 0, false) + " annua")}
        ${rd ? kv("Crescita implicita nel prezzo", rd.g_implied != null ? pct(rd.g_implied, 1, false) + " annua (5 anni)" : "n.d.") : ""}
        ${rd ? kv("Crescita di consenso", rd.g_consensus != null ? pct(rd.g_consensus, 1) : "n.d.") : ""}
        ${rd && rd.base_rate != null ? kv("Aziende che l'hanno raggiunta", "circa " + pct(rd.base_rate, 0, false)) : ""}
        ${vx ? kv("VIX", `${num(vx.level, 1)} (${vx.pct != null ? "più alto del " + pct(vx.pct, 0, false) + " della storia" : ""})`) : ""}
        ${vx ? kv("Regime", esc(vx.regime)) : ""}
      </div>
      <p class="tiny muted">Fonte: ${esc(mk.source || "–")}.${rd && rd.g_implied == null && rd.why_missing ? " Reverse DCF non calcolabile: " + esc(rd.why_missing) + "." : ""}
      ${rd && rd.base_rate != null ? " Percentuale di aziende: " + esc(rd.note) : ""}</p>
    </div>`;
  const rows = o.not_priced || [];
  const act = rows.filter((r) => r.status === "attiva");
  const off = rows.filter((r) => r.status !== "attiva");
  const rowHtml = (r) => `
    <div class="sigrow">
      <div class="sr-h"><b>${esc(r.label)}</b><span class="${cls(r.contrib)}">${r.status === "attiva" ? pts(r.contrib, 1) : "0 punti"}</span></div>
      <div class="tiny">${esc(r.text)}${r.rank != null ? ` · rango ${r.rank >= 0 ? "+" : ""}${num(r.rank, 2)}` : ""}</div>
      ${rankBar(r.rank)}
      <div class="tiny muted">${stChip(r.status)} ${esc(r.tested)}${r.status !== "attiva" && r.reasons && r.reasons.length ? " — " + esc(r.reasons[0]) : ""}</div>
    </div>`;
  const cb = o.class_b || [];
  const notYet = `
    <div class="pblock"><h4>Cosa non è ancora nel prezzo</h4>
      ${act.length ? act.map(rowHtml).join("") : `<p class="tiny muted">${pn.state === "non addestrato" ? "Il Laboratorio non ha ancora eseguito i test." : "Nessun segnale ha superato i test: oggi non abbiamo informazione che il prezzo non contenga già."}</p>`}
      ${off.length ? `<details><summary>Segnali testati e spenti (${off.length})</summary>${off.map(rowHtml).join("")}</details>` : ""}
      ${cb.length ? `<details><summary>In raccolta, classe B (${cb.length}, peso 0)</summary>${cb.map((r) => `
        <div class="sigrow"><div class="sr-h"><b>${esc(r.label)}</b><span>0 punti</span></div>
        <div class="tiny muted">${stChip(r.status)} servono ${r.need} periodi indipendenti (~18 mesi) prima di poterla testare</div></div>`).join("")}</details>` : ""}
    </div>`;
  const ci = e.ci;
  const we = `
    <div class="pblock"><h4>Noi stimiamo</h4>
      <div class="bignum ${Math.abs(p.edge) < 0.005 ? "" : cls(p.edge)}">${pct(e.p_up, 0, false)}</div>
      <div class="tiny muted">${ci ? `intervallo al 95%: ${pct(ci[0], 0, false)}–${pct(ci[1], 0, false)} · ` : ""}frequenza storica dei rialzi ${pct(o.base_rate, 0, false)} · fonte: ${esc(e.source)}</div>
    </div>`;
  const b = pn.bin;
  const diff = `
    <div class="pblock"><h4>Differenza</h4>
      <div class="kv">
        ${kv("Noi − riferimento", `<span class="${cls(p.edge)}">${pts(p.edge, 1)}</span>`)}
        ${kv("Riferimento", pct(p.ref, 0, false) + (mk.p_market != null && p.ref > mk.p_market + 1e-9 ? " (frequenza storica)" : " (mercato)"))}
        ${b ? kv("Affidabilità storica", `${pct(b.freq, 0, false)} su ${num(b.n, 0)} casi`) : ""}
        ${b ? kv("Periodi indipendenti", "circa " + num(b.n_indep, 0)) : ""}
      </div>
      <ul class="checks">${(p.checks || []).map((c) => `<li>${ok(c.ok)} ${esc(c.name)}</li>`).join("")}</ul>
    </div>`;
  return `<div class="card priced"><h3>Cosa c'è nel prezzo, cosa non ancora</h3>
    <p class="story">${esc(o.story)}</p>${market}${notYet}${we}${diff}</div>`;
}

function renderResult(o) {
  const e = o.ensemble, p = o.plan, m = o.metrics, f = o.fundamentals || {};
  const k = sigKey(p.signal);
  const planRow = (lab, key, fmt) => `<tr><td>${lab}</td><td class="${p.use === "market" ? "hl" : ""}">${fmt(p.plan_market[key])}</td><td class="${p.use === "limit" ? "hl" : ""}">${fmt(p.plan_limit[key])}</td></tr>`;
  const pc = (x) => pct(x, 0, false);
  const agentCard = (a) => `
    <div class="agent">
      <div class="ah"><b>${esc(a.name)}</b><span class="${cls(a.exp_return)}" style="font-weight:700">${pct(a.exp_return)}</span></div>
      <div class="fam">${esc(a.family)} · ${esc((a.extra && a.extra.status) || "")}</div>
      <div class="bar"><div style="width:${(a.p_up * 100).toFixed(0)}%"></div><span class="mark" style="left:50%"></span></div>
      <div class="nums"><span>rialzo ${pc(a.p_up)}</span><span>peso ${num(a.weight, 0)}</span></div>
      <p>${esc(a.note)}</p>
    </div>`;
  const baseAg = o.agents.find((a) => a.family === "base");
  const infoAg = o.agents.filter((a) => a.family !== "base");
  const fundBlock = o.is_index ? "" : `
    <div class="card"><h3>Scheda del titolo <span class="sub">bilanci: solo informativi</span></h3>
      ${f.summary ? `<p class="tiny muted">${esc(f.summary)}</p>` : ""}
      <div class="kv">
        ${kv("Settore", esc(f.sector || "–"))}${kv("Capitalizzazione", big(f.market_cap))}
        ${kv("P/E (ultimi 12m)", num(f.pe_trailing, 1))}${kv("P/E atteso", num(f.pe_forward, 1))}
        ${kv("Prezzo / valore contabile", num(f.pb, 1))}${kv("EV / EBITDA", num(f.ev_ebitda, 1))}
        ${kv("Dividendo", pct(f.dividend_yield, 1, false))}${kv("ROE", pct(f.roe, 0, false))}
        ${kv("Margine netto", pct(f.profit_margin, 0, false))}${kv("Debito / equity", num(f.debt_to_equity, 0) + (f.debt_to_equity != null ? "%" : ""))}
        ${kv("Crescita utili", pct(f.earnings_growth, 0))}${kv("Crescita ricavi", pct(f.revenue_growth, 0))}
        ${kv("Obiettivo analisti (solo dato)", num(f.target_mean) + (f.analyst_count ? ` (${num(f.analyst_count, 0)})` : ""))}
        ${kv("Beta (252 sedute)", num(o.beta, 2))}
      </div>
      ${!f.sector && !f.pe_trailing ? `<p class="tiny muted">Fondamentali non disponibili (installa yfinance sul server).</p>` : ""}
    </div>`;
  const val = (o.agents.find((a) => a.family === "fondamentale") || {}).extra;
  $("#result").innerHTML = `
    <div class="card">
      <div class="hero">
        <div><div class="muted tiny">${esc(o.ticker)} · ${esc(o.exchange || "")} · dati al ${esc(o.asof)}</div>
          <div style="font-size:18px;font-weight:700">${esc(o.name)}</div>
          <div class="price">${num(p.price)} <span class="tiny muted">${esc(o.currency || "")}</span></div></div>
        <div class="tiny" style="text-align:right">oggi <b class="${cls(m.chg_1d)}">${pct(m.chg_1d)}</b><br>1 mese <b class="${cls(m.chg_1m)}">${pct(m.chg_1m)}</b><br>1 anno <b class="${cls(m.chg_1y)}">${pct(m.chg_1y)}</b></div>
      </div>
    </div>

    <div class="card signal-card ${k}">
      <div class="row-between"><div class="big">${esc(p.signal)}</div><div class="tiny muted">forza ${num(p.strength, 0)}/100</div></div>
      <p style="margin:6px 0 10px">${esc(p.why)}</p>
      <div class="kv">
        ${kv("Noi stimiamo (rialzo)", `<span class="${Math.abs(p.edge) < 0.005 ? "" : cls(p.edge)}">${pc(e.p_up)}</span>`)}
        ${kv("Riferimento", pc(p.ref))}
        ${kv("Differenza", `<span class="${cls(p.edge)}">${pts(p.edge, 1)}</span>`)}
        ${kv("Rendimento atteso", `<span class="${cls(e.exp_return)}">${pct(e.exp_return)}</span>`)}
        ${kv("Orizzonte", esc(o.horizon_label))}
        ${kv("Peso suggerito", p.position_size ? pct(p.position_size, 1, false) + " del portafoglio" : "–")}
      </div>
    </div>

    ${forkBlock(o)}

    ${pricedBlock(o)}

    <div class="card"><h3>Previsione a ventaglio</h3>${fanChart(o)}</div>

    <div class="card summary"><h3>In parole semplici</h3>${o.summary.map((s) => `<p>${esc(s)}</p>`).join("")}</div>

    <div class="card"><h3>Piano operativo</h3>
      <table class="plan">
        <tr><th></th><th>A mercato</th><th>Ordine limite</th></tr>
        ${planRow("Ingresso", "entry", num)}${planRow("Stop", "stop", num)}${planRow("Obiettivo", "target", num)}
        ${planRow("Guadagno / rischio", "reward_risk", (x) => num(x, 1))}
        ${planRow("Prima l'obiettivo", "p_target_first", pc)}${planRow("Prima lo stop", "p_stop_first", pc)}
        ${planRow("Valore atteso", "ev", (x) => pct(x))}
        ${planRow("Al netto dei costi", "ev_net", (x) => pct(x))}
      </table>
      <p class="tiny muted">Limite: ${esc(p.limit_name)}. Stop a 2,5 ATR (ATR = ${num(p.atr)}, ${pct(p.atr_pct, 1, false)} al giorno). Obiettivo al 75° percentile. Probabilità da 6.000 simulazioni. Costi andata e ritorno ${pct(p.cost_round_trip, 2, false)}.</p>
      <details><summary>Livelli chiave</summary><div class="kv" style="margin-top:8px">
        ${Object.entries(p.supports).map(([k2, v]) => kv(esc(k2), num(v))).join("")}
        ${val && val.fair_value ? kv("Valore equo CFA (informativo)", num(val.fair_value)) : ""}
        ${kv("Massimo 52 sett.", num(m.high_52w))}${kv("Minimo 52 sett.", num(m.low_52w))}
        ${kv("Volatilità annua", pct(m.vol_annual, 0, false))}${kv("Max ribasso 1 anno", pct(m.max_drawdown_1y, 0))}
      </div></details>
    </div>

    ${baseAg ? `<div class="card"><h3>Modello di base</h3><div class="list">${agentCard(baseAg)}</div></div>` : ""}
    <div class="card"><details><summary>Agenti informativi (${infoAg.length}, peso 0, non validati)</summary>
      <p class="tiny muted">Restano visibili come informazione. Non entrano nella previsione perché il banco di prova panel non li ha validati.</p>
      <div class="list">${infoAg.map(agentCard).join("")}</div>
      ${o.errors.length ? `<p class="tiny muted">Agenti non riusciti: ${o.errors.map((x) => esc(x.agent)).join(", ")}</p>` : ""}
    </details></div>
    ${fundBlock}
    <button class="secondary" id="addPf">+ Aggiungi ${esc(o.ticker)} al portafoglio</button>
    <p class="tiny muted">Tasso privo di rischio usato ${pct(o.rf, 2, false)}; rendimento di fondo CAPM ${pct(o.prior_annual, 1, false)} annuo. Calcolo in ${num(o.elapsed, 1)} s.
    Strumento di studio personale: non è una raccomandazione d'investimento.</p>`;
  $("#addPf").onclick = () => {
    showTab("pf");
    const fm = $("#pfForm");
    fm.ticker.value = o.ticker; fm.avg_price.value = p.price.toFixed(2); fm.qty.focus();
  };
}

/* ---------------- SCANNER ---------------- */
let curMkt = "";
async function loadSignals() {
  const u = await api("/api/universe");
  $("#mkts").innerHTML = ["", ...Object.keys(u)].map((m) => `<button data-m="${esc(m)}" class="${m === curMkt ? "on" : ""}">${m || "Tutti"}</button>`).join("") +
    `<button id="scanThis">▶ Scansiona ${curMkt || "tutto"}</button>`;
  const rows = await api("/api/signals" + (curMkt ? "?market=" + encodeURIComponent(curMkt) : ""));
  $("#sigList").innerHTML = rows.length ? rows.map((s) => `
    <div class="item" data-t="${esc(s.ticker)}">
      <div class="l"><b>${esc(s.name)}</b><span>${esc(s.ticker)} · ${esc(s.horizon)} · ${pct(s.p_up, 0, false)} vs rif. ${pct(s.ref ?? s.base_rate, 0, false)}</span></div>
      <div class="r">${chip(s.signal)}<div class="tiny ${cls(s.exp_return)}">${pct(s.exp_return)}</div></div>
    </div>`).join("") : `<div class="card muted">Nessun titolo analizzato in questo mercato. Premi "Scansiona".</div>`;
}

/* ---------------- PORTAFOGLIO ---------------- */
async function loadPortfolio() {
  $("#pfList").innerHTML = `<div class="loading"><span class="spin"></span>Carico i prezzi…</div>`;
  const o = await api("/api/portfolio");
  $("#pfSummary").innerHTML = `
    <div class="tile"><div class="t-small">Valore</div><div class="t-big">€ ${num(o.total_eur, 0)}</div></div>
    <div class="tile"><div class="t-small">Utile / perdita</div><div class="t-big ${cls(o.pnl_eur)}">€ ${num(o.pnl_eur, 0)}</div><div class="t-small">${o.cost_eur ? pct(o.pnl_eur / o.cost_eur) : ""}</div></div>`;
  const r = o.risk;
  $("#pfRisk").innerHTML = r ? `<h3>Rischio complessivo</h3><div class="kv">
      ${kv("Volatilità annua", pct(r.vol_annual, 1, false))}
      ${kv("Perdita max 1 mese (95%)", "€ " + num(r.var95_1m_eur, 0))}
      ${kv("Posizioni effettive", num(r.effective_positions, 1))}
      ${kv("Indice di diversificazione", num(r.diversification_ratio, 2))}</div>
      ${r.high_corr_pairs.length ? `<p class="tiny">Titoli molto correlati (si muovono insieme): ${r.high_corr_pairs.map((x) => `${esc(x.a)}–${esc(x.b)} (${num(x.corr, 2)})`).join(", ")}</p>` : ""}
      <p class="tiny muted">${esc(r.note)} VaR parametrico: in 19 mesi su 20 la perdita non dovrebbe superare questo importo.</p>` :
    `<span class="muted tiny">Aggiungi almeno un titolo per vedere il rischio di portafoglio.</span>`;
  $("#pfList").innerHTML = o.items.length ? o.items.map((i) => i.error ? `<div class="item"><div class="l"><b>${esc(i.ticker)}</b><span class="neg">${esc(i.error)}</span></div><button class="danger" data-del="${i.id}">Elimina</button></div>` : `
    <div class="card">
      <div class="row-between"><div class="l" style="min-width:0"><b>${esc(i.name)}</b> <span class="tiny muted">${esc(i.ticker)}</span></div>${chip(i.signal)}</div>
      <div class="kv" style="margin-top:8px">
        ${kv("Quantità", num(i.qty, i.qty % 1 ? 2 : 0))}${kv("Carico → oggi", `${num(i.avg_price)} → ${num(i.price)} ${esc(i.currency)}`)}
        ${kv("Valore", "€ " + num(i.value_eur, 0))}${kv("Utile / perdita", `<span class="${cls(i.pnl_eur)}">€ ${num(i.pnl_eur, 0)} (${pct(i.pnl_pct)})</span>`)}
        ${kv("Peso", pct(i.weight, 1, false))}${kv("Previsione", i.exp_return != null ? `<span class="${cls(i.exp_return)}">${pct(i.exp_return)}</span> · rialzo ${pct(i.p_up, 0, false)}` : "–")}
      </div>
      <p class="tiny" style="margin:8px 0 0">${esc(i.advice)}${i.signal && !i.signal_fresh ? " (segnale vecchio: aggiorna)" : ""}</p>
      ${i.alerts.map((a) => `<div class="alert">⚠ ${esc(a)}</div>`).join("")}
      <div class="row-between" style="margin-top:8px"><button data-t="${esc(i.ticker)}">Analizza</button><button class="danger" data-del="${i.id}">Elimina</button></div>
    </div>`).join("") : `<div class="card muted">Nessun titolo in portafoglio.</div>`;
}

/* ---------------- LABORATORIO ---------------- */
let labPanel = "stocks", labTimer = null, labData = null;

function reliabilitySvg(bins) {
  if (!bins || !bins.length) return `<p class="tiny muted">Dati insufficienti.</p>`;
  const vals = bins.flatMap((b) => [b.p_mean, b.wilson_lo, b.wilson_hi]);
  let lo = Math.max(0, Math.min(...vals) - 0.02), hi = Math.min(1, Math.max(...vals) + 0.02);
  const W = 320, H = 240, L = 40, R = 10, T = 10, B = 34;
  const X = (x) => L + (x - lo) / (hi - lo) * (W - L - R);
  const Y = (y) => T + (1 - (y - lo) / (hi - lo)) * (H - T - B);
  const nmax = Math.max(...bins.map((b) => b.n));
  const ticks = [];
  const stp = (hi - lo) > 0.3 ? 0.1 : 0.05;
  for (let t = Math.ceil(lo / stp) * stp; t <= hi + 1e-9; t += stp) ticks.push(t);
  return `<svg class="chart rel" viewBox="0 0 ${W} ${H}" role="img" aria-label="Diagramma di affidabilità">
    ${ticks.map((t) => `<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}" stroke="var(--border)"/><line x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--border)"/>
      <text x="${X(t)}" y="${H - B + 14}" font-size="10" fill="currentColor" opacity=".7" text-anchor="middle">${Math.round(t * 100)}%</text>
      <text x="${L - 4}" y="${Y(t) + 3}" font-size="10" fill="currentColor" opacity=".7" text-anchor="end">${Math.round(t * 100)}%</text>`).join("")}
    <line x1="${X(lo)}" y1="${Y(lo)}" x2="${X(hi)}" y2="${Y(hi)}" stroke="var(--muted)" stroke-dasharray="4 3"/>
    ${bins.map((b) => `<line x1="${X(b.p_mean)}" x2="${X(b.p_mean)}" y1="${Y(b.wilson_lo)}" y2="${Y(b.wilson_hi)}" stroke="var(--accent)" stroke-width="1.5" opacity=".55"/>
      <circle cx="${X(b.p_mean)}" cy="${Y(b.freq)}" r="${3 + 4 * Math.sqrt(b.n / nmax)}" fill="var(--accent)"/>`).join("")}
    <text x="${(L + W - R) / 2}" y="${H - 4}" font-size="11" fill="currentColor" opacity=".8" text-anchor="middle">probabilità prevista</text>
    <text x="12" y="${(T + H - B) / 2}" font-size="11" fill="currentColor" opacity=".8" text-anchor="middle" transform="rotate(-90 12 ${(T + H - B) / 2})">frequenza osservata</text>
  </svg>
  <div class="legend"><span><i style="background:var(--accent)"></i>classe di previsioni (area = numerosità)</span><span><i style="background:var(--muted)"></i>calibrazione perfetta</span></div>`;
}

function yearBars(rows) {
  if (!rows || !rows.length) return `<p class="tiny muted">Dati insufficienti.</p>`;
  const W = 320, H = 150, L = 34, R = 6, T = 8, B = 22;
  const m = Math.max(0.05, ...rows.map((r) => Math.abs(r.ic)));
  const bw = (W - L - R) / rows.length;
  const Y = (v) => T + (1 - (v + m) / (2 * m)) * (H - T - B);
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="IC per anno">
    <line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" stroke="currentColor" opacity=".4"/>
    <text x="${L - 4}" y="${Y(m) + 8}" font-size="10" fill="currentColor" opacity=".7" text-anchor="end">${num(m, 2)}</text>
    <text x="${L - 4}" y="${Y(-m)}" font-size="10" fill="currentColor" opacity=".7" text-anchor="end">${num(-m, 2)}</text>
    ${rows.map((r, i) => `<rect x="${L + i * bw + 1.5}" width="${Math.max(bw - 3, 1)}" y="${Math.min(Y(r.ic), Y(0))}" height="${Math.max(Math.abs(Y(r.ic) - Y(0)), 1)}" fill="${r.ic >= 0 ? "var(--buy)" : "var(--sell)"}" rx="2"/>
      ${rows.length <= 14 || i % 2 === 0 ? `<text x="${L + i * bw + bw / 2}" y="${H - 6}" font-size="10" fill="currentColor" opacity=".7" text-anchor="middle">'${String(r.year).slice(2)}</text>` : ""}`).join("")}
  </svg>`;
}

function tile(label, value, sub) {
  return `<div class="tile static"><div class="t-small">${label}</div><div class="t-big">${value}</div>${sub ? `<div class="t-small">${sub}</div>` : ""}</div>`;
}

function renderLab(st) {
  labData = st;
  $("#labChips").innerHTML = [["stocks", "Azioni (31 sedute)"], ["index", "Indici (3 mesi)"]].map(([k, l]) => `<button data-lab="${k}" class="${k === labPanel ? "on" : ""}">${l}</button>`).join("");
  renderLabRun(st.state);
  const rep = st.report;
  if (!rep || !rep[labPanel]) {
    $("#labBody").innerHTML = `<div class="card"><h3>Nessun test ancora eseguito</h3><p>Il banco di prova non ha ancora girato. Finché non dà esito positivo nessun titolo riceve segnali. Premi <b>Rilancia i test</b>.</p></div>`;
    return;
  }
  const R = rep[labPanel], d = R.dev || {}, s = R.sample || {}, ho = R.holdout || {}, sp = R.spread;
  const on = R.state === "attivo";
  const when = rep.ts ? new Date(rep.ts * 1000).toLocaleString("it-IT") : "–";
  const crit = (R.criterion || []).map((c) => `<li>${ok(c.ok)} ${esc(c.name)}${c.value != null ? ` <span class="muted">(${c.of != null ? c.value + " su " + c.of : num(c.value, 3)}${c.t != null ? ", t " + num(c.t, 1) : ""})</span>` : ""}</li>`).join("");
  const feats = (R.features || []).map((f) => `<tr>
      <td><b>${esc(f.label)}</b><div class="tiny muted">${esc(f.ref || "")}${f.lit ? "" : " · soglia t ≥ 3"}</div>
        ${f.status !== "attiva" && f.reasons && f.reasons.length ? `<div class="tiny muted">${esc(f.reasons[0])}</div>` : ""}</td>
      <td class="${cls(f.ic)}">${num(f.ic, 3)}</td><td>${num(f.t, 1)}</td><td>${stChip(f.status)}</td></tr>`).join("");
  const cb = ((rep.class_b || {}).fields || []).map((f) => `<tr><td>${esc(f.label)}</td><td>${f.periods}/${f.need}</td><td>${stChip(f.status)}</td></tr>`).join("");
  const bench = (R.benchmarks || []).map((b) => `<tr><td>${esc(b.name)}<div class="tiny muted">${esc(b.target)}</div></td><td>${num(b.brier, 4)}</td><td>${num(b.model, 4)}</td><td>${ok(b.beaten)}</td></tr>`).join("");
  const grp = (rows) => (rows || []).map((g) => `<tr><td>${esc(g.group)}</td><td class="${cls(g.ic)}">${num(g.ic, 3)}</td><td>${num(g.t, 1)}</td><td>${num(g.n_indep, 0)}</td></tr>`).join("");
  const ch = R.challenger;
  const dsr = sp && sp.dsr;
  const cal = Object.entries(R.calibration || {}).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ");
  $("#labBody").innerHTML = `
    <div class="card signal-card ${on ? "COMPRA" : "NESSUN"}">
      <div class="row-between"><div class="big">${on ? "MODELLO ATTIVO" : "MODELLO SPENTO"}</div><div class="tiny muted">test del ${esc(when)}</div></div>
      <p style="margin:6px 0">${on ? "I test fuori campione sono superati: le previsioni del modello entrano nei segnali." :
        "I test fuori campione non sono superati: tutti i titoli mostrano NESSUN SEGNALE. È un esito accettabile e onesto: meglio nessun segnale che un segnale falso."}</p>
      ${!on && R.reasons && R.reasons.length ? `<p class="tiny"><b>Perché:</b> ${R.reasons.map(esc).join("; ")}.</p>` : ""}
      <p class="tiny muted">${esc(R.final_model || R.model)}. Una precisione realistica, quando il modello è attivo, è del 52-55%.${rep.demo ? ` DEMO: dati sintetici${rep.demo_signal ? ` con un segnale inserito (IC ${num(rep.demo_signal.ic, 2)} sulla sorpresa utili)` : ""}.` : ""}</p>
    </div>
    <div class="grid lab-tiles">
      ${tile("Campione effettivo", num(s.n_indep, 0) + " periodi", `indipendenti · ${num(s.n_obs, 0)} osservazioni · ${num(s.years, 1)} anni`)}
      ${tile("IC medio (rango)", `<span class="${cls(d.ic)}">${num(d.ic, 3)}</span>`, `t di Newey-West ${num(d.ic_t, 1)}`)}
      ${tile("Brier Skill Score", `<span class="${cls(d.bss)}">${pct(d.bss, 2)}</span>`, `contro la frequenza storica · 95%: ${pct(d.bss_lo, 2)} / ${pct(d.bss_hi, 2)}`)}
      ${tile("Errore di calibrazione", num((d.ece || 0) * 100, 1) + " punti", "ECE su 10 classi (soglia 3)")}
      ${sp ? tile("Spread 20% alto − basso", `<span class="${cls(sp.mean_net)}">${pct(sp.mean_net, 2)}</span>`, `netto costi per periodo di ${sp.period_days} sedute · ${pct(sp.ann_net, 1)} annuo · rotazione ${pct(sp.turnover, 0, false)}`) : ""}
      ${dsr ? tile("Deflated Sharpe", pct(dsr.dsr, 0, false), `probabilità che lo Sharpe sia reale dopo ${dsr.n_trials} configurazioni provate`) : ""}
    </div>
    <div class="card"><h3>Criterio di successo</h3><ul class="checks">${crit}</ul>
      <p class="tiny muted">Misurato sul modello finale, fuori campione, nel periodo ${esc(d.first || "–")} – ${esc(d.last || "–")}. Modello completo (tutte le misure, nessuna scelta): IC ${num((R.dev_full || {}).ic, 3)}, Brier Skill Score ${pct((R.dev_full || {}).bss, 2)}.</p></div>
    <div class="card"><h3>Affidabilità delle probabilità</h3>${reliabilitySvg(d.reliability)}
      <p class="tiny muted">Ogni punto è una classe di previsioni: se il modello dice 55%, quante volte è andata davvero bene? Le barre sono l'intervallo al 95%. Calibrazione per blocco: ${cal || "–"}.</p></div>
    <div class="card"><h3>Le misure testate</h3>
      <table class="tbl"><tr><th>Misura</th><th>IC</th><th>t</th><th>Stato</th></tr>${feats}</table>
      <p class="tiny muted">IC = correlazione di rango tra la misura e il rendimento successivo, calcolata data per data e poi mediata. t corretto per la sovrapposizione delle finestre (Newey-West, ${esc(d.ic_lag || "")} ritardi). Controllo dei falsi positivi: Benjamini-Hochberg al 10%. Una misura resta attiva solo se migliora davvero la previsione (ablation).</p></div>
    ${labPanel === "stocks" ? `<div class="card"><h3>In raccolta (classe B)</h3>
      <table class="tbl"><tr><th>Dato</th><th>Periodi</th><th>Stato</th></tr>${cb}</table>
      <p class="tiny muted">${esc(((rep.class_b || {}).rule) || "")}</p></div>` : ""}
    <div class="card"><h3>Benchmark (Brier, più basso è meglio)</h3>
      <table class="tbl"><tr><th>Benchmark</th><th>Loro</th><th>Noi</th><th>Battuto</th></tr>${bench}</table></div>
    <div class="card"><h3>Stabilità</h3><div class="tiny muted">IC per anno</div>${yearBars(d.by_year)}
      ${(R.by_area || []).length ? `<table class="tbl"><tr><th>${labPanel === "stocks" ? "Area" : "Indice"}</th><th>IC</th><th>t</th><th>Periodi</th></tr>${grp(R.by_area)}</table>` : ""}
      ${(R.by_vix || []).length ? `<table class="tbl"><tr><th>Regime VIX</th><th>IC</th><th>t</th><th>Periodi</th></tr>${grp(R.by_vix)}</table>` : ""}</div>
    <div class="card"><h3>Holdout (ultime ${num(s.holdout_days, 0)} sedute)</h3>
      <p>${ho.tripped ? `<b class="neg">Interruttore scattato:</b> ${esc((ho.why || []).join("; "))}.` : ho.ok ? `<b class="pos">Nessuna contraddizione</b> con il test.` : esc((ho.why || []).join("; ") || "Non valutato.")}</p>
      ${ho.ok ? `<div class="kv">${kv("IC", num(ho.ic, 3))}${kv("t", num(ho.ic_t, 1))}${kv("Brier Skill Score", pct(ho.bss, 2))}${kv("Periodi indipendenti", num(ho.n_indep, 0))}</div>` : ""}
      <p class="tiny muted">Queste sedute non sono mai servite a scegliere misure o soglie: funzionano solo come interruttore.</p></div>
    ${ch ? `<div class="card"><h3>Modello sfidante</h3><p class="tiny">${esc(ch.name)}: Brier ${num(ch.brier, 4)} contro ${num(ch.brier_primary, 4)} della logistica (p = ${num(ch.p, 2)}). ${ch.adopted ? "<b>Adottato</b>: è statisticamente migliore." : "Non adottato: non è statisticamente migliore (serve p &lt; 0,05)."}</p></div>` : ""}
    <div class="card"><details><summary>Come è stato fatto il test</summary><div class="kv" style="margin-top:8px">
      ${kv("Titoli", num(s.n_tickers, 0))}${kv("Righe del panel", num(s.rows_total, 0))}
      ${kv("Una fotografia ogni", s.step + " sedute")}${kv("Orizzonte", s.h + " sedute")}
      ${kv("Storia minima", s.min_train + " sedute")}${kv("Riaddestramento", "ogni " + s.retrain + " sedute")}
      ${kv("Pausa (purge + embargo)", s.h + " + " + s.embargo + " sedute")}${kv("Dati dal", esc(s.calendar_first || "–"))}
      ${kv("Configurazioni provate", num(R.n_trials, 0))}${kv("Durata del test", num(R.elapsed, 0) + " s")}
    </div></details></div>`;
}

function renderLabRun(state) {
  const p = $("#labProg");
  if (state && state.running) {
    p.classList.remove("hidden");
    p.firstElementChild.style.width = Math.round(100 * (state.pct || 0)) + "%";
    $("#labRunInfo").textContent = `Test in corso: ${Math.round(100 * (state.pct || 0))}% — ${state.msg || ""}`;
    $("#labRun").disabled = true;
  } else {
    p.classList.add("hidden");
    $("#labRun").disabled = false;
    $("#labRunInfo").textContent = state && state.error ? "Ultimo test interrotto da un errore: " + state.error : "";
  }
}

async function loadLab() {
  const st = await api("/api/lab/status");
  renderLab(st);
  if (st.state.running && !labTimer) pollLab();
}

function pollLab() {
  labTimer = setInterval(async () => {
    const st = await api("/api/lab/status");
    renderLabRun(st.state);
    if (!st.state.running) { clearInterval(labTimer); labTimer = null; renderLab(st); }
  }, 2000);
}

/* ---------------- METODO ---------------- */
async function loadAgentsDoc() {
  const a = await api("/api/agents");
  $("#agentsDoc").innerHTML = a.map((x) => `
    <div class="agent"><div class="ah"><b>${esc(x.name)}</b><span class="chip ${x.enabled ? (x.role === "base" ? "s-COMPRA" : "s-NESSUN") : "s-NESSUN"}">${x.enabled ? (x.role === "base" ? "modello di base" : "peso 0") : "da installare"}</span></div>
    <div class="fam">${esc(x.family)} · ${x.applies_to === "stock" ? "solo azioni" : "azioni e indici"}</div>
    <p>${esc(x.description)}</p><p class="tiny">Fonte: ${esc(x.source)}</p></div>`).join("");
}

/* ---------------- eventi ---------------- */
document.addEventListener("click", async (ev) => {
  const nav = ev.target.closest("nav.bottom button");
  if (nav) return showTab(nav.dataset.tab);
  const go = ev.target.closest("[data-goto]");
  if (go) return showTab(go.dataset.goto);
  const lp = ev.target.closest("[data-lab]");
  if (lp) { labPanel = lp.dataset.lab; if (labData) renderLab(labData); return; }
  const del = ev.target.closest("[data-del]");
  if (del) {
    if (confirm("Eliminare questo titolo dal portafoglio?")) { await api("/api/portfolio/" + del.dataset.del, { method: "DELETE" }); loadPortfolio(); }
    return;
  }
  const m = ev.target.closest("#mkts [data-m]");
  if (m) { curMkt = m.dataset.m; return loadSignals(); }
  if (ev.target.closest("#scanThis")) {
    await api("/api/scan", { method: "POST", body: JSON.stringify({ markets: curMkt ? [curMkt] : null }) });
    showTab("home"); return;
  }
  const t = ev.target.closest("[data-t]");
  if (t) return analyze(t.dataset.t);
});

$("#searchForm").onsubmit = (ev) => { ev.preventDefault(); const v = $("#q").value.trim(); if (v) analyze(v); };
let sugTimer;
$("#q").addEventListener("input", () => {
  clearTimeout(sugTimer);
  const v = $("#q").value.trim();
  if (v.length < 2) { $("#suggest").innerHTML = ""; return; }
  sugTimer = setTimeout(async () => {
    const r = await api("/api/search?q=" + encodeURIComponent(v)).catch(() => []);
    $("#suggest").innerHTML = r.slice(0, 6).map((s) => `<div class="item" data-t="${esc(s.symbol)}"><div class="l"><b>${esc(s.name || s.symbol)}</b><span>${esc(s.symbol)} · ${esc(s.exchange || "")}</span></div></div>`).join("");
  }, 350);
});
$("#scanBtn").onclick = async () => { await api("/api/scan", { method: "POST", body: "{}" }); loadHome(); pollScan(); };
$("#labRun").onclick = async () => { await api("/api/lab/run", { method: "POST", body: "{}" }); loadLab(); };
$("#pfRefresh").onclick = async () => { const r = await api("/api/portfolio/refresh", { method: "POST" }); alert(r.started ? "Aggiornamento avviato: torna tra qualche minuto." : "Una scansione è già in corso."); };
$("#pfForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const fd = Object.fromEntries(new FormData(ev.target));
  try { await api("/api/portfolio", { method: "POST", body: JSON.stringify(fd) }); ev.target.reset(); loadPortfolio(); }
  catch (e) { alert(e.message); }
};

initTheme();
initDisclaimer();
loadHome().catch((e) => console.error(e));


// Forchetta attesa: non "sale o scende", ma "entro quanto si muoverà" (80%, calibrata sul passato)
function forkBlock(o) {
  const f = o.forchetta;
  if (!f) return "";
  const cur = (v) => num(v, 2) + " " + esc(o.currency || "");
  const rows = Object.entries(f.bands).map(([lab, b]) =>
    kv(`Tra ${esc(lab)}`, `pessimistico ${cur(b.low)} <span class="muted">(${pct(b.low_pct)})</span> · ` +
      `<b>mediano ${cur(b.mid)}</b> <span class="muted">(${pct(b.mid_pct)})</span> · ` +
      `ottimistico ${cur(b.high)} <span class="muted">(${pct(b.high_pct)})</span>`)).join("");
  const size = f.size_risk ? pct(f.size_risk, 1, false) + " del portafoglio" : "–";
  return `<div class="card"><h3>Forchetta attesa (80%)</h3>
    <p class="tiny muted" style="margin:4px 0 8px">Non è una previsione di rialzo o ribasso: è l'intervallo in cui il prezzo
    è rimasto 8 volte su 10 in casi simili; il mediano è il risultato centrale storico (metà dei casi sopra, metà sotto). Nelle crisi (2008, 2020) è stato superato più spesso.</p>
    <div class="kv">${rows}
      ${kv("Stop di protezione (2,5 ATR)", cur(f.stop))}
      ${kv("Peso con rischio 0,5%", size)}
    </div></div>`;
}
