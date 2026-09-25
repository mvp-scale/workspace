/* Stabiliser for the voice server's transcript snapshots (docs/voice-flow-integration-plan.md, "Stabiliser").
 *
 * Input:  full snapshots {segments:[{speaker,start_time,end_time,words}], audio_s}, one per model step.
 * Output: append-only committed words {spk, w, t, st, turnId, last, seg} that never repeat, plus a tentative
 *         tail (display only). Same word shape flow.html's onWord(wd) consumes, so live and replay share code.
 *
 * A word is committed once it is stable, and only as a prefix (order is never broken):
 *   - its segment is closed (a later segment exists, or audio_s - end_time > closeGap), or
 *   - at least K (default 2, measured) newer words follow it in its own segment, or
 *   - flush().
 * `last` = final word of a closed segment (an utterance chunk). Measured on real speech: trailing punctuation on a
 * segment's final word can arrive hundreds of words late, so runners must use `last`, not "." , to end a chunk.
 * `turnId` changes on a speaker change, or a same-speaker segment after a pause longer than `pause` seconds.
 * A committed word that later differs in the snapshot is never re-emitted; it is counted in stats.
 *   rewrites      = the word's letters changed      punctUpdates = only trailing punctuation changed
 *   speakerFlips  = the word is now attributed to another speaker
 * `t` is the audio clock (audio_s) when committed; `st` is the word's estimated speech time inside its segment.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(); else root.VoiceSource = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const norm = (w) => w.replace(/[^\p{L}\p{N}']+/gu, "").toLowerCase();

  function createStabiliser(opts) {
    const o = Object.assign({ K: 2, closeGap: 3, pause: 2 }, opts || {});
    let committed = [], seen = [], turnId = -1, prev = null, audio = 0, tail = [], lastSnap = { segments: [] };
    const stats = { snapshots: 0, committed: 0, rewrites: 0, punctUpdates: 0, speakerFlips: 0, lagSum: 0, lagMax: 0 };

    function flatten(snap) {
      const segs = (snap.segments || []).filter((g) => g.words && g.words.trim()), seq = [];
      segs.forEach((g, si) => {
        const ws = g.words.trim().split(/\s+/), dur = Math.max(g.end_time - g.start_time, 0);
        ws.forEach((w, k) => seq.push({ spk: g.speaker, w, si, k, n: ws.length, seg: g, st: g.start_time + dur * (k / Math.max(ws.length, 1)) }));
      });
      return { seq, nseg: segs.length };
    }

    function step(snap, isFlush) {
      audio = snap.audio_s != null ? snap.audio_s : audio; lastSnap = snap; stats.snapshots++;
      const { seq, nseg } = flatten(snap), out = [];
      // audit: committed words that changed in this snapshot (counted once per distinct new value, never re-emitted)
      for (let i = 0; i < committed.length; i++) {
        const now = seq[i]; if (!now || (seen[i].w === now.w && seen[i].spk === now.spk)) continue;
        if (now.spk !== seen[i].spk) stats.speakerFlips++;
        else if (norm(now.w) === norm(seen[i].w)) stats.punctUpdates++; else stats.rewrites++;
        seen[i] = { w: now.w, spk: now.spk };
      }
      let i = committed.length;
      for (; i < seq.length; i++) {
        const x = seq[i], closed = isFlush || x.si < nseg - 1 || audio - x.seg.end_time > o.closeGap;
        if (!closed && x.n - 1 - x.k < o.K) break;
        const newTurn = !prev || prev.spk !== x.spk || (prev.si !== x.si && x.seg.start_time - prev.seg.end_time > o.pause);
        if (newTurn) turnId++;
        const wd = { spk: x.spk, w: x.w, t: audio, st: +x.st.toFixed(2), turnId, last: closed && x.k === x.n - 1, seg: x.si };
        committed.push(wd); seen.push({ w: x.w, spk: x.spk }); out.push(wd); prev = x; stats.committed++;
        const lag = audio - x.st; stats.lagSum += lag; if (lag > stats.lagMax) stats.lagMax = lag;
      }
      tail = seq.slice(i).map((x) => ({ spk: x.spk, w: x.w }));
      return out;
    }

    return {
      feed: (snap) => step(snap, false),
      flush: (snap) => step(snap || lastSnap, true),
      tail: () => tail,
      committed: () => committed,
      stats: () => Object.assign({}, stats, { lagMean: stats.committed ? stats.lagSum / stats.committed : 0 }),
      reset: () => { lastSnap = { segments: [] }; committed = []; seen = []; turnId = -1; prev = null; tail = []; },
    };
  }
  return { createStabiliser, norm };
});
