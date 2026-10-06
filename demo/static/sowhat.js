/* So what composer: pure, dependency-free, deterministic.
   Browser: window.SoWhat. Node: module.exports.
   Rules: probes/world-engine/spec/so-what-ontology.md and so-what-contract.md. Words: sowhat_frames / sowhat_lexicon / sowhat_templates CSVs.
   compose(ctx) or compose(story, focusRows, tables) returns {headline, line2, spans, beats, template, lead, frame, shrink} or null (never throws). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(); else root.SoWhat = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const MIN_MOVE = 0.25, LN2 = Math.LN2, LN10 = Math.LN10;
  const SENSE_NEEDED = { squeeze: "not up", relief: "not down", scare: "not up", blow: "not up", shake_up: "any", surge: "any", freeze: "not up", rift: "any", boost: "not down", ripple: "any", plain: "any" };
  const HEDGE_OFFSET = { squeeze: 0, scare: 0, shake_up: 0, freeze: 0, boost: 0, plain: 0, relief: 1, blow: 1, surge: 1, rift: 1, ripple: 1 };
  const LOCAL_OFFSET = { squeeze: 0, freeze: 0, plain: 0, scare: 1, surge: 1, relief: 1, boost: 1, blow: 2, shake_up: 2, rift: 2, ripple: 2 };
  const TIER_SAL = { Negligible: 0.2, Minor: 0.4, Notable: 0.7, Major: 1, Historic: 1 }, BAND_SAL = { none: 0, small: 0.3, clear: 0.5, big: 1, huge: 1 };
  const TIER_ICON = { Negligible: "tier1", Minor: "tier2", Notable: "tier3", Major: "tier4", Historic: "tier5" }, BAND_ICON = { small: "tier2", clear: "tier3", big: "tier4", huge: "tier5" };
  const ARC_SAL = { builds: 0.8, builds_sticks: 0.8, sticks: 0.6, jolt: 0.6, fades: 0.3 }, ARC_ICON = { jolt: "now", builds: "next", builds_sticks: "next", sticks: "later", fades: "later" };
  const CERT_ICON = { happened: "now", announced: "next", pending: "next", forecast: "eye", opinion: "share", unclear: "dot" };

  /* ---------- small helpers ---------- */
  const num = (x) => typeof x === "number" && isFinite(x);
  const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const words = (s) => (s.trim() ? s.trim().split(/\s+/).length : 0);
  const sg = (v, d = 2) => (v >= 0 ? "+" : "-") + Math.abs(v).toFixed(d);
  const peakOf = (v) => { let b = 0; for (const x of v) if (num(x) && Math.abs(x) > Math.abs(b)) b = x; return b; };
  const hash = (t) => { let h = 5381; for (let i = 0; i < t.length; i++) h = ((h * 33) ^ t.charCodeAt(i)) >>> 0; return h; };   /* djb2: deterministic, never random */
  const S = (text, beat) => ({ text: text || "", spans: text && beat ? [{ start: 0, end: text.length, beat }] : [] });

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

  /* ---------- tables ---------- */
  const rowsOf = (x) => typeof x === "string" ? parseCsv(x) : Array.isArray(x) ? x : x && Array.isArray(x.rows) ? x.rows : null;
  const cache = typeof WeakMap === "function" ? new WeakMap() : null;
  function index(t) {
    if (!t || typeof t !== "object") return null; if (cache && cache.has(t)) return cache.get(t);
    const fr = rowsOf(t.frames), lx = rowsOf(t.lexicon), tp = rowsOf(t.templates); if (!fr || !lx || !tp || !lx.length || !tp.length) return null;
    const lex = {}; for (const r of lx) (lex[r.kind] || (lex[r.kind] = {}))[r.id] = r;
    const ix = { frames: Object.fromEntries(fr.map((r) => [r.id, r])), lex, templates: tp, get: (k, id) => (lex[k] || {})[id], list: (k) => Object.values(lex[k] || {}) };
    for (const k of ["decision", "theme", "condition", "degree", "tier", "band", "reach", "certainty", "arc", "who", "who_lead", "ref", "line2", "place"]) if (!lex[k]) return null;
    if (cache) cache.set(t, ix); return ix;
  }
  function degree(ix, size) {
    const k = size < 0.75 ? "small" : size < 3 ? "mid" : "large", r = ix.get("degree", k) || {}, alt = /\{degp\}=\s*(.*)$/.exec(r.text_alt || "");
    return { deg: r.text || "", degp: alt ? " " + alt[1].trim() : "" };
  }
  const putDeg = (verb, d) => verb.replace("{deg}", d.deg).replace("{degp}", d.degp).replace(/\s+/g, " ").trim();
  const bandOf = (v) => { const a = Math.abs(v); return a < 0.25 ? "none" : a < 1 ? "small" : a < 3 ? "clear" : a < 8 ? "big" : "huge"; };
  const reachKey = (p) => p >= 90 ? "r90" : p >= 60 ? "r60" : p >= 40 ? "r40" : p >= 20 ? "r20" : p >= 5 ? "r5" : "r0";

  /* ---------- places and subjects ---------- */
  const takesThe = (n) => /^(United |Netherlands|Philippines|Democratic Republic)/.test(n);
  function makePlaces(rows, ix) {
    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    const cname = (label) => { const c = String(label).split(" · ")[0]; return { plain: c, the: (takesThe(c) ? "the " : "") + c }; };
    const aud = (r) => { const a = ix.get("audience", r.label); return a && a.text ? a.text : String(r.label).toLowerCase().replace(/,/g, "").replace(/\s+/g, " ").trim() + " people"; };
    function place(r) {
      if (r.level === "world") return "the world"; if (r.level === "audience") return aud(r);
      if (r.level === "country") return cname(r.label).the;
      const parts = String(r.label).split(" · "), par = byId[r.parent], c = cname(par ? par.label : parts[0]), suf = parts[1] || "", pr = ix.get("place", suf);
      if (!pr) return (suf ? suf + " " : "") + c.the;
      const alt = pr.text_alt && takesThe(c.plain) ? pr.text_alt.replace("{name}", c.plain) : null;
      return alt || pr.text.replace("{country}", c.the);
    }
    return { byId, place, countryOf: (r) => r.level === "country" ? r : byId[r.parent],
      subj: (r) => r.level === "world" ? "people" : r.level === "audience" ? aud(r) : "people in " + place(r),
      there: (r) => r.level === "audience" ? "they" : "people there", s: (r) => r.level === "audience" ? "" : "s" };
  }

  /* ---------- numbers per row ---------- */
  function peaksAt(places, id) {
    const P = places && places[id]; if (!P || typeof P !== "object") return null;
    const out = []; for (const d of Object.keys(P)) { const v = P[d]; if (Array.isArray(v) && v.length >= 3 && v.every(num)) out.push({ id: d, v, p: peakOf(v) }); }
    return out.length ? out : null;
  }
  const lead = (pk) => pk.reduce((a, b) => Math.abs(b.p) > Math.abs(a.p) ? b : a, pk[0]);
  const peakDec = (places, row, d) => { const P = places[row]; return P && Array.isArray(P[d]) ? peakOf(P[d]) : 0; };
  function sense(pk) { const x = pk.filter((q) => ["spend", "buy_new", "subscribe", "travel"].includes(q.id)).reduce((a, q) => a + q.p, 0); return { v: x, dir: x <= -MIN_MOVE ? "down" : x >= MIN_MOVE ? "up" : "flat" }; }
  const senseOk = (family, dir) => { const n = SENSE_NEEDED[family] || "any"; return n === "any" || (n === "not up" && dir !== "up") || (n === "not down" && dir !== "down"); };

  function themesOf(pk, ix) {
    const by = Object.fromEntries(pk.map((q) => [q.id, q])), out = [];
    for (const th of ix.list("theme")) {
      const ms = String(th.text).split(";").map((s) => s.trim()).filter(Boolean).map((id) => by[id]).filter((q) => q && Math.abs(q.p) >= MIN_MOVE).sort((a, b) => Math.abs(b.p) - Math.abs(a.p));
      if (!ms.length) continue;
      const top = ms[0], sign = top.p < 0 ? "down" : "up", same = ms.filter((q) => (q.p < 0) === (top.p < 0)), size = Math.abs(top.p), d = degree(ix, size);
      const useTheme = same.length >= 2 && Math.abs(same[1].p) >= 0.5 * size, dec = ix.get("decision", top.id);
      const raw = useTheme ? th[sign] : dec ? dec[sign] : th[sign]; if (!raw) continue;
      out.push({ theme: th.id, size, sign, top: top.id, members: ms, useTheme, verb: putDeg(raw, d) });
    }
    return out.sort((a, b) => b.size - a.size);   /* stable */
  }

  /* ---------- trigger clause ---------- */
  function clause(ix, pick, modal) {
    const c = ix.get("condition", pick.dial); if (!c) return null;
    const down = pick.direction === "down", plain = down ? c.down : c.up, bare = (down ? c.down_bare : c.up_bare) || plain;
    if (modal) return `${c.noun} ${modal} ${bare}`;
    if (pick.basis === "expected" || pick.mode === "expected_pending") return `${c.noun} should ${bare}`;
    return `${c.noun} ${plain}`;
  }

  /* ---------- WHO ---------- */
  function ratio(rowP, refP) {
    const both = Math.abs(rowP) >= MIN_MOVE && Math.abs(refP) >= MIN_MOVE;
    let r = refP ? rowP / refP : 0, kind, sal;
    if (r <= 0) { kind = both && rowP * refP < 0 ? "opposite" : "far_less"; sal = kind === "opposite" ? 2 : LN10 / 2; }
    else { kind = r >= 2.5 ? "x_many" : r >= 1.75 ? "x2" : r >= 1.25 ? "more" : r > 0.8 ? "same" : r > 0.6 ? "bit_less" : r > 0.35 ? "half" : "far_less"; sal = Math.min(Math.abs(Math.log(r)), LN10); if (r < 1) sal /= 2; if (kind === "same") sal = 0; }
    return { r, kind, sal };
  }
  function whoText(ix, k, r, plural, refText) {   /* "react{s} about twice as much as most people" with {s} filled */
    const row = ix.get("who", k); if (!row) return null;
    let t = row.text; if (k === "x_many") t = r.r > 5 ? t.replace("about {n}", "many") : t.replace("{n}", String(Math.round(r.r)));
    return t.replace("{ref}", refText).replace(/\{s\}/g, plural ? "" : "s");
  }

  /* ---------- arc ---------- */
  function arcOf(v) {
    const pk = peakOf(v), pi = v.reduce((b, x, i) => Math.abs(x) > Math.abs(v[b]) ? i : b, 0), keeps = pk ? Math.max(0, Math.min(1, v[2] / pk)) : 0;
    const kind = pi > 0 && Math.abs(v[1]) >= 1.25 * Math.abs(v[0]) ? (keeps >= 0.6 ? "builds_sticks" : "builds") : keeps >= 0.6 ? "sticks" : pi === 0 && keeps < 0.35 ? "jolt" : "fades";
    return { kind, keeps, peakIdx: pi };
  }

  /* ---------- template filling ---------- */
  function fill(tpl, slots) {
    let out = "", spans = [], last = 0, m; const re = /\{(\w+)\}/g;
    while ((m = re.exec(tpl))) {
      out += tpl.slice(last, m.index); const v = slots[m[1]], o = v == null ? { text: "", spans: [] } : typeof v === "string" ? { text: v, spans: [] } : v, st = out.length;
      out += o.text; for (const s of o.spans) spans.push({ start: st + s.start, end: st + s.end, beat: s.beat }); last = re.lastIndex;
    }
    return { text: out + tpl.slice(last), spans: mergeSpans(spans) };
  }
  function mergeSpans(sp) {
    const o = []; for (const s of sp.slice().sort((a, b) => a.start - b.start || b.end - a.end)) { const p = o[o.length - 1]; if (p && p.beat === s.beat && s.start <= p.end && s.end >= p.end) p.end = s.end; else o.push({ ...s }); } return o;
  }
  const pickTemplate = (ix, family, leadK, certKind) => {
    const ok = (r) => r.lead === leadK && (r.certainty === "any" || r.certainty.split("|").includes(certKind));
    return ix.templates.find((r) => r.frame === family && ok(r)) || ix.templates.find((r) => r.frame === "plain" && ok(r)) || null;
  };

  /* ---------- the composer ---------- */
  function normalise(a, b, c) {
    const ctx = b !== undefined || c !== undefined ? Object.assign({}, b, { story: a, tables: c }) : a;
    return ctx && typeof ctx === "object" ? ctx : null;
  }
  function compose(a, b, c) {
    try { return run(normalise(a, b, c)); } catch (e) { return null; }
  }
  function run(ctx) {
    if (!ctx) return null;
    const story = ctx.story, ix = index(ctx.tables || ctx.rules), rows = ctx.rows;
    if (!story || !story.certainty || !story.frame || !ix || !Array.isArray(rows) || !rows.length) return null;
    const P = makePlaces(rows, ix), focusRow = P.byId[ctx.focus] || rows.find((r) => r.level === "world") || rows[0], worldRow = rows.find((r) => r.level === "world") || rows[0];
    const places = ctx.places || {}, rank = Array.isArray(ctx.rank) ? ctx.rank : [], textLen = String(ctx.text || "").length;
    const kind = story.certainty.kind, modal = story.certainty.modal || "", isWorld = focusRow.level === "world", entry = story.entry || {};
    const localStory = !!(entry.local && P.byId[entry.id]), local = localStory && isWorld;
    /* where the story is (ontology 1.8): only a real country row lets the so-what name a place; the world entry names none; an unresolved place (a bloc, two countries, a country with no row) falls back to the plain place-free template */
    const entryKind = entry.id && P.byId[entry.id] && P.byId[entry.id].level === "country" ? "country" : entry.place === "unresolved" ? "unresolved" : "world", placeOk = entryKind === "country";
    const picks = story.trigger && Array.isArray(story.trigger.picks) ? story.trigger.picks : [];
    const hedgeRow = ix.get("certainty", kind);
    const frameRow = ix.frames[story.frame.id];
    const beats = [];
    const certBeat = { kind: "certainty", icon: CERT_ICON[kind] || "dot", text: kind, trace: story.certainty.trace || "" };

    /* quiet: no impact */
    if (kind === "no_impact") {
      const t = ix.templates.find((r) => r.id === "NO-X"); if (!t) return null;
      return { headline: t.template, line2: "", template: "NO-X", lead: "quiet", frame: null, spans: [], shrink: [], beats: [certBeat] };
    }
    if (!frameRow || !hedgeRow || !picks.length && story.trigger && story.trigger.asked !== false && story.trigger.picks == null) return null;

    const respId0 = local ? entry.id : focusRow.id, pk0 = peaksAt(places, respId0);
    if (!pk0) return null;
    const themes0 = themesOf(pk0, ix);

    /* ---- quiet: counted but nothing reaches MIN_MOVE ---- */
    if (!themes0.length) {
      const fam = frameRow.template_family || frameRow.id, id = kind === "opinion" ? "NO-O" : kind === "forecast" || kind === "unclear" ? "NO-F" : fam === "ripple" && ix.templates.some((r) => r.id === "RP-S") ? "RP-S" : "NO-Q";
      const t = ix.templates.find((r) => r.id === id); if (!t) return null;
      const var1 = (HEDGE_OFFSET[fam] || 0) + textLen, forS = isWorld ? "" : " for " + P.subj(focusRow);
      let usePicks = picks, shrinkQ = [], tcl = trigClause(ix, usePicks, modal);
      const hedge = hedgeRow ? (var1 % 2 && hedgeRow.text_alt ? hedgeRow.text_alt : hedgeRow.text) : "";
      const slots = { Trigger: S(cap(tcl), "trigger"), trigger: S(tcl, "trigger"), Hedge: S(hedge, "certainty"), for_subj: S(forS, "who") };
      const mk = () => tcl || id === "NO-O" ? fill(t.template, slots) : fill("No decision moves enough to matter{for_subj}.", slots);
      let f = mk();
      if (words(f.text) > 22 && picks.length > 1) { usePicks = [keepOne(picks)]; tcl = trigClause(ix, usePicks, modal); slots.Trigger = S(cap(tcl), "trigger"); slots.trigger = S(tcl, "trigger"); f = mk(); shrinkQ.push("dropped 2nd trigger"); }
      if (words(f.text) > 22 && hedgeRow.text_alt && words(hedgeRow.text_alt) < words(hedge)) { slots.Hedge = S(hedgeRow.text_alt, "certainty"); f = mk(); shrinkQ.push("shorter hedge"); }
      if (words(f.text) > 22) { f = fill("No decision moves enough to matter{for_subj}.", slots); shrinkQ.push("plain quiet sentence"); }
      const mx = Math.max(0, ...pk0.map((q) => Math.abs(q.p)));
      return { headline: f.text, line2: "", template: id, lead: "quiet", frame: fam, spans: f.spans.map((s) => ({ line: 1, ...s })), shrink: shrinkQ,
        beats: [{ kind: "trigger", icon: "condition", text: tcl, trace: (story.trigger && story.trigger.trace) || "" }, certBeat, { kind: "response", icon: "dot", text: "none", trace: `largest move ${sg(mx)} pts at ${P.place(P.byId[respId0] || focusRow)}, under ${MIN_MOVE}` }] };
    }

    /* ---- non-quiet: build with optional shrink steps and variant flips ---- */
    function build(opt) {
      const trigPicks = opt.dropTrig2 ? [keepOne(picks)] : picks;
      let respId = respId0, rowR = P.byId[respId] || focusRow;
      let pk = pk0, ld = lead(pk);
      /* WHO candidates */
      const refW = (id) => peakDec(places, worldRow.id, id);
      let who = null, whoFrag = null, whoLeads = false, localLead = false;
      const cands = [];
      const consider = (r, ref, refText, refId, extra) => { if (r.level !== "audience" && !placeOk) return; const rp = peakDec(places, r.id, ld.id), rr = ratio(rp, ref); cands.push({ row: r, rp, ref, refText, refId, ...rr, ...extra }); };
      if (isWorld && !local) { for (const r of rows) if ((r.level === "country" && (r.share || 0) >= 0.005) || r.level === "audience") consider(r, refW(ld.id), ix.get("ref", "world").text, worldRow.id, { sub: true }); }
      else if (focusRow.level === "country") {
        consider(focusRow, refW(ld.id), ix.get("ref", "world").text, worldRow.id, { sub: false });
        for (const r of rows) if (r.level === "region" && r.parent === focusRow.id) consider(r, peakDec(places, focusRow.id, ld.id), ix.get("ref", "country").text.replace("{country}", P.place(focusRow)), focusRow.id, { sub: true });
      } else if (!isWorld) consider(focusRow, refW(ld.id), ix.get("ref", "world").text, worldRow.id, { sub: false });
      else if (local) { /* world focus, local story: the entry row leads; nothing to compare */ }
      /* a country is named only when its change is clearly above every other country's (at least twice the runner-up), so noise between near-equal rows is never reported as "hardest hit" */
      if (isWorld && !local) { const cs = cands.filter((x) => x.row.level === "country").sort((p, q) => Math.abs(q.rp) - Math.abs(p.rp)); if (cs.length && !(Math.abs(cs[0].rp) >= 2 * Math.abs((cs[1] || { rp: 0 }).rp))) for (const x of cs) cands.splice(cands.indexOf(x), 1); }
      const leadable = cands.filter((x) => x.sub && ["x2", "x_many", "opposite"].includes(x.kind) && x.sal >= LN2).sort((p, q) => q.sal - p.sal);
      if (local) { localLead = true; who = { row: P.byId[entry.id], kind: "local" }; whoLeads = true; }
      else if (leadable.length) { who = leadable[0]; whoLeads = true; }
      const frag = cands.filter((x) => x.kind !== "same" && x !== who).sort((p, q) => Math.min(q.sal, 0.95) - Math.min(p.sal, 0.95))[0] || null;
      if (whoLeads && !localLead && isWorld) { respId = who.row.id; rowR = who.row; pk = peaksAt(places, respId) || pk; ld = lead(pk); }
      else if (whoLeads && !localLead && !isWorld) { /* a sub-row leads: the response stays at the focus */ }
      const themes = themesOf(pk, ix), th = opt.dropTheme2 ? themes.slice(0, 1) : themes.filter((t, i) => i === 0 || t.size >= 0.4 * themes[0].size).slice(0, 2);
      if (!th.length) return null;

      /* frame + coherence guard */
      const sn = sense(pk); let fam = frameRow.template_family || frameRow.id, guard = "";
      if (!senseOk(fam, sn.dir)) {
        const ru = story.frame.runner_up && ix.frames[story.frame.runner_up.id], rf = ru && (ru.template_family || ru.id);
        if (rf && senseOk(rf, sn.dir)) { guard = `top frame ${fam} contradicts the response, runner-up ${rf} used`; fam = rf; } else { guard = `top frame ${fam} contradicts the response, plain used`; fam = "plain"; }
      }
      if (entryKind === "unresolved" && fam !== "plain") { guard = `place not resolved (${story.entry && story.entry.id}), plain used`; fam = "plain"; }
      const frameNoun = fam === "plain" ? "shift" : (ix.frames[fam] || ix.frames[Object.keys(ix.frames).find((k) => (ix.frames[k].template_family || k) === fam)] || {}).noun || fam;

      /* arc, scale */
      const arc = arcOf(peakVals(places, respId, ld.id));
      const rk = rank.find((x) => x.decision === ld.id), band = bandOf(ld.p), tier = story.scale && story.scale.tier, worldScale = isWorld && !local && tier && ix.get("tier", tier);
      const scale = worldScale ? { word: ix.get("tier", tier).text, sal: TIER_SAL[tier] == null ? 0.4 : TIER_SAL[tier], icon: TIER_ICON[tier] || "tier2", reachWord: rk && num(rk.reach) && entryKind !== "unresolved" ? (ix.get("reach", reachKey(rk.reach)) || {}).text : null, world: true }
        : { word: (ix.get("band", band) || {}).text || "", sal: BAND_SAL[band] || 0, icon: BAND_ICON[band] || "tier1", world: false, band };

      /* lead beat */
      let leadK = "trigger";
      if (kind === "forecast" || kind === "opinion" || kind === "unclear") leadK = "certainty";
      else if (whoLeads) leadK = "who";
      else if (scale.sal >= 1 && scale.word && entryKind !== "unresolved") leadK = "scale";
      if (leadK === "scale" && fam === "relief" && !(scale.world && scale.reachWord)) leadK = "trigger";

      /* variants */
      const off = HEDGE_OFFSET[fam] || 0; let hv = (off + textLen) % 2, lv = ((LOCAL_OFFSET[fam] || 0) + textLen) % 3;
      if (opt.flip) { hv = 1 - hv; lv = (lv + 1) % 3; }
      let hedge = hv && hedgeRow.text_alt ? hedgeRow.text_alt : hedgeRow.text;
      if (opt.shortHedge && hedgeRow.text_alt && words(hedgeRow.text_alt) < words(hedge)) hedge = hedgeRow.text_alt; else if (opt.shortHedge && words(hedgeRow.text) < words(hedge)) hedge = hedgeRow.text;

      /* slots */
      const clauses = trigPicks.map((p) => clause(ix, p, modal)).filter(Boolean); if (!clauses.length) return null;
      const tcl = clauses.join(" and ");
      const resp = (modal ? modal + " " : "") + th[0].verb, resp2 = th[1] ? " and " + th[1].verb : "";
      const subjR = P.subj(rowR), whoRow = who && who.row, plural = whoRow ? whoRow.level === "audience" : false, s = whoRow ? P.s(whoRow) : "s";
      const slots = {
        Trigger: S(cap(tcl), "trigger"), trigger: S(tcl, "trigger"),
        subj: rowR.level === "world" ? "people" : S(subjR, "who"), there: whoRow ? S(P.there(whoRow), "who") : S(P.there(rowR), "who"),
        resp: S(resp, "response"), resp2: S(resp2, "response"), mod_: modal ? modal + " " : "",
        lands: modal ? modal + " land" : "lands", scale: S(scale.word, "scale"), band: S((ix.get("band", band) || {}).text || "", "scale"), reach: S(scale.reachWord || "", "scale"),
        Hedge: S(hedge, "certainty"), for_subj: "", frame: frameNoun,
      };
      if (leadK === "who" && whoRow) {
        const placeTxt = P.place(whoRow); let key, txt;
        if (localLead) key = lv === 0 ? "local" : lv === 1 ? "local_b" : "local_c"; else key = who.kind === "opposite" ? "opposite" : "more";
        const wl = ix.get("who_lead", key); if (!wl) return null; txt = wl.text;
        let out = "", spans = [], i = 0, m; const re = /\{(Place|place|s|frame)\}/g;
        while ((m = re.exec(txt))) { out += txt.slice(i, m.index); const val = m[1] === "Place" ? cap(placeTxt) : m[1] === "place" ? placeTxt : m[1] === "s" ? s : frameNoun; const st = out.length; out += val; if (m[1] === "frame") spans.push({ start: st, end: out.length, beat: "frame" }); i = re.lastIndex; }
        out += txt.slice(i);
        slots.Who_lead = { text: out, spans: [{ start: 0, end: out.length, beat: "who" }, ...spans] };
        if (!slots.there || !who) slots.there = S("people there", "who");
      }
      const tpl = pickTemplate(ix, opt.plain ? "plain" : fam, leadK, kind); if (!tpl) return null;
      const f = fill(tpl.template, slots);

      /* line 2 */
      const frags = [], push = (k, text, sal, order, force) => { if (text && sal >= 0.3 && (force || k !== leadK)) frags.push({ kind: k, text, sal, order }); };
      const elRow = ix.get("line2", "elsewhere") || {}, elseText = hash(f.text) % 2 && elRow.text_alt ? elRow.text_alt : elRow.text;   /* second variant chosen by a hash of the headline */
      if (local && isWorld && fam !== "ripple") push("who", elseText, 1.0, 0, true);   /* the ripple frame already says it */
      if (kind === "announced" || kind === "pending") push("certainty", hedgeRow.down, 0.95, 1);
      if (localStory && focusRow.id === entry.id) push("who", ix.get("line2", "alone").text.replace("{place}", P.place(focusRow)), 0.9, 2);
      else if (!local && frag && !(whoLeads && who === frag)) {
        const subjectless = !frag.sub || (frag.row.id === focusRow.id), wt = whoText(ix, frag.kind, frag, frag.row.level === "audience", frag.refText);
        if (wt) { const nm = P.place(frag.row), t = subjectless ? cap(wt.replace(/^(react|move)s?\s+/, (mm) => mm.startsWith("move") ? "Moves " : "")) : cap(nm) + " " + wt.replace(/^react\b/, frag.row.level === "audience" ? "react" : "reacts").replace(/^move\b/, frag.row.level === "audience" ? "move" : "moves"); push("who", t.replace(/^Moves the other/, "Moves the other") + ".", Math.min(frag.sal, 0.95), 2); }
      }
      if (ARC_SAL[arc.kind] != null) push("arc", (ix.get("arc", arc.kind) || {}).text, ARC_SAL[arc.kind], 3);
      if (scale.word) {
        const t = scale.world ? (scale.reachWord ? ix.get("line2", "scale_world").text.replace("{scale}", scale.word).replace("{reach}", scale.reachWord) : entryKind === "unresolved" ? ix.get("line2", "scale_focus").text.replace("{band}", scale.word).replace(" here", "") : "") : ix.get("line2", "scale_focus").text.replace("{band}", scale.word).replace("here", isWorld ? "there" : "here");
        const tiny = scale.world ? tier === "Negligible" : band === "small";   /* a tiny move always carries its size */
        push("scale", t, tiny ? 1.0 : scale.sal, 4);
      }
      frags.sort((p, q) => q.sal - p.sal || p.order - q.order);
      const sel = []; for (const x of frags) { if (sel.length < 2 && (!sel.length || words(sel.concat(x).map((y) => y.text).join(" ")) <= 14)) sel.push(x); }
      let line2 = "", spans2 = [];
      for (const x of sel) { if (line2) line2 += " "; spans2.push({ line: 2, start: line2.length, end: line2.length + x.text.length, beat: x.kind }); line2 += x.text; }

      /* beats */
      const tPick = trigPicks[0];
      const rowName = P.place(rowR) === "the world" ? "World" : rowR.label;
      const bs = [
        { kind: "trigger", icon: "condition", text: tcl, trace: (story.trigger && story.trigger.trace) || `trigger ${tPick.dial} ${tPick.direction}` },
        certBeat,
        { kind: "frame", icon: "topic", short: frameNoun, p: story.frame.p, text: frameNoun, trace: `${story.frame.trace || "frame " + story.frame.id}; response sense ${sn.dir} (spend+buy_new+subscribe+travel ${sg(sn.v)})${guard ? "; " + guard : ""}` },
        { kind: "response", icon: th[0].top, decision: th[0].top, short: th[0].verb, text: [th[0].verb, th[1] && th[1].verb].filter(Boolean).join(" and "), trace: th.map((t) => `${t.theme}: ${t.members.slice(0, 3).map((q) => q.id + " " + sg(q.p)).join(", ")} (peak pts at ${rowName})`).join("; ") },
        { kind: "arc", icon: ARC_ICON[arc.kind], short: ((ix.get("arc", arc.kind) || {}).text || "").replace(/\.$/, "").replace(/^A /, "").toLowerCase(), text: (ix.get("arc", arc.kind) || {}).text, trace: `${ld.id} at ${rowName}: now ${sg(ld.v[0])}, next ${sg(ld.v[1])}, later ${sg(ld.v[2])}; peak ${["now", "next", "later"][arc.peakIdx]}; keeps ${Math.round(arc.keeps * 100)}%` },
        { kind: "scale", icon: scale.icon, short: scale.word ? (scale.world ? scale.word + (scale.reachWord ? " · " + scale.reachWord : "") : scale.word) : "", text: scale.word ? (scale.world ? `A ${scale.word} shift${scale.reachWord ? " that reaches " + scale.reachWord : ""}.` : `A ${scale.word} shift.`) : "", trace: scale.world ? `Size ${num(story.scale.score) ? story.scale.score : "?"} (${tier})${rk ? `; ${ld.id} reach ${rk.reach}%` : ""}` : `${ld.id} ${sg(ld.p)} pts at ${rowName} -> band ${band} (cuts 0.25/1/3/8)` },
      ];
      const ws = frag || (who && !localLead ? who : null);
      if (localLead) bs.push({ kind: "who", icon: "place", short: P.place(who.row), text: elseText, trace: `entry ${entry.id}: world max ${sg(entry.world_max || 0)} vs entry max ${sg(entry.entry_max || 0)}` });
      else if (ws) bs.push({ kind: "who", icon: ws.row.level === "audience" ? "group" : "place", short: P.place(ws.row), text: whoText(ix, ws.kind, ws, ws.row.level === "audience", ws.refText) || "", trace: `${ld.id}: ${ws.row.label} ${sg(ws.rp)} vs ${ws.refId === worldRow.id ? "world" : (P.byId[ws.refId] || {}).label} ${sg(ws.ref)} (x${ws.r.toFixed(2)})` });
      return { headline: f.text, line2, template: tpl.id, lead: leadK, frame: fam, spans: [...f.spans.map((x) => ({ line: 1, ...x })), ...spans2], beats: bs };
    }
    function peakVals(pl, row, d) { const P = pl[row]; return P && Array.isArray(P[d]) ? P[d] : [0, 0, 0]; }

    const shrink = [];
    const prev = typeof ctx.prev === "string" ? ctx.prev : "", first3 = (t) => t.split(/\s+/).slice(0, 3).join(" ").toLowerCase();
    let opt = { dropTrig2: false, dropTheme2: false, flip: false }, res = build(opt); if (!res) return null;
    if (prev && first3(res.headline) === first3(prev)) { const r2 = build({ ...opt, flip: true }); if (r2 && first3(r2.headline) !== first3(prev)) { res = r2; opt.flip = true; } }
    if (words(res.headline) > 22 && picks.length > 1) { opt.dropTrig2 = true; const r2 = build(opt); if (r2) { res = r2; shrink.push("dropped 2nd trigger"); } }
    if (words(res.headline) > 22) { opt.dropTheme2 = true; const r2 = build(opt); if (r2) { res = r2; shrink.push("dropped 2nd response theme"); } }
    if (words(res.headline) > 22 && ["forecast", "opinion", "unclear"].includes(kind)) { opt.shortHedge = true; const r2 = build(opt); if (r2 && words(r2.headline) < words(res.headline)) { res = r2; shrink.push("shorter hedge"); } }
    if (words(res.headline) > 22) { opt.plain = true; const r2 = build(opt); if (r2 && words(r2.headline) < words(res.headline)) { res = r2; shrink.push("plain template"); } }
    res.shrink = shrink; return res;
  }
  const keepOne = (picks) => picks.find((p) => p.basis !== "expected") || picks[0];   /* when a second trigger is dropped, the reported reading is kept over an expected one */
  function trigClause(ix, picks, modal) { return picks.map((p) => clause(ix, p, modal)).filter(Boolean).join(" and "); }

  /* ---------- the story the backend will send, derived from a fixture plus the two classifier answers (tests and page injection) ---------- */
  function deriveStory(resp, cls) {
    const I = resp.identify, imp = resp.impact, byAmt = (a, b) => Math.abs(b.amount) - Math.abs(a.amount), all = I.readings || [], rd = all.filter((r) => r.basis !== "expected").sort(byAmt).concat(all.filter((r) => r.basis === "expected").sort(byAmt)).slice(0, 6), w = I.weight || {}, g = I.gate || {};
    const gv = (k) => g[k] || 0;   /* kind from the GATE, same order as sowhat_story.certainty */
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
      version: 1,
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
    if (/\b(next|last) (week|month|year)|for (days|weeks|months|years)\b|\bin (days|weeks|months)\b/i.test(t)) v.push("calendar time");
    const body = t.replace(/^(If|Once|When)\b[^,]*, /, "").replace(/^(An opinion piece|One writer's view); [^,]*, /, "");   /* an opening hedge ends in a comma and is not a list item */
    const w = "[\\w'-]+(?: [\\w'-]+){0,2}", flat = body.replace(/, (and|or) /g, " & ");   /* ", and" only ever joins clauses; a list is "X, Y and Z" or "X, Y, and Z" */
    if (new RegExp(`${w}, (?!so |and |but |because )${w}(?:,)? (?:and|or) [\\w'-]+`).test(flat) || /, (and|or) /.test(body) && new RegExp(`${w}, ${w}, (?:and|or) `).test(body)) v.push("comma list");
    return v;
  }

  return { compose, deriveStory, parseCsv, banned, version: 1 };
});
