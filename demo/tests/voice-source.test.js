// node --test demo/tests/voice-source.test.js
// Fixtures: voice/fixtures/twovoice-snapshots.json (in repo, synthetic). The real-speech fixture lives in
// data/voice-fixtures/ (not in git: third-party audio) and its tests skip when it is absent.
const test = require("node:test"), assert = require("node:assert"), fs = require("node:fs"), path = require("node:path");
const { createStabiliser, norm } = require("../static/voice-source.js");
const ROOT = path.join(__dirname, "..", "..");
const load = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const flat = (s) => s.segments.flatMap((g) => g.words.trim().split(/\s+/).filter(Boolean).map((w) => [g.speaker, w]));
const run = (snaps, opts) => { const st = createStabiliser(opts), out = []; for (const s of snaps) out.push(...st.feed(s)); out.push(...st.flush()); return { st, out }; };

const TWO = load("voice/fixtures/twovoice-snapshots.json");

test("two-voice clip: committed sequence equals the final transcript, in order, once", () => {
  const { out, st } = run(TWO), want = flat(TWO[TWO.length - 1]);
  assert.deepStrictEqual(out.map((w) => [w.spk, w.w]), want);
  assert.strictEqual(st.stats().rewrites + st.stats().punctUpdates + st.stats().speakerFlips, 0);
  assert.deepStrictEqual(out.map((w) => w.turnId).filter((v, i, a) => a.indexOf(v) === i), [0, 1, 2]);   // the clip is speaker 0, 1, 0
  for (let i = 1; i < out.length; i++) assert.ok(out[i].t >= out[i - 1].t);   // commit clock never goes back
});

test("an open segment keeps its last K words back; a closed one is released", () => {
  const seg = (a, b, w) => ({ speaker: "speaker_0", start_time: a, end_time: b, words: w });
  const words = "a b c d e f g h i j";
  const st = createStabiliser({ K: 5 });
  assert.strictEqual(st.feed({ audio_s: 5, segments: [seg(1, 5, words)] }).length, 5);     // 10 words, 5 newest held
  assert.strictEqual(st.tail().length, 5);
  assert.strictEqual(st.feed({ audio_s: 6, segments: [seg(1, 5, words), seg(5.5, 6, "k l")] }).length, 5);   // later segment closes the first
  const late = createStabiliser({ K: 5, closeGap: 3 });
  assert.strictEqual(late.feed({ audio_s: 9.5, segments: [seg(1, 5, words)] }).length, 10);  // silent for > closeGap: closed
});

test("flush commits the tail and marks segment ends", () => {
  const st = createStabiliser();
  for (const s of TWO.slice(0, 8)) st.feed(s);
  const before = st.committed().length, tail = st.tail().length, out = st.flush();
  assert.strictEqual(out.length, tail);
  assert.strictEqual(st.committed().length, before + tail);
  assert.strictEqual(out[out.length - 1].last, true);
  assert.strictEqual(st.flush().length, 0);                                    // idempotent
});

test("an injected rewrite of a committed word emits nothing twice and is counted", () => {
  const snaps = JSON.parse(JSON.stringify(TWO)), st = createStabiliser();
  let n = 0; for (const s of snaps.slice(0, 12)) n += st.feed(s).length;
  const c = st.committed(), victim = c[0];
  const bad = JSON.parse(JSON.stringify(snaps[12])); bad.segments[0].words = bad.segments[0].words.replace(victim.w, "ZZZ");
  const out = st.feed(bad);
  assert.ok(!out.some((w) => w.w === "ZZZ"));
  assert.strictEqual(st.committed()[0].w, victim.w);                           // committed text is never rewritten
  assert.strictEqual(st.stats().rewrites, 1);
  const again = st.feed(bad); assert.strictEqual(st.stats().rewrites, 1);      // same change is not counted twice
  void n; void again;
});

test("punctuation-only and speaker changes are counted separately", () => {
  const st = createStabiliser(); for (const s of TWO.slice(0, 12)) st.feed(s);
  const w0 = st.committed()[0].w, snap = JSON.parse(JSON.stringify(TWO[12]));
  snap.segments[0].words = snap.segments[0].words.replace(w0, w0 + ".");
  st.feed(snap); assert.strictEqual(st.stats().punctUpdates, 1); assert.strictEqual(st.stats().rewrites, 0);
  const s2 = JSON.parse(JSON.stringify(TWO[13])); s2.segments[0].speaker = "speaker_5";
  st.feed(s2); assert.ok(st.stats().speakerFlips >= 1);
});

test("a same-speaker segment after a long pause starts a new turn; a short gap does not", () => {
  const seg = (a, b, w) => ({ speaker: "speaker_0", start_time: a, end_time: b, words: w });
  const mk = (gap) => ({ audio_s: 30, segments: [seg(1, 3, "one two three four five six"), seg(3 + gap, 6 + gap, "seven eight nine ten eleven twelve")] });
  const short = createStabiliser(); short.feed(mk(1)); short.flush();
  const long = createStabiliser(); long.feed(mk(4)); long.flush();
  assert.strictEqual(new Set(short.committed().map((w) => w.turnId)).size, 1);
  assert.strictEqual(new Set(long.committed().map((w) => w.turnId)).size, 2);
  assert.deepStrictEqual(short.committed().filter((w) => w.last).map((w) => w.w), ["six", "twelve"]);
});

const APOLLO = path.join(ROOT, "data/voice-fixtures/apollo13-snapshots.json");
test("real speech (Apollo 13 narration, 7 speaker labels): no word or speaker rewritten after commit", { skip: !fs.existsSync(APOLLO) }, () => {
  const snaps = JSON.parse(fs.readFileSync(APOLLO, "utf8")), { out, st } = run(snaps), s = st.stats();
  const want = flat(snaps[snaps.length - 1]);
  assert.strictEqual(out.length, want.length);
  assert.deepStrictEqual(out.map((w) => norm(w.w)), want.map(([, w]) => norm(w)));
  assert.strictEqual(s.rewrites, 0); assert.strictEqual(s.speakerFlips, 0);
  console.log("apollo K=5:", JSON.stringify(s));
});
