"""Blend of the Kaggle e5-base models with e5tfidf trained on r3 vs on r5 data (r3 + loop4 + loop5), paired bootstrap on the same frozen test.
  kev/.venv/bin/python newsreader/bitmob/compare_r5tfidf.py [B=500] -> data/suite_r5/compare.json"""
import numpy as np, json, sys
from sklearn.metrics import average_precision_score as ap
W = "/workspace/data/"; ld = lambda p: np.load(W + p + ".npz", allow_pickle=True); B = int(sys.argv[1]) if len(sys.argv) > 1 else 500; rs = np.random.RandomState(0); out = {}
cfg = {"topic": "suite_kaggle3/e5b_ep3_lr3e-5/topic", "country": "suite_kaggle2/e5-base-v2/country", "conditions": "suite_kaggle4/e5-base-v2/conditions", "type": "suite_kaggle4/e5-base-v2/type"}
for a, p in cfg.items():
    k = ld(p); z5 = ld(f"suite_r5/e5tfidf/{a}"); t3 = ld(f"suite_r3/e5tfidf/{a}")["P"]; kk = list(k["keys"]); zk = list(z5["keys"]); t5 = np.stack([z5["P"][:, zk.index(x)] if x in zk else np.zeros(len(z5["P"])) for x in kk], 1); miss = [str(x) for x in kk if x not in zk]; Y = k["Y"]; n = len(Y); b3 = (k["P"] + t3) / 2; b5 = (k["P"] + t5) / 2
    if a in ("topic", "country"): f = lambda P, i: (Y[i].argmax(1) == P[i].argmax(1)).mean(); nm = "acc"
    else: cols = [j for j in range(Y.shape[1]) if Y[:, j].sum() >= 3]; f = lambda P, i: np.mean([ap(Y[i, j], P[i, j]) for j in cols]); nm = "mAP"
    full = np.arange(n); v3, v5 = f(b3, full), f(b5, full); nb = B if nm == "acc" else max(100, B // 3); d = []
    for _ in range(nb if nm == "acc" else nb): i = rs.randint(0, n, n); d.append(f(b5, i) - f(b3, i))
    lo, hi = np.percentile(d, [2.5, 97.5]); out[a] = {"keys missing in r5 tfidf (zero-filled)": miss, nm + " blend with r3 tfidf": round(float(v3), 4), nm + " blend with r5 tfidf": round(float(v5), 4), "diff [95% CI]": [round(float(v5 - v3), 4), round(float(lo), 4), round(float(hi), 4)], "B": nb}
    if a == "conditions":
        c = [j for j in cols]; out[a]["K2 AP>=0.70 r3 / r5 tfidf blend"] = [int(sum(ap(Y[:, j], b3[:, j]) >= .7 for j in c)), int(sum(ap(Y[:, j], b5[:, j]) >= .7 for j in c))]
json.dump(out, open(W + "suite_r5/compare.json", "w"), indent=1); print(json.dumps(out, indent=1))
