/* Stabiliser for the voice server's transcript snapshots (docs/voice-flow-integration-plan.md, "Stabiliser").
 *
 * Input:  full snapshots {segments:[{speaker,start_time,end_time,words}], audio_s}, one per model step.
 * Output: append-only committed words {spk, w, t, st, turnId, last, seg} that never repeat, plus a tentative
 *         tail (display only). Same word shape flow.html's onWord(wd) consumes, so live and replay share code.
 *
 * Words are tracked PER VOICE, not in one combined list. Concurrent voices (an interjection over a long
 * segment) make the server list segments in a different order from one snapshot to the next; a combined list then
 * shifts positions and re-emits words that were already shown. One voice's own words never reorder, so each voice
 * has its own append-only stream, and words emitted in the same snapshot are ordered by speech time.
 * A word is committed once it is stable, and only as a prefix of its voice's stream:
 *   - its segment is closed (someone spoke after it ended, or audio_s - end_time > closeGap), or
 *   - at least K (default 2, measured) newer words follow it in its own segment, or
 *   - flush().
 * `last` = final word of a closed segment (an utterance chunk). Measured on real speech: trailing punctuation on a
 * segment's final word can arrive hundreds of words late, so runners must use `last`, not "." , to end a chunk.
 * `turnId` changes on a speaker change, or a same-speaker segment after a pause longer than `pause` seconds.
 * A committed word that later differs in the snapshot is never re-emitted; it is counted in stats.
 *   rewrites      = the word's letters changed      punctUpdates = only trailing punctuation changed
 *   speakerFlips  = a word already shown re-appeared under another voice label (suppressed, not re-emitted)
 * `t` is the audio clock (audio_s) when committed; `st` is the word's estimated speech time inside its segment.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(); else root.VoiceSource = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const norm = (w) => w.replace(/[^\p{L}\p{N}']+/gu, "").toLowerCase();

  function createStabiliser(opts) {
    const o = Object.assign({ K: 2, closeGap: 3, pause: 2 }, opts || {});
    let committed = [], done = {}, emitted = new Set(), turnId = -1, prev = null, audio = 0, tail = [], lastSnap = { segments: [] };
    const stats = { snapshots: 0, committed: 0, rewrites: 0, punctUpdates: 0, speakerFlips: 0, lagSum: 0, lagMax: 0 };

    /* one stream of words per voice, its segments in time order */
    function streams(snap) {
      const segs = (snap.segments || []).filter((g) => g.words && g.words.trim()).map((g, i) => ({ i, start: g.start_time, end: g.end_time, spk: g.speaker, ws: g.words.trim().split(/\s+/) }));
      segs.sort((a, b) => a.start - b.start || a.i - b.i);
      const by = {};
      for (const sg of segs) {
        const closed = audio - sg.end > o.closeGap || segs.some((x) => x !== sg && x.start >= sg.end - 0.05), dur = Math.max(sg.end - sg.start, 0);
        sg.ws.forEach((w, k) => (by[sg.spk] ||= []).push({ w, spk: sg.spk, seg: sg, k, n: sg.ws.length, closed, st: sg.start + dur * (k / Math.max(sg.ws.length, 1)) }));
      }
      return by;
    }

    function step(snap, isFlush) {
      audio = snap.audio_s != null ? snap.audio_s : audio; lastSnap = snap; stats.snapshots++;
      const by = streams(snap), fresh = [], tails = [];
      for (const spk of Object.keys(by)) {
        const seq = by[spk], d = (done[spk] ||= []);
        for (let i = 0; i < d.length && i < seq.length; i++) {       // audit: a committed word that changed (counted once per new value, never re-emitted)
          if (seq[i].w === d[i]) continue;
          if (norm(seq[i].w) === norm(d[i])) stats.punctUpdates++; else stats.rewrites++;
          d[i] = seq[i].w;
        }
        let i = d.length;
        for (; i < seq.length; i++) {
          const x = seq[i];
          if (!(isFlush || x.closed) && x.n - 1 - x.k < o.K) break;
          d.push(x.w);
          const key = x.seg.start.toFixed(1) + "|" + x.k + "|" + norm(x.w);
          if (emitted.has(key)) { stats.speakerFlips++; continue; }  // the same word already shown (a relabelled voice): never emit it twice
          emitted.add(key); fresh.push(x);
        }
        for (; i < seq.length; i++) tails.push(seq[i]);
      }
      fresh.sort((a, b) => a.st - b.st);                             // words that settle in the same snapshot: in speech order
      const out = [];
      for (const x of fresh) {
        const newTurn = !prev || prev.spk !== x.spk || (prev.segStart !== x.seg.start && x.seg.start - prev.segEnd > o.pause);
        if (newTurn) turnId++;
        const wd = { spk: x.spk, w: x.w, t: audio, st: +x.st.toFixed(2), turnId, last: x.closed && x.k === x.n - 1 || (isFlush && x.k === x.n - 1), seg: x.seg.i };
        committed.push(wd); out.push(wd); prev = { spk: x.spk, segStart: x.seg.start, segEnd: x.seg.end }; stats.committed++;
        const lag = audio - x.st; stats.lagSum += lag; if (lag > stats.lagMax) stats.lagMax = lag;
      }
      tail = tails.sort((a, b) => a.st - b.st).map((x) => ({ spk: x.spk, w: x.w }));
      return out;
    }

    return {
      feed: (snap) => step(snap, false),
      flush: (snap) => step(snap || lastSnap, true),
      tail: () => tail,
      committed: () => committed,
      stats: () => Object.assign({}, stats, { lagMean: stats.committed ? stats.lagSum / stats.committed : 0 }),
      reset: () => { lastSnap = { segments: [] }; committed = []; done = {}; emitted = new Set(); turnId = -1; prev = null; tail = []; },
    };
  }
  return { createStabiliser, norm };
});
