/* Call cockpit variants: shared pieces on top of ../mock.js. Everything scripted (MOCK) except the timing-derived
   talk share and pace, which are computed from the playback clock. DOM is built with textContent only. */
(function () {
  const { h, cvar, mmss, clamp } = Mock;
  const MODELS = [
    { id: "SEMIF4", name: "SemIf", kind: "local", meta: "local GPU · loaded", lag: 1.8 },
    { id: "KEV4B", name: "kev 4B", kind: "local", meta: "local GPU · loaded", lag: 1.1 },
    { id: "JEV113", name: "Jev 1.13.0", kind: "hosted", meta: "hosted · billed per token · asks first", lag: 0.3 }];
  const WINS = [5, 10, 20, 40];
  const initials = (n) => { const w = n.replace(/\(.*\)/, "").trim().split(/\s+/); return ((w[0][0] || "") + (w[1] ? w[1][0] : w[0][1] || "")).toUpperCase(); };
  const $ = (id) => document.getElementById(id);
  const short = (n) => n.replace(/ \(.*\)/, "");

  /* estimated cost of a check: ~160 tokens per question (9 questions is about 1,450 tokens) plus the window text */
  function estimate(S) {
    const tokens = Math.round(S.watch.length * 160 + S.win * 1.3), perMin = S.cadence === "sentence" ? 13 : 31;
    const cost = S.model === "JEV113" ? `about $${(tokens * perMin * 0.042 / 1e6).toFixed(4)} per call minute (estimate at $0.042 per million tokens)` : "free: runs on this machine";
    return { tokens, cost };
  }

  function seg(items, cur, on, label) {
    return h("span", { class: "seg", role: "group", "aria-label": label }, items.map(([v, t]) => h("button", { "aria-pressed": String(v === cur), onclick: () => on(v) }, t)));
  }

  /* model, window and cadence controls. compact = one row (chips); full = cards with lag bars */
  function ModelControls(S, root, compact) {
    let pending = null;
    const draw = () => {
      root.replaceChildren();
      const est = estimate(S);
      const setM = (m) => { if (m.kind === "hosted" && S.model !== m.id) { pending = m; draw(); } else { pending = null; S.setModel(m.id, m.lag); } };
      const win = seg(WINS.map((n) => [n, n + (compact ? "" : " words")]), S.win, (n) => S.setWin(n), "Window per person");
      const cad = seg([["sentence", "each sentence"], ["w5", "every 5 words"]], S.cadence, (c) => S.setCadence(c), "How often to score");
      const confirm = !pending ? document.createComment("") : h("div", { class: "confirm" }, h("div", null, `${pending.id} runs on the hosted API and is billed per token, about $${(estimate({ ...S, model: "JEV113", watch: S.watch, win: S.win, cadence: S.cadence }).tokens * (S.cadence === "sentence" ? 13 : 31) * 0.042 / 1e6).toFixed(4)} per call minute at these settings. Use it for this call?`),
        h("div", { class: "row" }, h("button", { class: "btn primary", onclick: () => { const m = pending; pending = null; S.setModel(m.id, m.lag); } }, "Use " + pending.id), h("button", { class: "btn", onclick: () => { pending = null; draw(); } }, "Keep " + S.model)));
      if (compact) {
        root.append(h("div", { class: "mchips" },
          h("span", { class: "seg", role: "radiogroup", "aria-label": "Model" }, MODELS.map((m) => h("button", { role: "radio", "aria-checked": String(m.id === S.model), "aria-pressed": String(m.id === S.model), title: m.meta, onclick: () => setM(m) }, m.id + " " + m.lag.toFixed(1) + "s"))),
          h("span", { class: "l" }, "Window"), win, h("span", { class: "l" }, "Score"), cad),
          confirm, h("div", { class: "est" }, `~${est.tokens} tokens a check · ${est.cost}`));
        return;
      }
      root.append(h("div", { class: "mlist", role: "radiogroup", "aria-label": "Model" }, MODELS.map((m) => {
        const bar = h("i", { style: `transform:scaleX(${(m.lag / 2).toFixed(2)})` });
        return h("button", { class: "mcard", role: "radio", "aria-checked": String(m.id === S.model), onclick: () => setM(m) },
          h("span", { class: "code" }, m.id), h("span", { class: "nm" }, m.name, h("span", { class: "meta" }, m.meta)), h("span", { class: "lg" }, h("span", { class: "pb" }, bar), h("span", { class: "num" }, "~" + m.lag.toFixed(1) + " s")));
      })), confirm,
      h("div", { class: "opt" }, h("span", { class: "l" }, "Window, per person"), win),
      h("div", { class: "opt" }, h("span", { class: "l" }, "Score"), cad),
      h("div", { class: "est" }, `~${est.tokens} tokens a check for ${S.watch.length} questions · ${est.cost}`),
      h("div", { class: "hint" }, "In this mock the model sets when a highlight lands (its typical lag) and the window sets which words are bright. Scores are scripted; the real models would change them."));
    };
    draw(); S.onSettings(draw); S.onWatch(draw); return { draw };
  }

  function boot(opts) {
    opts = opts || {}; let S, cfg = { model: "KEV4B", lag: 1.1, win: 20, cadence: "sentence" };
    const list = window.MockCockpit;
    function load(scn) {
      if (S) S.destroy();
      ["track", "wbar", "lane-them", "lane-us", "sigs", "moms", "moms-us", "facts", "balance", "checklist", "model", "banner", "pill", "ctl", "modelpop"].forEach((id) => { const e = $(id); if (e) e.replaceChildren(); });
      for (const sel of ["#ch canvas", "#wave"]) { const c = document.querySelector(sel); if (c) c.replaceWith(c.cloneNode()); }
      S = Mock.Session(scn); S.max = 8; S.model = cfg.model; S.lag = cfg.lag; S.win = cfg.win; S.cadence = cfg.cadence;
      S.onSettings(() => { cfg = { model: S.model, lag: S.lag, win: S.win, cadence: S.cadence }; pill(); });
      $("banner").append(h("span", { class: "pill mock", title: "MOCK-UP. Scripted playback: no audio, no speech-to-text, no model calls; only talk share and pace are computed. " + scn.blurb }, "MOCK-UP · scripted"));
      $("pill").append(Mock.LivePill(S)); $("ctl").append(Mock.Controls(S));
      Mock.Wave(S, $("wave"));
      const mp = $("modelpill"), mb = $("modelbtn"), pill = () => { const t = `${S.model} · ${S.lag.toFixed(1)} s · ${S.win} words`; if (mp) mp.textContent = t; if (mb) mb.textContent = "Model: " + t + " ▾"; }; pill();

      /* watch bar with a Them / Us choice */
      const wb = $("wbar"); let side = "them";
      const input = h("input", { type: "text", id: "watch-in", placeholder: "Add something to watch for, in a sentence", "aria-label": "What to watch for" }), note = h("div", { class: "note" }), chips = h("div", { class: "chips" });
      const sideSeg = h("span", { class: "seg", role: "group", "aria-label": "Whose words" });
      const drawSide = () => sideSeg.replaceChildren(...[["them", "Them"], ["us", "Us"]].map(([v, t]) => h("button", { "aria-pressed": String(v === side), onclick: () => { side = v; drawSide(); } }, t)));
      drawSide();
      let nt = 0; const say = (t) => { note.textContent = t; clearTimeout(nt); nt = setTimeout(() => { note.textContent = ""; }, 4500); };
      const add = () => { const r = S.addWatch(input.value, { side }); say(r.ok ? `Added ${r.item.code} for ${side === "us" ? "our" : "their"} words. Mock: fires on keyword overlap; the real build asks Jev.` : r.msg); if (r.ok) input.value = ""; };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
      const drawChips = () => chips.replaceChildren(...S.watch.map((w) => h("span", { class: "code chip", style: cvar(w.slot), title: w.prompt + " (" + (w.side === "us" ? "our words" : "their words") + ")" }, (w.side === "us" ? "U " : "T ") + w.code, h("button", { class: "x", "aria-label": "Remove " + w.code, onclick: () => S.removeWatch(w.code) }, "×"))));
      drawChips(); S.onWatch(drawChips);
      wb.classList.add("wbar"); wb.append(h("span", { class: "wl" }, "Watching for"), chips, h("div", { class: "wadd" }, input, sideSeg, h("button", { class: "btn", onclick: add }, "Add")), note);

      /* conversation as a message thread; each person keeps their own reading window */
      const bySpk = {}, applied = {}, people = {};
      const readAll = () => { for (const k in bySpk) { const a = bySpk[k], lim = Math.max(0, a.length - S.win); a.forEach((sp, i) => sp.classList.toggle("out", i < lim)); applied[k] = lim; } };
      S.onSettings(readAll); S.onReset(() => { for (const k in bySpk) delete bySpk[k]; for (const k in applied) delete applied[k]; });
      Mock.Transcript(S, $("view"), $("track"), {
        phrase: true, codes: opts.codes !== false,
        build(i, tu) {
          const sd = S.sideOf(tu.speaker), n = people[tu.speaker] = people[tu.speaker] || Object.keys(people).length + 1, words = h("div", { class: "words" });
          const av = h("div", { class: "av", style: `--av:hsl(215 ${sd === "us" ? 0 : 6}% ${sd === "us" ? 30 : 34 + n * 7}%)`, "aria-hidden": "true" }, initials(tu.speaker));
          return { words, el: h("div", { class: "msg " + sd, "data-spk": tu.speaker }, av, h("div", { class: "bub" }, h("div", { class: "who" }, h("span", null, tu.speaker), h("span", { class: "ts num" }, mmss(tu.t0))), h("div", { class: "txt" }, h("div", { class: "ghost", "aria-hidden": "true" }, tu.text), words))) };
        },
        onWord(i, k, sp) { const spk = S.turns[i].speaker, a = (bySpk[spk] = bySpk[spk] || []); a.push(sp); let b = applied[spk] || 0; const lim = Math.max(0, a.length - S.win); for (; b < lim; b++) a[b].classList.add("out"); applied[spk] = b; },
      });
      const rd = $("readnote"); if (rd) { const t = () => { rd.textContent = `Bright text is what the model reads: the last ${S.win} words of each person.`; }; t(); S.onSettings(t); }
      S.onReset(() => { people && Object.keys(people).forEach((k) => delete people[k]); });

      /* signals */
      const bySide = (sd) => (w) => w.side === sd;
      if ($("lane-them")) { Mock.Signals(S, $("lane-them"), { filter: bySide("them") }); Mock.Signals(S, $("lane-us"), { filter: bySide("us") }); }
      if ($("sigs")) Mock.Signals(S, $("sigs"), {});
      const who = { them: $("who-them"), us: $("who-us") };
      S.onTurn((i, tu) => { const sd = S.sideOf(tu.speaker); for (const k in who) if (who[k]) who[k].textContent = k === sd ? "● " + short(tu.speaker) : ""; });
      S.onReset(() => { for (const k in who) if (who[k]) who[k].textContent = ""; });

      /* cue cards */
      /* cue cards carry their cues; our own guidance shows in the lanes and the checklist. Repeats of a signal within 12 s merge. */
      Mock.Moments(S, $("moms"), { more: $("more"), speaker: true, merge: 12, gap: 6, filter: (m, it) => it.side !== "us" });

      /* captured facts */
      if ($("facts")) { const fs = Mock.Stack(S, $("facts"), 0); S.onFire((m) => { if (m.fact) fs.add(h("div", { class: "fact", "data-flag": m.id }, h("span", null, m.fact[0]), h("b", null, m.fact[1]), h("span", { class: "by" }, short(S.turns[m.turn].speaker)))); }); S.onReset(() => fs.clear()); const fm = $("fmore"); if (fm) S.onFrame(() => { const n = fs.hiddenCount(), t = n ? `+${n} more` : ""; if (fm.textContent !== t) fm.textContent = t; }); }

      /* our side: checklist and timing-derived balance */
      if ($("checklist")) {
        const rows = {}, box = $("checklist"), prog = $("cprog"); let done = 0;
        (scn.checklist || []).forEach((c) => { const g = h("span", { class: "g" }, "○"), ts = h("span", { class: "ts num" }); rows[c.id] = { g, ts, el: h("div", { class: "ck" }, g, h("span", { class: "t" }, c.label), ts) }; box.append(rows[c.id].el); });
        const upd = () => { if (prog) prog.textContent = `${done} of ${(scn.checklist || []).length} covered`; }; upd();
        S.onFire((m) => { const r = m.check && rows[m.check]; if (r && r.g.textContent !== "✓") { r.g.textContent = "✓"; r.el.classList.add("done"); r.ts.textContent = mmss(m.t); done++; upd(); } });
        S.onReset(() => { done = 0; });
      }
      if ($("balance")) {
        const bar = h("div", { class: "split" }, h("i", { class: "th" }), h("i", { class: "me" })), thI = bar.children[0], meI = bar.children[1];
        const l1 = h("div", { class: "bl num" }), l2 = h("div", { class: "bl num" }), tip = h("div", { class: "tip" });
        $("balance").append(h("div", { class: "bt" }, "Talk share, last 60 s"), bar, l1, h("div", { class: "bt" }, "Pace"), l2, tip);
        let nx = 0; const cache = {};
        S.onFrame(() => {
          if (performance.now() < nx) return; nx = performance.now() + 250;
          let th = 0, me = 0; const lo = S.t - 60; for (let k = S.log.length - 1; k >= 0 && S.log[k].t >= lo; k--) (S.sideOf(S.turns[S.log[k].i].speaker) === "us" ? me++ : th++);
          const tot = th + me, sh = tot ? me / tot : 0, span = Math.max(10, Math.min(60, S.t)), wpm = (n) => Math.round(n * 60 / span);
          thI.style.transform = `scaleX(${tot ? (1 - sh).toFixed(3) : 0.5})`; meI.style.transform = `scaleX(${tot ? sh.toFixed(3) : 0.5})`;
          const t1 = tot ? `THEM ${Math.round((1 - sh) * 100)}% · US ${Math.round(sh * 100)}%` : "waiting for speech", t2 = tot ? `THEM ${wpm(th)} wpm · US ${wpm(me)} wpm` : "";
          const t3 = tot < 20 ? "Listening." : sh > 0.65 ? "We are doing most of the talking. Ask a question." : sh < 0.25 ? "They are doing most of the talking. Listen for cues." : "Balanced.";
          if (cache.a !== t1) { l1.textContent = t1; cache.a = t1; } if (cache.b !== t2) { l2.textContent = t2; cache.b = t2; } if (cache.c !== t3) { tip.textContent = t3; cache.c = t3; }
        });
      }

      /* model controls */
      if ($("model")) ModelControls(S, $("model"), opts.modelMode === "chips");
      if ($("modelpop")) { ModelControls(S, $("modelpop"), false); }

      /* chart: solid = their words, dashed = ours */
      Mock.Chart(S, document.querySelector("#ch canvas"), { window: 60, series: () => S.watch.map((w) => ({ id: w.code, slot: w.slot, samples: S.hist[w.code] || [], live: S.levelOf(w.code), dash: w.side === "us" ? [5, 4] : null })) });
      S.start();
    }
    const sel = h("select", { class: "pick", "aria-label": "Scenario" }, list.map((s) => h("option", { value: s.id }, s.title.replace(/ \(invented script\)/, ""))));
    sel.addEventListener("change", () => load(list.find((s) => s.id === sel.value))); $("pick").append(sel);
    /* popover (variant B) */
    const pb = $("modelbtn"), pp = $("modelpop");
    if (pb && pp) {
      const close = () => { pp.hidden = true; pb.setAttribute("aria-expanded", "false"); };
      pb.addEventListener("click", (e) => { e.stopPropagation(); pp.hidden = !pp.hidden; pb.setAttribute("aria-expanded", String(!pp.hidden)); });
      document.addEventListener("click", (e) => { if (!pp.hidden && !pp.contains(e.target) && e.target !== pb) close(); });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
    }
    /* tab panels inside a card (variant A) */
    document.querySelectorAll("[data-tabs]").forEach((box) => {
      const btns = box.querySelectorAll("[data-for]"), panes = box.querySelectorAll("[data-tabpane]");
      const show = (id) => { btns.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.for === id))); panes.forEach((p) => { p.hidden = p.dataset.tabpane !== id; }); };
      btns.forEach((b) => b.addEventListener("click", () => show(b.dataset.for))); show(btns[0].dataset.for);
    });
    /* phone navigation */
    const stage = $("stage"), nav = $("tabs");
    if (stage && nav) nav.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { stage.dataset.tab = b.dataset.t; nav.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", String(x === b))); }));
    load(list[0]);
    return { get S() { return S; } };
  }
  window.Cockpit = { boot, MODELS };
})();
