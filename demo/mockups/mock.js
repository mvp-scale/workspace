/* Shared mock-up engine. Plays a scripted scenario word by word like a live transcription.
   No network calls. Every annotation is scripted (MOCK). DOM is built with textContent only. */
(function () {
  const h = (tag, props, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") n.className = v;
      else if (k === "style") n.setAttribute("style", v);
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) n.setAttribute(k, v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
    return n;
  };

  const all = () => [window.MockApollo, ...window.MockScenarios].filter(Boolean);
  const byId = (id) => all().find((s) => s.id === id) || all()[0];
  const hueOf = (scn, code) => (scn.watch.find((w) => w.code === code) || { hue: 210 }).hue;
  const chipStyle = (hue) => `--h:${hue}`;

  const norm = (w) => w.replace(/^[.…\[]+|[.,!?;:…\]]+$/g, "");

  /* words of a turn, with each mark resolved to a [from,to) word range */
  function prepare(scn) {
    return scn.turns.map((t, i) => {
      const words = t.text.split(/\s+/);
      const marks = scn.marks.filter((m) => m.turn === i).map((m) => {
        const pw = m.phrase.split(/\s+/);
        for (let s = 0; s + pw.length <= words.length; s++) {
          if (pw.every((w, k) => norm(words[s + k]) === norm(w))) return { ...m, from: s, to: s + pw.length };
        }
        return null;
      }).filter(Boolean);
      return { ...t, words, marks };
    });
  }

  /* Player: wps = words per second. Callbacks: turn, word, mark, checkpoint, done. */
  function Player(scn, cb) {
    const turns = prepare(scn);
    const st = { paused: true, speed: 1, gen: 0, wps: 3.2, t: 0, w: 0, total: 0, started: false };
    let timer = null;
    const isEnd = (w) => /[.!?…]$|\.\.\.$|\]$/.test(w);

    function step(gen) {
      if (gen !== st.gen || st.paused) return;
      if (st.t >= turns.length) { cb.done && cb.done(); return; }
      const turn = turns[st.t];
      if (st.w === 0) cb.turn && cb.turn(st.t, turn);
      const w = turn.words[st.w];
      st.w++; st.total++;
      cb.word && cb.word(st.t, st.w - 1, w, turn);
      for (const m of turn.marks) if (m.to === st.w) cb.mark && cb.mark(m, st.t, turn);
      let delay = 1000 / (st.wps * st.speed);
      const last = st.w >= turn.words.length;
      if (isEnd(w) || last) {
        cb.checkpoint && cb.checkpoint(st.t, st.w, turn, turns);
        delay += 260 / st.speed;
      }
      if (last) { st.t++; st.w = 0; delay += 620 / st.speed; }
      if (/,$/.test(w)) delay += 90 / st.speed;
      timer = setTimeout(() => step(gen), delay);
    }
    return {
      turns, state: st,
      play() { if (!st.paused && st.started) return; st.paused = false; st.started = true; step(++st.gen); },
      pause() { st.paused = true; st.gen++; clearTimeout(timer); },
      toggle() { st.paused ? this.play() : this.pause(); return !st.paused; },
      restart() { this.pause(); st.t = 0; st.w = 0; st.total = 0; st.started = false; cb.reset && cb.reset(); },
      speed(x) { st.speed = x; },
    };
  }

  /* deterministic pseudo-random for mock scores */
  function rnd(seed) { let x = 0; for (const c of String(seed)) x = (x * 31 + c.charCodeAt(0)) >>> 0; x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return (x % 1000) / 1000; }

  /* MOCK score for a watch code at a checkpoint: high if a mark for that code ended inside the last `win` words, else low noise. */
  function mockScore(scn, turns, t, endWord, code, win, model) {
    let words = 0, best = 0;
    for (let i = t; i >= 0 && words < win; i--) {
      const upto = i === t ? endWord : turns[i].words.length;
      for (const m of turns[i].marks) {
        if (m.code !== code || m.to > upto) continue;
        const dist = words + (upto - m.to);
        if (dist < win) best = Math.max(best, m.p * (1 - 0.25 * dist / win));
      }
      words += upto;
    }
    const jitter = (rnd(`${scn.id}${t}${endWord}${code}${model || ""}`) - 0.5) * (model === "SEMIF4" ? 0.16 : model === "KEV4B" ? 0.12 : 0.06);
    return Math.max(0.02, Math.min(0.99, (best || 0.06 + rnd(`n${code}${t}${endWord}`) * 0.1) + jitter * (best ? 1 : 0.4)));
  }

  function bar(p, hue) {
    return h("span", { class: "bar", style: chipStyle(hue) }, h("i", { style: `width:${Math.round(p * 100)}%` }));
  }
  function conf(p) { return p >= 0.85 ? "strong" : p >= 0.65 ? "likely" : "weak"; }

  function scenarioPicker(current, onPick) {
    const sel = h("select", { class: "pick", "aria-label": "Scenario" },
      all().map((s) => h("option", { value: s.id, selected: s.id === current.id }, s.title)));
    sel.addEventListener("change", () => onPick(byId(sel.value)));
    return sel;
  }

  function mockBanner(scn) {
    return h("div", { class: "banner" },
      h("b", null, "MOCK-UP. "), "Scripted playback, no audio, no speech-to-text, no model calls. ", scn.blurb);
  }

  /* fake waveform: purely decorative, animated by the words arriving */
  function Wave(canvas) {
    const ctx = canvas.getContext("2d"); let level = 0, raf = 0; const hist = [];
    const css = () => getComputedStyle(document.documentElement).getPropertyValue("--wave").trim() || "#6b8afd";
    function draw() {
      const w = canvas.width = canvas.clientWidth * devicePixelRatio, hh = canvas.height = canvas.clientHeight * devicePixelRatio;
      level *= 0.9; hist.push(level); if (hist.length > 160) hist.shift();
      ctx.clearRect(0, 0, w, hh); ctx.fillStyle = css();
      const bw = w / 160;
      hist.forEach((v, i) => { const bh = Math.max(2 * devicePixelRatio, v * hh * 0.9); ctx.fillRect(i * bw, (hh - bh) / 2, bw * 0.7, bh); });
      raf = requestAnimationFrame(draw);
    }
    draw();
    return { pulse(x) { level = Math.min(1, 0.35 + (x || Math.random()) * 0.65); }, stop() { cancelAnimationFrame(raf); } };
  }

  function controls(player, extra) {
    const play = h("button", { class: "btn primary", onclick: () => { const on = player.toggle(); play.textContent = on ? "Pause" : "Play"; } }, "Play");
    const speed = h("select", { class: "pick small", "aria-label": "Speed", onchange: (e) => player.speed(+e.target.value) },
      [["0.6", "0.6x"], ["1", "1x"], ["2", "2x"], ["4", "4x"]].map(([v, t]) => h("option", { value: v, selected: v === "1" }, t)));
    const restart = h("button", { class: "btn", onclick: () => { player.restart(); play.textContent = "Play"; } }, "Restart");
    return h("div", { class: "controls" }, play, restart, speed, extra);
  }

  window.Mock = { h, all, byId, hueOf, chipStyle, prepare, Player, mockScore, bar, conf, scenarioPicker, mockBanner, Wave, controls, rnd };
})();
