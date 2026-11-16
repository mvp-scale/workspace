"""T181: selective answering for the Function student vs the teacher label. Thresholds fitted on one random half of the out-of-fold scores, evaluated on the other half (both directions, 5 random splits). Prediction in ledger L2254.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t181_selective_function.py"""
import json, numpy as np, pathlib
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
z = np.load("runs/pulse/t172/t173_embeddings.npz"); X = np.vstack([z["q"], z["c"]]); p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
oof = np.zeros(len(y))
for a, b in KFold(5, shuffle=True, random_state=0).split(X): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; t_hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); t_lo = pos[int(np.floor(fn * len(pos)))]; return t_lo, t_hi
def evaluate(s, yy, t_lo, t_hi):
    yes = s > t_hi; no = s < t_lo; ans = yes | no; fp = int(np.sum(yes & (yy == 0))); fnn = int(np.sum(no & (yy == 1)))
    return {"coverage": round(float(ans.mean()), 3), "eff_tpr": round(1 - fnn / max(int((yy == 1).sum()), 1), 3), "eff_fpr": round(fp / max(int((yy == 0).sum()), 1), 4), "fp": fp, "fn": fnn}
res = {"in_sample": None, "splits": []}; t_lo, t_hi = fit(oof, y); res["in_sample"] = evaluate(oof, y, t_lo, t_hi)
rng = np.random.RandomState(1)
for k in range(5):
    idx = rng.permutation(len(y)); a, b = idx[: len(y) // 2], idx[len(y) // 2:]
    for tr, te in ((a, b), (b, a)):
        lo, hi = fit(oof[tr], y[tr]); res["splits"].append(evaluate(oof[te], y[te], lo, hi))
for key in ("coverage", "eff_tpr", "eff_fpr"): res["mean_" + key] = round(float(np.mean([s[key] for s in res["splits"]])), 4); res["worst_" + key] = (round(float(min(s[key] for s in res["splits"])), 4) if key != "eff_fpr" else round(float(max(s[key] for s in res["splits"])), 4))
json.dump(res, open("runs/pulse/t179/t181_selective_function.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "splits"}))
