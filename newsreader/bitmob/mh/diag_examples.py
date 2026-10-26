"""User hypothesis (2026-10-23): the training examples show no condition/direction/intent; the labels are consequences the story text does not state. Pull real examples for MM3 to judge:
12 strongest Clef triggers (attribute mean >= 0.85) that the round-6 reader MISSES at the tune-chosen cut, and 12 it CATCHES; fixed seed, test stories only. Also: how consistent are Clef's two wordings on triggers.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/mh/diag_examples.py"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; OUT = "/workspace/data/diag/lever"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A]); trig = lambda Y: Y >= C.ATTR_MIN
YS = np.stack([ck(r["P"]) for r in T]); YT = Z["cond"][keep]
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
neg = np.sort(HT[~trig(YT)])[::-1]; c = neg[max(int(0.0005 * len(neg)), 1) - 1]
w0 = np.array([[r["P"][f"a|{d}|{dr}|{i}|0"] for d, dr, i in A] for r in T]); w1 = np.array([[r["P"][f"a|{d}|{dr}|{i}|1"] for d, dr, i in A] for r in T]); tr = trig(YS)
print(f"wording consistency on {tr.sum()} trigger cells: both wordings >= 0.5 in {((w0 >= .5) & (w1 >= .5) & tr).sum()/tr.sum():.1%}; mean |w0 - w1| = {np.abs(w0 - w1)[tr].mean():.3f}")
rng = np.random.default_rng(7)
def pick(mask, n=12): idx = np.argwhere(mask); sel = idx[rng.permutation(len(idx))[:n]]; return [(int(a), int(b)) for a, b in sel]
for name, mask in (("missed", tr & (YS >= 0.85) & (HS < c)), ("caught", tr & (YS >= 0.85) & (HS >= c))):
    ex = pick(mask); out = [f"# {name.upper()} examples: strong Clef triggers (attribute mean >= 0.85) that the small reader {'did NOT flag' if name == 'missed' else 'DID flag'}. Each: the story, the question Clef answered, Clef's value.\n"]
    for n, (s, j) in enumerate(ex, 1):
        d, dr, i = A[j]; q = C.QS[f"a|{d}|{dr}|{i}|0"]; out.append(f"## Example {n}\nStory: {' '.join(T[s]['state_text'].split())[:600]}\nQuestion Clef answered ({d}, {dr}): {' '.join(str(q).split())[:400]}\nClef value {YS[s, j]:.2f}\n")
    open(f"{OUT}/ex_{name}.md", "w").write("\n".join(out)); print(name, len(ex), "examples from", int(mask.sum()), "candidates")
