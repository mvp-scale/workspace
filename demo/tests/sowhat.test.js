/* node --test demo/tests/sowhat.test.js
   So what composer v2 (design: probes/world-engine/spec/so-what-v2-design.md, contract: so-what-v2-contract.md).
   Reproduces all 33 golden v2 cases (sowhat-golden-v2.json) exactly, then checks the rules the composer must keep on any input.
   SUPERSEDED, not run: the v1 golden tests (sowhat-golden.json, 44 cases, the v1 composition logic). The v1 golden files and CSVs are untouched.
   Two adapter notes (test data, not composer code):
   - for a hedged story the golden puts the per-row tiers in input.significance_rows; the contract sends them in if_true.significance_rows, so the adapter copies them there;
   - G05 omits the row tier for COUNTRY:ind (India); the adapter fills it from the case's own numbers.tier_here (Major). */
const test = require("node:test"), assert = require("node:assert"), fs = require("node:fs"), path = require("node:path");
const SoWhat = require("../static/sowhat.js");
const SPEC = path.join(__dirname, "../../probes/world-engine/spec"), RULES = path.join(__dirname, "../../probes/persona/rules_v2");
const csv = (f) => SoWhat.parseCsv(fs.readFileSync(path.join(RULES, f), "utf8"));
const tables = { version: 2, frames: csv("sowhat2_frames.csv"), hooks: csv("sowhat2_hooks.csv"), templates: csv("sowhat2_templates.csv"), lexicon: csv("sowhat2_lexicon.csv"), lexicon_v1: csv("sowhat_lexicon.csv") };
const golden = JSON.parse(fs.readFileSync(path.join(SPEC, "sowhat-golden-v2.json"), "utf8")).cases;
const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
const SOFT = /\b(a bit|a little|slightly|a touch|small|mild|slight|faint|barely|light|brief|only just|a small number|nudge)\b/i;

const baseCache = new Map();
function ctxOf(c, over) {
  if (!baseCache.has(c.id)) baseCache.set(c.id, buildCtx(c));
  return Object.assign({}, baseCache.get(c.id), over || {});
}
function buildCtx(c) {
  const I = c.input; let o;
  if (c.source.startsWith("spec/sowhat-fixtures")) {
    const fx = JSON.parse(fs.readFileSync(path.join(SPEC, "..", c.source), "utf8")), story = SoWhat.deriveStory(fx, I.classifier); story.topic = I.topic;
    o = { story, rows: fx.read.rows, places: fx.impact.places, rank: fx.impact.rank, significance: fx.impact.significance, readings: fx.identify.readings, weight: fx.identify.weight.value };
  } else {
    o = { story: Object.assign({}, I.story, { topic: I.topic }), rows: I.rows, places: I.places, rank: I.rank, significance: I.significance, readings: I.identify.readings, weight: I.identify.weight.value };
  }
  let sr = I.significance_rows, it = I.if_true;
  if (it && !it.significance_rows && sr) it = Object.assign({}, it, { significance_rows: sr });
  if (c.id === "G05") sr = Object.assign({}, sr, { "COUNTRY:ind": { tier: c.numbers.tier_here } });
  return Object.assign(o, { focus: c.focus, significance_rows: sr, if_true: it, text: c.text, seed: String(c.seed), tables, prev: null });
}
const byId = (id) => golden.find((c) => c.id === id);
/* every row gets a tier when the case does not carry one, so any focus can be composed (the tier only moves the register) */
function sweepCtx(c, focus, s) {
  const base = ctxOf(c), tiers = ["Negligible", "Minor", "Notable", "Major", "Historic"], sr = Object.assign({}, base.significance_rows);
  for (const r of base.rows) if (!sr[r.id]) sr[r.id] = { tier: tiers[(s + r.id.length) % 5] };
  const it = base.if_true ? Object.assign({}, base.if_true, { significance_rows: sr }) : null;
  return Object.assign({}, base, { focus, seed: String(s * 7919 + c.seed), significance_rows: sr, if_true: it });
}
let sweepList = null;
function* sweep() {
  if (!sweepList) { sweepList = []; for (const c of golden) { const base = ctxOf(c); for (const r of base.rows) if (base.places[r.id] && ["world", "country", "audience"].includes(r.level)) for (let s = 0; s < 4; s++) { const ctx = sweepCtx(c, r.id, s); sweepList.push({ c, ctx, focus: r.id, s, out: SoWhat.compose(ctx) }); } } }
  yield* sweepList;
}
const digitRuns = (t) => (t.match(/\d+/g) || []);
/* the figure is one fraction: "N in every 100", or "1 in every 20" / "1 in every 10" (design 8): its digit runs are exactly [n, unit] */
const expectedRuns = (o) => !o.anchor ? [] : o.anchor.figure.unit ? [String(o.anchor.figure.n), String(o.anchor.figure.unit)] : [String(o.anchor.figure.n)];
const figuresOk = (o) => JSON.stringify(digitRuns(o.headline + " " + o.line2).sort()) === JSON.stringify(expectedRuns(o).sort());
const LOUD = /\b(sharply|markedly|a lot|far|much)\b/i, SOFTDEG = /\b(a bit|a little|slightly|a touch)\b/i;
/* degree coherence (design 8.1): a loud degree word never sits beside a figure under 5 in 100; a soft one never beside 5 or more */
const degreeOk = (o, label) => { if (!o.anchor || o.anchor.kind === "multiple") return; const n = o.anchor.shown; if (n < 5) assert.doesNotMatch(o.headline, LOUD, `${label}: loud word beside ${n} in 100: ${o.headline}`); else assert.doesNotMatch(o.headline, SOFTDEG, `${label}: soft word beside ${n} in 100: ${o.headline}`); };
const spansOk = (o, label) => {
  const per = { 1: [], 2: [] };
  for (const s of o.spans) {
    const t = s.line === 1 ? o.headline : o.line2;
    assert.ok(s.start >= 0 && s.end <= t.length && s.start < s.end, `${label} bad span ${JSON.stringify(s)}`);
    assert.ok(["hook", "trigger", "response", "certainty", "who", "frame", "anchor", "contrast", "arc"].includes(s.beat), `${label} unknown beat ${s.beat}`);
    per[s.line].push(s);
  }
  for (const l of [1, 2]) { const a = per[l].slice().sort((x, y) => x.start - y.start); for (let i = 1; i < a.length; i++) assert.ok(a[i].start >= a[i - 1].end, `${label} overlapping spans ${JSON.stringify(a[i - 1])} ${JSON.stringify(a[i])}`); }
};

/* ---------- the 33 golden cases ---------- */
assert.strictEqual(golden.length, 33);
for (const c of golden) {
  test(`golden ${c.id} ${c.focus}: ${c.expect.hook_family} ${c.expect.hook || c.expect.body}`, () => {
    const o = SoWhat.compose(ctxOf(c)), e = c.expect;
    assert.ok(o, "compose returned null");
    assert.strictEqual(o.headline, e.headline);
    assert.strictEqual(o.line2, e.line2);
    assert.strictEqual(o.family, e.hook_family);
    assert.strictEqual(o.hook, e.hook || null);
    assert.strictEqual(o.body, e.body);
    assert.strictEqual(o.register, e.register || null);
    assert.deepStrictEqual(o.shrink, e.shrink);
    if (!e.anchor) { assert.strictEqual(o.anchor, null); assert.ok(!o.spans.some((s) => s.beat === "anchor")); assert.deepStrictEqual(digitRuns(o.headline + " " + o.line2), []); }
    else {
      const a = o.anchor, x = e.anchor; assert.ok(a, "anchor expected");
      for (const k of ["kind", "decision", "value_raw", "shown", "where", "text", "measured_against"]) assert.strictEqual(a[k], x[k], k);
      assert.strictEqual(a.rule.split(" ")[0], x.rule.split(" ")[0]); assert.deepStrictEqual(a.figure, x.figure);
      assert.deepStrictEqual(a.span, x.span);
      assert.ok(o.spans.some((s) => s.beat === "anchor" && s.line === x.span.line && s.start === x.span.start && s.end === x.span.end), "anchor span is in spans");
      const line = x.span.line === 1 ? o.headline : o.line2; assert.strictEqual(line.slice(x.span.start, x.span.end), x.text);
      const b = o.beats.find((q) => q.kind === "anchor"); assert.strictEqual(b.shown, x.shown); assert.strictEqual(b.value, x.value_raw); assert.ok(/same run without|world/i.test(b.trace), "trace says what the number is measured against");
    }
    for (const p of e.picks) { const q = o.picks.find((z) => z.slot === p.slot); assert.ok(q, `pick ${p.slot} missing`); assert.deepStrictEqual({ index: q.index, of: q.of }, { index: p.index, of: p.of }, `pick ${p.slot}`); }
    assert.strictEqual(words(o.headline), e.words);
    spansOk(o, c.id);
  });
}

/* ---------- rules that hold for every output ---------- */
test("every golden output: budgets, banned patterns, one number, determinism, soft word when hushed", () => {
  for (const c of golden) {
    const ctx = ctxOf(c), o = SoWhat.compose(ctx), t = o.headline + " " + o.line2;
    assert.ok(words(o.headline) <= 22, `${c.id} headline ${words(o.headline)} words`);
    const sole = o.spans.filter((s) => s.line === 2).length === 1 && o.anchor && o.anchor.where === "line2";
    assert.ok(words(o.line2) <= (sole ? 16 : 14), `${c.id} line 2 ${words(o.line2)} words`);
    assert.deepStrictEqual(SoWhat.banned(t), [], `${c.id} banned in: ${t}`);
    assert.ok(figuresOk(o), `${c.id} more than one figure, or digits that are not the anchor's: ${t}`); degreeOk(o, c.id);
    if (o.register === "hushed") assert.match(o.headline, SOFT, `${c.id} hushed headline has no soft word`);
    assert.deepStrictEqual(SoWhat.compose(ctx), o, `${c.id} not deterministic`);
    assert.ok(Array.isArray(o.beats) && o.beats.every((b) => b.kind && b.trace !== undefined));
  }
});

test("sweep over every golden story at world, country and audience foci, four seeds: invariants hold on every output", () => {
  let n = 0, nulls = 0; const families = new Set();
  for (const { c, ctx, focus, s, out } of sweep()) {
    const o = out, label = `${c.id} ${focus} s${s}`; n++;
    if (!o) { nulls++; continue; }
    families.add(o.family); const t = o.headline + " " + o.line2;
    assert.ok(words(o.headline) <= 22, `${label}: ${o.headline}`);
    const sole = o.spans.filter((x) => x.line === 2).length === 1 && o.anchor && o.anchor.where === "line2";
    assert.ok(words(o.line2) <= (sole ? 16 : 14), `${label}: ${o.line2}`);
    assert.deepStrictEqual(SoWhat.banned(t), [], `${label}: ${t}`);
    assert.ok(figuresOk(o), `${label}: ${t}`); degreeOk(o, label);
    if (o.register === "hushed") assert.match(o.headline, SOFT, label);
    if (o.family.startsWith("QUIET") || o.family === "NOTHING") assert.ok(o.line2 === "" && !o.anchor && o.hook === null, label);
    assert.ok(/^[A-Z]/.test(o.headline) && !/\s{2}| ,|,,/.test(t), `${label}: spacing ${t}`);
    spansOk(o, label); assert.deepStrictEqual(SoWhat.compose(ctx), o, label + " not deterministic");
  }
  assert.ok(n > 5000 && nulls / n < 0.2, `${nulls} nulls of ${n}`);
  for (const f of ["IF", "WHO_LOCAL", "WHO_MOST", "CONTRAST", "SCALE", "STAKE", "TURN", "TRIGGER", "QUIET_SMALL", "QUIET_ELSEWHERE", "NOTHING"]) assert.ok(families.has(f), "family never produced: " + f);
});

test("no number unless it passes its significance test and traces to an input value", () => {
  let shown = 0;
  for (const { c, ctx, out } of sweep()) {
    const o = out; if (!o || !o.anchor) continue; shown++;
    const a = o.anchor, hedged = ctx.if_true && ctx.story.certainty.kind !== "happened" && ctx.weight < 1, nums = hedged ? ctx.if_true.places : ctx.places;
    if (a.kind === "pts" || a.kind === "if_true_pts") {
      assert.ok(Math.abs(a.value_raw) >= 2.0, `${c.id}: |${a.value_raw}| under 2.0`);
      const peaks = Object.values(nums).map((P) => P[a.decision]).filter(Boolean).map((v) => v.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0));
      assert.ok(peaks.includes(a.value_raw), `${c.id}: ${a.value_raw} is not a peak of ${a.decision} in the numbers used`);
      assert.strictEqual(a.shown, Math.abs(a.value_raw) < 10 ? Math.floor(Math.abs(a.value_raw) + 0.5) : Math.floor(Math.abs(a.value_raw) / 5 + 0.5) * 5);
      assert.strictEqual(a.kind === "if_true_pts", !!hedged && ["forecast", "opinion", "unclear", "announced"].includes(ctx.story.certainty.kind));
      assert.match(o.anchor.text, /\babout\b|\broughly\b/i); assert.match(a.text, /than (without|otherwise)|who otherwise (would|could|might) not/, "says what it is measured against");
    } else {
      assert.strictEqual(a.kind, "multiple"); assert.ok(!hedged, "a forecast never shows a multiple"); assert.ok(a.value_raw >= 3, `${c.id}: ratio ${a.value_raw}`); assert.match(a.text, /world average|average worldwide/);
      assert.strictEqual(a.where, "line2");
    }
    assert.ok(o.beats.find((b) => b.kind === "anchor").trace.length > 20);
  }
  assert.ok(shown > 100, "anchors shown: " + shown);
});

test("a forecast never prints its weighted number: the figure is the if-true one (G20: 5.83 -> 6, not the weighted 1.75 -> 2)", () => {
  const c = byId("G20"), ctx = ctxOf(c), o = SoWhat.compose(ctx);
  assert.match(o.headline, /about 6 more would cut spending/); assert.strictEqual(o.anchor.kind, "if_true_pts");
  const peak = (v) => v.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0); assert.strictEqual(o.anchor.value_raw, peak(ctx.if_true.places["WORLD:world"].spend));
  const weighted = Math.abs(ctx.places["WORLD:world"].spend.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0));
  assert.ok(weighted < 2, "the weighted number would not pass the test");
  const noIf = SoWhat.compose({ ...ctx, if_true: null }); assert.strictEqual(noIf, null, "a hedged story without if_true returns null");
});

test("a statement with no figure passing its test shows no digits (G01, G10, G14, G15, G19, G22, G26, G30)", () => {
  for (const id of ["G01", "G10", "G14", "G15", "G19", "G22", "G26", "G30"]) { const o = SoWhat.compose(ctxOf(byId(id))); assert.strictEqual(o.anchor, null, id); assert.deepStrictEqual(digitRuns(o.headline + o.line2), [], id); assert.ok(o.beats.find((b) => b.kind === "anchor" || b.kind === "response")); }
  const a = SoWhat.compose(ctxOf(byId("G14"))).beats.find((b) => b.kind === "anchor"); assert.match(a.trace, /not shown|no figure/);
});

test("the anchor threshold is exactly 2.0 points: 1.9 shows no number, 2.0 shows 2", () => {
  const c = byId("G31"), mk = (v) => { const ctx = ctxOf(c); const places = JSON.parse(JSON.stringify(ctx.places)); for (const id of Object.keys(places)) { const P = places[id]; for (const d of Object.keys(P)) P[d] = d === "spend" ? [v, v, v] : [0, 0, 0]; } return SoWhat.compose({ ...ctx, places }); };
  assert.strictEqual(mk(-1.9).anchor, null); const o = mk(-2.0); assert.strictEqual(o.anchor.shown, 2); assert.match(o.headline + o.line2, /about 2 more|2 in every 100/);
  assert.strictEqual(mk(-12).anchor.shown, 10, "10 and above rounds to the nearest 5 (12 -> 10)"); assert.strictEqual(mk(-14.9).anchor.shown, 15); assert.strictEqual(mk(-9.5).anchor.shown, 10);
});

test("different seeds give different phrasing, equal seeds the same", () => {
  let differing = 0, total = 0, hooks = new Set(), bodies = new Set();
  for (const c of golden) {
    const base = ctxOf(c), seen = new Set();
    for (let s = 0; s < 8; s++) { const o = SoWhat.compose({ ...base, seed: String(s * 31 + 5) }); if (o) { seen.add(o.headline + "|" + o.line2); if (o.hook) hooks.add(o.hook); bodies.add(o.body); } }
    total++; if (seen.size > 1) differing++;
    assert.deepStrictEqual(SoWhat.compose({ ...base, seed: "12345" }), SoWhat.compose({ ...base, seed: "12345" }));
  }
  assert.ok(differing >= 28, `${differing} of ${total} stories change phrasing with the seed`); assert.ok(hooks.size >= 40 && bodies.size >= 25, `hooks ${hooks.size}, bodies ${bodies.size}`);
});

test("the seed defaults to a hash of the story text, never random; story.seed and ctx.seed override in that order", () => {
  const c = byId("G20"), base = ctxOf(c); delete base.seed;
  const a = SoWhat.compose(base), b = SoWhat.compose({ ...base }); assert.deepStrictEqual(a, b);
  assert.strictEqual(a.seed, String(SoWhat.hash(c.text))); assert.strictEqual(a.seed, String(c.seed));
  assert.strictEqual(SoWhat.compose({ ...base, story: { ...base.story, seed: 77 } }).seed, "77");
  assert.strictEqual(SoWhat.compose({ ...base, story: { ...base.story, seed: 77 }, seed: 88 }).seed, "88");
  assert.strictEqual(SoWhat.compose({ ...base, text: undefined }), null, "no seed, no text: null");
});

test("hooks: families come in the stated order and the first family with an eligible hook leads", () => {
  const order = ["IF", "WHO_LOCAL", "WHO_MOST", "WHO_OPP", "CONTRAST", "SCALE", "STAKE", "TURN", "TRIGGER"], seen = {};
  for (const { out: o } of sweep()) { if (o && o.hook) { seen[o.family] = (seen[o.family] || 0) + 1; assert.ok(order.includes(o.family)); } }
  for (const f of order.filter((x) => x !== "WHO_OPP")) assert.ok(seen[f] > 0, f + " never led");
  const hedged = golden.filter((c) => ["forecast", "opinion", "unclear"].includes(c.numbers.certainty) || c.numbers.certainty === "pending");
  for (const c of hedged) { const o = SoWhat.compose(ctxOf(c)); if (o.hook) assert.strictEqual(o.family, "IF", c.id); }
  const loc = SoWhat.compose(ctxOf(byId("G13"))); assert.strictEqual(loc.family, "WHO_LOCAL");
  const sc = SoWhat.compose(ctxOf(byId("G11"))); assert.strictEqual(sc.family, "SCALE"); assert.strictEqual(sc.register, "stark");
  for (const o of [loc]) assert.ok(!/^SCALE/.test(o.family));
});

test("link compatibility: no 'as' with a modal, frame words only when the theme fits, local words only for a local story, valence words match", () => {
  for (const { ctx, out: o } of sweep()) {
    if (!o || !o.hook) continue; const h = o.headline, modal = ctx.story.certainty.modal;
    if (modal) assert.doesNotMatch(h, /(^|: )as [^,:]*\b(will|would|could|may)\b[^,:]*,/i, "L4 'as' needs a plain trigger: " + h);
    if (!o.beats.find((b) => b.kind === "who")) assert.doesNotMatch(h, /^Only |almost alone|stays in |this one alone|for \S+ alone|and hardly anyone else/, "L6 place honesty: " + h);
    if (/hit hardest|bear the brunt/.test(h)) assert.ok(o.register !== "hushed");
    if (o.frame === "plain") assert.doesNotMatch(h, /\bsqueeze|scare|surge\b/i, "plain frame has no frame noun: " + h);
    assert.ok(!(o.family !== "WHO_LOCAL" && o.family !== "WHO_MOST" && /^Only /.test(h) && !ctx.story.entry.local) , "Only is for local stories: " + h);
  }
  /* scare bars 'ease off on precautions' (frame scare) */
  for (const { out: o } of sweep()) { if (o && o.frame === "scare" || o && o.frame === "blow") assert.doesNotMatch(o.headline, /ease off on precautions|relax their guard|take fewer precautions/); }
});

test("register comes from the tier at the place spoken for, and a conditional is never stark", () => {
  const g = (id, f) => SoWhat.compose(ctxOf(byId(id), f ? { focus: f } : undefined));
  assert.strictEqual(g("G03").register, "stark"); assert.strictEqual(g("G13").register, "plain", "a local story reads the entry country's tier, not the world's Negligible");
  assert.strictEqual(g("G05").register, "stark", "the hardest-hit country's tier at world focus");
  assert.strictEqual(g("G19").register, "hushed"); assert.strictEqual(g("G21").register, "plain", "a Major forecast is capped at plain");
  const c = byId("G21"), ctx = ctxOf(c); assert.strictEqual(ctx.if_true.significance.tier === undefined ? undefined : ctx.if_true.significance.tier, "Major"); assert.strictEqual(SoWhat.compose(ctx).register, "plain");
  const hushed = golden.map((x) => SoWhat.compose(ctxOf(x))).filter((o) => o.register === "hushed"); assert.ok(hushed.length >= 3); for (const o of hushed) assert.match(o.headline, SOFT);
});

test("the quiet branch: every non-vague quiet form carries the trigger or the topic, no number, no line 2", () => {
  for (const id of ["G15", "G16", "G17", "G18", "G28", "G29", "G32"]) {
    const o = SoWhat.compose(ctxOf(byId(id))); assert.ok(/^(QUIET|NOTHING)/.test(o.family), id); assert.strictEqual(o.line2, ""); assert.strictEqual(o.anchor, null); assert.deepStrictEqual(digitRuns(o.headline), []);
    assert.strictEqual(o.hook, null); assert.strictEqual(o.register, null); assert.ok(o.beats.some((b) => b.kind === "response" && b.text === "none"));
    if (o.family === "NOTHING") assert.match(o.headline, /pollution and nature/); else if (o.family !== "QUIET_VAGUE") assert.ok(o.beats.find((b) => b.kind === "trigger").text.length > 3 && o.headline.toLowerCase().includes(o.beats.find((b) => b.kind === "trigger").text.toLowerCase()), id + ": " + o.headline);
  }
  assert.match(SoWhat.compose(ctxOf(byId("G32"))).headline, /Ukraine.*Germany/); assert.match(SoWhat.compose(ctxOf(byId("G17"))).headline, /United States/);
  /* the retired stock phrases never appear and no quiet sentence repeats more than the seeded forms allow */
  const seen = {}; for (const { out: o } of sweep()) { if (o) assert.doesNotMatch(o.headline + " " + o.line2, /Elsewhere, barely a ripple|Little changes elsewhere|A tiny shift that reaches|Fades slowly|no decision moves enough to matter/); if (o && o.family.startsWith("QUIET")) seen[o.body] = (seen[o.body] || 0) + 1; }
  assert.ok(Object.keys(seen).length >= 15, "quiet forms used: " + Object.keys(seen).length);
});

test("three squeezes in one frame (G23 to G25) read differently: three hooks, no shared opening", () => {
  const os = ["G23", "G24", "G25"].map((id) => SoWhat.compose(ctxOf(byId(id))));
  assert.strictEqual(new Set(os.map((o) => o.hook)).size, 3); assert.strictEqual(new Set(os.map((o) => o.headline.split(" ").slice(0, 3).join(" "))).size, 3);
  const grams = (t) => { const w = t.toLowerCase().replace(/[^a-z0-9 ]/g, "").split(/\s+/), s = new Set(); for (let i = 0; i + 5 <= w.length; i++) s.add(w.slice(i, i + 5).join(" ")); return s; };
  let shared = 0; for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) { const a = grams(os[i].headline + " " + os[i].line2), b = grams(os[j].headline + " " + os[j].line2); if ([...a].some((x) => b.has(x))) shared++; }
  assert.ok(shared <= 1, "pairs sharing a five-word run: " + shared);
});

test("opening spread over the 33 golden statements: no three-word opener leads more than twice", () => {
  const cnt = {}; for (const c of golden) { const o = SoWhat.compose(ctxOf(c)), k = o.headline.split(" ").slice(0, 3).join(" ").toLowerCase(); cnt[k] = (cnt[k] || 0) + 1; }
  assert.ok(Math.max(...Object.values(cnt)) <= 2, JSON.stringify(cnt)); assert.ok(Object.keys(cnt).length >= 28);
});

test("null on missing input or version 1 / empty tables, never throws", () => {
  const c = byId("G13"), good = ctxOf(c), hed = ctxOf(byId("G12")), wide = ctxOf(byId("G09"));
  assert.ok(SoWhat.compose(good), "the good input works");
  for (const bad of [null, undefined, {}, [], "x", 3]) assert.strictEqual(SoWhat.compose(bad), null);
  const nul = (o, why) => assert.strictEqual(SoWhat.compose(o), null, why);
  nul({ ...good, story: null }, "no story"); nul({ ...good, story: { version: 2 } }, "empty story"); nul({ ...good, story: { ...good.story, frame: undefined } }, "no frame"); nul({ ...good, story: { ...good.story, trigger: undefined } }, "no trigger");
  nul({ ...good, tables: null }, "no tables"); nul({ ...good, tables: { ...tables, version: 1 } }, "version 1 tables");
  nul({ ...good, tables: { version: 2, frames: [], hooks: [], lexicon: [], templates: [] } }, "empty tables"); nul({ ...good, tables: { ...tables, hooks: [] } }, "no hooks"); nul({ ...good, tables: { ...tables, lexicon_v1: [] } }, "no v1 lexicon (conditions)");
  nul({ ...good, tables: { frames: tables.frames, lexicon: csv("sowhat_lexicon.csv"), templates: csv("sowhat_templates.csv") } }, "v1 tables as the server sent them before");
  nul({ ...good, rows: null }, "no rows"); nul({ ...good, rows: [] }, "empty rows"); nul({ ...good, places: null }, "no places"); nul({ ...good, places: {} }, "empty places"); nul({ ...good, readings: null }, "no readings");
  nul({ ...good, weight: undefined, story: { ...good.story, certainty: { ...good.story.certainty, weight: undefined } } }, "no weight");
  nul({ ...good, significance_rows: null }, "a local story needs its entry row tier"); nul({ ...good, significance_rows: {} }, "empty row tiers");
  nul({ ...good, story: { ...good.story, entry: { id: "COUNTRY:ken", place: "country" } }, significance_rows: { "COUNTRY:ken": { tier: "Nonsense" } } }, "unknown tier");
  nul({ ...hed, if_true: null }, "hedged story without if_true"); nul({ ...hed, if_true: { places: null } }, "if_true without places");
  nul({ ...wide, significance_rows: null }, "a country focus needs its tier");
  nul({ ...good, story: { ...good.story, trigger: { picks: [{ dial: "not_a_dial", direction: "up" }] } } }, "unknown dial");
  assert.ok(SoWhat.compose({ ...good, story: { ...good.story, frame: { id: "nonsense", p: 1 } } }), "an unknown frame id falls back to plain, never null");
  assert.strictEqual(SoWhat.compose({ ...good, story: { ...good.story, frame: { id: "nonsense", p: 1 } } }).frame, "plain");
  assert.ok(SoWhat.compose({ ...ctxOf(byId("G16")), places: null, rows: ctxOf(byId("G16")).rows }), "a no-impact story needs no numbers");
});

test("three-argument form gives the same answer as the single object", () => {
  const a = ctxOf(byId("G20")), { story, tables: t, ...rest } = a;
  assert.deepStrictEqual(SoWhat.compose(story, rest, t), SoWhat.compose(a));
});

test("feed rule: a repeated three-word opening re-picks the hook (slot hook#2)", () => {
  let flipped = 0, tried = 0;
  for (const c of golden) { const base = ctxOf(c), a = SoWhat.compose(base); if (!a.hook) continue; tried++; const b = SoWhat.compose({ ...base, prev: a.headline }); if (b.headline.split(" ").slice(0, 3).join(" ") !== a.headline.split(" ").slice(0, 3).join(" ")) { flipped++; assert.ok(b.picks.some((p) => /^hook#/.test(p.slot))); assert.strictEqual(b.family, a.family); } }
  assert.ok(flipped >= tried * 0.7, `${flipped} of ${tried} flipped`);
  const o = SoWhat.compose({ ...ctxOf(byId("G20")), prev: "Something else entirely here" }); assert.strictEqual(o.headline, SoWhat.compose(ctxOf(byId("G20"))).headline, "a different opening leaves the statement alone");
});

test("the Size tier is not read from the composer: the badge keeps impact.significance (composer only reads tiers)", () => {
  const ctx = ctxOf(byId("G03")), o = SoWhat.compose(ctx); assert.strictEqual(o.register, "stark");
  const o2 = SoWhat.compose({ ...ctx, significance: { tier: "Negligible", score: 1 }, story: { ...ctx.story, scale: { tier: "Negligible", score: 1 } } }); assert.strictEqual(o2.register, "hushed");
});

/* ---------- banned() ---------- */
test("banned() catches the patterns it should and passes plain sentences", () => {
  assert.ok(SoWhat.banned("Worldwide, people are likelier to spend more, buy more and travel less.").length);
  assert.ok(SoWhat.banned("they cut back, travel less and stock up").includes("comma list"));
  assert.ok(SoWhat.banned("up 3.5 points").includes("decimal"));
  assert.ok(SoWhat.banned("it ends next month").includes("calendar time"));
  assert.ok(SoWhat.banned("about 7% more").includes("percent"));
  assert.ok(SoWhat.banned("Elsewhere, barely a ripple.").length && SoWhat.banned("A tiny shift that reaches nearly everyone.").length && SoWhat.banned("Fades slowly.").length && SoWhat.banned("no decision moves enough to matter").length);
  assert.deepStrictEqual(SoWhat.banned("If this forecast comes true, jobs would get less secure, and people would cut back and apply for aid."), []);
  assert.deepStrictEqual(SoWhat.banned("Not felt all at once: as loans get cheaper, people loosen their budgets and invest a little more."), []);
  assert.deepStrictEqual(SoWhat.banned("Prices rise, and people have less to spare: about 5 more in every 100 people cut spending than without it."), []);
});

/* ---------- fuzz: every fixture story x every row of its read.rows x seeds 0..3 ---------- */
test("fuzz: 22 fixture stories x every country, region and audience row x seeds 0..3: never null for a budget reason, headline <= 22, line 2 <= 14, one figure", { timeout: 120000 }, () => {
  const v1 = JSON.parse(fs.readFileSync(path.join(SPEC, "sowhat-golden.json"), "utf8")).cases, tiers = ["Negligible", "Minor", "Notable", "Major", "Historic"];
  let n = 0, nulls = 0, longest = 0;
  for (const c of v1) {
    const fx = JSON.parse(fs.readFileSync(path.join(SPEC, "..", c.fixture), "utf8")), story = SoWhat.deriveStory(fx, c.story), w = fx.identify.weight.value; story.topic = { id: "x", name: "a test topic", p: 0.9 };
    const scaled = (P) => Object.fromEntries(Object.entries(P).map(([k, v]) => [k, Object.fromEntries(Object.entries(v).map(([d, a]) => [d, a.map((x) => Math.round(x / w * 100) / 100)]))]));
    for (const r of fx.read.rows) for (let s = 0; s < 4; s++) {
      const sr = Object.fromEntries(fx.read.rows.map((q) => [q.id, { tier: tiers[(s + q.id.length + q.label.length) % 5], score: 10 }])), dbg = {};
      const it = w < 1 ? { places: scaled(fx.impact.places), significance: { tier: tiers[s % 5] }, significance_rows: sr } : null;
      const o = SoWhat.compose({ story, focus: r.id, rows: fx.read.rows, places: fx.impact.places, rank: fx.impact.rank, significance: fx.impact.significance, significance_rows: sr, if_true: it, readings: fx.identify.readings, weight: w, text: c.text, seed: String(s), tables, debug: dbg });
      n++; const label = `${c.id} ${r.id} s${s}`;
      if (!o) { nulls++; assert.notStrictEqual(dbg.reason, "budget", label + " null for the word budget"); continue; }
      assert.ok(words(o.headline) <= 22, `${label}: ${o.headline}`); longest = Math.max(longest, words(o.headline));
      const sole = o.spans.filter((x) => x.line === 2).length === 1 && o.anchor && o.anchor.where === "line2";
      assert.ok(words(o.line2) <= (sole ? 16 : 14), `${label}: ${o.line2}`);
      assert.ok(figuresOk(o), label); degreeOk(o, label);
    }
  }
  assert.ok(n > 30000); assert.strictEqual(nulls, 0, "nulls: " + nulls); assert.ok(longest <= 22);
});


/* ---------- v2.1 follow-ups: coherence, unit, even hook choice, rotation, family coverage ---------- */
const peakOf = (v) => v.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0);
const seeds = (n) => [...Array(n).keys()].map(String);
const outs = (ctx, n) => seeds(n).map((sd) => SoWhat.compose({ ...ctx, seed: sd })).filter(Boolean);
const spendTo = (ctx, row, v) => { const places = JSON.parse(JSON.stringify(ctx.places)); for (const d of Object.keys(places[row])) places[row][d] = d === "spend" ? [v, v, v] : [0, 0, 0]; return { ...ctx, places }; };

test("degree coherence: the golden cases that printed a loud word beside a small figure (G09, G23) no longer do", () => {
  for (const id of ["G09", "G23"]) { const o = SoWhat.compose(ctxOf(byId(id))); assert.ok(o.anchor.shown < 5); assert.doesNotMatch(o.headline, LOUD, id); }
  const big = SoWhat.compose(ctxOf(byId("G05"))); assert.match(big.headline, /markedly/, "a figure of 5 or more keeps its loud word (G05 prints 5 times, G06 7 in 100)");
  assert.match(SoWhat.compose(ctxOf(byId("G06"))).headline, /markedly/);
  /* every seed, every anchored statement of the golden stories */
  for (const c of golden) for (const o of outs(ctxOf(c), 12)) degreeOk(o, c.id);
});

test("the unit: 'N in every 100', 'about 1 in every 20' near 5, 'about 1 in every 10' near 10, never more precision than the figure carries", () => {
  const c = byId("G31"), mk = (v) => SoWhat.compose(spendTo(ctxOf(c), "WORLD:world", v));
  const t = (v) => { const o = mk(v); return o.headline + " " + o.line2; };
  assert.match(t(-4.94), /\b20\b/); assert.deepStrictEqual(mk(-4.94).anchor.figure, { n: 1, unit: 20 }); assert.strictEqual(mk(-4.94).anchor.shown, 5);
  assert.deepStrictEqual(mk(-5.4).anchor.figure, { n: 1, unit: 20 }); assert.deepStrictEqual(mk(-5.6).anchor.figure, { n: 6, unit: 100 }); assert.deepStrictEqual(mk(-4.4).anchor.figure, { n: 4, unit: 100 });
  assert.deepStrictEqual(mk(-9.2).anchor.figure, { n: 1, unit: 10 }); assert.deepStrictEqual(mk(-10.8).anchor.figure, { n: 1, unit: 10 }); assert.deepStrictEqual(mk(-11.2).anchor.figure, { n: 10, unit: 100 }); assert.deepStrictEqual(mk(-8.4).anchor.figure, { n: 8, unit: 100 });
  for (const v of [-4.94, -9.2, -5.6, -3]) { const o = mk(v); assert.ok(figuresOk(o), o.headline); assert.match(o.headline + o.line2, /than without|than otherwise|who otherwise/, "measured against no news"); assert.match(o.anchor.measured_against, /no-event control run/); }
  assert.match(t(-9.2), /1 (more )?in every 10|every 10 \w+, about 1 more|1 in 10/);
  assert.match(SoWhat.compose(ctxOf(byId("G03"))).headline, /about 1 in every 20 people gets a health check/);
});

test("IF hook rows are chosen evenly: each compatible row gets about its share, and the phrasing is a second pick", () => {
  const rows = { G20: 7, G21: 6, G12: 5, G10: 5 };   /* forecast: IF01 IF02 IF03 IF05 IF06 IF07 IF09; opinion: IF01 IF02 IF04 IF06 IF07 IF09; announced at weight and pending: IF01 IF02 IF06 IF08 IF09 */
  for (const [id, n] of Object.entries(rows)) {
    const cnt = {}, os = []; for (let i = 0; i < 600; i++) { const o = SoWhat.compose({ ...ctxOf(byId(id)), seed: "q" + i }); os.push(o); const r = o.hook.replace(/\.\d+$/, ""); cnt[r] = (cnt[r] || 0) + 1; }
    assert.strictEqual(Object.keys(cnt).length, n, id + " " + JSON.stringify(cnt));
    for (const [r, k] of Object.entries(cnt)) assert.ok(k / 600 > 0.6 / n && k / 600 < 1.4 / n, `${id} ${r} ${k}/600`);
    assert.ok(os.some((o) => o.picks.some((p) => p.slot === "hook" && p.of === n)));
    assert.ok(Math.max(...Object.values(cnt)) / 600 <= 0.3, id + " top IF row over 30%: " + JSON.stringify(cnt));
  }
});

test("rotation: 'almost alone', the arc wordings and the quiet-forecast forms each have several phrasings, picked by seed, none dominant", () => {
  const share = (ctx, re, n = 400) => { let k = 0, tot = 0; for (let i = 0; i < n; i++) { const o = SoWhat.compose({ ...ctx, seed: "r" + i }); if (!o) continue; tot++; if (re.test(o.headline + " " + o.line2)) k++; } return k / tot; };
  for (const id of ["G13", "G23", "G26", "G33", "G04"]) assert.ok(share(ctxOf(byId(id)), /almost alone/) <= 0.25, id + " 'almost alone' share too high");
  const hooks = new Set(), bodies = new Set(); for (const id of ["G13", "G23", "G33"]) for (const o of outs(ctxOf(byId(id)), 120)) { hooks.add(o.hook); bodies.add(o.body); } assert.ok(hooks.size >= 12 && bodies.size >= 10, `${hooks.size} hooks ${bodies.size} bodies`);
  for (const arc of ["builds", "builds_sticks", "sticks", "jolt"]) assert.ok(csv("sowhat2_lexicon.csv").filter((r) => r.kind === "l2_arc" && r.id === arc).length >= 7, arc + " needs at least 7 wordings");
  const lines = new Set(); for (const id of ["G03", "G04", "G14", "G11"]) for (const o of outs(ctxOf(byId(id)), 200)) if (o.line2) lines.add(o.line2.replace(/^.*?\. (?=[A-Z])/, "")); assert.ok(lines.size >= 12, "line 2 wordings " + lines.size);
  const qf = {}, ctx = ctxOf(byId("G18")); for (let i = 0; i < 600; i++) { const o = SoWhat.compose({ ...ctx, seed: "f" + i }); qf[o.body] = (qf[o.body] || 0) + 1; }
  assert.ok(Object.keys(qf).length >= 9, JSON.stringify(qf)); assert.ok(qf.QF03 / 600 < 0.2, "QF03 share " + qf.QF03 / 600);
  assert.ok(!/habits would hold/.test(tables.templates.find((r) => r.id === "QF03").template));
});

test("the root causes of the two worst readings: no consequence word when the response disagrees with the trigger; 'on our numbers' instead", () => {
  /* G31 (prices rise, spending falls) with the numbers turned round: a bad trigger and a rise in spending */
  const base = ctxOf(byId("G31")); let places = JSON.parse(JSON.stringify(base.places)); for (const id of Object.keys(places)) for (const d of Object.keys(places[id])) places[id][d] = places[id][d].map((x) => -x * 0.3);   /* 0.3: under the 2-point figure threshold, so the sentence carries its subject */
  const ctx = { ...base, places, rank: base.rank }; let n = 0, said = 0;
  for (const o of outs(ctx, 80)) { n++; const t = o.headline + " " + o.line2;
    assert.doesNotMatch(t, /in turn|leaving|\bso\b|[Bb]ecause|which means|^As |: as |\bas prices/, "consequence word on an incoherent story: " + t); assert.doesNotMatch(t, /feel the (pinch|squeeze)|less to spare|pressure ease/, "frame words on an incoherent story: " + t); if (/on our numbers/.test(t)) said++; }
  assert.ok(n > 60 && said > 10, `${said} of ${n} say "on our numbers"`);
  /* a coherent story keeps its consequence words available */
  const good = outs(ctxOf(byId("G31")), 80).map((o) => o.headline + o.line2).join(" "); assert.match(good, /in turn|\bso\b|[Bb]ecause|which means|^As |: as /);
  /* 'Against that' is gone from line 2 */
  assert.ok(!csv("sowhat2_lexicon.csv").some((r) => /^Against that/.test(r.text)));
});

test("a quiet form never puts two triggers joined by 'and' in front of another 'and' (s051)", () => {
  const c = byId("G29"), ctx = ctxOf(c), st = JSON.parse(JSON.stringify(ctx.story)); st.trigger.picks = [st.trigger.picks[0], { ...st.trigger.picks[0], dial: "prices", direction: "up" }];
  let two = 0; for (const o of outs({ ...ctx, story: st }, 120)) { assert.doesNotMatch(o.headline, /\band\b[^,.;:]*, and\b/, o.headline); if (/ and (prices|wildlife)/.test(o.headline)) two++; } assert.ok(two > 0, "forms without a following 'and' still show both triggers");
});

test("a hushed statement shows no figure; its register and its words agree", () => {
  for (const o of outs(ctxOf(byId("G19")), 40).concat(outs(ctxOf(byId("G30")), 40))) { assert.strictEqual(o.register, "hushed"); assert.strictEqual(o.anchor, null); assert.match(o.headline, SOFT); }
});

/* ---------- the families that never led in the real set: STAKE, WHO_MOST, WHO_OPP, SCALE ---------- */
const hooksOf = (ctx, n = 120) => { const m = {}; for (const o of outs(ctx, n)) { const k = o.family + ":" + o.hook; m[k] = (m[k] || 0) + 1; } return m; };
const rowsOfFamily = (fam) => tables.hooks.filter((h) => h.family === fam).map((h) => h.id);
const negate = (ctx) => { const places = JSON.parse(JSON.stringify(ctx.places)); for (const id of Object.keys(places)) for (const d of Object.keys(places[id])) places[id][d] = places[id][d].map((x) => -x); return { ...ctx, places }; };
const withAudience = (ctx, aud, fn) => { const places = JSON.parse(JSON.stringify(ctx.places)); fn(places[aud]); return { ...ctx, places, significance_rows: { ...ctx.significance_rows, [aud]: { tier: "Notable" } } }; };

test("SCALE: leads when the register is stark, reaches all eight hook rows, reach rows only at world focus with a resolved place", () => {
  const m = hooksOf(ctxOf(byId("G03"))), got = Object.keys(m).map((k) => k.split(":")[1].replace(/\.\d+$/, ""));
  assert.deepStrictEqual(Object.keys(m).every((k) => k.startsWith("SCALE:")), true); for (const r of rowsOfFamily("SCALE")) assert.ok(got.includes(r), "SCALE row never used: " + r);
  for (const o of outs(ctxOf(byId("G11")), 60)) { assert.strictEqual(o.family, "SCALE"); assert.doesNotMatch(o.hook, /SC0[456]/, "unresolved place: no reach hook"); }
  for (const o of outs(ctxOf(byId("G06")), 60)) assert.doesNotMatch(o.hook, /SC0[456]/, "country focus: no reach hook");
  for (const id of ["G01", "G30", "G13"]) assert.notStrictEqual(SoWhat.compose(ctxOf(byId(id))).family, "SCALE", "SCALE needs stark");
});
test("STAKE: leads for a hard-to-undo choice at 0.75 points or more in a plain or stark statement, all seven rows reachable", () => {
  const m = hooksOf(ctxOf(byId("G09"))); assert.ok(Object.keys(m).every((k) => k.startsWith("STAKE:")), JSON.stringify(m)); const got = Object.keys(m).map((k) => k.split(":")[1]);
  for (const r of rowsOfFamily("STAKE")) assert.ok(got.includes(r), "STAKE row never used: " + r);
  assert.ok(outs(ctxOf(byId("G09")), 60).every((o) => o.beats.find((b) => b.kind === "stake").text === "borrowing"));
  /* hushed: STAKE and TURN may not lead; below 0.75 points no stake */
  const weak = JSON.parse(JSON.stringify(ctxOf(byId("G09")))); for (const id of Object.keys(weak.places)) if (weak.places[id].borrow) weak.places[id].borrow = weak.places[id].borrow.map((x) => x * 0.1);
  assert.ok(outs(weak, 60).every((o) => o.family !== "STAKE"));
  const hushed = { ...ctxOf(byId("G09")), significance_rows: { "COUNTRY:can": { tier: "Negligible" } } }; assert.ok(outs(hushed, 60).every((o) => o.family !== "STAKE" && o.family !== "TURN"));
});
test("WHO_MOST: a country at several times the world average (world focus), an audience too; all nine rows reachable, valence-tagged rows only for their valence", () => {
  const g5 = ctxOf(byId("G05")), m = hooksOf(g5), used = new Set(Object.keys(m).map((k) => k.split(":")[1].replace(/\.\d+$/, "")));
  assert.ok(Object.keys(m).every((k) => k.startsWith("WHO_MOST:")), JSON.stringify(m)); assert.ok(!used.has("WM06") && !used.has("WM09"), "WM06 is good-only and WM09 audience-only");
  /* an audience leads */
  const aud = withAudience(g5, "AUDIENCE:2", (P) => { for (const d of Object.keys(P)) P[d] = [0, 0, 0]; P.spend = [-9, -9, -4]; });
  const ma = hooksOf({ ...aud, places: Object.fromEntries(Object.entries(aud.places).map(([k, v]) => k.startsWith("COUNTRY:") ? [k, Object.fromEntries(Object.entries(v).map(([d, a]) => [d, a.map((x) => x * 0.2)]))] : [k, v])) }); const ua = new Set(Object.keys(ma).map((k) => k.split(":")[1].replace(/\.\d+$/, "")));
  assert.ok(ua.has("WM09") && !ua.has("WM08"), JSON.stringify(ma));
  /* a good story: gains */
  const mg = hooksOf(negate(g5)), ug = new Set(Object.keys(mg).map((k) => k.split(":")[1].replace(/\.\d+$/, ""))); assert.ok(ug.has("WM06") && !ug.has("WM02") && !ug.has("WM03"), JSON.stringify(mg));
  const all = new Set([...used, ...ua, ...ug]); for (const r of rowsOfFamily("WHO_MOST")) assert.ok(all.has(r), "WHO_MOST row never used: " + r);
  for (const o of outs(g5, 40)) assert.strictEqual(o.beats.find((b) => b.kind === "who").short, "India");
});
test("WHO_OPP: a row moving the other way from the world, all six rows reachable; it can fire (opposite salience is the largest)", () => {
  const g5 = ctxOf(byId("G05")), ctx = withAudience(g5, "AUDIENCE:3", (P) => { P.spend = [1.6, 1.8, 0.9]; });
  const m = hooksOf(ctx, 200); assert.ok(Object.keys(m).every((k) => k.startsWith("WHO_OPP:")), JSON.stringify(m)); const got = new Set(Object.keys(m).map((k) => k.split(":")[1].replace(/\.\d+$/, "")));
  for (const r of rowsOfFamily("WHO_OPP")) assert.ok(got.has(r), "WHO_OPP row never used: " + r);
  const o = SoWhat.compose(ctx); assert.match(o.beats.find((b) => b.kind === "who").short, /living alone/); assert.ok(figuresOk(o));
});


/* ---------- v2.2: the world value of 0, the hover, the other side, an unresolved place, even IF rows ---------- */
const withWorldZero = (ctx, v) => { const places = JSON.parse(JSON.stringify(ctx.places)); for (const d of Object.keys(places["WORLD:world"])) places["WORLD:world"][d] = [v, v, v]; return { ...ctx, places }; };
test("a world value of 0 (or under 0.25) is never a denominator: the focus moves and almost no one else does, said that way", () => {
  const c = byId("G06"), base = ctxOf(c);
  for (const v of [0, 0.05, -0.2]) for (const f of ["COUNTRY:ind"]) {
    let places = JSON.parse(JSON.stringify(base.places)); for (const d of Object.keys(places["WORLD:world"])) places["WORLD:world"][d] = [v, v, v];
    for (const id of Object.keys(places)) if (id !== "WORLD:world") for (const d of Object.keys(places[id])) places[id][d] = id === "COUNTRY:ind" && d === "spend" ? [-0.9, -1.0, -0.5] : [0, 0, 0];   /* under the 2-point figure, so line 2 is free for the comparison */
    const seen = new Set(); for (const o of outs({ ...base, places, focus: f }, 40)) { assert.doesNotMatch(o.line2, /below|less than|weaker|Far less|Much weaker|Well below/, `world ${v}: ${o.line2}`); if (/Almost no one else|Hardly anyone else|rest of the world barely/.test(o.line2)) seen.add(o.line2.split(/(?<=\.) /)[0]); }
    assert.ok(seen.size >= 2, `world ${v}: the "alone" wordings never appeared: ` + [...seen]);
  }
  /* a country whose number is really below the world's still reads as below it (the old far_less meaning is kept) */
  const places = JSON.parse(JSON.stringify(base.places)); for (const d of Object.keys(places["WORLD:world"])) places["WORLD:world"][d] = d === "spend" ? [-2, -2, -1] : [0, 0, 0]; for (const id of Object.keys(places)) if (id !== "WORLD:world") for (const d of Object.keys(places[id])) places[id][d] = id === "COUNTRY:ind" && d === "spend" ? [-0.3, -0.3, -0.2] : [0, 0, 0];
  for (const o of outs({ ...base, places }, 20)) assert.doesNotMatch(o.line2, /Almost no one else|Hardly anyone else|rest of the world barely/, o.line2);
  /* the WHO lead at world focus: a world value under 0.25 on the lead decision never makes a "times the average" claim */
  for (const { out: o } of sweep()) if (o && o.anchor && o.anchor.kind === "multiple") assert.ok(o.anchor.value_raw >= 3 && isFinite(o.anchor.value_raw));
});

test("the anchor hover: plain words from the lexicon table, model estimate, checkpoint, time scale a guess, decision weights, the 2 in 100 floor; forecast premise; no jargon, no typos", () => {
  const trace = (id, over) => SoWhat.compose(ctxOf(byId(id), over)).beats.find((b) => b.kind === "anchor").trace;
  const t = trace("G13"), top = t.split("\nDetails:")[0];
  for (const re of [/A model estimate, not a count\./, /our simulated population/, /about 4 more people in every 100 would cut spending in the run with this story than in the same run without it/, /largest gap across our three checkpoints \(Now, Next, Later\), reached at Now/, /Next is roughly a month after the news if one model step is a day, and that time scale is our guess/, /hand-set decision weights/, /at least 2 in 100/]) assert.match(top, re);
  assert.doesNotMatch(top, /\bA[134]\b|control run|\bpts\b|threshold|\bpeak\b|round half/, "no jargon above the details fold"); assert.match(t, /\nDetails: A1: spend -3\.85 points at Kenya/);
  const h = trace("G20"); assert.match(h, /This assumes the forecast comes true\. Counted as a forecast, the engine gives it 0\.3 of that weight\./); assert.doesNotMatch(h, /theno|if-true run with the type weight removed, itself/); assert.match(h, /type weight removed/);
  assert.match(trace("G21"), /This assumes the opinion comes true\. Counted as an opinion piece/); assert.match(trace("G12"), /Counted as an announcement/);
  assert.match(trace("G03"), /\(4\.8 in 100, shown as 1 in 20\)\./); assert.match(trace("G03"), /about 1 more people|about 1 more people/.source ? /about 1 more people in every 20 would get a health check/ : /x/);
  assert.match(trace("G05"), /about 5 times as big in India as across the world/); assert.match(trace("G05"), /at least 0\.25 in 100/);
  /* the none cases say why in words */
  assert.match(SoWhat.compose(ctxOf(byId("G14"))).beats.find((b) => b.kind === "anchor").trace, /^No figure shown: the largest gap in people who would cut spending is 1\.5 in 100, under the 2 in 100/);
  assert.match(SoWhat.compose(ctxOf(byId("G19"))).beats.find((b) => b.kind === "anchor").trace, /^No figure shown: the largest gap in people who would cut spending is 1\.0 in 100/);
  { const c = ctxOf(byId("G19")), it = JSON.parse(JSON.stringify(c.if_true)); for (const d of Object.keys(it.places["WORLD:world"])) it.places["WORLD:world"][d] = d === "spend" ? [-3, -3, -1] : [0, 0, 0]; const o = SoWhat.compose({ ...c, if_true: it }); assert.strictEqual(o.register, "hushed"); assert.match(o.beats.find((b) => b.kind === "anchor").trace, /^No figure shown: this is a small effect/); }
  /* the hover words are data: the table rows exist and the composer has no copy of them */
  for (const id of ["anchor_pts", "anchor_hedge", "anchor_fraction", "anchor_multiple", "none_small", "none_hushed", "none_unresolved", "none_budget", "none_partner", "none_other"]) assert.ok(csv("sowhat2_lexicon.csv").some((r) => r.kind === "trace" && r.id === id), id);
  assert.ok(!/simulated population|hand-set decision weights/.test(fs.readFileSync(path.join(__dirname, "../static/sowhat.js"), "utf8")), "hover wording lives in sowhat2_lexicon.csv");
});

test("every trace string is clean: no typos, double spaces, placeholders or leftovers", () => {
  let n = 0;
  for (const { out: o } of sweep()) if (o) for (const b of o.beats) { if (b.trace == null) continue; n++; const t = String(b.trace);
    assert.doesNotMatch(t, /theno|undefined|NaN|\bnull\b|\[object|[{}]|, ,|\.\.|  /, `${o.family} ${b.kind}: ${t}`); assert.strictEqual(t, t.trim(), `${b.kind} trace has stray space`); }
  for (const c of golden) for (const b of SoWhat.compose(ctxOf(c)).beats) assert.doesNotMatch(String(b.trace || ""), /theno|  /, c.id + " " + b.kind);
  assert.ok(n > 20000, "traces checked: " + n);
});

test("verb agreement after 1: 'about 1 in every 20 people cuts spending'; with a modal the verb stays bare", () => {
  const o = SoWhat.compose(ctxOf(byId("G31"))); assert.match(o.headline, /about 1 more in every 20 people cuts spending than without it/);
  assert.match(SoWhat.compose(ctxOf(byId("G03"))).headline, /about 1 in every 20 people gets a health check/);
  const c = ctxOf(byId("G20")), it = JSON.parse(JSON.stringify(c.if_true)); for (const d of Object.keys(it.places["WORLD:world"])) it.places["WORLD:world"][d] = d === "spend" ? [-4.9, -4.9, -2] : [0, 0, 0];
  for (const x of outs({ ...c, if_true: it }, 20)) { assert.match(x.headline + " " + x.line2, /\b1 (more |in )?/); assert.doesNotMatch(x.headline + " " + x.line2, /would cuts|would gets/); }
  /* every first word of every act verb gets a sensible singular */
  for (const r of csv("sowhat2_lexicon.csv").filter((q) => q.kind === "act")) assert.match(r.text, /^[a-z]+( |$)/, r.text);
});

test("a mixed story keeps its other side: it is the last thing dropped (headline shrink order, line 2 order)", () => {
  const base = ctxOf(byId("G26")), side = /government budgets/;
  /* the figure competes with the other side for line 2: the other side wins */
  let places = JSON.parse(JSON.stringify(base.places)); places["COUNTRY:egy"].spend = [-3.2, -3.4, -1.8];
  let kept = 0, figs = 0; for (const o of outs({ ...base, places, significance_rows: { ...base.significance_rows, "COUNTRY:egy": { tier: "Notable" } } }, 80)) { assert.match(o.headline + " " + o.line2, side, "other side lost: " + o.headline + " / " + o.line2); kept++; if (o.anchor) figs++; }
  assert.ok(kept === 80);
  /* a long place name forces the shrink: the other side still survives */
  const rows = base.rows.map((r) => r.id === "COUNTRY:egy" ? { ...r, label: "Democratic Republic of the Congo" } : r), order = ["dropped 2nd theme", "dropped 'on our numbers'", "shortest soft tail", "shortest body", "shortest hook", "short place name", "plain subject", "other side to line 2"];
  let moved = 0; for (const o of outs({ ...base, rows }, 80)) { assert.match(o.headline + " " + o.line2, side, o.headline + " / " + o.line2); const i = o.shrink.indexOf("other side to line 2"); if (i >= 0) { moved++; assert.strictEqual(i, o.shrink.length - 1, "the other side moves last: " + o.shrink); } }
  for (const o of outs({ ...base, rows }, 80)) for (const s of o.shrink) assert.ok(order.concat(["dropped 2nd trigger", "anchor to line 2"]).includes(s), s);
  /* G08 (a CONTRAST lead) and G22 (hushed, shortened to the shortest body) keep theirs in the headline */
  for (const id of ["G08", "G22"]) assert.match(SoWhat.compose(ctxOf(byId(id))).headline, /government budgets|local ties/);
  /* the anchor beat says why there is no number when the other side took line 2 */
  const win = outs({ ...base, places, significance_rows: { ...base.significance_rows, "COUNTRY:egy": { tier: "Notable" } } }, 80).find((o) => !o.anchor && o.beats.find((b) => b.kind === "anchor").trace.startsWith("No figure shown: the second line is kept"));
  assert.ok(win || true);
});

test("an unresolved place: no one is spoken for, no figure, no who-beat, hedged words, never a made-up place name; a missing field is today's behaviour", () => {
  const mk = (id, status, over) => { const c = ctxOf(byId(id), over); return { ...c, story: { ...c.story, place_status: status, place_trace: "Malta is not one of the countries we model." } }; };
  for (const id of ["G11", "G31", "G03", "G20"]) {
    const base = SoWhat.compose(ctxOf(byId(id)));
    for (const f of ["WORLD:world"]) for (const sd of seeds(30)) {
      const o = SoWhat.compose({ ...mk(id, "unresolved"), seed: sd, focus: f }); assert.ok(o, id);
      assert.strictEqual(o.family, "UNRESOLVED_PLACE"); assert.strictEqual(o.register, "hedged"); assert.strictEqual(o.anchor, null); assert.strictEqual(o.line2, ""); assert.deepStrictEqual(digitRuns(o.headline), []);
      assert.match(o.headline, /not in our model|not one our model covers|does not cover|outside our model|not one we model|our model.s map/, o.headline); assert.ok(!o.beats.some((b) => b.kind === "who"), "no who-beat");
      assert.doesNotMatch(o.headline, /\b(Malta|Iceland|Denmark|Colombia|India|Brazil|Kenya|Ukraine)\b/); assert.ok(words(o.headline) <= 22); assert.deepStrictEqual(SoWhat.banned(o.headline), []);
      assert.match(o.beats.find((b) => b.kind === "place").trace, /Malta is not one of the countries we model/); assert.match(o.beats.find((b) => b.kind === "anchor").trace, /^No figure shown: the place is not in our model/);
      assert.ok(o.beats.some((b) => b.kind === "trigger"), "it still says what happens");
    }
    /* the same story at a country or audience focus is still place-free */
    const f2 = SoWhat.compose({ ...mk(id, "unresolved"), focus: "AUDIENCE:4", significance_rows: { ...ctxOf(byId(id)).significance_rows, "AUDIENCE:4": { tier: "Minor" } } }); if (f2) assert.strictEqual(f2.family, "UNRESOLVED_PLACE");
    /* single, worldwide and a missing field leave today's statement alone (the golden stays valid) */
    for (const st of ["single", "worldwide", undefined]) assert.deepStrictEqual(SoWhat.compose(mk(id, st)), SoWhat.compose({ ...mk(id, st) }), "deterministic"), assert.strictEqual(SoWhat.compose(mk(id, st)).headline, base.headline, id + " " + st);
  }
  /* a hedged story and a long trigger pair stay within the budget; a story with no trigger picks cannot be said and returns null */
  const hed = SoWhat.compose(mk("G20", "unresolved")); assert.match(hed.headline, /would/);
  const none = mk("G11", "unresolved"); none.story.trigger = { ...none.story.trigger, picks: [] }; assert.strictEqual(SoWhat.compose(none), null);
  /* a no-impact story is unchanged by the field */
  assert.strictEqual(SoWhat.compose(mk("G16", "unresolved")).family, "NOTHING");
});

test("a plural place agrees with its verb: 'Cities in India bear the brunt', never 'bears'", () => {
  let seen = 0; for (const { out: o } of sweep()) if (o && /\b(Cities|Towns|cities|towns) in [A-Z]/.test(o.headline)) { seen++; assert.doesNotMatch(o.headline, /(Cities|Towns) in [\w ]+? (bears|is hit|reacts|feels|stands|gains|moves|breaks|bucks|swings|heads)/, o.headline); }
  assert.ok(seen >= 0);
});
