"""Does a bigger speaker memory keep a returning speaker's label after a long absence?
Truth: A 0.5-7.9s, then absent ~50s, returns 58.4-66.4s; B and C alternate in between."""
import sys, time, numpy as np
import mt_pipeline as mt

asr, diar = mt.load_models()
pcm = np.fromfile("longwindow.pcm", dtype=np.int16)
TRUTH = [("A", 0.5, 7.9), ("B", 8.4, 16.0), ("C", 16.5, 22.8), ("B", 23.3, 30.3), ("C", 30.8, 36.7),
         ("B", 37.2, 44.5), ("C", 45.0, 50.9), ("B", 51.4, 57.9), ("A", 58.4, 66.4)]

def label_at(segs, t0, t1):
    """Speaker label with the most overlapping time inside [t0, t1]."""
    best, tot = None, {}
    for s in segs:
        ov = min(s["end_time"], t1) - max(s["start_time"], t0)
        if ov > 0: tot[s["speaker"]] = tot.get(s["speaker"], 0) + ov
    return max(tot, key=tot.get) if tot else "-"

def run(name, fifo, spk):
    diar.sortformer_modules.spkcache_len = spk
    settings = {"fifo_len": fifo}
    try:
        sess = mt.LiveMultitalkerSession(asr, diar, settings=settings)
    except Exception as e:
        print(f"{name:34} REJECTED by NeMo: {type(e).__name__}: {str(e)[:120]}"); return
    t = time.time()
    for off in range(0, len(pcm), 4096): sess.accept_audio(pcm[off:off+4096])
    sess.accept_audio(np.zeros(20000, dtype=np.int16))
    dt = time.time() - t
    segs = sess.segments()
    got = [label_at(segs, a + 0.3, b - 0.3) for _, a, b in TRUTH]
    a_first, a_last = got[0], got[-1]
    verdict = "SAME label for A" if a_first == a_last else f"A changed: {a_first} -> {a_last}"
    print(f"{name:34} labels per turn: {' '.join(got)}   | {verdict} | {1000*dt/sess.step_num:.0f} ms/step")

print("truth turns:", " ".join(t[0] for t in TRUTH))
run("short   fifo=88  cache=88  (7s)", 88, 88)
run("default fifo=264 cache=264 (21s)", 264, 264)
run("long    fifo=528 cache=528 (42s)", 528, 528)
run("longer  fifo=1056 cache=1056 (84s)", 1056, 1056)
run("default again (repeatability)", 264, 264)
