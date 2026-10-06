/* node --test demo/tests/sowhat.test.js
   Reproduces every golden case (headline, line2, template, lead, shrink) from probes/world-engine/spec/sowhat-golden.json. */
const test = require("node:test"), assert = require("node:assert"), fs = require("node:fs"), path = require("node:path");
const SoWhat = require("../static/sowhat.js");
const SPEC = path.join(__dirname, "../../probes/world-engine/spec"), RULES = path.join(__dirname, "../../probes/persona/rules_v2");
const csv = (f) => SoWhat.parseCsv(fs.readFileSync(path.join(RULES, f), "utf8"));
const tables = { frames: csv("sowhat_frames.csv"), lexicon: csv("sowhat_lexicon.csv"), templates: csv("sowhat_templates.csv") };
const golden = JSON.parse(fs.readFileSync(path.join(SPEC, "sowhat-golden.json"), "utf8")).cases;
const fixture = (c) => JSON.parse(fs.readFileSync(path.join(SPEC, "sowhat-fixtures", c.id + ".json"), "utf8"));

function input(c, fx, focus, story) {
  return { story: story || SoWhat.deriveStory(fx, c.story), focus, rows: fx.read.rows, places: fx.impact.places, rank: fx.impact.rank, readings: fx.identify.readings, text: c.text, tables, prev: null };
}
const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
const all = [];

for (const c of golden) {
  const fx = fixture(c);
  for (const f of c.foci) {
    test(`golden ${c.id} ${f.focus}: ${f.expect.template}`, () => {
      const out = SoWhat.compose(input(c, fx, f.focus));
      assert.ok(out, "compose returned null");
      assert.strictEqual(out.headline, f.expect.headline);
      assert.strictEqual(out.line2, f.expect.line2);
      assert.strictEqual(out.template, f.expect.template);
      assert.strictEqual(out.lead, f.expect.lead);
      assert.deepStrictEqual(out.shrink, f.expect.shrink);
    });
  }
}

test("budgets, banned patterns, spans and determinism hold for every golden output", () => {
  let n = 0;
  for (const c of golden) {
    const fx = fixture(c);
    for (const f of c.foci) {
      const inp = input(c, fx, f.focus), out = SoWhat.compose(inp);
      assert.ok(words(out.headline) <= 22, `${c.id} headline over 22 words: ${out.headline}`);
      assert.ok(words(out.line2) <= 14, `${c.id} line2 over 14 words: ${out.line2}`);
      assert.deepStrictEqual(SoWhat.banned(out.headline + " " + out.line2), [], `${c.id} banned pattern in: ${out.headline} ${out.line2}`);
      for (const s of out.spans) {
        const t = s.line === 1 ? out.headline : out.line2;
        assert.ok(s.start >= 0 && s.end <= t.length && s.start < s.end, `${c.id} bad span ${JSON.stringify(s)}`);
        assert.ok(["trigger", "response", "frame", "certainty", "scale", "who", "arc"].includes(s.beat));
      }
      assert.deepStrictEqual(SoWhat.compose(inp), out, "not deterministic");
      assert.ok(Array.isArray(out.beats));
      n++;
    }
  }
  assert.strictEqual(n, 44);
});

test("banned() catches the patterns it should and passes plain sentences", () => {
  assert.ok(SoWhat.banned("Worldwide, people are likelier to spend more, buy more and travel less.").length);
  assert.ok(SoWhat.banned("they cut back, travel less and stock up").includes("comma list"));
  assert.ok(SoWhat.banned("up 3.5 points").includes("decimal"));
  assert.ok(SoWhat.banned("it ends next month").includes("calendar time"));
  assert.deepStrictEqual(SoWhat.banned("If this forecast comes true, jobs would get less secure, and people would cut back and apply for aid."), []);
  assert.deepStrictEqual(SoWhat.banned("Loans get cheaper: people open their wallets and invest a bit more."), []);
});

test("banned(): an opening hedge is not a list item, a real list still is", () => {
  assert.deepStrictEqual(SoWhat.banned("An opinion piece; if enough people agree, prices could rise, and people could spend less."), []);
  assert.deepStrictEqual(SoWhat.banned("If this forecast comes true, prices would rise, and people would spend less."), []);
  assert.ok(SoWhat.banned("If it holds, they cut back, travel less and stock up").includes("comma list"));
});

test("null on missing input, never throws", () => {
  const c = golden[0], fx = fixture(c), good = input(c, fx, "WORLD:world");
  assert.strictEqual(SoWhat.compose(null), null);
  assert.strictEqual(SoWhat.compose(undefined), null);
  assert.strictEqual(SoWhat.compose({}), null);
  assert.strictEqual(SoWhat.compose({ ...good, story: null }), null);
  assert.strictEqual(SoWhat.compose({ ...good, story: { version: 1 } }), null);
  assert.strictEqual(SoWhat.compose({ ...good, tables: null }), null);
  assert.strictEqual(SoWhat.compose({ ...good, tables: { frames: [], lexicon: [], templates: [] } }), null);
  assert.strictEqual(SoWhat.compose({ ...good, rows: null }), null);
  assert.strictEqual(SoWhat.compose({ ...good, places: null }), null);
  assert.strictEqual(SoWhat.compose({ ...good, places: {} }), null);
  assert.strictEqual(SoWhat.compose({ ...good, story: { ...good.story, frame: { id: "nonsense", p: 1 } } }), null);
  assert.strictEqual(SoWhat.compose({ ...good, story: { ...good.story, trigger: { picks: [{ dial: "not_a_dial", direction: "up" }] } } }), null);
  assert.ok(SoWhat.compose(good), "the good input still works");
});

test("three-argument form gives the same answer as the single object", () => {
  const c = golden[0], fx = fixture(c), a = input(c, fx, "WORLD:world"), { story, tables: t, ...rest } = a;
  assert.deepStrictEqual(SoWhat.compose(story, rest, t), SoWhat.compose(a));
});

test("feed rule: a repeated opening flips the variant", () => {
  const c = golden.find((x) => x.id === "20"), fx = fixture(c), a = SoWhat.compose(input(c, fx, "WORLD:world")), b = SoWhat.compose({ ...input(c, fx, "WORLD:world"), prev: a.headline });
  assert.notStrictEqual(b.headline.split(" ").slice(0, 3).join(" "), a.headline.split(" ").slice(0, 3).join(" "));
});

test("quiet form for a country the story never reaches", () => {
  const c = golden.find((x) => x.id === "10"), fx = fixture(c), out = SoWhat.compose(input(c, fx, "COUNTRY:ind"));
  assert.strictEqual(out.template, "NO-Q"); assert.match(out.headline, /for people in India\.$/);
});

/* ---------- review fixes (2026-10-06) ---------- */
const byId = (id) => golden.find((x) => x.id === id);
const gateStory = (id, gate, over) => { const c = byId(id), fx = fixture(c), fx2 = JSON.parse(JSON.stringify(fx)); fx2.identify.gate = { ...fx2.identify.gate, ...gate }; if (over) over(fx2); return { c, fx: fx2, story: SoWhat.deriveStory(fx2, c.story) }; };
const run = (c, fx, story, focus = "WORLD:world", extra = {}) => SoWhat.compose({ ...input(c, fx, focus, story), ...extra });

test("certainty comes from the gate, in the stated order (certainty rule)", () => {
  const k = (g, id = "09") => gateStory(id, g).story.certainty.kind;
  assert.strictEqual(k({ opinion: 0.95, forecast: 0.9, announced: 0.9, happened: 0.9 }), "opinion");
  assert.strictEqual(k({ opinion: 0.71, forecast: 0.99, announced: 0.12, happened: 0.02 }), "forecast");   /* below the 0.9 cut, opinion does not win */
  assert.strictEqual(k({ opinion: 0.2, forecast: 0.99, announced: 0.94, happened: 0.03 }), "forecast");   /* a warning */
  assert.strictEqual(k({ opinion: 0.2, forecast: 0.83, announced: 0.99, happened: 0.1 }), "announced");
  assert.strictEqual(k({ opinion: 0, forecast: 0.1, announced: 0.1, happened: 0.1 }), "announced");
  assert.strictEqual(k({ opinion: 0.2, forecast: 0.8, announced: 0.7, happened: 0.9 }), "happened");
  assert.strictEqual(SoWhat.deriveStory(fixture(byId("22")), byId("22").story).certainty.kind, "no_impact");
  for (const [id, kind] of [["15", "announced"], ["20", "forecast"], ["13", "pending"], ["09", "announced"], ["12", "announced"], ["21", "opinion"]]) assert.strictEqual(SoWhat.deriveStory(fixture(byId(id)), byId(id).story).certainty.kind, kind, id);
});

test("pending: plain present for the event, 'should' for the readings, 'Effects not felt yet.', never 'will' (fix 2)", () => {
  const c = byId("13"), fx = fixture(c), st = SoWhat.deriveStory(fx, c.story), out = run(c, fx, st);
  assert.strictEqual(st.certainty.modal, "");
  assert.match(out.headline, /^Health risks should fall, and people ease off/); assert.doesNotMatch(out.headline + out.line2, /\bwill\b|Not in effect yet/);
  assert.match(out.line2, /Effects not felt yet\./);
});

test("templates: no certainty template hard-codes a verb or purpose (fix 3)", () => {
  for (const t of tables.templates.filter((r) => /-C$/.test(r.id))) assert.doesNotMatch(t.template, /stay safe|room to breathe|hold back|get room/, t.id);
  assert.match(tables.templates.find((r) => r.id === "RP-S").template, /\{for_subj\}/);
  const c = byId("06"), fx = fixture(c), st = SoWhat.deriveStory(fx, { ...c.story, frame_choice: { ...c.story.frame_choice, p: { ripple: 0.9, shake_up: 0.1 } } });
  assert.strictEqual(run(c, fx, st, "WORLD:world").template, "RP-S");
  assert.match(run(c, fx, st, "COUNTRY:usa").headline, /^Barely a ripple for people in the United States: /);
});

test("line 2: a tiny move always shows its size; the ripple frame drops 'Elsewhere'; both 'elsewhere' variants occur and are deterministic (fixes 4, 5)", () => {
  const c = byId("13"), fx = fixture(c); assert.match(run(c, fx, SoWhat.deriveStory(fx, c.story)).line2, /^A tiny shift/);
  const c5 = byId("05"), fx5 = fixture(c5), rip = SoWhat.deriveStory(fx5, { ...c5.story, frame_choice: { ...c5.story.frame_choice, p: { ripple: 0.9, shake_up: 0.1 } } }), r = run(c5, fx5, rip);
  assert.strictEqual(r.template, "RP-W"); assert.doesNotMatch(r.line2, /lsewhere/);
  const seen = new Set();
  for (const id of ["03", "05", "10", "11", "12", "16", "17", "18", "19"]) { const cc = byId(id), ff = fixture(cc);
    for (let i = 0; i < 6; i++) { const inp = { ...input(cc, ff, "WORLD:world"), text: cc.text + " ".repeat(i) }, o = SoWhat.compose(inp); const m = /(Elsewhere, barely a ripple\.|Little changes elsewhere\.)/.exec(o.line2); if (m) seen.add(m[1]); assert.deepStrictEqual(SoWhat.compose(inp), o); } }
  assert.deepStrictEqual([...seen].sort(), ["Elsewhere, barely a ripple.", "Little changes elsewhere."]);
});

test("no headline ever exceeds 22 words, whatever the certainty (fix 4, third shrink step)", () => {
  let n = 0;
  for (const c of golden) { const fx = fixture(c); if (!fx.identify.counted) continue;
    for (const g of [{ opinion: 0, forecast: 0.9, announced: 0.1, happened: 0.1 }, { opinion: 0.95 }, { opinion: 0, forecast: 0, announced: 0.2, happened: 0 }]) for (const f of c.foci) {
      const { fx: fx2, story } = gateStory(c.id, g), o = run(c, fx2, story, f.focus); assert.ok(o, `${c.id} null`); assert.ok(words(o.headline) <= 22, `${c.id} ${f.focus}: ${o.headline}`); assert.ok(words(o.line2) <= 14); n++; } }
  assert.ok(n >= 60);
});

test("second trigger: when dropped, the reported reading is kept over an expected one (fix 4)", () => {
  const c = byId("15"), fx = fixture(c), st = SoWhat.deriveStory(fx, c.story);
  st.trigger.picks = [{ ...st.trigger.picks[0], basis: "expected", mode: "expected_in_effect" }, { ...st.trigger.picks[0], dial: "tech_adoption", direction: "up", basis: "reported", mode: "reported" }];
  const o = run(c, fx, st); assert.ok(o); assert.match(o.beats[0].text, /(jobs|digital tools)/);
});

test("honest about place: the world entry names no country; an unresolved place gives the plain place-free template (rule A)", () => {
  /* 01: entry is the world (ask_country said global with p 0.99): no country-level WHO beat, no "hardest hit" */
  const c = byId("01"), fx = fixture(c), out = run(c, fx, SoWhat.deriveStory(fx, c.story));
  assert.ok(!out.beats.some((b) => b.kind === "who" && /^(?!.*(people|earners|retirees|parents|adopters|sharers))/.test(b.text) && b.text));
  /* 14: ask_country said global with no probability (a part of the world, no country in it): unresolved */
  const c14 = byId("14"), fx14 = fixture(c14), st = SoWhat.deriveStory(fx14, c14.story);
  assert.strictEqual(st.entry.place, "unresolved");
  const o = run(c14, fx14, st); assert.strictEqual(o.template, "PL-T"); assert.doesNotMatch(o.headline + " " + o.line2, /Only |alone|most|reaches|squeeze/);
  assert.ok(o.beats.filter((b) => b.kind === "who").every((b) => /Higher-income|Older|Retired|Young|With kids|Sharing|Living alone|Big-city/.test(b.trace)), "only audiences, never a country");
  /* the same story with a real country entry would name it; with a genuine world answer it stays place-free but keeps its frame */
  const w = JSON.parse(JSON.stringify(fx14)); w.identify.country_p = 0.9; assert.strictEqual(SoWhat.deriveStory(w, c14.story).entry.place, "world");
  assert.notStrictEqual(run(c14, w, SoWhat.deriveStory(w, c14.story)).template, "PL-T");
});

test("a country is named only when it is clearly above the others (twice the runner-up) (rule A threshold)", () => {
  const mk = (usa, can) => gateStory("08", {}, (f) => { f.identify.entry = "COUNTRY:usa"; f.identify.country = "usa"; f.identify.country_p = 0.99;
    for (const id of Object.keys(f.impact.places)) if (/^COUNTRY:/.test(id)) for (const d of Object.keys(f.impact.places[id])) f.impact.places[id][d] = [0.1, 0.1, 0.1];
    const ld = "break_rules"; f.impact.places["COUNTRY:usa"][ld] = [usa, usa, usa]; f.impact.places["COUNTRY:can"][ld] = [can, can, can]; });
  const a = mk(3, 0.5), b = mk(3, 2);
  const oa = run(a.c, a.fx, a.story), ob = run(b.c, b.fx, b.story);
  assert.ok(oa.beats.some((x) => x.kind === "who" && /United States/.test(x.text + x.trace)) || /United States/.test(oa.headline), "clear leader is named: " + oa.headline);
  assert.ok(!/United States|Canada/.test(ob.headline + ob.line2), "near-equal rows are not named: " + ob.headline + " | " + ob.line2);
});
