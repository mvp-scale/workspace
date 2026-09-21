/* Jev Bench Console — shared helpers. Every page loads this first: <script src="/static/app.js"></script> */
(() => {
  const NAV = [["/", "Leaderboard"], ["/compare", "Baseline compare"], ["/scenarios", "Scenario lab"], ["/windows", "Text windows"], ["/stream", "Call monitor"], ["/models", "How they work"], ["/report", "Report"]];

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
  /* Header + footer shell, injected once so every page shares one source of truth. */
  function shell() {
    const path = location.pathname.replace(/\/$/, "") || "/";
    document.body.prepend(
      el("a", { class: "skip", href: "#main", text: "Skip to content" }),
      el("header", { class: "topbar" }, el("div", { class: "topbar-inner" },
        el("a", { class: "brand", href: "/" }, "Jev Bench ", el("span", { text: "Console" })),
        el("nav", { class: "nav", "aria-label": "Primary" }, NAV.map(([h, t]) => el("a", { href: h, "aria-current": h === path ? "page" : null, text: t }))),
        theme())));
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

  window.Jev = { el, fmt, api, toast, download, csv, copy, skeleton, empty, failure, mount, sortable, meter, load };
  document.addEventListener("DOMContentLoaded", shell);
})();
