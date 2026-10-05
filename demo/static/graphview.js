/* GraphView: a small dependency-free canvas viewer for the world engine's layered graph.
   Layers: world, country, region, audience, person, decision. Semantic zoom between layers (nodes glide and fade),
   pulses for news items travelling down the structure, hover tips, Ctrl/Cmd+wheel zoom, drag to pan.
   Everything drawn is data passed in; pulses show the PATH a story takes, not its size. */
(function () {
  const LAYERS = ["world", "country", "region", "audience", "person", "decision"];
  const COUNT_LABEL = { world: "World", country: "Country", region: "Region", audience: "Audience", person: "Person", decision: "Decision" };
  const STAGE = { world: 0, country: 450, region: 900, audience: 1350, person: 1800, decision: 1e9 };
  const PULSE_MS = 1300, AGE_MAX = 3400;
  const mulberry = (a) => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v)), ell = (s, n) => s.length > n ? s.slice(0, n - 1) + "…" : s;

  function GraphView(host, data, opts) {
    opts = opts || {};
    const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d"), tip = document.createElement("div");
    canvas.className = "gv-canvas"; tip.className = "gv-tip"; host.append(canvas, tip);
    const R = mulberry(7), nodes = [], edges = [], byId = new Map(), la = {}, nC = data.countries.length, nR = data.regionNames.length;
    LAYERS.forEach(l => la[l] = 1);
    const add = (n) => { Object.assign(n, { x: 0, y: 0, tx: 0, ty: 0, r: 4, tr: 4 }); byId.set(n.id, n); nodes.push(n); return n; };
    const perDot = Math.round(data.people / (nC * nR * data.dotsPerRegion));
    add({ id: "WORLD", layer: "world", label: "World", info: data.people.toLocaleString() + " simulated people" });
    data.countries.forEach((c, i) => {
      add({ id: "C:" + c.id, layer: "country", label: c.name, idx: i, pop: c.pop_m, info: c.pop_m + " million people (simulated mix)" }); edges.push(["WORLD", "C:" + c.id]);
      data.regionNames.forEach((rn, j) => {
        const rid = `R:${c.id}:${j}`; add({ id: rid, layer: "region", label: c.name + " · " + rn, idx: j, cidx: i, parent: "C:" + c.id, info: "a settlement type inside " + c.name }); edges.push(["C:" + c.id, rid]);
        for (let k = 0; k < data.dotsPerRegion; k++) { add({ id: `P:${rid}:${k}`, layer: "person", label: "Simulated people", cidx: i, parent: rid, dx: R() * 2 - 1, dy: R() * 2 - 1, info: "one dot is about " + perDot.toLocaleString() + " people" }); edges.push([rid, `P:${rid}:${k}`]); }
      });
    });
    data.audiences.forEach((a, i) => add({ id: "A:" + i, layer: "audience", label: a, idx: i, info: "a group of people; groups cut across countries" }));
    data.decisions.forEach((d, i) => add({ id: "D:" + i, layer: "decision", label: d.label, idx: i, val: d.value, info: d.value == null ? "a decision rule (ask a question to colour it)" : "world average change: " + (d.value > 0 ? "+" : "") + d.value.toFixed(1) + " points" }));
    const layerNodes = (l) => nodes.filter(n => n.layer === l), counts = { world: 1, country: nC, region: nC * nR, audience: data.audiences.length, person: data.people, decision: data.decisions.length };
    let W = 0, H = opts.height || 460, dpr = 1, view = "all", k = 1, ox = 0, oy = 0, tk = 1, tox = 0, toy = 0, playing = false, raf = 0, last = 0, nextAt = 0, evI = 0, hover = null, col = null, colAt = 0;
    const pulses = [];

    /* ---------- layout ---------- */
    const grid = (i, n, cols, x0, x1, y0, y1) => { const rows = Math.ceil(n / cols), c = i % cols, r = Math.floor(i / cols); return [x0 + (x1 - x0) * (c + .5) / cols, y0 + (y1 - y0) * (r + .5) / rows]; };
    function layout() {
      const all = view === "all", L = 128, cw = Math.max(200, W - L - 16), slot = cw / nC, set = (n, x, y, r) => { n.tx = x; n.ty = y; n.tr = r; };
      const maxPop = Math.max(...data.countries.map(c => c.pop_m)), rowY = { world: .08, country: .23, region: .39, audience: .55, person: .745, decision: .93 };
      const cx = (i) => all ? L + slot * (i + .5) : grid(i, nC, 4, 40, W - 40, 40, H - 40)[0], cy = (i) => all ? H * rowY.country : grid(i, nC, 4, 40, W - 40, 60, H - 50)[1];
      for (const n of nodes) {
        if (n.layer === "world") set(n, all ? L + cw / 2 : W / 2, all ? H * rowY.world : H / 2, all ? 11 : 46);
        else if (n.layer === "country") set(n, cx(n.idx), cy(n.idx), (all ? 6 : 14) + (all ? 6 : 24) * Math.sqrt(n.pop / maxPop));
        else if (n.layer === "region") { const dxr = all ? (n.idx - (nR - 1) / 2) * slot * .3 : (n.idx - (nR - 1) / 2) * 74, dyr = all ? 0 : (n.idx === 1 ? -28 : 20); set(n, cx(n.cidx) + dxr, (all ? H * rowY.region : cy(n.cidx)) + dyr, all ? 4.5 : 11); }
        else if (n.layer === "person") { const rg = byId.get(n.parent); const bx = all ? cx(n.cidx) + (rg.idx - (nR - 1) / 2) * slot * .3 : cx(n.cidx) + (rg.idx - (nR - 1) / 2) * 74, by = all ? H * rowY.person : cy(n.cidx) + (rg.idx === 1 ? -28 : 20), sp = all ? slot * .1 : 22; set(n, bx + n.dx * sp, by + n.dy * (all ? H * .055 : 20), all ? 1.7 : 2.2); }
        else if (n.layer === "audience") { const p = all ? [L + cw * (.2 + .6 * (n.idx + .5) / data.audiences.length), H * rowY.audience] : grid(n.idx, data.audiences.length, 4, 70, W - 70, 70, H - 70); set(n, p[0], p[1], all ? 6 : 26); }
        else if (n.layer === "decision") { const p = all ? [L + cw * (.2 + .6 * (n.idx + .5) / data.decisions.length), H * rowY.decision] : grid(n.idx, data.decisions.length, 4, 70, W - 70, 70, H - 70); set(n, p[0], p[1], all ? 6 : 26); }
      }
    }
    const visible = (l) => view === "all" || view === l;

    /* ---------- pulses ---------- */
    function reach(ev) {
      const w = ev.entry === "WORLD:world", cid = w ? null : "C:" + ev.entry.split(":")[1], off = w ? 0 : STAGE.country, ci = w ? -1 : data.countries.findIndex(c => "C:" + c.id === cid);
      return (n) => { const d = STAGE[n.layer] - off; switch (n.layer) {
        case "world": return w ? 0 : -1; case "country": return w || n.id === cid ? d : -1; case "region": case "person": return w || n.cidx === ci ? d : -1; case "audience": return d; default: return -1; } };
    }
    function launch(now) { if (!data.events.length) return; const ev = data.events[evI % data.events.length]; evI++; pulses.push({ ev, t0: now, reach: reach(ev) }); if (pulses.length > 5) pulses.shift(); if (opts.onEvent) opts.onEvent(ev, (evI - 1) % data.events.length, data.events.length); }

    /* ---------- drawing ---------- */
    function colors() { const cs = getComputedStyle(host), g = (v, d) => (cs.getPropertyValue(v) || d).trim() || d; return { surf: g("--surface", "#111"), s2: g("--surface-2", "#1a1a1a"), b: g("--border", "#2a2a2a"), bs: g("--border-strong", "#3a3a3a"), t: g("--text", "#eee"), t2: g("--text-2", "#bbb"), t3: g("--text-3", "#888"), ac: g("--accent", "#5b9cff"), fo: g("--for", "#4f8ff7"), ag: g("--against", "#e9843b"), font: getComputedStyle(document.body).fontFamily }; }
    function frame(now) { raf = requestAnimationFrame(frame); const dt = Math.min(64, now - (last || now)); last = now; step(dt, now); }
    function step(dt, now) {
      if (!col || now - colAt > 1000) { col = colors(); colAt = now; }
      if (playing && now >= nextAt) { launch(now); nextAt = now + 1500; }
      while (pulses.length && now - pulses[0].t0 > AGE_MAX) pulses.shift();
      const e = 1 - Math.pow(.0006, dt / 1000);
      k += (tk - k) * e; ox += (tox - ox) * e; oy += (toy - oy) * e;
      for (const l of LAYERS) la[l] += ((visible(l) ? 1 : 0) - la[l]) * e;
      for (const n of nodes) { n.x += (n.tx - n.x) * e; n.y += (n.ty - n.y) * e; n.r += (n.tr - n.r) * e; }
      draw(now);
    }
    function draw(now) {
      const c = col; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H); ctx.font = "11px " + c.font; ctx.textBaseline = "middle";
      ctx.save(); ctx.translate(ox, oy); ctx.scale(k, k);
      const lit = (a, b) => { let best = 0; for (const p of pulses) { const da = p.reach(a), db = p.reach(b); if (da < 0 || db < 0) continue; const t = (now - p.t0 - da) / Math.max(1, db - da); if (t >= 0 && t <= 1) best = Math.max(best, 1); } return best; };
      // edges
      ctx.lineWidth = 1; ctx.strokeStyle = c.bs;
      for (const pass of [0, 1]) { ctx.globalAlpha = pass ? .07 : .3; ctx.beginPath(); for (const [a, b] of edges) { const A = byId.get(a), B = byId.get(b); if ((B.layer === "person") !== !!pass || Math.min(la[A.layer], la[B.layer]) < .05) continue; ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); } ctx.stroke(); }
      ctx.globalAlpha = 1;
      if (view === "all" || la.audience > .05) { const aa = byId.get("A:0"), az = byId.get("A:" + (data.audiences.length - 1)); if (aa && az) { ctx.globalAlpha = la.audience * (view === "all" ? .9 : 0); ctx.fillStyle = c.s2; ctx.beginPath(); ctx.roundRect(aa.x - 22, aa.y - 17, az.x - aa.x + 44, 34, 17); ctx.fill(); ctx.globalAlpha = la.audience * (view === "all" ? 1 : 0); ctx.fillStyle = c.t3; ctx.textAlign = "center"; ctx.fillText("cut across all countries", (aa.x + az.x) / 2, aa.y - 26); ctx.textAlign = "left"; } }
      ctx.globalAlpha = 1;
      // travelling dots along edges
      for (const p of pulses) for (const [a, b] of edges) { const A = byId.get(a), B = byId.get(b), al = Math.min(la[A.layer], la[B.layer]); if (al < .3) continue; const da = p.reach(A), db = p.reach(B); if (da < 0 || db < 0) continue; const t = (now - p.t0 - da) / Math.max(1, db - da); if (t < 0 || t > 1) continue; ctx.globalAlpha = al * .9; ctx.fillStyle = c.ac; ctx.beginPath(); ctx.arc(A.x + (B.x - A.x) * t, A.y + (B.y - A.y) * t, B.layer === "person" ? 1.4 : 2.4, 0, 6.2832); ctx.fill(); }
      // nodes
      for (const n of nodes) {
        const al = la[n.layer]; if (al < .03) continue; ctx.globalAlpha = al; const tint = n.layer === "decision" && n.val != null ? (Math.abs(n.val) < .05 ? null : `color-mix(in srgb, ${n.val > 0 ? c.fo : c.ag} ${Math.round(25 + 65 * Math.min(1, Math.abs(n.val) / (data.decisionMax || 1)))}%, ${c.s2})`) : null;
        ctx.fillStyle = n.layer === "person" ? c.t3 : tint || c.s2; ctx.strokeStyle = hover === n ? c.t : c.bs; ctx.lineWidth = hover === n ? 1.6 : 1.2; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.2832); ctx.fill(); if (n.layer !== "person") ctx.stroke();
        if (n.layer === "person" && hover === n) { ctx.strokeStyle = c.t; ctx.stroke(); }
      }
      // rings
      for (const p of pulses) for (const n of nodes) { if (la[n.layer] < .1) continue; const d = p.reach(n); if (d < 0) continue; const age = now - p.t0 - d; if (age < 0 || age > PULSE_MS) continue; const f = age / PULSE_MS, aud = n.layer === "audience";
        ctx.globalAlpha = la[n.layer] * (1 - f) * (aud ? .5 : .85); ctx.strokeStyle = c.ac; ctx.fillStyle = c.ac; ctx.lineWidth = 2;
        if (n.layer === "person") { ctx.beginPath(); ctx.arc(n.x, n.y, n.r + f * 3.5, 0, 6.2832); ctx.fill(); } else { ctx.beginPath(); ctx.arc(n.x, n.y, n.r + f * (view === "all" ? 12 : 26), 0, 6.2832); ctx.stroke(); } }
      // labels
      ctx.globalAlpha = 1; ctx.textAlign = "center"; ctx.fillStyle = c.t2;
      for (const n of nodes) { const al = la[n.layer]; if (al < .4 || n.layer === "person") continue; const all = view === "all";
        if (all && (n.layer === "region" || n.layer === "audience" || n.layer === "decision")) continue;
        ctx.globalAlpha = al; ctx.fillStyle = c.t2; ctx.fillText(ell(n.layer === "region" ? n.label.split(" · ").pop() : n.label, view === "all" ? 14 : n.layer === "region" ? 22 : 26), n.x, n.y + n.r + 11); }
      if (view === "region" && la.region > .5) { const cs = layerNodes("country"); ctx.font = "600 12px " + c.font; ctx.fillStyle = c.t; ctx.globalAlpha = la.region; for (const cn of cs) ctx.fillText(cn.label, cn.tx, cn.ty - 52); }
      ctx.restore(); ctx.globalAlpha = 1; ctx.textAlign = "left";
      if (view === "all") { const rowY = [["world", .08], ["country", .23], ["region", .39], ["audience", .55], ["person", .745], ["decision", .93]]; ctx.fillStyle = c.t3; for (const [l, y] of rowY) { ctx.font = "600 11px " + c.font; ctx.fillStyle = c.t2; ctx.fillText(COUNT_LABEL[l], 12, H * y * k + oy - 6); ctx.font = "11px " + c.font; ctx.fillStyle = c.t3; ctx.fillText(counts[l].toLocaleString(), 12, H * y * k + oy + 8); } }
    }

    /* ---------- interaction ---------- */
    const toWorld = (x, y) => [(x - ox) / k, (y - oy) / k];
    function pick(x, y) { const [wx, wy] = toWorld(x, y); let best = null, bd = 1e9; for (const n of nodes) { if (la[n.layer] < .5) continue; const d = Math.hypot(n.x - wx, n.y - wy), lim = Math.max(n.r + 3, n.layer === "person" ? 4 : 0); if (d < lim && d / lim < bd) { bd = d / lim; best = n; } } return best; }
    let drag = null, moved = false;
    canvas.addEventListener("mousedown", (e) => { drag = { x: e.offsetX, y: e.offsetY, ox: tox, oy: toy }; moved = false; });
    window.addEventListener("mouseup", onUp); function onUp() { drag = null; }
    canvas.addEventListener("mousemove", (e) => { if (drag) { const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) moved = true; tox = drag.ox + dx; toy = drag.oy + dy; ox = tox; oy = toy; tip.style.opacity = 0; return; }
      hover = pick(e.offsetX, e.offsetY); canvas.style.cursor = hover ? "pointer" : "grab";
      if (hover) { tip.replaceChildren(); const b = document.createElement("b"); b.textContent = hover.label; const s = document.createElement("div"); s.textContent = hover.info; s.style.color = "var(--text-3)"; tip.append(b, s); tip.style.left = Math.min(W - 230, e.offsetX + 14) + "px"; tip.style.top = Math.max(4, e.offsetY - 10) + "px"; tip.style.opacity = 1; } else tip.style.opacity = 0; });
    canvas.addEventListener("mouseleave", () => { hover = null; tip.style.opacity = 0; });
    canvas.addEventListener("click", (e) => { if (moved) return; const n = pick(e.offsetX, e.offsetY); if (view === "all") { if (n && opts.onLayer) opts.onLayer(n.layer); else if (e.offsetX < 120) { const rows = [["world", .08], ["country", .23], ["region", .39], ["audience", .55], ["person", .745], ["decision", .93]]; const hit = rows.reduce((a, b) => Math.abs(b[1] * H - e.offsetY) < Math.abs(a[1] * H - e.offsetY) ? b : a); if (opts.onLayer) opts.onLayer(hit[0]); } } });
    canvas.addEventListener("wheel", (e) => { if (!(e.ctrlKey || e.metaKey)) return; e.preventDefault(); const f = Math.exp(-e.deltaY * .0025), nk = clamp(tk * f, .6, 5); tox = e.offsetX - (e.offsetX - tox) * (nk / tk); toy = e.offsetY - (e.offsetY - toy) * (nk / tk); tk = nk; }, { passive: false });
    canvas.addEventListener("dblclick", () => self.resetZoom());

    /* ---------- sizing and API ---------- */
    function size() { W = Math.max(320, host.clientWidth); dpr = Math.min(2, window.devicePixelRatio || 1); canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); canvas.style.width = W + "px"; canvas.style.height = H + "px"; layout(); }
    const ro = new ResizeObserver(() => size()); ro.observe(host); size();
    nodes.forEach(n => { n.x = n.tx; n.y = n.ty; n.r = n.tr; });
    const self = {
      setView(v) { view = v; tk = 1; tox = 0; toy = 0; layout(); }, get view() { return view; },
      zoom(f) { const nk = clamp(tk * f, .6, 5); tox = W / 2 - (W / 2 - tox) * (nk / tk); toy = H / 2 - (H / 2 - toy) * (nk / tk); tk = nk; },
      resetZoom() { tk = 1; tox = 0; toy = 0; },
      play() { playing = true; nextAt = 0; }, pause() { playing = false; }, get playing() { return playing; },
      settle(n) { const now = performance.now(); for (let i = 0; i < (n || 40); i++) step(16, now); },
      frameCost(n) { const t = performance.now(); for (let i = 0; i < n; i++) step(16, t + i * 16); return (performance.now() - t) / n; },
      destroy() { cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener("mouseup", onUp); canvas.remove(); tip.remove(); },
    };
    raf = requestAnimationFrame(frame);
    return self;
  }
  window.GraphView = GraphView;
})();
