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

test("punctuation-only changes are counted separately from letter changes", () => {
  const st = createStabiliser(); for (const s of TWO.slice(0, 12)) st.feed(s);
  const w0 = st.committed()[0].w, snap = JSON.parse(JSON.stringify(TWO[12]));
  snap.segments[0].words = snap.segments[0].words.replace(w0, w0 + ".");
  st.feed(snap); assert.strictEqual(st.stats().punctUpdates, 1); assert.strictEqual(st.stats().rewrites, 0);
});

test("concurrent voices: the server reordering segments between snapshots never repeats or drops a word", () => {
  // A long segment from voice 0 keeps growing while voice 1 interjects over it from the same start time.
  // Successive snapshots list the two segments in alternating order (the real-world trigger of the "Code" loop).
  const seg = (spk, a, b, w) => ({ speaker: spk, start_time: a, end_time: b, words: w });
  const long = "so before guiding michael through the form the scammer instructed him to install something called a remote access software which allows them to view his computer".split(" ");
  const snaps = []; for (let n = 4; n <= long.length; n += 3) {
    const A = seg("speaker_0", 10, 10 + n * 0.35, long.slice(0, n).join(" ")), B = seg("speaker_1", 10, 10.4, "Code Code");
    snaps.push({ audio_s: 10 + n * 0.35 + 0.3, segments: (snaps.length % 2 ? [B, A] : [A, B]) });
  }
  const st = createStabiliser({ K: 2 }), out = []; for (const s of snaps) out.push(...st.feed(s)); out.push(...st.flush());
  const v1 = out.filter((w) => w.spk === "speaker_1").map((w) => w.w), v0 = out.filter((w) => w.spk === "speaker_0").map((w) => w.w);
  assert.deepStrictEqual(v1, ["Code", "Code"]);                                  // the interjection appears once, not on every snapshot
  assert.deepStrictEqual(v0, long.slice(0, v0.length)); assert.ok(v0.length >= long.length - 3);   // the long voice keeps its own order, nothing skipped
});

test("a word shown under one voice label is never emitted again under another (relabel guard)", () => {
  const seg = (spk) => ({ speaker: spk, start_time: 5, end_time: 8, words: "one two three four five six" });
  const st = createStabiliser(); const a = st.feed({ audio_s: 20, segments: [seg("speaker_0")] });
  const b = st.feed({ audio_s: 21, segments: [seg("speaker_3")] });
  assert.strictEqual(a.length, 6); assert.strictEqual(b.length, 0); assert.strictEqual(st.stats().speakerFlips, 6);
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

const REAL = ["apollo13", "nanobaiter"].map((n) => [n, path.join(ROOT, "data/voice-fixtures/" + n + "-snapshots.json")]);
for (const [name, file] of REAL) {
  test(`real speech (${name}): every word appears exactly once, none repeated, none lost`, { skip: !fs.existsSync(file) }, () => {
    const snaps = JSON.parse(fs.readFileSync(file, "utf8")), { out, st } = run(snaps), s = st.stats();
    const finalWords = snaps[snaps.length - 1].segments.reduce((n, g) => n + g.words.trim().split(/\s+/).filter(Boolean).length, 0);
    assert.strictEqual(out.length, finalWords);
    const seen = new Set(); let dup = 0; for (const w of out) { const k = w.spk + "|" + w.w + "|" + w.st; if (seen.has(k)) dup++; seen.add(k); }
    assert.strictEqual(dup, 0);
    assert.ok(s.rewrites <= 2, "letter rewrites after commit: " + s.rewrites);
    console.log(name + " K=2:", JSON.stringify({ committed: s.committed, rewrites: s.rewrites, punctUpdates: s.punctUpdates, meanLagS: +s.lagMean.toFixed(2) }));
  });
}
