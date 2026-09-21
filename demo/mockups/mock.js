/* Shared mock-up engine v2.
   A call clock (sim seconds) drives everything. Signals are levels over time that rise, hold and fade.
   All motion is transform/opacity from one requestAnimationFrame loop. DOM is built with textContent only.
   Nothing here talks to a network; every fire is scripted (MOCK) unless a page says otherwise. */
(function () {
  const h = (tag, props, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") n.className = v;
      else if (k === "style") n.setAttribute("style", v);
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
    return n;
  };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const mmss = (s) => { s = Math.max(0, Math.floor(s)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
  const norm = (w) => w.replace(/^[.…\[]+|[.,!?;:…\]]+$/g, "");
  const ACT = 0.65, HOLD = 30, MAXW = 6;
  const cvar = (slot) => `--c:var(--s${(slot % 8) + 1})`;

  const all = () => [window.MockApollo, ...window.MockScenarios].filter(Boolean);
  const byId = (id) => all().find((s) => s.id === id) || all()[0];

  function prepare(scn) {
    return scn.turns.map((t, i) => {
      const words = t.text.split(/\s+/);
      const marks = scn.marks.filter((m) => m.turn === i).map((m) => {
        const pw = m.phrase.split(/\s+/);
        for (let s = 0; s + pw.length <= words.length; s++)
          if (pw.every((w, k) => norm(words[s + k]) === norm(w))) return { ...m, from: s, to: s + pw.length };
        return null;
      }).filter(Boolean);
      return { ...t, words, marks };
    });
  }

  const STOP = new Set("about after again also because been before being could from have into just like more only other over some such than that their them then there these they this very want what when where which while will with would your anyone someone something whenever tell mention mentions mentioning mentioned flag notice says said saying talk talking anybody people person".split(" "));
  const kwOf = (text) => text.toLowerCase().replace(/[^a-z ]/g, " ").split(/\s+/).filter((w) => w.length > 3 && !STOP.has(w)).map((w) => w.slice(0, Math.max(4, w.length - 2)));
  const codeOf = (text, taken) => {
    const ws = text.toUpperCase().replace(/[^A-Z ]/g, "").split(/\s+/).filter((w) => w.length > 2 && !STOP.has(w.toLowerCase()));
    let c = ws.length >= 3 ? ws.slice(0, 3).map((w) => w[0]).join("") : ws.length === 2 ? ws[0][0] + ws[1].slice(0, 2) : (ws[0] || "XXX").slice(0, 3);
    c = (c + "XXX").slice(0, 3);
    for (let i = 2; taken.has(c); i++) c = c.slice(0, 2) + i;
    return c;
  };

  /* ---------------------------------------------------------------- Session */
  function Session(scn, cb) {
    cb = cb || {};
    const turns = prepare(scn);
    let tt = 0.05;
    for (const tu of turns) {
      tu.t0 = tt; tu.wt = [];
      tu.words.forEach((w) => { tu.wt.push(tt); tt += 0.16 + 0.05 * w.replace(/\W/g, "").length; if (/[,;]$/.test(w)) tt += 0.12; if (/[.!?…]$|\]$/.test(w)) tt += 0.4; });
      tu.t1 = tt; tt += 0.9;
    }
    const flat = []; turns.forEach((tu, i) => tu.words.forEach((w, k) => flat.push({ i, k, w, t: tu.wt[k] })));

    const S = {
      scn, turns, duration: tt, t: 0, playing: false, speed: 1, done: false,
      watch: scn.watch.map((w, i) => ({ ...w, slot: i })), sig: {}, hist: {}, moments: [], seq: 0,
      _frame: [], _watch: [], _fire: [], _reset: [], _turn: [], _word: [], _settings: [], log: [],
      model: null, lag: 0, win: 20, cadence: "phrase", max: MAXW,
      onFrame(f) { S._frame.push(f); }, onWatch(f) { S._watch.push(f); }, onFire(f) { S._fire.push(f); }, onReset(f) { S._reset.push(f); },
      onTurn(f) { S._turn.push(f); }, onWord(f) { S._word.push(f); }, onSettings(f) { S._settings.push(f); },
      sideOf(spk) { return (scn.us || []).includes(spk) ? "us" : "them"; },
    };
    const newSig = (item) => ({ item, marks: [], disp: 0.05, lastFire: -1e9, peak: 0, above: null, lastMoment: null });
    const initSigs = () => { S.sig = {}; S.hist = {}; S.watch.forEach((w) => { S.sig[w.code] = newSig(w); S.hist[w.code] = []; }); };
    initSigs();
    let ptr = 0, nextSample = 0, last = performance.now(); const queue = [];

    const base = (item, t) => 0.05 + 0.025 * Math.sin(t * 0.8 + item.slot * 2.1) + 0.015 * Math.sin(t * 1.9 + item.slot);
    function target(sg, t) {
      let best = base(sg.item, t);
      for (const m of sg.marks) {
        const a = t - m.t; if (a < 0) continue;
        const v = a < 0.9 ? m.p * (a / 0.9) : a <= HOLD ? m.p * (1 - 0.25 * (a - 0.9) / (HOLD - 0.9)) : m.p * 0.75 * Math.exp(-(a - HOLD) / 12);
        if (v > best) best = v;
      }
      return best;
    }
    S.stateOf = (code) => {
      const sg = S.sig[code]; if (!sg) return "Quiet"; const a = S.t - sg.lastFire;
      return a < 0 ? "Quiet" : a < 4 ? "Live" : a <= HOLD ? "Holding" : sg.disp > 0.2 ? "Fading" : "Quiet";
    };
    S.levelOf = (code) => (S.sig[code] ? S.sig[code].disp : 0);
    S.highFor = (code) => { const sg = S.sig[code]; return sg && sg.above != null ? S.t - sg.above : null; };

    function fire(m) {
      const sg = S.sig[m.code]; if (!sg) return;
      const mo = { ...m, id: "f" + (++S.seq), t: S.t, quote: S.turns[m.turn].words.slice(m.from, m.to).join(" ") };
      sg.marks.push(mo); sg.lastFire = S.t; sg.peak = m.p; sg.lastMoment = mo; S.moments.push(mo);
      S._fire.forEach((f) => f(mo));
    }
    function schedule(m, i, k) {
      let at = S.t;
      if (S.cadence === "sentence") { const tu = turns[i]; let k2 = k; while (k2 < tu.words.length - 1 && !/[.!?…]$|\]$/.test(tu.words[k2])) k2++; at = tu.wt[k2]; }
      else if (S.cadence === "w5") { const gb = Math.min(flat.length - 1, Math.ceil(ptr / 5) * 5 - 1); at = flat[Math.max(gb, ptr - 1)].t; }
      at += S.lag;
      if (at <= S.t) fire(m); else { queue.push({ m, at }); queue.sort((a, b) => a.at - b.at); }
    }
    function reveal(upto) {
      while (ptr < flat.length && flat[ptr].t <= upto) {
        const { i, k, w, t: wtime } = flat[ptr++]; const tu = turns[i]; S.log.push({ t: wtime, i });
        if (k === 0) S._turn.forEach((f) => f(i, tu));
        S._word.forEach((f) => f(i, k, w, tu));
        for (const m of tu.marks) if (m.to === k + 1 && S.sig[m.code]) schedule(m, i, k);
        const nw = norm(w).toLowerCase();
        for (const item of S.watch) if (item.custom && (!item.side || S.sideOf(tu.speaker) === item.side) && item.kw.some((q) => nw.startsWith(q)) && S.t - S.sig[item.code].lastFire > 6)
          schedule({ turn: i, from: k, to: k + 1, code: item.code, p: 0.72, note: "Keyword match (mock heuristic, not a model)" }, i, k);
      }
    }
    function frame(now) {
      S._raf = requestAnimationFrame(frame);
      const dt = Math.min(0.1, (now - last) / 1000); last = now;
      if (S.playing) {
        S.t += dt * S.speed; reveal(S.t);
        while (queue.length && queue[0].at <= S.t) fire(queue.shift().m);
        if (!S.done && ptr >= flat.length && S.t > S.duration) { S.done = true; S.playing = false; cb.done && cb.done(); }
      }
      const kk = 1 - Math.exp(-dt / 0.18);
      for (const code in S.sig) {
        const sg = S.sig[code]; sg.disp += (target(sg, S.t) - sg.disp) * kk;
        if (sg.disp >= ACT && sg.above == null) sg.above = S.t; else if (sg.disp < 0.6) sg.above = null;
      }
      if (S.playing) while (nextSample <= S.t) {
        for (const code in S.sig) { const hs = S.hist[code]; hs.push([nextSample, S.sig[code].disp]); if (hs.length > 700) hs.shift(); }
        nextSample += 0.2;
      }
      S._frame.forEach((f) => f(dt, S.t));
    }
    S.play = () => { if (S.done) S.restart(); S.playing = true; last = performance.now(); };
    S.pause = () => { S.playing = false; };
    S.toggle = () => { S.playing ? S.pause() : S.play(); return S.playing; };
    S.restart = () => {
      S.playing = false; S.done = false; S.t = 0; ptr = 0; nextSample = 0; S.moments = []; S.seq = 0; queue.length = 0; S.log.length = 0;
      S.watch = scn.watch.map((w, i) => ({ ...w, slot: i })); initSigs(); S._reset.forEach((f) => f()); S._watch.forEach((f) => f());
    };
    S.setSpeed = (x) => { S.speed = x; };
    const chg = () => S._settings.forEach((f) => f());
    S.setModel = (id, lag) => { S.model = id; S.lag = lag; chg(); };
    S.setWin = (n) => { S.win = n; chg(); };
    S.setCadence = (c) => { S.cadence = c; chg(); };
    S.addWatch = (text, o) => {
      text = text.trim(); if (!text) return { ok: false, msg: "Write what to watch for." };
      if (S.watch.length >= S.max) return { ok: false, msg: `${S.max} is the most that stay readable. Remove one first.` };
      const used = new Set(S.watch.map((w) => w.slot)); let slot = 0; while (used.has(slot)) slot++;
      const code = codeOf(text, new Set(S.watch.map((w) => w.code)));
      const item = { code, label: text.length > 26 ? text.slice(0, 25) + "…" : text, prompt: text, slot, custom: true, kw: kwOf(text), side: (o && o.side) || undefined };
      S.watch.push(item); S.sig[code] = newSig(item); S.hist[code] = []; S._watch.forEach((f) => f());
      return { ok: true, item };
    };
    S.removeWatch = (code) => { S.watch = S.watch.filter((w) => w.code !== code); delete S.sig[code]; delete S.hist[code]; S._watch.forEach((f) => f()); };
    S.start = () => { window.__mockClock = () => S.t; last = performance.now(); S._raf = requestAnimationFrame(frame); };
    S.destroy = () => cancelAnimationFrame(S._raf);
    return S;
  }

  /* --------------------------------------------------------------- Glide */
  /* A track that moves up by transform so the newest line stays at the bottom. No scrollTop, no jumps. */
  function Glide(S, view, track, tau) {
    let y = 0, tgt = 0, dirty = true; tau = tau || 0.25;
    const ro = new ResizeObserver(() => { dirty = true; }); ro.observe(track); ro.observe(view);
    const api = { get y() { return y; }, dirty() { dirty = true; }, reset() { y = 0; tgt = 0; track.style.transform = ""; dirty = true; } };
    S.onFrame((dt) => {
      if (dirty) { tgt = Math.max(0, track.offsetHeight - view.clientHeight + 6); dirty = false; }
      y += (tgt - y) * (1 - Math.exp(-dt / tau)); if (Math.abs(tgt - y) < 0.05) y = tgt;
      track.style.transform = `translate3d(0,${-y.toFixed(2)}px,0)`;
      (window.__glideY = window.__glideY || {})[view.id || "g"] = y;
    });
    return api;
  }

  /* --------------------------------------------------------------- Stack */
  /* Absolutely positioned cards moved by transform: adding or removing never reflows its neighbours. */
  function Stack(S, root, gap) {
    gap = gap == null ? 8 : gap; const items = []; root.style.position = "relative"; root.style.overflow = "hidden"; root.classList.add("stackroot");
    const layout = () => { let y = 0; for (const it of items) { if (it.leaving) continue; it.h = it.el.offsetHeight; it.ty = y; y += it.h + gap; } };
    new ResizeObserver(layout).observe(root);
    const api = {
      items,
      add(el, o) {
        o = o || {}; el.style.cssText += ";position:absolute;left:0;right:0;top:0;opacity:0;will-change:transform,opacity";
        root.append(el); const it = { el, h: el.offsetHeight, y: -(el.offsetHeight + gap), ty: 0, o: 0, leaving: false, data: o.data };
        items.unshift(it); layout(); return it;
      },
      remove(it) { it.leaving = true; it.ty = it.y - 12; setTimeout(() => { el_remove(it); layout(); }, 420); layout(); },
      visible() { const H = root.clientHeight; return items.filter((it) => !it.leaving && it.ty + it.h <= H + 2 && it.o > 0.5); },
      clear() { items.splice(0).forEach((it) => it.el.remove()); },
      hiddenCount() { const H = root.clientHeight; return items.filter((it) => !it.leaving && it.ty + it.h > H + 2).length; },
    };
    const el_remove = (it) => { const i = items.indexOf(it); if (i >= 0) items.splice(i, 1); it.el.remove(); };
    S.onFrame((dt) => {
      const k = 1 - Math.exp(-dt / 0.17), H = root.clientHeight;
      for (const it of items) {
        it.y += (it.ty - it.y) * k;
        const want = it.leaving ? 0 : it.ty + it.h > H + 2 ? 0 : 1; it.o += (want - it.o) * k * 1.3;
        it.el.style.transform = `translate3d(0,${it.y.toFixed(1)}px,0)`; it.el.style.opacity = it.o.toFixed(3);
      }
    });
    return api;
  }

  /* ------------------------------------------------------------- Moments */
  /* Flagged moments: each stays hot for HOLD sim seconds, then cools but stays until dismissed. */
  function Moments(S, root, opt) {
    opt = opt || {}; const st = Stack(S, root, opt.gap == null ? 8 : opt.gap); const cards = [];
    const lead = (m) => (opt.speaker ? S.turns[m.turn].speaker.replace(/ \(.*\)/, "") + " · " : "") + (m.p >= 0.85 ? "strong · " : m.p >= 0.65 ? "likely · " : "weak · ") + m.note;
    const quote = (m) => "“" + m.quote.replace(/[.,!?;:]+$/, "") + "”";
    S.onFire((m) => {
      const item = S.watch.find((w) => w.code === m.code) || { slot: 0 };
      if (opt.filter && !opt.filter(m, item)) return;
      if (opt.merge) {
        const c = cards.find((c) => c.m.code === m.code && S.t - c.m.t < opt.merge);
        if (c) { c.n++; c.m = m; c.q.textContent = quote(m); c.note.textContent = lead(m); c.cnt.textContent = "×" + c.n; c.el.setAttribute("data-flag", c.el.getAttribute("data-flag") + " " + m.id); return; }
      }
      const bar = h("i"), age = h("span", { class: "age num" }, "0:00 ago"), pin = h("button", { class: "btn ghost", "aria-pressed": "false" }, "Pin");
      const q = h("span", { class: "q" }, quote(m)), note = h("span", { class: "n" }, lead(m)), cnt = h("span", { class: "cnt" });
      const el = h("article", { class: "moment", style: cvar(item.slot), "data-flag": m.id },
        h("div", { class: "mh" }, h("span", { class: "code" }, m.code), cnt, q, age),
        h("div", { class: "ft" }, note, pin, h("button", { class: "btn ghost", onclick: () => dismiss(card) }, "Done")),
        h("div", { class: "hold", "aria-hidden": "true" }, bar));
      const card = { m, n: 1, el, bar, age, q, note, cnt, pinned: false, lastAge: "", it: null };
      pin.addEventListener("click", () => { card.pinned = !card.pinned; pin.setAttribute("aria-pressed", String(card.pinned)); el.classList.toggle("pinned", card.pinned); pin.textContent = card.pinned ? "Pinned" : "Pin"; });
      card.it = st.add(el); cards.push(card);
    });
    const dismiss = (card) => { st.remove(card.it); const i = cards.indexOf(card); if (i >= 0) cards.splice(i, 1); };
    S.onReset(() => { st.clear(); cards.length = 0; });
    S.onFrame(() => {
      for (const c of cards) {
        const a = S.t - c.m.t, hot = a < HOLD || c.pinned;
        c.bar.style.transform = `scaleX(${c.pinned ? 1 : clamp(1 - a / HOLD, 0, 1).toFixed(3)})`;
        const txt = mmss(a) + " ago"; if (txt !== c.lastAge) { c.age.textContent = txt; c.lastAge = txt; }
        if (c.el.classList.contains("cool") === hot) c.el.classList.toggle("cool", !hot);
      }
      if (opt.more) { const n = st.hiddenCount(); const t = n ? `+${n} earlier` : ""; if (opt.more.textContent !== t) opt.more.textContent = t; }
    });
    return st;
  }

  /* ------------------------------------------------------------- Signals */
  function Signals(S, root, opt) {
    let rows = {}; const flt = (opt && opt.filter) || (() => true);
    const G = { Live: "●", Holding: "◐", Fading: "○", Quiet: "–" };
    function build() {
      rows = {}; root.replaceChildren();
      for (const w of S.watch.filter(flt)) {
        const bar = h("i"), st = h("span", { class: "st num" }), foot = h("span"), pct = h("span", { class: "num" }, "5%");
        const el = h("div", { class: "sig quiet", style: cvar(w.slot), title: w.prompt, "data-side": w.side || null },
          h("div", { class: "top" }, h("span", { class: "code" }, w.code), h("span", { class: "lab" }, w.label), st),
          h("div", { class: "meter", role: "img", "aria-label": w.label + " level" }, bar, h("b")),
          h("div", { class: "foot" }, foot, pct));
        rows[w.code] = { el, bar, st, foot, pct, cache: {} }; root.append(el);
      }
    }
    build(); S.onWatch(build);
    S.onFrame(() => {
      for (const w of S.watch.filter(flt)) {
        const r = rows[w.code], sg = S.sig[w.code]; if (!r) continue;
        r.bar.style.transform = `scaleX(${clamp(sg.disp, 0, 1).toFixed(3)})`;
        const stt = S.stateOf(w.code), hf = S.highFor(w.code);
        const st = `${G[stt]} ${stt.toUpperCase()}`, pct = Math.round(sg.disp * 100) + "%";
        const foot = hf != null ? `▲ high for ${mmss(hf)}` : sg.lastMoment ? `${mmss(S.t - sg.lastFire)} since last · peak ${Math.round(sg.lastMoment.p * 100)}%` : "nothing heard yet";
        if (r.cache.st !== st) { r.st.textContent = st; r.cache.st = st; }
        if (r.cache.foot !== foot) { r.foot.textContent = foot; r.cache.foot = foot; }
        if (r.cache.pct !== pct) { r.pct.textContent = pct; r.cache.pct = pct; }
        const hot = sg.disp >= ACT; if (r.cache.hot !== hot) { r.el.classList.toggle("hot", hot); r.cache.hot = hot; }
        const q = stt === "Quiet"; if (r.cache.q !== q) { r.el.classList.toggle("quiet", q); r.cache.q = q; }
      }
    });
    root.addEventListener("mouseover", (e) => { const s = e.target.closest(".sig"); const code = s && Object.keys(rows).find((k) => rows[k].el === s); S.focus = code || null; });
    root.addEventListener("mouseleave", () => { S.focus = null; });
    return { rows: () => rows };
  }

  /* --------------------------------------------------------------- Chart */
  /* Rolling chart: x is call time, so the plot scrolls continuously. Lines 2px, end dots with surface ring, direct labels. */
  function Chart(S, canvas, o) {
    o = o || {}; const win = o.window || 60, ctx = canvas.getContext("2d"); let W = 0, H = 0, dpr = 1, colors = [], css = {}, cAt = 0, mx = null;
    const series = o.series || (() => S.watch.map((w) => ({ id: w.code, slot: w.slot, samples: S.hist[w.code] || [], live: S.levelOf(w.code), area: false })));
    const ro = new ResizeObserver(() => { dpr = devicePixelRatio || 1; W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = W * dpr; canvas.height = H * dpr; }); ro.observe(canvas);
    canvas.addEventListener("mousemove", (e) => { mx = e.clientX - canvas.getBoundingClientRect().left; });
    canvas.addEventListener("mouseleave", () => { mx = null; });
    const readCss = () => { const cs = getComputedStyle(document.documentElement); colors = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => cs.getPropertyValue("--s" + i).trim());
      css = { line: cs.getPropertyValue("--line").trim(), ink2: cs.getPropertyValue("--ink-2").trim(), ink3: cs.getPropertyValue("--ink-3").trim(), surf: cs.getPropertyValue("--surface").trim(), act: cs.getPropertyValue("--act").trim(), ink: cs.getPropertyValue("--ink").trim(), mono: cs.getPropertyValue("--mono").trim() }; };
    const at = (s, tt) => { let lo = 0, hi = s.length - 1; if (!s.length) return 0; while (lo < hi) { const m = (lo + hi) >> 1; if (s[m][0] < tt) lo = m + 1; else hi = m; } return s[lo][1]; };
    S.onFrame(() => {
      if (!W || !H) return; const now = performance.now(); if (now - cAt > 500) { readCss(); cAt = now; }
      const t = S.t, pad = { l: 34, r: 46, t: 8, b: 20 }, pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
      const x = (tt) => pad.l + pw - ((t - tt) / win) * pw, y = (v) => pad.t + ph * (1 - v);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H); ctx.lineWidth = 1; ctx.font = `10px ${css.mono}`;
      ctx.strokeStyle = css.line; ctx.fillStyle = css.ink3; ctx.textBaseline = "middle";
      for (const v of [0, 0.5, 1]) { ctx.beginPath(); ctx.moveTo(pad.l, Math.round(y(v)) + .5); ctx.lineTo(W - pad.r, Math.round(y(v)) + .5); ctx.stroke(); ctx.textAlign = "right"; ctx.fillText(Math.round(v * 100) + "%", pad.l - 6, y(v)); }
      ctx.strokeStyle = css.act; ctx.globalAlpha = .5; ctx.beginPath(); ctx.moveTo(pad.l, Math.round(y(ACT)) + .5); ctx.lineTo(W - pad.r, Math.round(y(ACT)) + .5); ctx.stroke(); ctx.globalAlpha = 1;
      ctx.textAlign = "right"; ctx.fillStyle = css.ink; ctx.fillText("act", pad.l - 6, y(ACT));
      ctx.textBaseline = "top"; ctx.fillStyle = css.ink3; ctx.textAlign = "center";
      for (let tt = Math.max(0, Math.ceil((t - win) / 15) * 15); tt <= t; tt += 15) { const xx = x(tt); if (xx > pad.l + 14 && xx < W - pad.r - 34) ctx.fillText(mmss(tt), xx, H - pad.b + 5); }
      ctx.textAlign = "right"; ctx.fillText("now", W - pad.r, H - pad.b + 5);
      ctx.save(); ctx.beginPath(); ctx.rect(pad.l, 0, pw + 1, H); ctx.clip();
      const ss = series(), labels = [];
      for (const s of ss) {
        const dim = (S.focus && S.focus !== s.id) ? 0.22 : 1, col = s.slot < 0 ? css.ink : (colors[s.slot % 8] || "#888"), pts = [];
        for (const p of s.samples) if (p[0] >= t - win - 1) pts.push([x(p[0]), y(p[1])]);
        pts.push([x(t), y(s.live)]); if (pts.length < 2) continue;
        ctx.globalAlpha = dim; ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.lineCap = "round";
        const path = new Path2D(); path.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length - 1; i++) path.quadraticCurveTo(pts[i][0], pts[i][1], (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2);
        path.lineTo(pts[pts.length - 1][0], pts[pts.length - 1][1]);
        if (s.area || S.focus === s.id) { const a = new Path2D(path); a.lineTo(pts[pts.length - 1][0], y(0)); a.lineTo(pts[0][0], y(0)); ctx.globalAlpha = dim * 0.1; ctx.fillStyle = col; ctx.fill(a); ctx.globalAlpha = dim; }
        ctx.setLineDash(s.dash || []); ctx.stroke(path); ctx.setLineDash([]); labels.push({ s, col, dim, yy: y(s.live), xx: x(t) });
      }
      ctx.restore(); ctx.globalAlpha = 1;
      labels.sort((a, b) => a.yy - b.yy); let prev = -99; ctx.textBaseline = "middle"; ctx.textAlign = "left";
      for (const l of labels) {
        ctx.globalAlpha = l.dim; ctx.fillStyle = css.surf; ctx.beginPath(); ctx.arc(l.xx, l.yy, 6, 0, 7); ctx.fill(); ctx.fillStyle = l.col; ctx.beginPath(); ctx.arc(l.xx, l.yy, 4, 0, 7); ctx.fill();
        const ly = Math.max(l.yy, prev + 12); prev = ly; ctx.fillStyle = css.ink2; ctx.fillText(l.s.short || l.s.id, l.xx + 9, ly);
      }
      ctx.globalAlpha = 1;
      if (mx != null && mx > pad.l && mx < W - pad.r) {
        const tt = t - ((W - pad.r - mx) / pw) * win; ctx.strokeStyle = css.ink3; ctx.beginPath(); ctx.moveTo(mx + .5, pad.t); ctx.lineTo(mx + .5, H - pad.b); ctx.stroke();
        const rows = ss.map((s) => ({ id: s.short || s.id, v: at(s.samples, tt), slot: s.slot })).sort((a, b) => b.v - a.v).slice(0, 6), bw = 104, bh = 18 + rows.length * 14;
        const bx = mx > W / 2 ? mx - bw - 8 : mx + 8; ctx.fillStyle = css.surf; ctx.strokeStyle = css.line; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(bx, pad.t + 2, bw, bh, 6); ctx.fill(); ctx.stroke();
        ctx.textBaseline = "top"; ctx.fillStyle = css.ink3; ctx.textAlign = "left"; ctx.fillText(mmss(tt), bx + 8, pad.t + 7);
        rows.forEach((r, i) => { const yy = pad.t + 21 + i * 14; ctx.fillStyle = r.slot < 0 ? css.ink : colors[r.slot % 8]; ctx.fillRect(bx + 8, yy + 2, 8, 8); ctx.fillStyle = css.ink2; ctx.fillText(`${r.id}  ${Math.round(r.v * 100)}%`, bx + 21, yy); });
      }
    });
    return { series };
  }


  /* ---------------------------------------------------------- Transcript */
  /* build(i, turn) -> {el, words, margin?}. Words fade in; the track glides; fires highlight the phrase and add a margin tag. */
  function Transcript(S, view, track, o) {
    const glide = Glide(S, view, track, o.tau), rows = [], spans = [], caret = h("span", { class: "caret" });
    S.onReset(() => { track.replaceChildren(); rows.length = 0; spans.length = 0; glide.reset(); });
    S.onTurn((i, tu) => { const r = o.build(i, tu); r.spans = []; rows[i] = r; track.append(r.el); glide.dirty(); });
    S.onWord((i, k, w) => {
      const r = rows[i], sp = h("span", { class: "w" }, w); r.spans[k] = sp; spans.push(sp);
      r.words.append(document.createTextNode(k ? " " : ""), sp, caret); glide.dirty(); if (o.onWord) o.onWord(i, k, sp);
    });
    S.onFire((m) => {
      const r = rows[m.turn]; if (!r) return; const item = S.watch.find((w) => w.code === m.code) || { slot: 0 };
      if (o.phrase) {
        const a = r.spans[m.from], b = r.spans[m.to - 1];
        if (a && b && a.parentNode === b.parentNode) {
          const wrap = h("span", { class: "ph", style: cvar(item.slot), "data-code": o.codes === false ? null : m.code }); a.parentNode.insertBefore(wrap, a);
          for (let n = a; n;) { const nx = n.nextSibling; wrap.append(n); if (n === b) break; n = nx; }
        }
      } else for (let k = m.from; k < m.to; k++) { const sp = r.spans[k]; if (sp) { sp.classList.add("hl"); sp.setAttribute("style", cvar(item.slot)); } }
      if (o.tag && r.margin) { r.margin.append(o.tag(m, item)); glide.dirty(); }
    });
    S.onFrame(() => { if (S.done && caret.isConnected) caret.remove(); });
    return { rows, spans, glide };
  }

  /* ---------------------------------------------------------- misc pieces */
  function Wave(S, canvas) {
    const ctx = canvas.getContext("2d"); const hist = new Array(200).fill(0); let level = 0, acc = 0, color = "#6b8afd", cAt = 0;
    S.onWord(() => { level = 0.35 + Math.random() * 0.65; });
    S.onFrame((dt) => {
      const W = canvas.clientWidth, H = canvas.clientHeight, dpr = devicePixelRatio || 1; if (canvas.width !== Math.round(W * dpr)) { canvas.width = W * dpr; canvas.height = H * dpr; }
      if (performance.now() - cAt > 500) { color = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim(); cAt = performance.now(); }
      acc += dt; if (acc > 0.03) { acc = 0; hist.push(level * (S.playing ? 1 : 0)); hist.shift(); } level *= Math.pow(0.02, dt);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H); ctx.fillStyle = color;
      const bw = W / hist.length; hist.forEach((v, i) => { const bh = Math.max(2, v * H * 0.9); ctx.globalAlpha = 0.35 + 0.65 * (i / hist.length); ctx.fillRect(i * bw, (H - bh) / 2, Math.max(1, bw * 0.6), bh); }); ctx.globalAlpha = 1;
    });
  }

  function Controls(S, extra) {
    const play = h("button", { class: "btn primary", onclick: () => { S.toggle(); sync(); } }, "Play");
    const sync = () => { play.textContent = S.playing ? "Pause" : S.done || S.t > 0 ? "Resume" : "Play"; };
    S.onFrame(() => { const t = S.playing ? "Pause" : S.t > 0 && !S.done ? "Resume" : "Play"; if (play.textContent !== t) play.textContent = t; });
    const speed = h("select", { class: "pick", "aria-label": "Speed", onchange: (e) => S.setSpeed(+e.target.value) }, [["0.6", "0.6x"], ["1", "1x"], ["2", "2x"], ["4", "4x"]].map(([v, t]) => h("option", { value: v, selected: v === "1" }, t)));
    const rs = h("button", { class: "btn", onclick: () => { S.restart(); sync(); } }, "Restart");
    if (window.__spaceH) document.removeEventListener("keydown", window.__spaceH);
    window.__spaceH = (e) => { if (e.code === "Space" && !/INPUT|TEXTAREA|SELECT|BUTTON/.test(document.activeElement.tagName)) { e.preventDefault(); S.toggle(); } };
    document.addEventListener("keydown", window.__spaceH);
    return h("div", { class: "controls" }, play, rs, speed, extra);
  }
  function LivePill(S) {
    const t = h("span", { class: "num" }, "00:00"), pill = h("span", { class: "pill" }, h("span", { class: "rec" }), h("span", null, "LIVE"), t);
    S.onFrame(() => { const s = mmss(S.t); if (t.textContent !== s) t.textContent = s; pill.classList.toggle("on", S.playing); });
    return pill;
  }
  function Picker(current, onPick) {
    const sel = h("select", { class: "pick", "aria-label": "Scenario" }, all().map((s) => h("option", { value: s.id, selected: s.id === current.id }, s.title)));
    sel.addEventListener("change", () => onPick(byId(sel.value))); return sel;
  }
  function Banner(scn) { return h("div", { class: "banner" }, h("b", null, "MOCK-UP"), " Scripted playback: no audio, no speech-to-text, no model calls. ", scn.blurb); }

  /* Watch editor: one bar. Chips + add box. Adding is allowed mid-call; space is reserved so nothing moves. */
  function WatchEditor(S, root, o) {
    o = o || {}; const input = h("input", { type: "text", id: "watch-in", placeholder: o.placeholder || "Add something to watch for, in a sentence", "aria-label": "What to watch for" });
    const note = h("div", { class: "note" }), chips = h("div", { class: "chips" });
    const add = () => { const r = S.addWatch(input.value); note.textContent = r.ok ? `Added ${r.item.code}. Mock: fires on keyword overlap; the real build asks Jev.` : r.msg; if (r.ok) input.value = ""; };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
    const draw = () => chips.replaceChildren(...S.watch.map((w) => h("span", { class: "code chip", style: cvar(w.slot), title: w.prompt }, w.code + " " + w.label, h("button", { class: "x", "aria-label": "Remove " + w.code, onclick: () => S.removeWatch(w.code) }, "×"))));
    draw(); S.onWatch(draw);
    root.classList.add("wbar"); root.append(h("span", { class: "wl" }, "Watching for"), chips, h("div", { class: "wadd" }, input, h("button", { class: "btn", onclick: add }, "Add")), note);
  }

  /* Flags currently visible on screen, for tools/measure.py (data-flag elements not clipped or faded). */
  window.__mockFlags = (sel) => {
    const out = {}, vh = innerHeight;
    document.querySelectorAll(sel || "[data-flag]").forEach((el) => {
      const r = el.getBoundingClientRect(); if (!r.width || !r.height || r.bottom < 0 || r.top > vh) return;
      if (+(getComputedStyle(el).opacity) < 0.5) return;
      const clip = el.closest(".glide,.stackroot"); if (clip) { const c = clip.getBoundingClientRect(); if (r.top < c.top || r.bottom > c.bottom + 2) return; }
      for (const id of el.getAttribute("data-flag").split(" ")) out[id] = window.__mockClock ? window.__mockClock() : 0;
    });
    return out;
  };

  /* deterministic pseudo-random + mock model score (page 4) */
  function rnd(seed) { let x = 0; for (const c of String(seed)) x = (x * 31 + c.charCodeAt(0)) >>> 0; x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return (x % 1000) / 1000; }
  function mockScore(scn, turns, t, endWord, code, win, model) {
    let words = 0, best = 0;
    for (let i = t; i >= 0 && words < win; i--) {
      const upto = i === t ? endWord : turns[i].words.length;
      for (const m of turns[i].marks) { if (m.code !== code || m.to > upto) continue; const dist = words + (upto - m.to); if (dist < win) best = Math.max(best, m.p * (1 - 0.25 * dist / win)); }
      words += upto;
    }
    const j = (rnd(`${scn.id}${t}${endWord}${code}${model || ""}`) - 0.5) * (model === "SEMIF4" ? 0.16 : model === "KEV4B" ? 0.12 : 0.06);
    return clamp((best || 0.06 + rnd(`n${code}${t}${endWord}`) * 0.1) + j * (best ? 1 : 0.4), 0.02, 0.99);
  }

  window.Mock = { h, all, byId, prepare, Session, Glide, Stack, Moments, Signals, Chart, Transcript, Wave, Controls, LivePill, Picker, Banner, WatchEditor, cvar, mmss, clamp, mockScore, rnd, ACT, HOLD };
})();
