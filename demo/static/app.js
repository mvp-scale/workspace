/* Jev Bench Console — shared helpers. Every page loads this first: <script src="/static/app.js"></script> */
(() => {
  const NAV = [["/", "Leaderboard"], ["/compare", "Baseline compare"], ["/scenarios", "Scenario lab"], ["/flow", "Conversation flow"], ["/models", "How they work"], ["/report", "Report"]];

  const el = (tag, attrs, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat(Infinity)) if (k != null && k !== false) n.append(k.nodeType ? k : document.createTextNode(k));
    return n;
  };
  const fmt = {
    pct: (v, d = 1) => v == null ? "–" : (v * 100).toFixed(d) + "%",
    num: (v, d = 3) => v == null ? "–" : Number(v).toFixed(d),
    ms: (s) => s == null ? "–" : s >= 1 ? (s).toFixed(2) + " s" : Math.round(s * 1000) + " ms",
  };

  function toast(message) {
    let region = document.querySelector(".toast-region");
    if (!region) { region = el("div", { class: "toast-region", role: "status", "aria-live": "polite" }); document.body.append(region); }
    const t = el("div", { class: "toast", text: message }); region.append(t); setTimeout(() => t.remove(), 2600);
  }
  async function api(path, opts) {
    let res;
    try { res = await fetch(path, opts); } catch { throw new Error("Can't reach the demo server. Check that it is running."); }
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Request failed (${res.status})`);
    return res.json();
  }
  function download(name, text, type) {
    const a = el("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name }); document.body.append(a); a.click(); a.remove();
  }
  const csv = (rows) => rows.map(r => r.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const copy = async (text) => { try { await navigator.clipboard.writeText(text); toast("Copied to clipboard"); } catch { toast("Copy failed. Select the text and copy manually."); } };

  /* Inline notices: loading skeleton, empty and error states with a retry. */
  const skeleton = (rows = 4) => el("div", { class: "stack", "aria-hidden": "true" }, Array.from({ length: rows }, () => el("div", { class: "skeleton", style: "height:40px" })));
  const empty = (title, body) => el("div", { class: "state" }, el("h3", { text: title }), el("p", { text: body }));
  const failure = (err, retry) => el("div", { class: "state", role: "alert" }, el("h3", { text: "Something went wrong" }), el("p", { text: err.message }),
    retry ? el("p", {}, el("button", { class: "btn", onclick: retry, text: "Try again" })) : null);
  /* Fills `node` with a skeleton, awaits `load`, then calls render(data). Errors get a retry button. */
  async function mount(node, load, render) {
    node.setAttribute("aria-busy", "true"); node.replaceChildren(skeleton());
    try { const data = await load(); node.replaceChildren(render(data)); }
    catch (e) { node.replaceChildren(failure(e, () => mount(node, load, render))); }
    finally { node.removeAttribute("aria-busy"); }
  }

  /* Makes a <table class="data"> sortable: put data-sort="num|text" on the <th>. */
  function sortable(table) {
    const ths = [...table.tHead.rows[0].cells];
    ths.forEach((th, i) => {
      if (!th.dataset.sort) return;
      th.setAttribute("aria-sort", "none"); const label = th.textContent; th.replaceChildren(el("button", { type: "button", text: label }));
      th.firstChild.addEventListener("click", () => {
        const dir = th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending";
        ths.forEach(o => o.hasAttribute("aria-sort") && o.setAttribute("aria-sort", "none")); th.setAttribute("aria-sort", dir);
        const val = (tr) => { const c = tr.cells[i]; const v = c.dataset.value ?? c.textContent; return th.dataset.sort === "num" ? (parseFloat(v) || 0) : v.toLowerCase(); };
        const rows = [...table.tBodies[0].rows].sort((a, b) => (val(a) > val(b) ? 1 : -1) * (dir === "ascending" ? 1 : -1));
        table.tBodies[0].append(...rows);
      });
    });
  }
  const meter = (value, label) => el("div", { class: "meter", role: "img", "aria-label": label || fmt.pct(value) },
    el("div", { class: "meter-track" }, el("div", { class: "meter-fill", style: `width:${Math.max(0, Math.min(1, value ?? 0)) * 100}%` })), el("span", { class: "meter-val", text: fmt.pct(value) }));

  function theme() {
    const root = document.documentElement, saved = (() => { try { return localStorage.getItem("theme"); } catch { return null; } })();
    if (saved) root.dataset.theme = saved;
    return el("button", { class: "btn ghost", type: "button", "aria-label": "Toggle colour theme", onclick: () => {
      const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark"; try { localStorage.setItem("theme", root.dataset.theme); } catch {}
    }, text: "Theme" });
  }

  /* ---- Models: one registry, one naming scheme (codes from models.json), live status from /api/status ---- */
  let FACTS = {}, ORDER = [], STATUS = null, RULE = "";
  const subs = new Set();
  const refreshStatus = async () => { try { STATUS = await api("/api/status"); ORDER = Object.keys(STATUS); subs.forEach(f => f(STATUS)); } catch { /* keep the last known status */ } };
  const ready = (async () => {
    try { const m = await api("/api/models"); m.models.forEach(x => { FACTS[x.id] = x; }); RULE = m.code_rule || ""; } catch { /* ids are shown instead */ }
    await refreshStatus();
  })();
  setInterval(refreshStatus, 10000);
  const codeOf = (id) => FACTS[id]?.code || STATUS?.[id]?.code || id;
  const nameOf = (id) => FACTS[id]?.name || STATUS?.[id]?.name || id;
  const isUp = (id) => !!STATUS?.[id]?.up;
  /* Code chip plus full name. Use {name:false} where space is tight; the code alone is always enough because the panel maps it. */
  const tag = (id, o = {}) => el("span", { class: "mtag", title: `${codeOf(id)} = ${nameOf(id)}` }, el("span", { class: "mcode", text: codeOf(id) }), o.name === false ? null : el("span", { class: "mname", text: nameOf(id) }));
  const gib = (mb) => (mb / 1024).toFixed(1) + " GiB";
  /* Fills a <select> from live status: loaded models first (with memory), the rest listed disabled. Refreshes itself. */
  function modelSelect(sel, o = {}) {
    const fill = () => {
      const st = STATUS || {}, ids = ORDER.length ? ORDER : Object.keys(FACTS), cur = sel.value || o.value;
      const label = (id) => { const s = st[id] || {}, bits = [codeOf(id), nameOf(id)]; if (s.hosted) bits.push("hosted, paid"); else if (s.up) bits.push(s.gpu_mb ? gib(s.gpu_mb) : "CPU"); return bits.join(" · "); };
      const up = ids.filter(id => st[id]?.up), down = ids.filter(id => !st[id]?.up);
      sel.replaceChildren(el("optgroup", { label: `Loaded now (${up.length})` }, up.map(id => el("option", { value: id, text: label(id) }))),
        down.length && !o.onlyLoaded ? el("optgroup", { label: "Not loaded" }, down.map(id => el("option", { value: id, disabled: true, class: "opt-off", text: `${label(id)} (not loaded)` }))) : null);
      const want = up.includes(cur) ? cur : up.includes(o.prefer) ? o.prefer : up[0];
      if (want) sel.value = want;
    };
    fill(); subs.add(fill); ready.then(fill); return fill;
  }
  /* The "Models 5/9" button and its panel: which models are loaded right now, what each code means, memory in use. */
  function modelsControl() {
    const dot = el("span", { class: "dot", "aria-hidden": "true" }), count = el("span", { text: "Models" });
    const btn = el("button", { class: "btn ghost models-btn", type: "button", "aria-expanded": "false", "aria-controls": "models-panel" }, dot, count);
    const panel = el("div", { class: "models-panel", id: "models-panel", hidden: true, role: "region", "aria-label": "Models and codes" });
    const render = () => {
      const st = STATUS || {}, ids = ORDER.length ? ORDER : Object.keys(FACTS), up = ids.filter(id => st[id]?.up);
      const used = up.reduce((n, id) => n + (st[id].gpu_mb || 0), 0);
      dot.className = "dot " + (up.length ? "up" : "down"); count.textContent = `Models ${up.length}/${ids.length || "–"}`;
      panel.replaceChildren(el("h3", { text: `Loaded now: ${up.length} of ${ids.length}` }),
        el("p", { class: "small muted", text: `${gib(used)} of GPU memory in use. Status is checked live from each running server, so this list cannot drift from what is really in memory.` }),
        el("div", { class: "table-wrap" }, el("table", { class: "data" }, el("thead", {}, el("tr", {}, ["Code", "Model", "Size", "State", "GPU", "Loaded as"].map(h => el("th", { scope: "col", text: h })))),
          el("tbody", {}, ids.map(id => { const s = st[id] || {};
            return el("tr", {}, el("td", {}, el("span", { class: "mcode", text: codeOf(id) })), el("td", { text: nameOf(id) }), el("td", { class: "dim", text: FACTS[id]?.params || "–" }),
              el("td", {}, el("span", { class: `dot ${s.up ? "up" : "down"}`, "aria-hidden": "true" }), s.up ? "Loaded" : (s.reason || "Not loaded")),
              el("td", { class: "dim", text: s.hosted ? "hosted" : s.up ? (s.gpu_mb ? gib(s.gpu_mb) : "CPU") : "–" }),
              el("td", { class: "dim", text: s.up ? (s.identity || "") + (s.identity_ok === false ? "  (does not match its label)" : "") : "" })); })))),
        el("p", { class: "note", text: RULE }));
    };
    btn.addEventListener("click", () => { const open = panel.hidden; panel.hidden = !open; btn.setAttribute("aria-expanded", String(open)); if (open) refreshStatus(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
    document.addEventListener("click", (e) => { if (!panel.hidden && !panel.contains(e.target) && !btn.contains(e.target)) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); } });
    subs.add(render); ready.then(render);
    return [btn, panel];
  }

  /* Header + footer shell, injected once so every page shares one source of truth. */
  function shell() {
    const path = location.pathname.replace(/\/$/, "") || "/";
    document.body.prepend(
      el("a", { class: "skip", href: "#main", text: "Skip to content" }),
      el("header", { class: "topbar" }, el("div", { class: "topbar-inner" },
        el("a", { class: "brand", href: "/" }, "Jev Bench ", el("span", { text: "Console" })),
        el("nav", { class: "nav", "aria-label": "Primary" }, NAV.map(([h, t]) => el("a", { href: h, "aria-current": h === path ? "page" : null, text: t }))),
        ...modelsControl(), theme())));
    document.body.append(el("footer", { class: "footer" }, el("div", { class: "footer-inner" },
      el("span", { text: "Runs on this machine's RTX 5090 with the public JevBench tiers." }),
      el("span", {}, "Benchmark harness: ", el("a", { href: "https://github.com/fstandhartinger/jevbench", text: "JevBench" })))));
    const main = document.querySelector("main"); if (main) main.id = "main";
  }
  /* Shared data: leaderboard rows merged with the model fact sheet. Cached per page load. */
  let cache;
  const load = () => cache ||= Promise.all([api("/api/leaderboard"), api("/api/models")]).then(([rows, meta]) => {
    const info = Object.fromEntries(meta.models.map(m => [m.id, m]));
    return { rows: rows.map(r => ({ ...r, info: info[r.id] || { id: r.id, name: r.id } })), models: meta.models, tiers: meta.tiers };
  }).catch(e => { cache = null; throw e; });

  window.Jev = { ready, codeOf, nameOf, isUp, tag, modelSelect, status: () => STATUS, onStatus: (f) => subs.add(f), el, fmt, api, toast, download, csv, copy, skeleton, empty, failure, mount, sortable, meter, load };
  document.addEventListener("DOMContentLoaded", shell);
})();
