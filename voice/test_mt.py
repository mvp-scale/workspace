"""Offline check of mt_pipeline.py against clips with known content/speaker boundaries."""
import json
import sys
import time

import numpy as np

import mt_pipeline as mt

t0 = time.time()
asr, diar = mt.load_models()
print(f"models loaded in {time.time()-t0:.1f}s", flush=True)

CLIPS = {
    "twovoice.pcm": "truth: A(male) 0.5-6.38s | B(female) 6.88-12.55s | A(male) 13.05-17.94s",
    "warmup.pcm": "truth: one voice, ~20s",
}
for name, truth in CLIPS.items():
    pcm = np.fromfile(name, dtype=np.int16)
    sess = mt.LiveMultitalkerSession(asr, diar)
    steps_t = []
    for off in range(0, len(pcm), 4096):
        t = time.time()
        n = sess.step_num
        sess.accept_audio(pcm[off : off + 4096])
        if sess.step_num != n:
            steps_t.append(time.time() - t)
    # flush the tail with silence so the last words are emitted
    sess.accept_audio(np.zeros(16000, dtype=np.int16))
    print(f"\n=== {name}  ({len(pcm)/16000:.1f}s audio)  {truth}")
    print(f"steps={sess.step_num}  hop={sess.hop_samples/16000:.2f}s  per-step compute mean={np.mean(steps_t)*1000:.0f}ms max={np.max(steps_t)*1000:.0f}ms")
    for s in sess.segments():
        print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}))
sys.stdout.flush()
