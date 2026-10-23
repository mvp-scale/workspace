"""Prep for the combined-reader run (F-0110): the SAME 300 fixed-seed frozen-test stories as screen_real (seed 20261022, screen_real_prep.py). BitMob (CPU, local) reads them once; the heads are
stored in the stories file so the Kaggle kernel needs no BitMob model (it only talks to Clef). Writes data/diag/combined/stories_all.jsonl (two halves of 150, 15 control stories at the end of each half), bitmob_keys.json.
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/reader/combined_prep.py"""
import os, sys, json, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, "/workspace/newsreader/bitmob/reader")
import numpy as np, combined_reader as CR
OUT = "/workspace/data/diag/combined"; os.makedirs(OUT, exist_ok=True)
R = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]; idx = np.load("/workspace/data/diag/screen_real/prep.npz")["idx"]; Rs = [R[i] for i in idx]
bm = CR.BitMob(); t = time.time(); H = bm.heads([r["state_text"] for r in Rs]); secs = time.time() - t
print(f"BitMob (round-6 + round-7 country) on {len(Rs)} stories: {secs:.1f} s CPU = {secs/len(Rs)*1000:.0f} ms/story")
rows = [{"id": r["id"], "text": r["state_text"], "day": r["day"], "heads": h} for r, h in zip(Rs, H)]
ctrl = {n for n in range(len(rows)) if n % 20 in (0, 11)}          # 30 control stories (full-battery rerun): 15 even-indexed + 15 odd-indexed, so each half holds 15
half = [[], []]
for n, x in enumerate(rows): x["ctrl"] = n in ctrl; half[n % 2].append(x)     # interleave so both halves hold 150 and 15 controls
out = []
for hh in half: out += [x for x in hh if not x["ctrl"]] + [x for x in hh if x["ctrl"]]
open(f"{OUT}/stories_all.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in out)); json.dump(bm.keys, open(f"{OUT}/bitmob_keys.json", "w"))
print("wrote", len(out), "stories;", [len(h) for h in half], "controls", sum(x["ctrl"] for x in out), "bitmob ms/story", round(secs / len(Rs) * 1000))
