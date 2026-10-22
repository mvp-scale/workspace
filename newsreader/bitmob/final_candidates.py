"""Final readers of the night vs the round-3 ensemble (same frozen test, paired bootstrap), and vs the round-2 ensemble headline numbers (patterns.md).
  topic: e5b ep3 (Kaggle run 3) + e5tfidf r5; country: e5-base run 2 + e5tfidf r3; type: e5-base run 4 alone; conditions: e5-base run 4 + e5tfidf r5.  -> data/suite_final/final.json"""
import numpy as np, json
from sklearn.metrics import average_precision_score as ap
W = "/workspace/data/"; ld = lambda p: np.load(W + p + ".npz", allow_pickle=True); rs = np.random.RandomState(1); out = {}
def al(z, kk):
    zk = list(z["keys"]); return np.stack([z["P"][:, zk.index(x)] if x in zk else np.zeros(len(z["P"])) for x in kk], 1)
for a, mk in {"topic": lambda k, t3, t5: (k + t5) / 2, "country": lambda k, t3, t5: (k + t3) / 2, "type": lambda k, t3, t5: k, "conditions": lambda k, t3, t5: (k + t5) / 2}.items():
    src = {"topic": "suite_kaggle7/e5b_ep3_lr3e-5/topic", "country": "suite_kaggle2/e5-base-v2/country", "type": "suite_kaggle4/e5-base-v2/type", "conditions": "suite_kaggle4/e5-base-v2/conditions"}[a]
    k = ld(src); kk = list(k["keys"]); Y = k["Y"]; n = len(Y); P = mk(k["P"], al(ld(f"suite_r3/e5tfidf/{a}"), kk), al(ld(f"suite_r5/e5tfidf/{a}"), kk)); E = ld(f"suite_r3/ensemble/{a}")["P"]
    if a in ("topic", "country"): f = lambda Q, i: (Y[i].argmax(1) == Q[i].argmax(1)).mean(); B = 1500; nm = "accuracy"
    else: cols = [j for j in range(Y.shape[1]) if Y[:, j].sum() >= 3]; f = lambda Q, i: np.mean([ap(Y[i, j], Q[i, j]) for j in cols]); B = 150; nm = "mean AP"
    full = np.arange(n); d = [f(P, i) - f(E, i) for i in (rs.randint(0, n, n) for _ in range(B))]; lo, hi = np.percentile(d, [2.5, 97.5])
    out[a] = {"metric": nm, "final": round(float(f(P, full)), 4), "round3 ensemble": round(float(f(E, full)), 4), "diff [95% CI]": [round(float(f(P, full) - f(E, full)), 4), round(float(lo), 4), round(float(hi), 4)], "B": B}
json.dump(out, open(W + "suite_final/final.json", "w"), indent=1); print(json.dumps(out, indent=1))
