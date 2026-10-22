/* Jev Bench Console — shared helpers. Every page loads this first: <script src="/static/app.js"></script> */
(() => {
  /* Secure mode (the top bar's neutral "Secure mode" flag; it never says what it does): every real model, encoder, vendor and author name on the page is replaced by the code
     names in demo/mask.json, including text drawn later and what the copy buttons copy. The page stays hidden until the
     setting is known, so real names never flash up. It masks what is shown, not the raw API data in developer tools. */
  let MASK = null, MASK_ON = false, MASK_CAN = false;
  document.documentElement.classList.add("mask-pending");
  const maskStr = (t) => (MASK && t ? t.replace(MASK.re, (m) => MASK.map.get(m) ?? m) : t);
  const maskUrl = (u) => { const i = u.search(/[?#]/); return i < 0 ? u : u.slice(0, i) + maskStr(u.slice(i)); };   // only the state part of a URL
  // pages read their state through Jev.hash(): code names in the address bar are turned back into real ids
  const hashReal = () => { let h = location.hash; if (MASK && MASK.ids) for (const [fake, real] of MASK.ids) h = h.split(encodeURIComponent(fake)).join(real).split(fake).join(real); return h; };
  const maskSkip = (n) => n && n.closest && n.closest("textarea, script, style, [contenteditable]");
  const maskAttrs = (n) => {
    for (const a of ["title", "placeholder", "aria-label", "alt"]) { const v = n.getAttribute(a); if (v) { const w = maskStr(v); if (w !== v) n.setAttribute(a, w); } }
    if (n.tagName === "A" && n.hasAttribute("href")) { try { if (new URL(n.href, location.href).host !== location.host) { n.removeAttribute("href"); n.title = "Not available in secure mode"; } } catch {} }
  };
  const maskNode = (root) => {
    if (!MASK || !root) return;
    if (root.nodeType === 3) { if (!maskSkip(root.parentElement)) { const v = maskStr(root.nodeValue); if (v !== root.nodeValue) root.nodeValue = v; } return; }
    if (root.nodeType !== 1 || maskSkip(root)) return;
    maskAttrs(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (n.nodeType === 3) { if (!maskSkip(n.parentElement)) { const v = maskStr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; } }
      else maskAttrs(n);
    }
  };
  const maskReady = fetch("/api/mask", { cache: "no-store" }).then(r => r.json()).then(d => {
    MASK_ON = !!d.on; MASK_CAN = !!d.can_switch;
    if (d.on && d.pairs && d.pairs.length) {
      const esc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), alnum = /[A-Za-z0-9]/;
      const alts = d.pairs.map(([real]) => (alnum.test(real[0]) ? "(?<![A-Za-z0-9])" : "") + esc(real) + (alnum.test(real.at(-1)) ? "(?![A-Za-z0-9])" : ""));
      MASK = { re: new RegExp(alts.join("|"), "g"), map: new Map(d.pairs), ids: [...(d.ids || [])].sort((a, b) => b[0].length - a[0].length) };
      // the address bar shows code names too: whatever a page writes, and after any hash navigation
      const rs = history.replaceState.bind(history), ps = history.pushState.bind(history);
      history.replaceState = (st, t, u) => rs(st, t, u == null ? u : maskUrl(String(u)));
      history.pushState = (st, t, u) => ps(st, t, u == null ? u : maskUrl(String(u)));
      const tidy = () => { const m = maskUrl(location.href); if (m !== location.href) rs(history.state, "", m); };
      addEventListener("hashchange", () => setTimeout(tidy, 0)); tidy();
      const start = () => { maskNode(document.documentElement); document.title = maskStr(document.title);
        new MutationObserver((ms) => { for (const m of ms) {
          if (m.type === "characterData") maskNode(m.target); else if (m.type === "attributes") maskAttrs(m.target); else m.addedNodes.forEach(maskNode); } })
          .observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["title", "placeholder", "aria-label", "alt", "href"] }); };
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
    }
  }).catch(() => {}).finally(() => document.documentElement.classList.remove("mask-pending"));
  setTimeout(() => document.documentElement.classList.remove("mask-pending"), 3000);   // never leave a page blank
  function maskControl() {
    const b = el("button", { class: "btn ghost", type: "button", text: "Secure mode" });
    maskReady.then(() => {
      b.textContent = MASK_ON ? "Secure mode: on" : "Secure mode: off"; b.disabled = !MASK_CAN;
      b.title = (MASK_ON ? "Secure mode is on." : "Secure mode is off.") + (MASK_CAN ? " Click to switch (applies for every visitor)." : " Only switchable from this machine.");
    });
    b.addEventListener("click", async () => {
      try { await api("/api/mask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ on: !MASK_ON }) }); location.reload(); }
      catch (e) { toast(e.message); }
    });
    return b;
  }

  const NAV = [["/", "Leaderboard"], ["/compare", "Baseline compare"], ["/scenarios", "Scenario lab"], ["/imagelab", "Image lab"], ["/worldengine", "World engine"], ["/worldengine-how", "How it works"], ["/flow", "Conversation flow"], ["/latent", "Latent lab"], ["/report", "Report"], ["/models", "How they work"]];

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
  const shareLink = async () => {   // the public Cloudflare link for this page while the share runs, else this page's own address
    try { const r = await fetch("/api/share"); const u = (await r.json()).url; if (u) return u + location.pathname + location.search + location.hash; } catch {}
    return location.href;
  };
  const copyLink = async () => copy(await shareLink());
  const copy = async (text) => {
    text = maskStr(text);   // demo mode: copied text carries code names too
    try { await navigator.clipboard.writeText(text); toast("Copied to clipboard"); return; } catch {}
    // plain-http pages (e.g. reached by IP address) have no clipboard API: fall back to a hidden textarea
    const ta = el("textarea", { style: "position:fixed;top:-1000px;opacity:0" }); ta.value = text; document.body.append(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch {}
    ta.remove(); toast(ok ? "Copied to clipboard" : "Copy failed. Select the text and copy manually.");
  };

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
  /* STATUS / ORDER: the models that answer any question, for every picker. ALL / ALL_ORDER add library-only models (BitMob,
     which is trained only on the questions it has learned), shown in the Models panel only. */
  /* REG: the one model registry (demo/registry.py via /api/models), in order. Retired models are dropped here, once, so
     no list anywhere shows them; Jev.models({ retired: true }) still returns them for pages that explain history. */
  let FACTS = {}, REG = [], ORDER = [], STATUS = null, ALL = null, ALL_ORDER = [], RULE = "";
  const subs = new Set();
  const retired = (id) => !!FACTS[id]?.retired;
  const refreshStatus = async () => { try { const raw = await api("api/status"); ALL = Object.fromEntries(Object.entries(raw).filter(([id]) => !retired(id))); ALL_ORDER = Object.keys(ALL);
    STATUS = Object.fromEntries(Object.entries(ALL).filter(([, s]) => !s.library_only)); ORDER = Object.keys(STATUS); subs.forEach(f => f(STATUS)); } catch { /* keep the last known status */ } };
  const ready = (async () => {
    try { const m = await api("api/models"); REG = m.models; m.models.forEach(x => { FACTS[x.id] = x; }); RULE = m.code_rule || ""; } catch { /* ids are shown instead */ }
    await refreshStatus();
  })();
  setInterval(refreshStatus, 10000);
  const codeOf = (id) => FACTS[id]?.code || STATUS?.[id]?.code || id;
  const nameOf = (id) => FACTS[id]?.name || STATUS?.[id]?.name || id;
  const isUp = (id) => !!(ALL || STATUS)?.[id]?.up;
  /* Every model, registry order, facts + abilities + live state. The one list pages use; never a page-local list. */
  const models = (o = {}) => REG.filter(m => o.retired || !m.retired).map(m => ({ ...m, ...((ALL || {})[m.id] || {}), up: !!(ALL || {})[m.id]?.up }));
  /* The registered models a page has no results for yet (registry order, retired ones left out): the one place that decides who
     is "not run yet", so a newly registered model shows on every page at once. have = ids the page already shows; opt.lib:false drops
     library-only models (BitMob answers only its learned questions). Pages label these rows "Not run yet"; they never get numbers. */
  const pending = (have = [], o = {}) => { const h = new Set(have); return models().filter(m => !h.has(m.id) && (o.lib !== false || !m.library_only)); };
  /* Code chip plus full name. Use {name:false} where space is tight; the code alone is always enough because the panel maps it. */
  const tag = (id, o = {}) => el("span", { class: "mtag", title: `${codeOf(id)} = ${nameOf(id)}` }, el("span", { class: "mcode", text: codeOf(id) }), o.name === false ? null : el("span", { class: "mname", text: nameOf(id) }));
  const gib = (mb) => (mb / 1024).toFixed(1) + " GiB";
  /* Fills a <select> from live status: loaded models first (with memory), the rest listed disabled. Refreshes itself. */
  function modelSelect(sel, o = {}) {
    const fill = () => {
      const st = ALL || STATUS || {}, ids = ALL_ORDER.length ? ALL_ORDER : Object.keys(FACTS), cur = sel.value || o.value;
      const label = (id) => { const s = st[id] || {}, bits = [codeOf(id), nameOf(id)]; if (s.hosted) bits.push("hosted, paid"); else if (s.up) bits.push(s.gpu_mb ? gib(s.gpu_mb) : "CPU"); return bits.join(" · "); };
      const lib = ids.filter(id => st[id]?.library_only), up = ids.filter(id => st[id]?.up && !st[id]?.library_only), down = ids.filter(id => !st[id]?.up && !st[id]?.library_only);
      sel.replaceChildren(el("optgroup", { label: `Loaded now (${up.length})` }, up.map(id => el("option", { value: id, text: label(id) }))),
        lib.length ? el("optgroup", { label: "Learned questions only" }, lib.map(id => el("option", { value: id, disabled: true, class: "opt-off", text: `${codeOf(id)} · ${nameOf(id)} (trained only on its learned questions)` }))) : null,
        down.length && !o.onlyLoaded ? el("optgroup", { label: "Not loaded" }, down.map(id => el("option", { value: id, disabled: true, class: "opt-off", text: `${label(id)} (not loaded)` }))) : null);
      const want = up.includes(cur) ? cur : up.includes(o.prefer) ? o.prefer : up[0];
      if (want) sel.value = want;
    };
    fill(); subs.add(fill); ready.then(fill); return fill;
  }
  /* The "Models 5/9" button and its panel: which models are loaded right now, what each code means, memory in use. */
  /* On-demand services (voice, the local classifier, Clef) with one switch each. Only a visitor on this machine may switch;
     anyone else sees the state. The console runs ./service.sh, so the terminal and these switches stay in step. */
  function servicesControl() {
    const dot = el("span", { class: "dot", "aria-hidden": "true" }), label = el("span", { text: "Services" });
    const btn = el("button", { class: "btn ghost models-btn", type: "button", "aria-expanded": "false", "aria-controls": "svc-panel" }, dot, label);
    const panel = el("div", { class: "models-panel svc-panel", id: "svc-panel", hidden: true, role: "region", "aria-label": "On-demand services" });
    let timer = null, last = null;
    const draw = (d) => {
      last = d; const on = d.services.filter(sv => sv.up).length, busy = d.services.some(sv => sv.busy);
      dot.className = "dot " + (busy ? "busy" : on ? "up" : "down"); label.textContent = `Services ${on}/${d.services.length}`;
      panel.replaceChildren(el("h3", { text: "On-demand services" }),
        el("p", { class: "small muted", text: "The console and the World Engine are always on. These start when you need them and free their memory when off." + (d.can_switch ? "" : " Switching works only from this machine.") }),
        el("div", { class: "svc-rows" }, ...d.services.map(sv => {
          const state = sv.busy ? (sv.busy === "start" ? "starting…" : "stopping…") : sv.up ? "on" : "off";
          return el("div", { class: "svc-row" }, el("span", { class: "dot " + (sv.busy ? "busy" : sv.up ? "up" : "down"), "aria-hidden": "true" }),
            el("b", { text: sv.label }), el("span", { class: "small muted", text: sv.gpu }), el("span", { class: "small", text: state }),
            el("button", { class: "btn", type: "button", disabled: !d.can_switch || !!sv.busy, text: sv.up ? "Turn off" : "Turn on",
              onclick: async () => {
                if (sv.up && !confirm(`Turn ${sv.label} off? Pages using it will say it is off until it is turned on again.`)) return;
                try { await api(`/api/services/${sv.name}/${sv.up ? "stop" : "start"}`, { method: "POST" }); } catch (e) { toast(e.message); }
                refresh(1500);
              } }));
        })),
        el("p", { class: "note", text: "Same as ./service.sh start|stop <name> in a terminal." }));
      return busy;
    };
    const refresh = (ms) => { clearTimeout(timer); timer = setTimeout(async () => {
      let busy = false; try { busy = draw(await api("/api/services")); } catch { label.textContent = "Services"; }
      refresh(busy ? 2000 : panel.hidden ? 20000 : 5000); }, ms); };
    btn.addEventListener("click", () => { const open = panel.hidden; panel.hidden = !open; btn.setAttribute("aria-expanded", String(open)); if (open) refresh(0); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
    document.addEventListener("click", (e) => { if (!panel.hidden && !panel.contains(e.target) && !btn.contains(e.target)) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); } });
    refresh(0);
    return [btn, panel];
  }
  function modelsControl() {
    const dot = el("span", { class: "dot", "aria-hidden": "true" }), count = el("span", { text: "Models" });
    const btn = el("button", { class: "btn ghost models-btn", type: "button", "aria-expanded": "false", "aria-controls": "models-panel" }, dot, count);
    const panel = el("div", { class: "models-panel", id: "models-panel", hidden: true, role: "region", "aria-label": "Models and codes" });
    const render = () => {
      const st = ALL || {}, ids = ALL_ORDER.length ? ALL_ORDER : Object.keys(FACTS), up = ids.filter(id => st[id]?.up);
      const used = up.reduce((n, id) => n + (st[id].gpu_mb || 0), 0);
      dot.className = "dot " + (up.length ? "up" : "down"); count.textContent = `Models ${up.length}/${ids.length || "–"}`;
      panel.replaceChildren(el("h3", { text: `Loaded now: ${up.length} of ${ids.length}` }),
        el("p", { class: "small muted", text: `${gib(used)} of GPU memory in use. Status is checked live from each running server, so this list cannot drift from what is really in memory.` }),
        el("div", { class: "table-wrap" }, el("table", { class: "data" }, el("thead", {}, el("tr", {}, ["Code", "Model", "Size", "State", "GPU", "Loaded as"].map(h => el("th", { scope: "col", text: h })))),
          el("tbody", {}, ids.map(id => { const s = st[id] || {};
            return el("tr", {}, el("td", {}, el("span", { class: "mcode", text: codeOf(id) })), el("td", { text: nameOf(id) }), el("td", { class: "dim", text: FACTS[id]?.params || "–" }),
              el("td", {}, el("span", { class: `dot ${s.up ? "up" : "down"}`, "aria-hidden": "true" }), s.up ? "Loaded" : (s.reason || "Not loaded")),
              el("td", { class: "dim", text: s.hosted ? "hosted" : s.up ? (s.gpu_mb ? gib(s.gpu_mb) : "CPU") : "–" }),
              el("td", { class: "dim", text: s.up ? (s.identity || "") + (s.identity_ok === false ? "  (does not match its label)" : "") : (s.engine_reader ? "World engine reader: answers the engine's questions only" : s.library_only ? "answers only the questions it has learned" : "") })); })))),
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
        ...servicesControl(), ...modelsControl(), maskControl(),
        el("button", { class: "btn ghost", type: "button", title: "Copy the public link to this page", onclick: () => copyLink(), text: "Share" }), theme())));
    document.body.append(el("footer", { class: "footer" }, el("div", { class: "footer-inner" },
      el("span", { text: "Runs on this machine's RTX 5090 with the public JevBench tiers." }),
      el("span", {}, "Benchmark harness: ", el("a", { href: "https://github.com/fstandhartinger/jevbench", text: "JevBench" })))));
    const main = document.querySelector("main"); if (main) main.id = "main";
  }
  /* Shared data: leaderboard rows merged with the model fact sheet. Cached per page load. */
  let cache;
  const load = () => cache ||= Promise.all([api("api/leaderboard"), api("api/models")]).then(([rows, meta]) => {
    const info = Object.fromEntries(meta.models.map(m => [m.id, m]));
    return { rows: rows.filter(r => !info[r.id]?.retired).map(r => ({ ...r, info: info[r.id] || { id: r.id, name: r.id } })), models: meta.models.filter(m => !m.retired), tiers: meta.tiers,
             retired: meta.models.filter(m => m.retired),
             pending: meta.models.filter(m => !m.retired && !m.unscored && !m.library_only && !rows.some(r => r.id === m.id)) };   /* registered, no leaderboard row yet */
  }).catch(e => { cache = null; throw e; });

  /* Heat-map colour: accuracy relative to chance, in seven steps. Shared by the Scenario lab and the Image lab. */
  const STEP_MIX = { "-3": 60, "-2": 38, "-1": 18, "0": 0, "1": 18, "2": 38, "3": 62 };
  const heat = { STEPS: [-3, -2, -1, 0, 1, 2, 3],
    stepOf: (acc, chance) => Math.max(-3, Math.min(3, Math.round((acc >= chance ? (acc - chance) / (1 - chance) : -(chance - acc) / chance) * 4))),
    stepBg: (i) => i === 0 ? "var(--surface-2)" : `color-mix(in srgb, var(${i > 0 ? "--good" : "--bad"}) ${STEP_MIX[i]}%, var(--surface))` };
  /* Heat-map ordering, computed from the data every render (so a new model or a landed run re-sorts the table). Shared by both labs.
     mean(values): mean of the non-null numbers, or null. sortBy(items, valueOf, tie): highest value first; null/NaN values last; ties by tie(item) (default: input order). */
  heat.mean = (vs) => { const v = vs.filter(x => typeof x === "number" && Number.isFinite(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
  heat.sortBy = (items, valueOf, tie) => items.map((it, i) => ({ it, i, v: valueOf(it) })).sort((a, b) => ((b.v ?? -Infinity) - (a.v ?? -Infinity) || 0) || ((tie ? tie(a.it) - tie(b.it) : 0) || a.i - b.i)).map(x => x.it);
  /* Columns (models): highest overall mean first (meanOf(id) -> number|null); ties and models with no result (null) in registry order. */
  heat.sortModels = (ids, meanOf) => { const reg = REG.map(m => m.id), at = (id) => { const i = reg.indexOf(id); return i < 0 ? 1e9 : i; };
    return heat.sortBy([...ids].sort((a, b) => at(a) - at(b)), meanOf, at); };
  /* Rows in groups: groups = [[name, rows]]; rowMean(row) -> number|null. Groups by their mean row value, rows within each group by theirs; empty groups dropped. */
  heat.sortGroups = (groups, rowMean) => heat.sortBy(groups.filter(([, rows]) => rows.length).map(([g, rows]) => [g, heat.sortBy(rows, rowMean)]), ([, rows]) => heat.mean(rows.map(rowMean)));
  heat.note = (rowNoun, transposed) => el("p", { class: "small muted heat-sorted", text: transposed ? `Sorted by accuracy: best model on top, best ${rowNoun} on the left.` : `Sorted by accuracy: best model on the left, best ${rowNoun} on top.` });
  /* Highlighted, indented JSON as DOM nodes (no innerHTML): keys, strings, numbers, literals, punctuation. */
  function jsonNodes(v, ind = 0) {
    const sp = "  ".repeat(ind), out = [], T = (c, t) => el("span", { class: "j-" + c, text: t });
    if (v === null) return [T("b", "null")]; if (typeof v === "string") return [T("s", JSON.stringify(v))]; if (typeof v === "number") return [T("n", String(v))]; if (typeof v === "boolean") return [T("b", String(v))];
    if (Array.isArray(v)) { if (!v.length) return [T("p", "[]")]; out.push(T("p", "[\n")); v.forEach((x, i) => out.push(document.createTextNode(sp + "  "), ...jsonNodes(x, ind + 1), T("p", i < v.length - 1 ? ",\n" : "\n"))); out.push(document.createTextNode(sp), T("p", "]")); return out; }
    const ks = Object.keys(v); if (!ks.length) return [T("p", "{}")]; out.push(T("p", "{\n")); ks.forEach((k, i) => out.push(document.createTextNode(sp + "  "), T("k", JSON.stringify(k)), T("p", ": "), ...jsonNodes(v[k], ind + 1), T("p", i < ks.length - 1 ? ",\n" : "\n"))); out.push(document.createTextNode(sp), T("p", "}")); return out;
  }
  /* Readable JSON: one line per key; long values wrap in their own column, aligned under where the value starts. */
  function jsonLines(v, depth = 0, key = null, last = true) {
    const T = (c, t) => el("span", { class: "j-" + c, text: t }), pad = { style: `padding-left:${depth * 1.4}em` };
    const head = key == null ? [] : [T("k", JSON.stringify(key)), T("p", ": ")], comma = last ? null : T("p", ",");
    if (v !== null && typeof v === "object") {
      const arr = Array.isArray(v), ks = arr ? v.map((_, i) => i) : Object.keys(v), [o, c] = arr ? ["[", "]"] : ["{", "}"];
      if (!ks.length) return [el("div", { class: "jl", ...pad }, el("span", { class: "jk" }, ...head), el("span", { class: "jv" }, T("p", o + c), comma))];
      return [el("div", { class: "jl", ...pad }, el("span", { class: "jk" }, ...head), el("span", { class: "jv" }, T("p", o))),
        ...ks.flatMap((k, i) => jsonLines(v[k], depth + 1, arr ? null : k, i === ks.length - 1)),
        el("div", { class: "jl", ...pad }, el("span", { class: "jv" }, T("p", c), comma))];
    }
    const val = v === null ? T("b", "null") : typeof v === "string" ? T("s", JSON.stringify(v)) : typeof v === "number" ? T("n", String(v)) : T("b", String(v));
    return [el("div", { class: "jl", ...pad }, el("span", { class: "jk" }, ...head), el("span", { class: "jv" }, val, comma))];
  }
  const jsonView = (v, label, opts = {}) => {
    const copyBtn = el("button", { class: "btn ghost jcopy", type: "button", text: "Copy", onclick: () => copy(JSON.stringify(v, null, 2)) });
    const bodyEl = opts.compact ? el("div", { class: "json json-inline" }, ...jsonNodes(JSON.parse(JSON.stringify(v))).map(n => (n.nodeType === 3 ? document.createTextNode(n.textContent.replace(/\n\s*/g, " ")) : (n.textContent = n.textContent.replace(/\n\s*/g, " "), n)))) : el("div", { class: "json" }, ...jsonLines(v));
    return el("div", { class: "jsonview" + (opts.compact ? " compact" : "") }, el("div", { class: "jsonview-head" }, el("span", { text: label || "JSON" }), copyBtn), bodyEl);
  };
  window.Jev = { hash: () => (MASK ? hashReal() : location.hash), masked: () => !!MASK, jsonView, jsonNodes, heat, ready, codeOf, nameOf, isUp, tag, modelSelect, status: () => STATUS, shareLink, copyLink, statusAll: () => ALL || STATUS, libOnly: (id) => !!FACTS[id]?.library_only, models, pending, isRetired: retired, LIB_NOTE: "is trained only on the questions it has learned (others get an untrained guess)", onStatus: (f) => subs.add(f), el, fmt, api, toast, download, csv, copy, skeleton, empty, failure, mount, sortable, meter, load };
  document.addEventListener("DOMContentLoaded", shell);
})();
