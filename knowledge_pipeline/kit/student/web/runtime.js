/* Student kit browser runtime (generalised from site/lab/demo.html). Needs onnxruntime-web 1.20.1 loaded as `ort`.
 *
 *   const rt = await KitRuntime.load("model/", {onProgress: (got, total) => ...});
 *   const out = await rt.run(text);   // {spans:[{start,end,label,text}], labels, label_probs, ms, tokens, windows}
 *
 * The model dir is export.py's output: labels.json (contract), the model file it names, tokenizer.json.
 * Tokenizer: WordPiece only (BERT-family tokenizer.json: BertNormalizer + BertPreTokenizer); options are read from
 * tokenizer.json (lowercase, strip_accents, clean_text, handle_chinese_chars, continuing_subword_prefix,
 * max_input_chars_per_word). Other tokenizer types (e.g. Ettin's BPE) throw: use runtime.py for those.
 * Windows / owner / decode / word snap follow runtime.py (= pipeline/ship/we_classifier.py). Offsets here are UTF-16
 * indices (JS strings); Python offsets are code points, so they differ only after astral characters (emoji etc.).
 */
(function (g) {
  "use strict";
  const isPunct = c => { const o = c.codePointAt(0); return (o >= 33 && o <= 47) || (o >= 58 && o <= 64) || (o >= 91 && o <= 96) || (o >= 123 && o <= 126) || /\p{P}/u.test(c); };
  const isCJK = o => (o >= 0x4E00 && o <= 0x9FFF) || (o >= 0x3400 && o <= 0x4DBF) || (o >= 0x20000 && o <= 0x2A6DF) || (o >= 0x2A700 && o <= 0x2B73F) || (o >= 0x2B740 && o <= 0x2B81F) || (o >= 0x2B820 && o <= 0x2CEAF) || (o >= 0xF900 && o <= 0xFAFF) || (o >= 0x2F800 && o <= 0x2FA1F);
  const alnum = x => /[\p{L}\p{N}]/u.test(x || "");

  function makeTokenizer(tj) {
    if (!tj.model || tj.model.type !== "WordPiece") throw new Error("web runner supports WordPiece tokenizers only (got " + (tj.model && tj.model.type) + "); use runtime.py");
    const VOCAB = tj.model.vocab, pre = tj.model.continuing_subword_prefix ?? "##", maxChars = tj.model.max_input_chars_per_word ?? 100;
    const UNK = VOCAB[tj.model.unk_token ?? "[UNK]"];
    const nz = tj.normalizer && tj.normalizer.type === "BertNormalizer" ? tj.normalizer : {};
    const lower = nz.lowercase ?? true, strip = nz.strip_accents ?? lower, clean = nz.clean_text ?? true, cjk = nz.handle_chinese_chars ?? true;
    return function tokenize(text) {
      const words = []; let cur = null;
      const flush = () => { if (cur && cur.s.length) words.push(cur); cur = null; };
      let i = 0;
      for (const ch of text) {
        const o = ch.codePointAt(0), at = i; i += ch.length;
        if (clean && (o === 0 || o === 0xFFFD || (/\p{C}/u.test(ch) && !/[\t\n\r]/.test(ch)))) continue;
        if (/\s/.test(ch)) { flush(); continue; }
        let n = lower ? ch.toLowerCase() : ch;
        if (strip) n = n.normalize("NFD").replace(/\p{Mn}/gu, "");
        if (!n) continue;
        if (isPunct(ch) || (cjk && isCJK(o))) { flush(); words.push({ s: n, o: Array(n.length).fill(0).map(() => [at, at + ch.length]) }); continue; }
        if (!cur) cur = { s: "", o: [] };
        for (let k = 0; k < n.length; k++) cur.o.push([at, at + ch.length]);
        cur.s += n;
      }
      flush();
      const ids = [], offs = [];
      for (const w of words) {
        const chars = [...w.s];
        if (chars.length > maxChars) { ids.push(UNK); offs.push([w.o[0][0], w.o[w.o.length - 1][1]]); continue; }
        const sub = []; let s = 0, bad = false;
        while (s < chars.length) {
          let e = chars.length, found = null;
          while (s < e) { let p = chars.slice(s, e).join(""); if (s > 0) p = pre + p; if (p in VOCAB) { found = VOCAB[p]; break; } e--; }
          if (found === null) { bad = true; break; }
          sub.push([found, s, e]); s = e;
        }
        if (bad) { ids.push(UNK); offs.push([w.o[0][0], w.o[w.o.length - 1][1]]); continue; }
        const cpStart = []; let u = 0; for (const c of chars) { cpStart.push(u); u += c.length; } cpStart.push(u);
        for (const [id, a, b] of sub) { ids.push(id); offs.push([w.o[cpStart[a]][0], w.o[cpStart[b] - 1][1]]); }
      }
      return { ids, offs };
    };
  }

  function startsOf(n, W, STEP) { if (n <= W) return [0]; const st = []; for (let s = 0; s <= n - W; s += STEP) st.push(s); if (st[st.length - 1] + W < n) st.push(n - W); return st; }
  function owner(n, starts, W) {
    const own = new Int32Array(n), best = new Int32Array(n).fill(-1);
    starts.forEach((s, wi) => { const e = Math.min(s + W, n); for (let p = s; p < e; p++) { const d = Math.min(p - s, e - 1 - p); if (d > best[p]) { best[p] = d; own[p] = wi; } } });
    return own;
  }
  function decode(text, offs, tags, channels) {
    const heads = [...new Set(channels)], res = {}; heads.forEach(h => res[h] = new Map());
    for (let c = 0; c < channels.length; c++) {
      const spans = []; let cur = null;
      for (let t = 0; t < tags.length; t++) {
        const v = tags[t][c];
        if (v === 1 || (v === 2 && cur === null)) { if (cur) spans.push(cur); cur = [offs[t][0], offs[t][1]]; }
        else if (v === 2) { cur[1] = offs[t][1]; }
        else { if (cur) spans.push(cur); cur = null; }
      }
      if (cur) spans.push(cur);
      const fixed = [];
      for (let [a, b] of spans) {
        while (a > 0 && alnum(text[a - 1]) && alnum(text[a])) a--;
        while (b < text.length && alnum(text[b]) && alnum(text[b - 1])) b++;
        if (fixed.length && a < fixed[fixed.length - 1][1]) fixed[fixed.length - 1] = [fixed[fixed.length - 1][0], Math.max(b, fixed[fixed.length - 1][1])];
        else fixed.push([a, b]);
      }
      fixed.forEach(([a, b]) => res[channels[c]].set(a + ":" + b, [a, b]));
    }
    const out = {}; heads.forEach(h => out[h] = [...res[h].values()].sort((x, y) => x[0] - y[0] || x[1] - y[1])); return out;
  }

  async function fetchBytes(url, onProgress) {
    const r = await fetch(url); if (!r.ok) throw new Error(url + " -> HTTP " + r.status);
    const total = +r.headers.get("content-length") || 0; const rd = r.body.getReader(); const parts = []; let got = 0;
    for (;;) { const { done, value } = await rd.read(); if (done) break; parts.push(value); got += value.length; if (onProgress) onProgress(got, total); }
    const buf = new Uint8Array(got); let o = 0; for (const p of parts) { buf.set(p, o); o += p.length; } return buf;
  }

  async function load(base, opts = {}) {
    base = base.endsWith("/") ? base : base + "/";
    ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
    ort.env.wasm.numThreads = opts.threads || 1;
    const spec = await fetch(base + "labels.json").then(r => { if (!r.ok) throw new Error("labels.json -> HTTP " + r.status); return r.json(); });
    const [tj, model] = await Promise.all([fetch(base + (spec.tokenizer_file || "tokenizer.json")).then(r => r.json()), fetchBytes(base + spec.model_file, opts.onProgress)]);
    const tokenize = makeTokenizer(tj);
    const sess = await ort.InferenceSession.create(model, { executionProviders: ["wasm"], graphOptimizationLevel: "all" });
    const W = spec.window, STEP = spec.stride, CLS = spec.cls_id, SEP = spec.sep_id, channels = spec.channels, seq = spec.sequence;
    const heads = [...new Set(channels)];

    async function run(text) {
      const t0 = performance.now();
      const { ids, offs } = tokenize(text);
      let spans = {}; heads.forEach(h => spans[h] = []);
      let seqLogits = null, nwin = 0;
      if (ids.length) {
        const st = startsOf(ids.length, W, STEP), own = owner(ids.length, st, W); nwin = st.length;
        const nch = channels.length, tags = Array.from({ length: ids.length }, () => new Int8Array(nch));
        for (let wi = 0; wi < st.length; wi++) {
          const s = st[wi], r = [CLS, ...ids.slice(s, s + W), SEP], L = r.length;
          const x = new ort.Tensor("int64", BigInt64Array.from(r.map(BigInt)), [1, L]);
          const m = new ort.Tensor("int64", new BigInt64Array(L).fill(1n), [1, L]);
          const o = await sess.run({ input_ids: x, attention_mask: m });
          const d = o[sess.outputNames[0]].data, D = nch * 3;
          for (let t = 0; t < L - 2; t++) {
            const p = s + t; if (p >= ids.length || own[p] !== wi) continue;
            for (let c = 0; c < nch; c++) { const b = ((t + 1) * D) + c * 3; let a = 0; if (d[b + 1] > d[b + a]) a = 1; if (d[b + 2] > d[b + a]) a = 2; tags[p][c] = a; }
          }
          if (seq && sess.outputNames.length > 1) {
            const q = Array.from(o[sess.outputNames[1]].data, Number);
            if (!seqLogits) seqLogits = q.map(v => [v]); else q.forEach((v, k) => seqLogits[k].push(v));
          }
        }
        spans = decode(text, offs, tags, channels);
      }
      const order = Object.fromEntries(heads.map((h, i) => [h, i]));
      const flat = heads.flatMap(h => spans[h].map(([a, b]) => ({ start: a, end: b, label: h, text: text.slice(a, b) })))
        .sort((x, y) => x.start - y.start || x.end - y.end || order[x.label] - order[y.label]);
      const out = { spans: flat };
      if (seq) {
        const pool = seq.pool || "max", thr = seq.threshold ?? 0.5;
        const probs = seq.labels.map((l, k) => { const v = seqLogits ? seqLogits[k] : [-Infinity]; const z = pool === "max" ? Math.max(...v) : v.reduce((a, b) => a + b, 0) / v.length; return 1 / (1 + Math.exp(-z)); });
        out.labels = seq.labels.filter((l, k) => probs[k] >= thr);
        out.label_probs = Object.fromEntries(seq.labels.map((l, k) => [l, +probs[k].toFixed(6)]));
      }
      out.model_sha256 = spec.model_sha256; out.ms = performance.now() - t0; out.tokens = ids.length; out.windows = nwin;
      return out;
    }
    return { spec, heads, run };
  }

  g.KitRuntime = { load, makeTokenizer, startsOf, owner, decode };
})(typeof window !== "undefined" ? window : globalThis);
