/* node compose_runs.js  -> writes test1.json and test2.json (raw composed outputs) into the diversity scratch dir. Read-only on every project file. */
const fs = require("fs"), path = require("path");
const SoWhat = require("/workspace/demo/static/sowhat.js");
const D = "/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/diversity/", REV = "/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/review/";
const SPEC = "/workspace/probes/world-engine/spec/", RULES = "/workspace/probes/persona/rules_v2/";
const csv = (f) => SoWhat.parseCsv(fs.readFileSync(RULES + f, "utf8"));
const csvTables = { frames: csv("sowhat_frames.csv"), lexicon: csv("sowhat_lexicon.csv"), templates: csv("sowhat_templates.csv") };
const live = JSON.parse(fs.readFileSync(D + "sowhat_tables_live.json"));
const KEYS = ["id", "kind", "frame", "lead", "certainty", "template", "noun", "down", "up", "down_bare", "up_bare", "theme", "text", "text_alt", "template_family"];
const proj = (rs) => JSON.stringify(rs.map((r) => KEYS.map((k) => String(r[k] == null ? "" : r[k]))));   /* only the columns the composer reads (note columns can hold stray commas) */
const same = ["frames", "lexicon", "templates"].every((k) => proj(live[k]) === proj(csvTables[k]));
console.log("live /sowhat tables identical to the CSVs:", same);
const tables = { frames: live.frames, lexicon: live.lexicon, templates: live.templates };
const peak = (v) => v.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0);
const mx = (P) => Math.max(0, ...Object.values(P || {}).map((v) => Math.abs(peak(v))));
const J = (f) => JSON.parse(fs.readFileSync(f));

/* ---------- TEST 1 ---------- */
const stories = J(D + "stories.json"), t1 = [], fails = [];
for (const s of stories) {
  const fp = D + s.id + ".resp.json"; if (!fs.existsSync(fp)) { fails.push({ id: s.id, why: "no response (HTTP failure)" }); continue; }
  const r = J(fp), imp = r.impact, I = r.identify, story = imp && imp.story, rows = r.read && r.read.rows, places = imp && imp.places;
  if (!story) { fails.push({ id: s.id, why: "no impact.story in response" }); continue; }
  const base = { story, rows, places, rank: imp.rank, readings: I.readings, text: s.text, tables, prev: null };
  const countries = rows.filter((x) => x.level === "country").map((x) => ({ id: x.id, m: mx(places[x.id]) })).sort((a, b) => b.m - a.m);
  const auds = rows.filter((x) => x.level === "audience").map((x) => ({ id: x.id, m: mx(places[x.id]) })).sort((a, b) => b.m - a.m);
  const foci = [["world", "WORLD:world"]];
  if (/^COUNTRY:/.test(I.entry) && countries[0]) foci.push(["country", countries[0].id]);
  if (auds[0]) foci.push(["audience", auds[0].id]);
  if (foci.length < 3 && auds[1]) foci.push(["audience2", auds[1].id]);
  for (const [fk, fid] of foci) {
    const o = SoWhat.compose({ ...base, focus: fid });
    if (!o) { fails.push({ id: s.id, why: "compose null at " + fk }); continue; }
    t1.push({ id: s.id, topic: s.topic, tags: [s.cert, s.scope, s.valence, s.effect], focus: fk, entry: I.entry, cert: story.certainty.kind, tier: story.scale && story.scale.tier, frame_raw: story.frame.id, headline: o.headline, line2: o.line2, template: o.template, lead: o.lead, frame: o.frame, shrink: o.shrink, banned: SoWhat.banned(o.headline + " " + o.line2) });
  }
}
fs.writeFileSync(D + "test1.json", JSON.stringify({ outputs: t1, fails }, null, 1)); console.log("test1 outputs", t1.length, "composer/data fails", fails.length);

/* ---------- TEST 2 ---------- */
const golden = J(SPEC + "sowhat-golden.json").cases, revStories = J(REV + "stories.json"), bases = [];
for (const c of golden) { const fx = J(SPEC + "sowhat-fixtures/" + c.id + ".json"); bases.push({ id: "fx" + c.id, text: c.text, rows: fx.read.rows, places: fx.impact.places, rank: fx.impact.rank, story: SoWhat.deriveStory(fx, c.story), entry: SoWhat.deriveStory(fx, c.story).entry }); }
for (const [id, , text] of revStories) { const r = J(REV + id + ".json"); bases.push({ id, text, rows: r.read.rows, places: r.impact.places, rank: r.impact.rank, story: r.impact.story, entry: r.impact.story.entry }); }
const t2 = []; let nul = 0;
for (const a of bases) for (const b of bases) {
  if (a === b) continue;
  const story = { ...b.story, entry: a.entry };   /* beats from b (frame, trigger, certainty, scale); place facts stay with a */
  const o = SoWhat.compose({ story, focus: "WORLD:world", rows: a.rows, places: a.places, rank: a.rank, text: a.text, tables, prev: null });
  if (!o) { nul++; continue; }
  t2.push({ rows_from: a.id, beats_from: b.id, cert: b.story.certainty.kind, headline: o.headline, line2: o.line2, template: o.template, lead: o.lead, frame: o.frame, shrink: o.shrink, banned: SoWhat.banned(o.headline + " " + o.line2) });
}
fs.writeFileSync(D + "test2.json", JSON.stringify({ outputs: t2, null_count: nul, bases: bases.length }, null, 1)); console.log("test2 bases", bases.length, "outputs", t2.length, "null", nul);
