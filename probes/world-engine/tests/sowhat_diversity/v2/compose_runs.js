/* HARNESS-2: node compose_runs.js -> test1.json, test2.json in the diversity2 scratch dir. Read-only on every project file.
   Same method as ../compose_runs.js; v2 composer inputs (hooks table, if_true, significance_rows, weight, seed from story). */
const fs = require("fs");
const SoWhat = require("/workspace/demo/static/sowhat.js");
const D = "/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/diversity2/";
const RULES = "/workspace/probes/persona/rules_v2/";
const live = JSON.parse(fs.readFileSync(D + "sowhat_tables_live.json"));
const tables = live;
console.log("tables version", live.version, "rows", ["frames", "hooks", "templates", "lexicon", "lexicon_v1"].map((k) => k + ":" + live[k].length).join(" "));
for (const [k, f] of [["frames", "sowhat2_frames.csv"], ["hooks", "sowhat2_hooks.csv"], ["templates", "sowhat2_templates.csv"], ["lexicon", "sowhat2_lexicon.csv"], ["lexicon_v1", "sowhat_lexicon.csv"]]) console.log(" live", k, "rows equal CSV rows:", SoWhat.parseCsv(fs.readFileSync(RULES + f, "utf8")).length === live[k].length);
const peak = (v) => v.reduce((b, x) => Math.abs(x) > Math.abs(b) ? x : b, 0);
const mx = (P) => Math.max(0, ...Object.values(P || {}).map((v) => Math.abs(peak(v))));
const J = (f) => JSON.parse(fs.readFileSync(f));
const ctxOf = (r, text, focus, extra) => { const I = r.impact, id = r.identify, w = id.weight && typeof id.weight === "object" ? id.weight.value : null;
  return { story: I.story, focus, rows: r.read.rows, places: I.places, rank: I.rank, significance: I.significance, significance_rows: I.significance_rows, if_true: I.if_true || null, readings: id.readings, weight: w, text, tables, prev: null, ...extra }; };
const slim = (o) => ({ headline: o.headline, line2: o.line2, template: o.body || o.template, family: o.family, hook: o.hook, body: o.body, register: o.register, lead: o.lead, frame: o.frame, shrink: o.shrink, anchor: o.anchor, seed: o.seed, beats: o.beats.filter((b) => ["anchor", "response", "register", "contrast", "certainty", "trigger"].includes(b.kind)).map((b) => ({ kind: b.kind, text: b.text, trace: b.trace, shown: b.shown, value: b.value, rule: b.rule })) });

const stories = J(D + "stories.json"), t1 = [], fails = [];
for (const s of stories) {
  const fp = D + s.id + ".resp.json"; if (!fs.existsSync(fp)) { fails.push({ id: s.id, why: "no response (HTTP failure)" }); continue; }
  const r = J(fp), imp = r.impact, I = r.identify, story = imp && imp.story, rows = r.read && r.read.rows, places = imp && imp.places;
  if (!story) { fails.push({ id: s.id, why: "no impact.story" }); continue; }
  const countries = rows.filter((x) => x.level === "country").map((x) => ({ id: x.id, m: mx(places[x.id]) })).sort((a, b) => b.m - a.m);
  const auds = rows.filter((x) => x.level === "audience").map((x) => ({ id: x.id, m: mx(places[x.id]) })).sort((a, b) => b.m - a.m);
  const foci = [["world", "WORLD:world"]];
  if (/^COUNTRY:/.test(I.entry) && countries[0]) foci.push(["country", countries[0].id]);
  if (auds[0]) foci.push(["audience", auds[0].id]);
  if (foci.length < 3 && auds[1]) foci.push(["audience2", auds[1].id]);
  for (const [fk, fid] of foci) {
    const o = SoWhat.compose(ctxOf(r, s.text, fid));
    if (!o) { fails.push({ id: s.id, why: "compose null at " + fk }); continue; }
    t1.push({ id: s.id, topic: s.topic, tags: [s.cert, s.scope, s.valence, s.effect], focus: fk, focus_id: fid, entry: I.entry, cert: story.certainty.kind, weight: I.weight && I.weight.value, tier: story.scale && story.scale.tier, frame_raw: story.frame.id, ...slim(o), banned: SoWhat.banned(o.headline + " " + o.line2) });
  }
}
fs.writeFileSync(D + "test1.json", JSON.stringify({ outputs: t1, fails }, null, 1)); console.log("test1 outputs", t1.length, "fails", fails.length, JSON.stringify(fails));

/* TEST 2: 46 bases = evenly spaced real responses; rows, places, rank, if_true, weight, seed from base a; story beats (frame, trigger, certainty, scale, topic) from base b; entry from a. */
const all = stories.filter((s) => fs.existsSync(D + s.id + ".resp.json")).map((s) => ({ s, r: J(D + s.id + ".resp.json") })).filter((x) => x.r.impact && x.r.impact.story);
const step = all.length / 46, bases = []; for (let i = 0; i < 46; i++) bases.push(all[Math.floor(i * step)]);
const t2 = []; let nul = 0;
for (const a of bases) for (const b of bases) {
  if (a === b) continue;
  const story = { ...b.r.impact.story, entry: a.r.impact.story.entry, seed: a.r.impact.story.seed, topic: b.r.impact.story.topic };
  const r2 = { ...a.r, impact: { ...a.r.impact, story } };
  const o = SoWhat.compose(ctxOf(r2, a.s.text, "WORLD:world"));
  if (!o) { nul++; continue; }
  t2.push({ rows_from: a.s.id, beats_from: b.s.id, cert: b.r.impact.story.certainty.kind, ...slim(o), banned: SoWhat.banned(o.headline + " " + o.line2) });
}
fs.writeFileSync(D + "test2.json", JSON.stringify({ outputs: t2, null_count: nul, bases: bases.length }, null, 1)); console.log("test2 bases", bases.length, "outputs", t2.length, "null", nul);
