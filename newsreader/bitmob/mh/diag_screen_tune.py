"""Screen-then-check, shortlist cut-off refit on Clef-labelled TUNE rows only (894), applied unchanged to the frozen test (F-0110).
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_screen_tune.py"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict
TUNE = "/workspace/data/kaggle/mh_r6c1/tune"
R = [json.loads(l) for l in open("data/clef-labels/test.jsonl")]
model, tok, K = load("data/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
assert not ({r["id"] for r in R} & set(json.load(open(f"{TUNE}/keys.json"))["ids"]))
HU = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); YU = Z["cond"][keep]
H = np.asarray(predict(model, tok, [r["state_text"] for r in R])["cond"])
A = [k.split("|") for k in K["cond"]]
Y = np.array([[(r["P"][f"a|{d}|{dr}|{i}|0"] + r["P"][f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A] for r in R])
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def read_with(n, vals):
    P = dict(R[n]["P"])
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(vals[j])
    return keys(C.read(P))
yc = YU >= C.ATTR_MIN; print("tune rows", len(keep), "trigger cells", yc.sum())
for rec in (0.90, 0.95, 0.98):
    s = np.sort(HU[yc])[::-1]; thr = s[int(rec * len(s)) - 1]
    flag = H >= thr; per = flag.sum(1); tr = Y >= C.ATTR_MIN
    tp = fp = pos = neg = 0
    for n in range(len(R)):
        b = keys(R[n]["read"]); m = read_with(n, np.where(flag[n], Y[n], H[n])); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    print(f"tune-fit {rec:.0%}: cut {thr:.4f}; test shortlist catches {(flag&tr).sum()/tr.sum():.1%} of Clef triggers; {per.mean():.1f} answers/story (median {np.median(per):.0f}) -> Clef asks ~{2*per.mean():.0f}/318 ({2*per.mean()/318:.1%}); conditions caught {tp/pos:.1%}, false alarms {fp/neg:.4%} ({fp}), {'PASS' if tp/pos>=.9 and fp/neg<=.001 else 'fail'}")
