"""T190: joint answer-when-sure coverage over the 15 Clef attributes with at least 200 positives (t182 setup). Prediction in ledger L2282.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t190_joint_coverage.py"""
import json, numpy as np
rows = []
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): rows.append(json.loads(l))
seen = set(); rows = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]; keys = list(rows[0]["P"]); Y = np.array([[r["P"][k] >= 0.5 for k in keys] for r in rows]).astype(int)
X = np.load("runs/pulse/t182/t182_embeddings.npy"); grp = np.array([r["id"] for r in rows]); use = [j for j in range(len(keys)) if Y[:, j].sum() >= 200]
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
OOF = np.zeros((len(rows), len(use)))
for c, j in enumerate(use):
    for a, b in GroupKFold(5).split(X, Y[:, j], grp): OOF[b, c] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], Y[a, j]).predict_proba(X[b])[:, 1]
rng = np.random.RandomState(1); res = {"n_stories": len(rows), "n_attributes": len(use), "repeats": []}
for k in range(10):
    ug = np.unique(grp); rng.shuffle(ug); ha = set(ug[: len(ug) // 2]); m = np.array([g in ha for g in grp])
    for tr, te in ((m, ~m), (~m, m)):
        A = np.zeros((int(te.sum()), len(use)), bool)
        for c, j in enumerate(use): lo, hi = fit(OOF[tr, c], Y[tr, j]); A[:, c] = (OOF[te, c] > hi) | (OOF[te, c] < lo)
        n = A.sum(1); res["repeats"].append({"mean_answered": float(n.mean()), "all": float((n == len(use)).mean()), "ge10": float((n >= 10).mean()), "ge5": float((n >= 5).mean()), "none": float((n == 0).mean())})
R = res["repeats"]; res["summary"] = {k: round(float(np.mean([r[k] for r in R])), 4) for k in R[0]}; res["summary"]["of"] = len(use); del res["repeats"]
json.dump(res, open("runs/pulse/t179/t190_joint_coverage.json", "w"), indent=1); print(json.dumps(res))
