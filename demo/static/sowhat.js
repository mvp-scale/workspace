/* So what composer, v2: pure, dependency-free, deterministic (never random).
   Browser: window.SoWhat. Node: module.exports.
   Rules: probes/world-engine/spec/so-what-v2-design.md and so-what-v2-contract.md. Words: sowhat2_frames / hooks / templates / lexicon CSVs (plus the v1 lexicon for conditions, places and audiences).
   compose(ctx) returns {headline, line2, family, hook, body, register, frame, seed, spans, beats, picks, shrink, anchor} or null (never throws).
   Null means "keep the old text": tables of version 1 or empty, or any input the rules read is missing. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(); else root.SoWhat = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const MIN_MOVE = 0.25, LN2 = Math.LN2, LN10 = Math.LN10, HEAD_MAX = 22, L2_MAX = 14, L2_ONLY_MAX = 16;
  const A1_MIN = 2.0, A3_RATIO = 3, A3_WORLD = 0.25, A3_ROW = 1, FIG_LOUD = 5;
  const TIER_REG = { Negligible: "hushed", Minor: "plain", Notable: "plain", Major: "stark", Historic: "stark" }, TIER_ICON = { Negligible: "tier1", Minor: "tier2", Notable: "tier3", Major: "tier4", Historic: "tier5" };
  const FAMILY_ORDER = ["IF", "WHO_LOCAL", "WHO_MOST", "WHO_OPP", "CONTRAST", "SCALE", "STAKE", "TURN", "TRIGGER"];
  const ARC_ICON = { jolt: "now", builds: "next", builds_sticks: "next", sticks: "later", fades: "later" };
  const CERT_ICON = { happened: "now", announced: "next", pending: "next", forecast: "eye", opinion: "share", unclear: "dot", no_impact: "dot" };
  
  /* ---------- small helpers ---------- */
  const num = (x) => typeof x === "number" && isFinite(x);
  const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const words = (s) => (String(s).trim() ? String(s).trim().split(/\s+/).length : 0);
  const sg = (v, d = 2) => (v >= 0 ? "+" : "-") + Math.abs(v).toFixed(d);
  const peakOf = (v) => { let b = 0; for (const x of v) if (num(x) && Math.abs(x) > Math.abs(b)) b = x; return b; };
  const hash = (t) => { let h = 5381; for (let i = 0; i < t.length; i++) h = ((h * 33) ^ t.charCodeAt(i)) >>> 0; return h; };   /* djb2 */
  const list = (s) => String(s || "").split("|").map((x) => x.trim()).filter(Boolean);
  const anyOf = (s, v) => { const l = list(s); return !l.length || l.includes("any") || l.includes(v); };
  const S = (text, beat) => ({ text: text || "", spans: text && beat ? [{ start: 0, end: text.length, beat }] : [] });
  const round5 = (a) => a < 10 ? Math.floor(a + 0.5) : Math.floor(a / 5 + 0.5) * 5;

  function parseCsv(text) {   /* RFC-4180-ish: quotes, doubled quotes, CRLF. Returns array of {header: value}. */
    const rows = []; let row = [], f = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
      else if (c === '"') q = true; else if (c === ",") { row.push(f); f = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); f = ""; if (row.length > 1 || row[0] !== "") rows.push(row); row = []; }
      else f += c;
    }
    if (f !== "" || row.length) { row.push(f); rows.push(row); }
    const h = rows.shift() || []; return rows.map((r) => Object.fromEntries(h.map((k, i) => [k, r[i] == null ? "" : r[i]])));
  }

  /* ---------- tables (version 2 only) ---------- */
  const rowsOf = (x) => typeof x === "string" ? parseCsv(x) : Array.isArray(x) ? x : x && Array.isArray(x.rows) ? x.rows : null;
  const cache = typeof WeakMap === "function" ? new WeakMap() : null;
  function index(t) {
    if (!t || typeof t !== "object") return null; if (cache && cache.has(t)) return cache.get(t);
    if (t.version != null && Number(t.version) !== 2) return null;
    const fr = rowsOf(t.frames), hk = rowsOf(t.hooks), tp = rowsOf(t.templates), lx = rowsOf(t.lexicon), l1 = rowsOf(t.lexicon_v1);
    if (!fr || !hk || !tp || !lx || !fr.length || !hk.length || !tp.length || !lx.length) return null;
    const lex = {}; for (const r of lx.concat(l1 || [])) (lex[r.kind] || (lex[r.kind] = [])).push(r);
    for (const k of ["decision", "act", "theme", "degree", "valence", "anchor", "anchor_l2", "condition", "there"]) if (!lex[k] || !lex[k].length) return null;
    const dec = {}, act = {}, th = {}, cond = {}, val = {}, aud = {}, plc = {};
    for (const r of lex.decision) ((dec[r.id] || (dec[r.id] = {}))[r.sign] || (dec[r.id][r.sign] = [])).push(r);
    for (const r of lex.act) (act[r.id] || (act[r.id] = {}))[r.sign] = r.text;
    for (const r of lex.theme) { const m = /members:\s*(.*)$/.exec(r.note || ""); const o = th[r.id] || (th[r.id] = { id: r.id, members: m ? m[1].split(";").map((s) => s.trim()).filter(Boolean) : [], rows: {} }); (o.rows[r.sign] || (o.rows[r.sign] = [])).push(r); }
    for (const r of lex.condition) cond[r.id] = r; for (const r of lex.valence) val[r.id] = r; for (const r of lex.audience || []) aud[r.id] = r; for (const r of lex.place || []) plc[r.id] = r;
    const by = (k, f) => (lex[k] || []).filter(f || (() => true));
    const ix = { frames: Object.fromEntries(fr.map((r) => [r.id, r])), hooks: hk.slice().sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0), templates: tp.slice().sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0), lex, dec, act, th, cond, val, aud, plc, by,
      softRe: new RegExp("\\b(" + by("soft").map((r) => r.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b", "i") };
    if (cache) cache.set(t, ix); return ix;
  }

  /* ---------- places and subjects ---------- */
  const takesThe = (n) => /^(United |Netherlands|Philippines|Democratic Republic)/.test(n);
  const SHORT_C = [[/^Democratic Republic of the Congo$/, "DR Congo"], [/^United States$/, "US"], [/^United Kingdom$/, "UK"], [/^United Arab Emirates$/, "UAE"], [/^(the )?Netherlands$/, "Netherlands"]];
  const shortCountry = (n) => { for (const [re, t] of SHORT_C) if (re.test(n)) return t; return n; };
  const shortAud = (a) => { const w = a.replace(/,/g, "").split(/\s+/); return w.length > 2 ? w.slice(-2).join(" ") : a; };
  function makePlaces(rows, ix) {
    const byId = Object.fromEntries(rows.map((r) => [r.id, r])), P = { mode: {} };   /* mode: shrink steps that shorten names (deterministic, applied only when a statement is over budget) */
    const cname = (label) => { const c = String(label).split(" · ")[0], sh = P.mode.shortName; return sh ? { plain: shortCountry(c), the: shortCountry(c) } : { plain: c, the: (takesThe(c) ? "the " : "") + c }; };
    const aud = (r) => { const a = ix.aud[r.label], t = a && a.text ? a.text : String(r.label).toLowerCase().replace(/,/g, "").replace(/\s+/g, " ").trim() + " people"; return P.mode.shortAud ? shortAud(t) : t; };
    function place(r) {
      if (r.level === "world") return "the world"; if (r.level === "audience") return aud(r);
      if (r.level === "country") return cname(r.label).the;
      const parts = String(r.label).split(" · "), par = byId[r.parent], c = cname(par ? par.label : parts[0]), suf = parts[1] || "", pr = ix.plc[suf];
      if (!pr) return (suf ? suf + " " : "") + c.the;
      const alt = pr.text_alt && takesThe(c.plain) ? pr.text_alt.replace("{name}", c.plain) : null;
      return alt || pr.text.replace("{country}", c.the);
    }
    const plural = (r) => r.level === "audience" || (r.level === "region" && /^(cities|towns) /.test(place(r)));   /* "retirees react", "cities in India react" */
    return Object.assign(P, { byId, place, subj: (r) => r.level === "world" ? "people" : P.mode.plainSubj ? "people" : r.level === "audience" ? aud(r) : "people in " + place(r), s: (r) => plural(r) ? "" : "s", is: (r) => plural(r) ? "are" : "is",
      thereKind: (r) => r.level === "audience" ? "audience" : "place" });
  }

  /* ---------- numbers per row ---------- */
  function peaksAt(places, id) {
    const P = places && places[id]; if (!P || typeof P !== "object") return null;
    const out = []; for (const d of Object.keys(P)) { const v = P[d]; if (Array.isArray(v) && v.length >= 3 && v.every(num)) out.push({ id: d, v, p: peakOf(v) }); }
    return out.length ? out : null;
  }
  const lead = (pk) => pk.reduce((a, b) => Math.abs(b.p) > Math.abs(a.p) ? b : a, pk[0]);
  const peakDec = (places, row, d) => { const P = places[row]; return P && Array.isArray(P[d]) ? peakOf(P[d]) : 0; };
  const maxAbs = (places, row) => { const P = places[row]; let m = 0; if (P) for (const d of Object.keys(P)) if (Array.isArray(P[d])) m = Math.max(m, Math.abs(peakOf(P[d]))); return m; };
  function sense(pk) { const x = pk.filter((q) => ["spend", "buy_new", "subscribe", "travel"].includes(q.id)).reduce((a, q) => a + q.p, 0); return { v: x, dir: x <= -MIN_MOVE ? "down" : x >= MIN_MOVE ? "up" : "flat" }; }
  const senseOk = (needed, dir) => { const n = needed || "any"; return n === "any" || (n === "not up" && dir !== "up") || (n === "not down" && dir !== "down"); };
  const degreeOf = (size) => size < 0.75 ? "small" : size >= 3 ? "large" : "mid";

  /* themes at one horizon (idx 0 Now, 1 Next, 2 Later) or at the peak (idx null): v1 rules */
  function themesOf(pk, ix, idx) {
    const val = (q) => idx == null ? q.p : q.v[idx], by = Object.fromEntries(pk.map((q) => [q.id, q])), out = [];
    for (const th of Object.values(ix.th)) {
      const ms = th.members.map((id) => by[id]).filter((q) => q && Math.abs(val(q)) >= MIN_MOVE).sort((a, b) => Math.abs(val(b)) - Math.abs(val(a)));
      if (!ms.length) continue;
      const top = ms[0], tv = val(top), sign = tv < 0 ? "down" : "up", same = ms.filter((q) => (val(q) < 0) === (tv < 0)), size = Math.abs(tv);
      const useTheme = same.length >= 2 && Math.abs(val(same[1])) >= 0.5 * size && !!(th.rows[sign] || []).length;
      if (!useTheme && !(ix.dec[top.id] && ix.dec[top.id][sign])) continue;
      out.push({ theme: th.id, size, sign, top: top.id, topP: tv, members: ms, useTheme, key: useTheme ? th.id : top.id });
    }
    return out.sort((a, b) => b.size - a.size);   /* stable */
  }

  /* ---------- trigger clause ---------- */
  function clause(ix, pick, modal) {
    const c = ix.cond[pick.dial]; if (!c) return null;
    const down = pick.direction === "down", plain = down ? c.down : c.up, bare = (down ? c.down_bare : c.up_bare) || plain;
    if (modal) return `${c.noun} ${modal} ${bare}`;
    if (pick.basis === "expected" || pick.mode === "expected_pending") return `${c.noun} should ${bare}`;
    return `${c.noun} ${plain}`;
  }
  const isShould = (pick) => pick.basis === "expected" || pick.mode === "expected_pending";
  const keepOne = (picks) => picks.find((p) => p.basis !== "expected") || picks[0];

  /* ---------- WHO (v1 rules) ---------- */
  function ratio(rowP, refP) {
    if (Math.abs(refP) < MIN_MOVE) return Math.abs(rowP) >= MIN_MOVE ? { r: Infinity, kind: "alone", sal: LN10 } : { r: 0, kind: "same", sal: 0 };   /* the world barely moves: never divide by it; the row moves and almost no one else does */
    const both = Math.abs(rowP) >= MIN_MOVE && Math.abs(refP) >= MIN_MOVE;
    let r = refP ? rowP / refP : 0, kind, sal;
    if (r <= 0) { kind = both && rowP * refP < 0 ? "opposite" : "far_less"; sal = kind === "opposite" ? 2 : LN10 / 2; }
    else { kind = r >= 2.5 ? "x_many" : r >= 1.75 ? "x2" : r >= 1.25 ? "more" : r > 0.8 ? "same" : r > 0.6 ? "bit_less" : r > 0.35 ? "half" : "far_less"; sal = Math.min(Math.abs(Math.log(r)), LN10); if (r < 1) sal /= 2; if (kind === "same") sal = 0; }
    return { r, kind, sal };
  }

  /* ---------- arc ---------- */
  function arcOf(v) {
    const pk = peakOf(v), pi = v.reduce((b, x, i) => Math.abs(x) > Math.abs(v[b]) ? i : b, 0), keeps = pk ? Math.max(0, Math.min(1, v[2] / pk)) : 0;
    const kind = pi > 0 && Math.abs(v[1]) >= 1.25 * Math.abs(v[0]) ? (keeps >= 0.6 ? "builds_sticks" : "builds") : keeps >= 0.6 ? "sticks" : pi === 0 && keeps < 0.35 ? "jolt" : "fades";
    return { kind, keeps, peakIdx: pi };
  }
  const ARC_WORD = { builds: "slow to start, stronger later, then easing", builds_sticks: "builds and stays", sticks: "lingers", jolt: "quick jolt, soon gone", fades: "fades" };

  /* ---------- template filling with spans ---------- */
  function fill(tpl, slots) {
    let out = "", spans = [], last = 0, m; const re = /\{(\w+)\}/g;
    while ((m = re.exec(tpl))) {
      out += tpl.slice(last, m.index); const v = slots[m[1]], o = v == null ? { text: "", spans: [] } : typeof v === "string" ? { text: v, spans: [] } : v, st = out.length;
      out += o.text; for (const s of o.spans) spans.push({ start: st + s.start, end: st + s.end, beat: s.beat }); last = re.lastIndex;
    }
    return { text: out + tpl.slice(last), spans: mergeSpans(spans) };
  }
  function mergeSpans(sp) {
    const o = []; for (const s of sp.slice().sort((a, b) => a.start - b.start || b.end - a.end)) { const p = o[o.length - 1]; if (p && p.beat === s.beat && s.start <= p.end && s.end >= p.end) p.end = s.end; else if (p && s.start < p.end) continue; else o.push({ ...s }); } return o;
  }
  /* the hook's own words become a "hook" span, around any trigger / certainty / who span inside it (spans never overlap) */
  function hookSpans(text, inner) {
    const out = [], cut = (a, b) => { while (a < b && /[\s,:;]/.test(text[a])) a++; while (b > a && /[\s,:;]/.test(text[b - 1])) b--; if (b > a && /[A-Za-z]/.test(text.slice(a, b))) out.push({ start: a, end: b, beat: "hook" }); };
    let k = 0; for (const s of inner.slice().sort((x, y) => x.start - y.start)) { cut(k, s.start); out.push(s); k = s.end; } cut(k, text.length); return out;
  }

  /* ---------- the composer ---------- */
  function normalise(a, b, c) {
    const ctx = b !== undefined || c !== undefined ? Object.assign({}, b, { story: a, tables: c }) : a;
    return ctx && typeof ctx === "object" ? ctx : null;
  }
  function compose(a, b, c) {
    try { return run(normalise(a, b, c)); } catch (e) { return null; }
  }
  const first3 = (t) => String(t).split(/\s+/).slice(0, 3).join(" ").toLowerCase();
  function run(ctx) {
    if (!ctx) return null;
    const out = build(ctx, "hook"); if (!out) return null;
    const prev = typeof ctx.prev === "string" ? ctx.prev : "";
    if (prev && out.family && out.hook && first3(out.headline) === first3(prev)) for (const slot of ["hook#2", "hook#3"]) { const o2 = build(ctx, slot); if (o2 && o2.headline && first3(o2.headline) !== first3(prev)) return o2; }
    return out;
  }

  function build(ctx, hookSlot) {
    const story = ctx.story, ix = index(ctx.tables || ctx.rules), rows = ctx.rows;
    if (!story || typeof story !== "object" || !story.certainty || !story.frame || !story.trigger || !ix || !Array.isArray(rows) || !rows.length) return null;
    const kind = story.certainty.kind, modal = story.certainty.modal || "", weight = num(ctx.weight) ? ctx.weight : story.certainty.weight;
    if (typeof kind !== "string" || !num(weight)) return null;
    const seed = String(ctx.seed != null ? ctx.seed : story.seed != null ? story.seed : ctx.text != null ? hash(String(ctx.text)) : "");
    if (!seed) return null;
    const picksLog = [], seen = new Set();
    const pick = (slot, cands) => { if (!cands || !cands.length) return undefined; const i = hash(seed + "|" + slot) % cands.length; if (!seen.has(slot)) { seen.add(slot); picksLog.push({ slot, index: i, of: cands.length }); } return cands[i]; };
    const P = makePlaces(rows, ix), worldRow = rows.find((r) => r.level === "world") || rows[0], focusRow = P.byId[ctx.focus] || worldRow, isWorld = focusRow.level === "world";
    const topic = story.topic || ctx.topic || null, entry = story.entry || {};
    const rank0 = Array.isArray(ctx.rank) ? ctx.rank : null;
    const certBeat = { kind: "certainty", icon: CERT_ICON[kind] || "dot", text: kind, trace: story.certainty.trace || `weight ${weight}` };

    /* ---- no impact: NOTHING (topic known) or QUIET_VAGUE ---- */
    if (kind === "no_impact") {
      const known = topic && num(topic.p) && topic.p >= 0.5 && topic.id && topic.id !== "other" && topic.name, fam = known ? "NOTHING" : "QUIET_VAGUE";
      const t = pick("quiet", ix.templates.filter((r) => r.families === fam)); if (!t) return null;
      const f = fill(t.template, { topic: known ? String(topic.name).toLowerCase() : "" });
      return { headline: f.text, line2: "", family: fam, hook: null, body: t.id, template: t.id, lead: "quiet", register: null, frame: null, seed, spans: [], shrink: [], anchor: null, picks: picksLog,
        beats: [certBeat, { kind: "response", icon: "dot", text: "none", trace: "the story names no event we can measure" }, { kind: "topic", icon: "topic", text: known ? topic.name : "", trace: known ? `topic ${topic.id} p ${topic.p}` : "no topic placed at 0.5 or more" }] };
    }
    if (!ctx.places || typeof ctx.places !== "object" || !Object.keys(ctx.places).length || !Array.isArray(ctx.readings)) return null;
    const hedgedKind = kind === "forecast" || kind === "opinion" || kind === "unclear" || (kind === "announced" && weight < 1);
    const useIf = hedgedKind && weight < 1;
    let numbers = ctx.places, sigRows = ctx.significance_rows, sigWorld = ctx.significance || story.scale;
    if (useIf) { const it = ctx.if_true; if (!it || !it.places || typeof it.places !== "object") return null; numbers = it.places; sigRows = it.significance_rows; sigWorld = it.significance; }
    const certKey = kind === "announced" && weight < 1 ? "announced_w" : kind;
    const hedgeLexId = kind === "announced" ? "announced" : kind;
    const picks = Array.isArray(story.trigger.picks) ? story.trigger.picks : [];
    const frameStart = ix.frames[story.frame.id] ? story.frame.id : "plain";

    const trigText = (ps, md) => ps.map((p) => clause(ix, p, md)).filter(Boolean).join(" and ");
    /* ---- the place is not in our model (story.place_status "unresolved"): never speak for everyone; no response, no figure, no who ---- */
    if (story.place_status === "unresolved") {
      if (!picks.length) return null;
      const forms = ix.templates.filter((r) => r.families === "UNRESOLVED_PLACE"); if (!forms.length) return null;
      const mkU = (t, ps) => { const tc = trigText(ps, modal); return tc ? { f: fill(t.template, { Trigger: S(cap(tc), "trigger"), trigger: S(tc, "trigger") }), tc } : null; };
      const shrinkU = []; let psU = picks, tU = pick("quiet", forms), rU = mkU(tU, psU); if (!rU) return null;
      if (words(rU.f.text) > HEAD_MAX && picks.length > 1) { psU = [keepOne(picks)]; rU = mkU(tU, psU); shrinkU.push("dropped 2nd trigger"); }
      if (words(rU.f.text) > HEAD_MAX) { const alt = forms.map((x) => ({ x, r: mkU(x, psU) })).filter((y) => y.r).sort((p, q) => words(p.r.f.text) - words(q.r.f.text))[0]; if (alt && words(alt.r.f.text) < words(rU.f.text)) { tU = alt.x; rU = alt.r; shrinkU.push("shortest form"); } }
      if (words(rU.f.text) > HEAD_MAX) return null;
      const trT = (id) => ((ix.by("trace", (x) => x.id === id)[0]) || {}).text || "";
      return { headline: rU.f.text, line2: "", family: "UNRESOLVED_PLACE", hook: null, body: tU.id, template: tU.id, lead: "quiet", register: "hedged", frame: "plain", seed, spans: rU.f.spans.map((x) => ({ line: 1, ...x })), shrink: shrinkU, anchor: null, picks: picksLog,
        beats: [{ kind: "trigger", icon: "condition", text: rU.tc, trace: story.trigger.trace || "" }, certBeat, { kind: "place", icon: "place", short: "not in our model", text: "not in our model", trace: story.place_trace || "The place in this story is not one our model covers." },
          { kind: "response", icon: "dot", text: "none", trace: "The place is not in our model, so no row's numbers are used and nobody is spoken for." }, { kind: "register", icon: "tier1", short: "hedged", text: "hedged", trace: "The words are hedged: we can say what happens, not who it reaches." }, { kind: "anchor", icon: "number", text: null, trace: trT("none_unresolved") }] };
    }

    /* where the story is (ontology 1.8) and the local test, on the numbers used */
    const entryRow = P.byId[entry.id], entryCountry = !!entryRow && entryRow.level === "country";
    const entryKind = entryCountry ? "country" : entry.place === "unresolved" ? "unresolved" : "world", placeOk = entryCountry;
    const wmax = maxAbs(numbers, worldRow.id), emax = entryCountry ? maxAbs(numbers, entry.id) : 0;
    const localStory = entryCountry && wmax < MIN_MOVE && emax >= MIN_MOVE, local = localStory && isWorld;

    const respId0 = local ? entry.id : focusRow.id, pk0 = peaksAt(numbers, respId0);
    if (!pk0) return null;
    const themes0 = themesOf(pk0, ix, null);

    /* ---- quiet: counted but nothing reaches MIN_MOVE ---- */
    if (!themes0.length) return quiet();
    function quiet() {
      if (!picks.length) return null;
      const elsewhere = localStory && focusRow.id !== entry.id;
      const fam = elsewhere ? "QUIET_ELSEWHERE" : kind === "opinion" ? "QUIET_OPINION" : hedgedKind || certKey === "announced_w" ? "QUIET_FORECAST" : ["major", "severe"].includes(picks[0].severity) ? "QUIET_NOTABLE" : "QUIET_SMALL";
      const forms = ix.templates.filter((r) => r.families === fam && anyOf(r.certainty, certKey)); if (!forms.length) return null;
      const shrink = [], mk = (t, ps0) => { const ps = ps0.length > 1 && /\{[Tt]rigger\}[^.{]*\band\b/.test(t.template) ? [keepOne(ps0)] : ps0, tc = trigText(ps, modal); if (!tc) return null;   /* two triggers joined by "and" never sit before another "and" */ return fill(t.template, { Trigger: S(cap(tc), "trigger"), trigger: S(tc, "trigger"), qsubj: P.subj(focusRow), focus_subj: P.subj(focusRow), for_subj: isWorld ? "" : " for " + P.subj(focusRow), entry_place: entryRow ? P.place(entryRow) : "" }); };
      let ps = picks, t = pick("quiet", forms), f = mk(t, ps); if (!f) return null;
      if (words(f.text) > HEAD_MAX && picks.length > 1) { ps = [keepOne(picks)]; f = mk(t, ps); shrink.push("dropped 2nd trigger"); }
      for (const m of [{ shortName: true, shortAud: true }, { plainSubj: true }]) { if (words(f.text) <= HEAD_MAX) break; P.mode = Object.assign({}, P.mode, m); const f2 = mk(t, ps); if (f2.text !== f.text) { f = f2; shrink.push(m.plainSubj ? "plain subject" : "short place name"); } }
      if (words(f.text) > HEAD_MAX) { const alt = forms.map((x) => ({ x, f: mk(x, ps) })).filter((y) => y.f).sort((p, q) => words(p.f.text) - words(q.f.text))[0]; if (alt && words(alt.f.text) < words(f.text)) { t = alt.x; f = alt.f; shrink.push("shortest form"); } }
      if (words(f.text) > HEAD_MAX) { if (ctx.debug) ctx.debug.reason = "budget"; return null; }
      const mx = Math.max(0, ...pk0.map((q) => Math.abs(q.p))), tc = trigText(ps, modal);
      return { headline: f.text, line2: "", family: fam, hook: null, body: t.id, template: t.id, lead: "quiet", register: null, frame: frameStart, seed, spans: f.spans.map((s) => ({ line: 1, ...s })), shrink, anchor: null, picks: picksLog,
        beats: [{ kind: "trigger", icon: "condition", text: tc, trace: story.trigger.trace || "" }, certBeat, { kind: "response", icon: "dot", text: "none", trace: `largest move ${sg(mx)} points at ${P.place(P.byId[respId0] || focusRow)}${useIf ? " (if true, type weight removed)" : ""}, under ${MIN_MOVE}` }] };
    }

    /* ---- WHO candidates and lead ---- */
    let respId = respId0, rowR = P.byId[respId] || focusRow, pk = pk0, ld = lead(pk);
    const ld0 = ld, refW = (id) => peakDec(numbers, worldRow.id, id), cands = [];
    const consider = (r, ref, refId, extra) => { if (r.level !== "audience" && !placeOk) return; const rp = peakDec(numbers, r.id, ld0.id), rr = ratio(rp, ref); cands.push({ row: r, rp, ref, refId, ...rr, ...extra }); };
    if (isWorld && !local) { for (const r of rows) if ((r.level === "country" && (r.share || 0) >= 0.005) || r.level === "audience") consider(r, refW(ld0.id), worldRow.id, { sub: true }); }
    else if (focusRow.level === "country") {
      consider(focusRow, refW(ld0.id), worldRow.id, { sub: false });
      for (const r of rows) if (r.level === "region" && r.parent === focusRow.id) consider(r, peakDec(numbers, focusRow.id, ld0.id), focusRow.id, { sub: true });
    } else if (!isWorld) consider(focusRow, refW(ld0.id), worldRow.id, { sub: false });
    if (isWorld && !local) { const cs = cands.filter((x) => x.row.level === "country").sort((p, q) => Math.abs(q.rp) - Math.abs(p.rp)); if (cs.length && !(Math.abs(cs[0].rp) >= 2 * Math.abs((cs[1] || { rp: 0 }).rp))) for (const x of cs) cands.splice(cands.indexOf(x), 1); }
    const leadable = cands.filter((x) => x.sub && ["x2", "x_many", "opposite", "alone"].includes(x.kind) && x.sal >= LN2).sort((p, q) => q.sal - p.sal);
    let who = null; if (local) who = { row: entryRow, kind: "local" }; else if (leadable.length) who = leadable[0];
    if (who && !local && isWorld) { respId = who.row.id; rowR = who.row; pk = peaksAt(numbers, respId) || pk; ld = lead(pk); }
    const whoRow = who ? who.row : null, whoKind = who ? (who.kind === "local" ? "local" : who.kind === "opposite" ? "opp" : "more") : null;

    /* ---- themes shown ---- */
    const themes = themesOf(pk, ix, null), th = themes.filter((t, i) => i === 0 || t.size >= 0.4 * themes[0].size).slice(0, 2);
    if (!th.length) return null;
    const sn = sense(pk);

    /* ---- frame and guards ---- */
    const thTok = (t) => t.theme + (t.sign === "down" ? "-" : "+"), shownToks = th.map(thTok);
    const passes = (id) => { const f = ix.frames[id]; if (!f) return false; if (!senseOk(f.sense_needed, sn.dir)) return false; const bars = String(f.bars_themes || "").split(";").map((s) => s.trim()).filter(Boolean); return !shownToks.some((t) => bars.includes(t)); };
    let frameId = frameStart, guard = "";
    if (frameId !== "plain" && !passes(frameId)) {
      const ru = story.frame.runner_up && story.frame.runner_up.id;
      if (ru && ru !== "plain" && passes(ru)) { guard = `top frame ${frameId} fails the guard, runner-up ${ru} used`; frameId = ru; } else { guard = `top frame ${frameId} fails the guard, plain used`; frameId = "plain"; }
    }
    if (entryKind === "unresolved" && frameId !== "plain") { guard = "place unresolved, plain used"; frameId = "plain"; }
    const frameRow = ix.frames[frameId] || ix.frames.plain || {};
    const fits = frameId !== "plain" && (String(frameRow.fits_themes || "any").trim() === "any" || String(frameRow.fits_themes).split(";").map((s) => s.trim()).includes(thTok(th[0])));
    const causal = frameRow.causal === "yes";
    const valence = frameRow.valence === "good" || frameRow.valence === "bad" ? frameRow.valence : sn.dir === "down" ? "bad" : sn.dir === "up" ? "good" : "flat";

    /* ---- register ---- */
    let tierRow, tierWhere;
    if (rowR.level === "world") { tierRow = sigWorld; tierWhere = "World"; } else { tierRow = sigRows && sigRows[rowR.id]; tierWhere = rowR.label; }
    if (!tierRow || !TIER_REG[tierRow.tier]) return null;
    let register = TIER_REG[tierRow.tier]; const capped = (hedgedKind || kind === "pending") && register === "stark"; if (capped) register = "plain";
    const hushed = register === "hushed";
    const noun = frameId === "plain" ? (hushed ? frameRow.noun_hushed : frameRow.noun) : hushed ? frameRow.noun_hushed : frameRow.noun;

    /* ---- arc, turn, stake, partner ---- */
    const arc = arcOf(pk.length && ld ? ld.v : [0, 0, 0]);
    const thNow = themesOf(pk, ix, 0), thLater = themesOf(pk, ix, 2), nowT = thNow[0], laterT = thLater[0];
    const turnShift = !!(nowT && laterT && nowT.theme !== laterT.theme);
    const stakeSet = new Set(ix.by("stake").map((r) => r.id)), stakeTh = th.find((t) => stakeSet.has(t.top) && Math.abs(t.topP) >= 0.75), stakeDec = stakeTh ? stakeTh.top : null;
    const builds = arc.kind === "builds" || arc.kind === "builds_sticks", buildsFades = arc.kind === "builds";
    /* contrast partner (numeric) */
    const readings = ctx.readings, valOf = (d, dir) => { const v = ix.val[d] && ix.val[d].text; if (v !== "good" && v !== "bad") return null; return dir === "up" ? v : v === "good" ? "bad" : "good"; };
    const leadPick = keepOne(picks), leadRd = readings.find((r) => r.dial === leadPick.dial), leadAmt = leadRd && num(leadRd.amount) ? Math.abs(leadRd.amount) : 0, leadVal = valOf(leadPick.dial, leadPick.direction);
    let partner = null;
    if (leadVal) {
      const pdials = picks.map((p) => p.dial), probs = story.trigger.probs || {};
      const cs = readings.filter((r) => r.dial !== leadPick.dial && ix.val[r.dial] && !/no_partner/.test(ix.val[r.dial].flags || "") && valOf(r.dial, r.direction) === (leadVal === "good" ? "bad" : "good") && (r.basis === "reported" || pdials.includes(r.dial)) && num(r.amount) && Math.abs(r.amount) >= 0.5 * leadAmt && ix.cond[r.dial])
        .sort((p, q) => (probs[q.dial] || 0) - (probs[p.dial] || 0) || Math.abs(q.amount) - Math.abs(p.amount));
      if (cs.length) partner = { dial: cs[0].dial, direction: cs[0].direction, basis: cs[0].basis, mode: cs[0].mode, val: valOf(cs[0].dial, cs[0].direction), amount: cs[0].amount, p: probs[cs[0].dial] };
    }
    const trigPicksAll = partner ? [leadPick] : picks;
    const clausePartner = partner ? clause(ix, partner, modal) : null;

    /* ---- anchor candidate (design 8) ---- */
    const decOf = (id, p) => ({ id, sign: p < 0 ? "down" : "up" });
    let anchor = null, anchorWhy = "", anchorWhyId = "none_other";
    const ptsAnchor = () => { const v = ld.p, a = Math.abs(v); if (a < A1_MIN) { anchorWhyId = "none_small"; anchorWhy = `A1 not shown: ${ld.id} ${sg(v)} points at ${tierWhere}, under ${A1_MIN.toFixed(1)}`; return null; }
      const rule = hedgedKind ? "A4" : "A1"; return { kind: "pts", rule, decision: ld.id, sign: v < 0 ? "down" : "up", value_raw: v, shown: round5(a), peakIdx: arc.peakIdx, row: rowR }; };
    const multAnchor = (row, dec, rp, wp) => { const r = wp ? rp / wp : 0; if (!(r >= A3_RATIO && Math.abs(wp) >= A3_WORLD && Math.abs(rp) >= A3_ROW)) { anchorWhyId = anchorWhyId === "none_small" ? "none_small" : "none_other"; anchorWhy = `A3 not shown: ${dec} ${row.label} ${sg(rp)} vs World ${sg(wp)} (x${r.toFixed(2)})`; return null; }
      return { kind: "multiple", rule: "A3", decision: dec, sign: rp < 0 ? "down" : "up", value_raw: Math.round(r * 100) / 100, shown: Math.min(10, Math.floor(r + 0.5)), more: r > 10 + 1e-9 || Math.floor(r + 0.5) > 10, row, rp, wp }; };
    if (hedgedKind) anchor = ptsAnchor();
    else if (who && who.kind !== "local" && whoKind === "more" && isWorld) anchor = multAnchor(who.row, ld0.id, who.rp, who.ref) || ptsAnchor();
    else { anchor = ptsAnchor(); if (!anchor && !isWorld && rowR.level !== "world") { const dec = ld.id; anchor = multAnchor(rowR, dec, ld.p, refW(dec)); } }
    if (hushed && anchor) { anchor = null; anchorWhyId = "none_hushed"; anchorWhy = "a hushed statement shows no figure"; }
    if (anchor) anchorWhy = "";
    else if (!anchorWhy) anchorWhy = "no figure passes its test";

    /* ---- hook eligibility ---- */
    const rk = (rank0 || []).find((x) => x.decision === ld.id), reach = rk && num(rk.reach) ? rk.reach : null;
    const worldFocusOk = isWorld && entryKind !== "unresolved";
    const plainTriggerOf = (ps) => !modal && !ps.some(isShould);
    const cohDir = sn.dir !== "flat" ? sn.dir : ["spending", "travel"].includes(th[0].theme) ? th[0].sign : "flat", coherent = !((leadVal === "bad" && cohDir === "up") || (leadVal === "good" && cohDir === "down")), qualify = !coherent;   /* a consequence word needs a response that agrees with the trigger; otherwise the response is said to be "on our numbers" */
    const cxBase = { coherent, fit: fits, causal, no_modal: !modal, local, who_more: whoKind === "more", who_opp: whoKind === "opp", partner: !!partner, stake: !!stakeDec, turn_shift: turnShift, builds, builds_fades: buildsFades,
      reach90: reach != null && reach >= 90, reach60: reach != null && reach >= 60, world_focus: worldFocusOk, geo: !!whoRow && whoRow.level !== "audience", audience: !!whoRow && whoRow.level === "audience" };
    const needOk = (tok, cx) => tok === "anchor" ? true : tok === "plain_trigger" ? cx.plain_trigger : !!cx[tok];
    const regOk = (r) => anyOf(r.register, register), certOk = (r) => anyOf(r.certainty, certKey);
    const valOk = (r) => !r.valence || r.valence === "any" || r.valence === valence;
    const framesOk = (r) => anyOf(r.frames, frameId) && (!r.frames_not || !list(r.frames_not).includes(frameId));
    const lexRows = (kindName, id) => ix.by(kindName, (r) => r.id === id && anyOf(r.register, register) && !list(r.frames_not).includes(frameId));

    /* hook candidates per family, in id order, hedge rows expanded */
    function hookCands(cx) {
      const out = [];
      for (const h of ix.hooks) {
        if (!certOk(h) || !regOk(h) || !valOk(h) || !framesOk(h)) continue;
        if (!list(h.needs).every((t) => needOk(t, cx))) continue;
        if (/\{Hedge\}|\{hedge_tail\}|\{Open\}/.test(h.text)) { const k = /\{Hedge\}/.test(h.text) ? "hedge" : /\{Open\}/.test(h.text) ? "hook_open" : "hedge_tail"; lexRows(k, k === "hook_open" ? h.id : hedgeLexId).forEach((r, i) => out.push({ id: `${h.id}.${i}`, row: h, text: h.text.replace(/\{Hedge\}|\{hedge_tail\}|\{Open\}/, r.text), lex: r })); }
        else out.push({ id: h.id, row: h, text: h.text });
      }
      return out.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    }

    /* ---- slot values that do not depend on options ---- */
    const therePick = pick("there", ix.by("there", (r) => r.id === P.thereKind(whoRow || rowR)).map((r) => r.text));
    const anchorFig = anchor && anchor.kind === "pts" ? anchor.shown : null;
    const lexVerb = (t, first) => {
      const rows0 = t.useTheme ? ix.th[t.theme].rows[t.sign] : ix.dec[t.top][t.sign], slot = t.useTheme ? `theme:${t.theme}:${t.sign}` : `verb:${t.top}:${t.sign}`;
      const okc = rows0.filter((r) => anyOf(r.register, register) && !list(r.frames_not).includes(frameId) && (first || !/\band\b/.test(r.flags || "")));
      const row = pick(slot, okc.length ? okc : rows0); if (!row) return null;
      let text = row.text; const dg = /\{(deg|degp)\}/.exec(text); let size = degreeOf(t.size);
      if (anchorFig != null && ((size === "large" && anchorFig < FIG_LOUD) || (size === "small" && anchorFig >= FIG_LOUD))) size = "mid";   /* degree word agrees with the printed figure: loud words need 5 in 100 or more, soft words never sit beside it */
      if (dg && size !== "mid") { const dr = pick(`deg:${t.key}:${size}:${dg[1]}`, ix.by("degree", (r) => r.id === size && r.sign === dg[1]).map((r) => r.text)); text = text.replace(`{${dg[1]}}`, dr == null ? "" : dr); }
      text = text.replace(/\{deg\}|\{degp\}/g, "").replace(/\s+/g, " ").trim();
      return { text, and: /\band\b/.test(row.flags || ""), row };
    };
    const v1 = lexVerb(th[0], true); if (!v1) return null;
    const v2 = th[1] && !v1.and ? lexVerb(th[1], false) : null;
    const vpList = String(frameRow["vp_" + register] || "").split(";").map((s) => s.trim()).filter(Boolean);
    const vpPick = vpList.length ? pick("vp", vpList) : null;
    const hasVp = !!vpList.length;
    const nowV = turnShift ? lexVerb(nowT, true) : null, laterV = turnShift ? lexVerb(laterT, true) : null;
    const tierWord = (ix.by("tier_word", (r) => r.id === tierRow.tier)[0] || {}).text || "";
    const stakeWord = stakeDec ? (ix.by("stake", (r) => r.id === stakeDec)[0] || {}).text || "" : "";

    /* anchor wording pieces */
    const actText = anchor && anchor.kind === "pts" ? ((ix.act[anchor.decision] || {})[anchor.sign] || null) : null;
    if (anchor && anchor.kind === "pts" && !actText) anchor = null;

    /* the unit: "N in every 100", or "1 in every 20" when the figure is within half a point of 5, "1 in every 10" when within one point of 10 (never more precision than the numbers carry) */
    const sing = (t) => t.replace(/^(\w+)/, (w) => /[^aeiou]y$/.test(w) ? w.slice(0, -1) + "ies" : /(s|sh|ch|x|z|o)$/.test(w) ? w + "es" : w + "s");   /* "1 in every 20 people cuts spending" */
    const unitOf = (a) => { const r = Math.abs(a.value_raw); return r >= 9 && r < 11 ? { n: 1, unit: 10 } : r >= 4.5 && r < 5.5 ? { n: 1, unit: 20 } : { n: a.shown, unit: 100 }; };
    const figText = (phr, a) => { const u = unitOf(a); return phr.replace("{n}", String(u.n)).replace("100", String(u.unit)).replace("who otherwise would not", modal === "could" ? "who otherwise could not" : modal === "may" ? "who otherwise might not" : "who otherwise would not"); };   /* the modal agrees with the clause it ends */

    /* ---- render one version of the statement ---- */
    function render(opt) {
      P.mode = { shortName: !!opt.shortName, shortAud: !!opt.shortAud, plainSubj: !!opt.plainSubj };
      const trigPicks = opt.dropTrig2 && trigPicksAll.length > 1 ? [keepOne(trigPicksAll)] : trigPicksAll, tcl = trigText(trigPicks, modal); if (!tcl) return null;
      const cx = { ...cxBase, plain_trigger: plainTriggerOf(trigPicks) };
      const hcs = hookCands(cx); let fam = null, fc = [];
      for (const f of FAMILY_ORDER) { fc = hcs.filter((h) => h.row.family === f); if (fc.length) { fam = f; break; } }
      if (!fam) return null;
      const th2 = opt.dropTheme2 || !v2 ? null : th[1];
      const resp = (modal ? modal + " " : "") + v1.text, resp2 = v2 && th2 ? " and " + v2.text : "";
      const there = whoRow ? S(therePick, "who") : S(therePick, "who");
      const qualOn = !coherent && !opt.noQual;
      const slotsBase = (grp, q) => ({
        Trigger: S(cap(tcl), "trigger"), trigger: S(tcl, "trigger"), trigger2: S(clausePartner || "", "contrast"), subj: q ? qs(rowR.level === "world" ? "people" : P.subj(rowR), q, rowR.level !== "world") : rowR.level === "world" ? "people" : S(P.subj(rowR), "who"), there: q ? qs(therePick, q, true) : there,
        resp: S(resp, "response"), resp2: S(resp2, "response"), mod_: modal ? modal + " " : "", frame_vp: vpPick || "", frame: noun || "", Frame_cap: cap(noun || ""), tier: tierWord, Stake_cap: cap(stakeWord),
        Place: whoRow ? S(cap(P.place(whoRow)), "who") : "", place: whoRow ? S(P.place(whoRow), "who") : "", s: whoRow ? P.s(whoRow) : "s", is: whoRow ? P.is(whoRow) : "is",
        does: modal || "does", feels: modal ? modal + " feel" : "feels", now_resp: nowV ? S((modal ? modal + " " : "") + nowV.text, "response") : "", later_resp: laterV ? S(laterV.text, "response") : "", grp });
      const qs = (text, q, span) => ({ text: q + text, spans: span ? [{ start: q.length, end: q.length + text.length, beat: "who" }] : [] });
      const hookFill = (h, slots) => { const f = fill(h.text, slots), inner = f.spans.filter((s) => s.beat !== "hook"); return { text: f.text, spans: hookSpans(f.text, inner) }; };
      const bodyOk = (b, h, anchorMode) => {
        if (!list(b.families).includes(h.row.family) || b.join !== h.row.join || String(b.trigger_in_hook) !== String(h.row.trigger_in_hook) || !certOk(b) || !regOk(b)) return false;
        const nd = list(b.needs); if (nd.includes("anchor") !== anchorMode) return false;
        if (nd.includes("turn_shift") !== list(h.row.needs).includes("turn_shift")) return false;
        return nd.every((t) => needOk(t, cx));
      };
      const bodyFor = (h, anchorMode, mode) => {
        let all = ix.templates.filter((b) => bodyOk(b, h, anchorMode));
        if (opt.partnerLast) all = all.filter((b) => !list(b.needs).includes("partner"));   /* the other side of a mixed story is the LAST thing dropped from the headline */
        else if (mode === "shortest") { const pb = all.filter((b) => list(b.needs).includes("partner")); if (pb.length) return pb; }
        if (mode === "shortest") return all;
        if (anchorMode) return all;
        const cls = [all.filter((b) => list(b.needs).includes("partner")), all.filter((b) => list(b.needs).includes("local")), all];
        return cls.find((c) => c.length) || [];
      };
      const hasSoft = (t) => ix.softRe.test(t);
      let anchorHead = !!anchor && anchor.kind === "pts" && !opt.anchorLine2, bodyRow = null, h = null, hf = null, f = null, anchorObj = null, tailUsed = false;
      const attempt = (anchorMode, hh) => {
        const bs = bodyFor(hh, anchorMode, opt.shortBody ? "shortest" : "pref"); if (!bs.length) return null;
        const mkAnchorSlot = (b) => {
          const grp = /^WHO_/.test(hh.row.family) ? therePick : (rowR.level === "world" ? "people" : P.subj(rowR));
          const phr = pick("anchor", ix.by("anchor", (r) => r.id === "pts").map((r) => r.text)), txt = figText(phr, anchor).replace("{grp}", grp).replace("{mod_}", modal ? modal + " " : "").replace("{act}", unitOf(anchor).n === 1 && !modal ? sing(actText) : actText);
          return S(txt, "anchor");
        };
        const render1 = (b, tail) => {
          const hslots = slotsBase(""), hfl = hookFill(hh, hslots);
          const sl = slotsBase("", qualOn && !/^(B07|B08|B61)$/.test(b.id) && !/\{trigger2\}/.test(b.template + hh.text) ? "on our numbers, " : "");   /* the net-response bodies already say "on balance" */ sl.Hook = { text: hfl.text, spans: hfl.spans }; sl.soft_tail = tail || ""; if (anchorMode) sl.anchor = mkAnchorSlot(b);
          return fill(b.template, sl);
        };
        let b = opt.shortBody ? bs.map((x) => ({ x, f: render1(x, "") })).sort((p, q) => words(p.f.text) - words(q.f.text))[0].x : pick("body", bs);
        let ff = render1(b, "");
        const tails = ix.by("soft_tail").map((r) => r.text);
        if (hushed && /\{soft_tail\}/.test(b.template) && !hasSoft(ff.text) && tails.length) { const tail = opt.shortTail ? tails.slice().sort((p, q) => words(p) - words(q))[0] : pick("soft_tail", tails); ff = render1(b, tail); tailUsed = true; }
        return { b, f: ff };
      };
      const tryHook = (hh) => {
        let r = null; if (anchorHead) r = attempt(true, hh); if (r) { anchorObj = anchor; return r; }
        anchorObj = null; return attempt(false, hh);
      };
      let hk = null;
      if (!opt.shortHook) {   /* pick the hook ROW evenly, then its phrasing: a hedge row with six phrasings must not outweigh a row with one */
        let pool = fc, slot = hookSlot;
        if (opt.fitHook) { pool = fc.filter((hh) => { const ts = tryHook(hh); return ts && words(ts.f.text) <= HEAD_MAX; }); slot = hookSlot + ":fit"; if (!pool.length) return null; }   /* another hook that fits, picked evenly, before the shortest one is forced */
        const groups = []; for (const c of pool) { const g = groups.find((x) => x[0].row.id === c.row.id); if (g) g.push(c); else groups.push([c]); }
        const g = pick(slot, groups); hk = g.length > 1 ? pick(slot + ":phr", g) : g[0];
      }
      if (opt.shortHook) { const ranked = fc.map((hh) => { const ts = tryHook(hh); return ts ? { hh, ts, w: words(ts.f.text) } : null; }).filter(Boolean).sort((p, q) => p.w - q.w); if (!ranked.length) return null; h = ranked[0].hh; const r = tryHook(h); bodyRow = r.b; f = r.f; }
      else { h = hk; let r = tryHook(h); if (!r) { for (const alt of fc) { if (alt !== h) { r = tryHook(alt); if (r) { h = alt; break; } } } } if (!r) return null; bodyRow = r.b; f = r.f; }
      /* hushed headline needs a soft word: an anchor body has no soft tail, so the anchor goes to line 2 */
      if (hushed && !hasSoft(f.text) && anchorObj) { const o2 = render({ ...opt, anchorLine2: true }); return o2; }
      return { fam: h.row.family, hook: h, body: bodyRow, f, anchorObj, trigPicks, tcl, resp, resp2, th2, cx };
    }

    const steps = [["dropped 2nd trigger", (o) => trigPicksAll.length > 1 ? { ...o, dropTrig2: true } : null], ["dropped 2nd theme", (o) => v2 ? { ...o, dropTheme2: true } : null], ["anchor to line 2", (o) => anchor && anchor.kind === "pts" && !o.anchorLine2 ? { ...o, anchorLine2: true } : null],
      ["dropped 'on our numbers'", (o) => qualify ? { ...o, noQual: true } : null], ["shortest soft tail", (o) => hushed ? { ...o, shortTail: true } : null], ["shortest body", (o) => ({ ...o, shortBody: true })], ["another hook that fits", (o) => ({ ...o, fitHook: true })], ["shortest hook", (o) => ({ ...o, shortHook: true, shortBody: true, fitHook: false })],
      ["short place name", (o) => ({ ...o, shortName: true, shortAud: true })], ["plain subject", (o) => ({ ...o, plainSubj: true })],
      ["other side to line 2", (o) => partner ? { ...o, partnerLast: true } : null]];
    let opt = {}, res = render(opt); if (!res) return null;
    const shrink = [];
    for (let pass = 0; pass < 3 && words(res.f.text) > HEAD_MAX; pass++) for (const [name, mod] of steps) {   /* a second pass lets an earlier step bite once a later one changed the body */
      if (words(res.f.text) <= HEAD_MAX) break;
      const o2 = mod(opt); if (!o2) continue; const r2 = render(o2); if (!r2) continue;
      if (r2.f.text !== res.f.text || (name === "anchor to line 2" && (!!res.anchorObj !== !!r2.anchorObj))) { opt = o2; res = r2; shrink.push(name); }
    }

    if (words(res.f.text) > HEAD_MAX) { if (ctx.debug) ctx.debug.reason = "budget"; return null; }
    P.mode = { shortName: !!opt.shortName, shortAud: !!opt.shortAud, plainSubj: !!opt.plainSubj };   /* line 2 and the beats use the same names as the headline */

    /* ---- anchor placement, line 2 ---- */
    const head = res.f, headSpans = head.spans, hf = res.hook, bodyRow = res.body;
    const trigPicks = res.trigPicks, headline = head.text;
    const anchorInHead = !!res.anchorObj;
    const sub2 = rowR.level === "world" ? "people" : P.subj(rowR);
    const frags = []; let anchorDropped = false, anchorL2Text = null;
    const modTxt = modal ? modal + " " : "";
    const l2Words = (t) => words(t);
    if (anchor && !anchorInHead) {
      const rows2 = ix.by("anchor_l2", (r) => r.id === anchor.kind);
      const mkL2 = (phr) => {
        if (anchor.kind === "pts") return figText(phr, anchor).replace("{grp}", sub2).replace("{mod_}", modTxt).replace("{act}", unitOf(anchor).n === 1 && !modal ? sing(actText) : actText);
        const nm = P.place(anchor.row); let txt = phr.replace("{Place_cap}", cap(nm)).replace("{place}", nm);
        txt = anchor.more ? txt.replace(/(about|roughly|some) \{n\}/, "more than 10").replace("{n}", "10") : txt.replace("{n}", String(anchor.shown));
        return anchor.row.level === "audience" ? txt.replace(/ moves /, " move ") : txt;
      };
      const fit2 = rows2.map((r) => mkL2(r.text)).filter((t) => l2Words(t) <= L2_ONLY_MAX), txt = pick("anchor_l2", fit2);   /* candidates that cannot fit line 2 are filtered before the pick */
      if (txt) { frags.push({ kind: "anchor", text: txt }); anchorL2Text = txt; } else anchorDropped = true;
    }
    const partnerInHead = !!clausePartner && (/\{trigger2\}/.test(hf.text) || /\{trigger2\}/.test(bodyRow.template));
    if (clausePartner && !partnerInHead) {
      const rows2 = ix.by("l2_contrast", (r) => r.id === "any" || r.id === partner.val), phr = pick("l2_contrast", rows2.map((r) => r.text));
      if (phr) frags.push({ kind: "contrast", text: phr.replace("{trigger2}", clausePartner) });
    } else if (!isWorld && !/^WHO_/.test(res.fam)) {
      const c0 = cands.find((x) => x.row.id === focusRow.id && !x.sub) || null;
      if (c0 && c0.sal >= LN2 && ix.by("l2_who", (r) => r.id === c0.kind).length) { const phr = pick("l2_who", ix.by("l2_who", (r) => r.id === c0.kind).map((r) => r.text)); frags.push({ kind: "who", text: phr }); }
    }
    if (!hushed && res.fam !== "TURN" && ["builds", "builds_sticks", "sticks", "jolt"].includes(arc.kind)) {
      const phr = pick("l2_arc", ix.by("l2_arc", (r) => r.id === arc.kind).map((r) => r.text)); if (phr) frags.push({ kind: "arc", text: phr });
    }
    if (kind === "pending" && res.fam !== "IF") { const phr = pick("l2_pending", ix.by("l2_pending").map((r) => r.text)); if (phr) frags.push({ kind: "certainty", text: phr }); }
    let anchorPartnerWon = false;   /* the other side of a mixed story outranks the figure when both cannot fit line 2 */
    { const ci = frags.findIndex((x) => x.kind === "contrast"), ai = frags.findIndex((x) => x.kind === "anchor"); if (ci >= 0 && ai >= 0 && l2Words(frags[ai].text) + l2Words(frags[ci].text) > L2_MAX) { frags.splice(ai, 1); anchorPartnerWon = true; } }
    const sel = []; let total = 0;
    for (const x of frags) { if (sel.length >= 2) break; const w = l2Words(x.text); const lim = sel.length === 0 && x.kind === "anchor" ? L2_ONLY_MAX : L2_MAX; if (!sel.length ? w <= lim : total + w <= L2_MAX) { sel.push(x); total += w; } }
    let line2 = "", spans2 = [];
    for (const x of sel) { if (line2) line2 += " "; spans2.push({ line: 2, start: line2.length, end: line2.length + x.text.length, beat: x.kind }); line2 += x.text; }
    const sel0 = sel[0]; if (sel0 && sel0.kind === "anchor" && sel.length > 1 && l2Words(sel0.text) > L2_MAX) { /* a long anchor travels alone */ }
    const anchorLine2Shown = sel.some((x) => x.kind === "anchor"), anchorShown = anchorInHead || anchorLine2Shown;

    /* ---- anchor result ---- */
    let anchorOut = null, anchorBeat;
    const T = (id, sl) => { const r = ix.by("trace", (x) => x.id === id)[0]; return r ? r.text.replace(/\{(\w+)\}/g, (m, k) => sl[k] != null ? sl[k] : m) : ""; };   /* hover words live in the lexicon table (kind trace) */
    const CP = ["Now", "Next", "Later"], whatK = kind === "announced" ? "announced" : kind;
    const aDetail = (a) => a.kind === "pts" ? `${a.rule}: ${a.decision} ${sg(a.value_raw)} points at ${tierWhere} (largest at ${CP[a.peakIdx]}); baseline: the same run without the story${a.rule === "A4" ? ", with the story counted in full (type weight removed)" : ""}; shown as ${a.shown} (rounded half up${a.shown >= 10 ? " to the nearest 5" : ""}); threshold ${A1_MIN.toFixed(1)}`
      : `A3: ${a.decision} ${a.row.label} ${sg(a.rp)} vs World ${sg(a.wp)} (x${a.value_raw.toFixed(2)}); shown as ${a.more ? "more than 10" : a.shown}; thresholds ratio ${A3_RATIO}, world ${A3_WORLD}, row ${A3_ROW}`;
    const aTrace = (a) => {
      if (a.kind === "pts") { const u = unitOf(a); return [T("anchor_pts", { n: u.n, unit: u.unit, act: actText, checkpoint: CP[a.peakIdx] }), hedgedKind ? T("anchor_hedge", { what: T("what_" + whatK, {}), counted_as: T("counted_" + whatK, {}), weight: weight }) : "", u.unit !== 100 ? T("anchor_fraction", { value: Math.abs(a.value_raw).toFixed(1), unit: u.unit }) : ""].filter(Boolean).join(" ") + "\nDetails: " + aDetail(a); }
      return T("anchor_multiple", { act: (ix.act[a.decision] || {})[a.sign] || "act", n: a.more ? "more than 10" : a.shown, place: P.place(a.row) }) + "\nDetails: " + aDetail(a);
    };
    const noFig = (id, detail) => T(id, { act: (ix.act[ld.id] || {})[ld.p < 0 ? "down" : "up"] || "act", value: Math.abs(ld.p).toFixed(1) }) + (detail ? "\nDetails: " + detail : "");
    if (anchor && anchorShown) {
      let spanObj, text;
      if (anchorInHead) { const sp = headSpans.find((s) => s.beat === "anchor"); spanObj = sp ? { line: 1, start: sp.start, end: sp.end, beat: "anchor" } : null; text = sp ? headline.slice(sp.start, sp.end) : ""; }
      else { const sp = spans2.find((s) => s.beat === "anchor"); spanObj = sp; text = anchorL2Text; }
      anchorOut = { kind: anchor.rule === "A4" ? "if_true_pts" : anchor.kind, rule: anchor.rule, decision: anchor.decision, value_raw: anchor.value_raw, shown: anchor.shown, where: anchorInHead ? "headline" : "line2", text, figure: anchor.kind === "pts" ? unitOf(anchor) : { n: anchor.shown, unit: null }, measured_against: anchor.kind === "pts" ? "no-event control run (points = extra people per 100 who take that decision)" : "world row, same decision (peak)", span: spanObj };
      anchorBeat = { kind: "anchor", icon: "number", short: anchor.kind === "pts" ? `${unitOf(anchor).n} in every ${unitOf(anchor).unit}` : `${anchor.more ? "10+" : anchor.shown} times the world`, text, value: anchor.value_raw, shown: anchor.shown, rule: anchor.rule, trace: aTrace(anchor) };
    } else anchorBeat = { kind: "anchor", icon: "number", text: null, trace: anchor ? noFig(anchorPartnerWon ? "none_partner" : "none_budget", aDetail(anchor)) : noFig(anchorWhyId, anchorWhy) };

    /* ---- spans and beats ---- */
    const spans = [...headSpans.map((x) => ({ line: 1, ...x })), ...spans2];
    const tPick = trigPicks[0], rowName = rowR.level === "world" ? "World" : rowR.label;
    const hookBeatText = hf.text.replace(/\{\w+\}/g, "").replace(/\s+/g, " ").replace(/[,:\s]+$/, "").trim();
    const beats = [
      { kind: "hook", icon: "dot", text: hookBeatText, short: res.fam, trace: `${res.fam}: first family in the order with an eligible hook; hook ${hf.id} (${hf.row.id}), body ${bodyRow.id}` },
      { kind: "trigger", icon: "condition", text: res.tcl, trace: story.trigger.trace || `trigger ${tPick.dial} ${tPick.direction}` },
      certBeat,
      { kind: "frame", icon: "topic", short: noun, p: story.frame.p, text: noun, trace: `${story.frame.trace || "frame " + story.frame.id}${guard ? "; " + guard : ""}; response sense ${sn.dir} (spend+buy_new+subscribe+travel ${sg(sn.v)}); ${fits ? "fits" : "does not fit"} theme ${thTok(th[0])}` },
      { kind: "register", icon: TIER_ICON[tierRow.tier] || "tier2", short: `${register} · ${tierRow.tier}`, text: register, trace: `${tierWhere} tier ${tierRow.tier}${num(tierRow.score) ? ` (score ${tierRow.score})` : ""} -> ${TIER_REG[tierRow.tier]}${capped ? "; a conditional is never stark, capped at plain" : ""}${useIf ? "; if-true run" : ""}` },
      { kind: "response", icon: th[0].top, decision: th[0].top, short: v1.text, text: [v1.text, res.th2 && v2 && v2.text].filter(Boolean).join(" and "), trace: th.map((t) => `${t.theme}: ${t.members.slice(0, 3).map((q) => q.id + " " + sg(q.p)).join(", ")} (peak points at ${rowName})`).join("; ") },
      anchorBeat,
      { kind: "arc", icon: ARC_ICON[arc.kind], short: ARC_WORD[arc.kind], text: arc.kind === "fades" ? null : (ix.by("l2_arc", (r) => r.id === arc.kind)[0] || {}).text, trace: `${ld.id} at ${rowName}: now ${sg(ld.v[0])}, next ${sg(ld.v[1])}, later ${sg(ld.v[2])}; peak ${["now", "next", "later"][arc.peakIdx]}; keeps ${Math.round(arc.keeps * 100)}%` },
      { kind: "contrast", icon: "condition", text: clausePartner, trace: partner ? `partner ${partner.dial} ${partner.direction} (${partner.val}, amount ${num(partner.amount) ? partner.amount.toFixed(3) : "?"}, Q2 p ${num(partner.p) ? partner.p.toFixed(3) : "?"}) against the lead ${leadPick.dial} (${leadVal})` : "no reported reading of the opposite valence at half the lead's weight" },
      { kind: "stake", icon: "dot", text: stakeDec ? stakeWord : null, trace: stakeDec ? `${stakeDec} has stakes >= 4 and moves ${sg(stakeTh.topP)} points` : "no shown theme with stakes >= 4 and 0.75 pts" },
      { kind: "turn", icon: "later", text: turnShift ? `${nowT.theme} then ${laterT.theme}` : null, trace: turnShift ? `${nowT.theme} leads at Now, ${laterT.theme} at Later` : nowT ? `${nowT.theme} leads at Now and at Later` : "no theme reaches 0.25 at Now" },
    ];
    if (whoRow) beats.push({ kind: "who", icon: whoRow.level === "audience" ? "group" : "place", short: P.place(whoRow), text: who.kind === "local" ? P.place(whoRow) : P.place(whoRow), trace: who.kind === "local" ? `entry ${entry.id}: world max ${sg(wmax)} vs entry max ${sg(emax)}` : `${ld0.id}: ${whoRow.label} ${sg(who.rp)} vs ${who.refId === worldRow.id ? "World" : (P.byId[who.refId] || {}).label} ${sg(who.ref)} ${num(who.r) && isFinite(who.r) ? `(x${who.r.toFixed(2)})` : "(the world moves under 0.25, so there is no ratio)"}` });
    return { headline, line2, family: res.fam, hook: hf.id, body: bodyRow.id, template: bodyRow.id, lead: res.fam, register, frame: frameId, seed, spans, beats, picks: picksLog, shrink, anchor: anchorOut };
  }

  /* ---------- the story the backend sends, derived from a fixture plus the two classifier answers (tests and page injection) ---------- */
  function deriveStory(resp, cls) {
    const I = resp.identify, imp = resp.impact, byAmt = (a, b) => Math.abs(b.amount) - Math.abs(a.amount), all = I.readings || [], rd = all.filter((r) => r.basis !== "expected").sort(byAmt).concat(all.filter((r) => r.basis === "expected").sort(byAmt)).slice(0, 6), w = I.weight || {}, g = I.gate || {};
    const gv = (k) => g[k] || 0;
    const kind = !I.counted ? "no_impact" : gv("opinion") >= 0.9 ? "opinion" : gv("happened") < 0.5 ? (gv("forecast") > gv("announced") ? "forecast" : "announced") : (rd.length && rd.every((r) => r.mode === "expected_pending") ? "pending" : "happened");
    const modal = { forecast: "would", opinion: "could", unclear: "may", announced: "will", pending: "" }[kind] || "";
    const fp = (cls.frame_choice && cls.frame_choice.p) || {}, fs = Object.entries(fp).sort((a, b) => b[1] - a[1]);
    const tp = cls.trigger_choice || {}, ts = Object.entries(tp).sort((a, b) => b[1] - a[1]), picks = [];
    const mk = (dial, p) => { const r = rd.find((x) => x.dial === dial); return r ? { dial, direction: r.direction, basis: r.basis, mode: r.mode, strength: r.strength, severity: r.severity, p } : null; };
    if (rd.length === 1) picks.push(mk(rd[0].dial, null)); else if (ts.length) { const a = mk(ts[0][0], ts[0][1]); if (a) picks.push(a); if (ts[1] && ts[0][1] - ts[1][1] < 0.2) { const b = mk(ts[1][0], ts[1][1]); if (b) picks.push(b); } }
    const mxAt = (id) => { const P = imp.places[id] || {}; return Math.max(0, ...Object.values(P).map((v) => Math.abs(peakOf(v)))); };
    const wm = mxAt("WORLD:world"), em = mxAt(I.entry);
    const f2 = (x) => (Math.round(x * 100) / 100).toString(), top = (a) => a ? `${a[0]} ${f2(a[1])}` : "";
    return {
      version: 2,
      certainty: { kind, modal, weight_type: w.type, weight: w.value, gate: g, trace: `weight ${w.type} ${w.value}; gate happened ${g.happened}, announced ${g.announced}, opinion ${g.opinion}, forecast ${g.forecast}` },
      frame: { id: fs.length ? fs[0][0] : "ripple", p: fs.length ? fs[0][1] : 0, runner_up: fs[1] ? { id: fs[1][0], p: fs[1][1] } : null, probs: fp, state_moves: (cls.frame_choice && cls.frame_choice.state_moves) || [], trace: `frame choice: ${top(fs[0])}${fs[1] ? ", runner-up " + top(fs[1]) : ""}` },
      trigger: { asked: rd.length >= 2, picks, runner_up: ts[1] ? { dial: ts[1][0], p: ts[1][1] } : null, probs: tp, trace: ts.length ? `trigger choice: ${top(ts[0])}${ts[1] ? ", runner-up " + top(ts[1]) : ""}` : "" },
      scale: { tier: imp.significance && imp.significance.tier, score: imp.significance && imp.significance.score, trace: imp.significance ? `Size ${imp.significance.score} (${imp.significance.tier})` : "" },
      entry: { id: I.entry, place: /^COUNTRY:/.test(I.entry || "") ? "country" : I.country === "global" && I.country_p == null && "country" in I ? "unresolved" : "world", local: /^COUNTRY:/.test(I.entry || "") && wm < MIN_MOVE && em >= MIN_MOVE, world_max: wm, entry_max: em },
    };
  }

  /* ---------- banned patterns (tests and a runtime check) ---------- */
  function banned(text) {
    const v = [], t = String(text || "");
    if (/likelier/i.test(t)) v.push("likelier");
    if (/\d\.\d/.test(t)) v.push("decimal");
    if (/%/.test(t)) v.push("percent");
    if (/\b(next|last) (week|month|year)|for (days|weeks|months|years)\b|\bin (days|weeks|months)\b/i.test(t)) v.push("calendar time");
    for (const s of ["Elsewhere, barely a ripple", "Little changes elsewhere", "A tiny shift that reaches", "Fades slowly", "no decision moves enough to matter"]) if (t.includes(s)) v.push("stock phrase: " + s);
    /* a comma list is "X, Y and Z" among items; a hook before a colon and a leading subordinate clause ("as ...,", "if ...,") are not list items */
    for (const sentence of t.split(/(?<=[.!?])\s+/)) {
      const body = sentence.replace(/^[^:]*: /, "").replace(/^(as|because|while|even if|if|once|when|should|were|taking|on our numbers|even granting|one writer's view|an opinion piece)\b[^,]*, /i, "").replace(/^in [^,]+, and hardly anywhere else, /i, "");
      const flat = body.replace(/, (and|or|so|but|yet|though|leaving|which) /g, " ~ ");   /* clause joiners are not list separators */
      if (/[\w'-]+, [\w'-]+(?: [\w'-]+){0,2},? (?:and|or) [\w'-]+/.test(flat)) v.push("comma list");
    }
    return v;
  }

  return { compose, deriveStory, parseCsv, banned, hash, version: 2 };
});
