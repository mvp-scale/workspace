"""Run 2 (country, conditions): e5-base fine-tuned on Kaggle, alone and blended with e5tfidf, vs the round-3 ensemble. Paired bootstrap over test stories.
  kev/.venv/bin/python newsreader/bitmob/kaggle_compare2.py [resamples_conditions=300]   (reads data/suite_kaggle2, data/suite_r3)"""
import numpy as np, json, sys, os
from sklearn.metrics import average_precision_score
sys.path.insert(0, os.path.dirname(__file__)); from progress import event
W = "/workspace/data/"; rs = np.random.RandomState(0); BC = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ld = lambda p: np.load(W + p + ".npz", allow_pickle=True); out = {}
def mapk(Y, P, idx, cols): return np.mean([average_precision_score(Y[idx, i], P[idx, i]) for i in cols])
def k_stats(P, Y, nn):
    Pv, Yv, Pt, Yt = P[:nn], Y[:nn].astype(bool), P[nn:], Y[nn:].astype(bool); k6 = 0
    for i in range(P.shape[1]):
        best, th = -1, 0.5
        for t in np.unique(np.round(Pv[:, i], 3)):
            pr = Pv[:, i] >= t; f1 = 2 * (pr & Yv[:, i]).sum() / max(1, pr.sum() + Yv[:, i].sum())
            if f1 > best: best, th = f1, t
        neg = ~Yt[:, i]; k6 += ((Pt[:, i] >= th) & neg).sum() / max(1, neg.sum()) <= 0.0025
    hi = Pt >= 0.9; return int(k6), (round(float(Yt[hi].mean()), 3) if hi.any() else None), int(hi.sum())
for area in ["country", "conditions"]:
    event("kaggle:score", "scoring", f"compare {area}: bootstrap")
    ens = ld(f"suite_r3/ensemble/{area}"); tf = ld(f"suite_r3/e5tfidf/{area}"); b = ld(f"suite_kaggle2/e5-base-v2/{area}"); Y = ens["Y"]; n = len(Y); assert (b["Y"] == Y).all()
    sets = {"ensemble": ens["P"], "e5-base-v2": b["P"], "e5-base-v2+e5tfidf": (b["P"] + tf["P"]) / 2}
    if area == "country": B = 2000; f = lambda P, i: (Y[i].argmax(1) == P[i].argmax(1)).mean(); name = "acc"
    else:
        B = BC; cols = [i for i in range(Y.shape[1]) if Y[:, i].sum() >= 3]; f = lambda P, i: mapk(Y, P, i, cols); name = "mAP"
    full = np.arange(n); val = {k: f(P, full) for k, P in sets.items()}; d = {c: [] for c in ("e5-base-v2", "e5-base-v2+e5tfidf")}
    for _ in range(B):
        i = rs.randint(0, n, n); r = f(sets["ensemble"], i)
        for c in d: d[c].append(f(sets[c], i) - r)
    for k, v in val.items(): out[f"{area}|{name}|{k}"] = round(float(v), 4)
    for c in d: lo, hi = np.percentile(d[c], [2.5, 97.5]); out[f"{area}|{name}|{c} vs ensemble"] = [round(float(val[c] - val["ensemble"]), 4), round(float(lo), 4), round(float(hi), 4), f"B={B}"]
    if area == "conditions":
        for k, P in sets.items():
            ap = [average_precision_score(Y[:, i], P[:, i]) for i in cols]; out[f"conditions|K2 keys AP>=0.70|{k}"] = f"{sum(a >= .70 for a in ap)} of {len(cols)}"
            k6, k8, n8 = k_stats(P, Y, int(b["n_night"])); out[f"conditions|K6 keys<=2.5/1000|{k}"] = f"{k6} of {Y.shape[1]}"; out[f"conditions|K8 share true at p>=0.9|{k}"] = f"{k8} (n={n8})"
json.dump(out, open(W + "suite_kaggle2/compare.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
event("kaggle:score", "done", "compare run 2 finished: data/suite_kaggle2/compare.json", win=True)
