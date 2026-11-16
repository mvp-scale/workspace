"""T184 (B2): selective answering coverage for the Function student with v6b, bge-small, e5-small embeddings (alone and concatenated), vs Jev labels, grouped CV by story, half-split thresholds (L2254 rule). Prediction in ledger L2263.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t184_combined_encoders_selective.py"""
import json, numpy as np
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E6 = load("runs/pulse/t172/t173_embeddings.npz"); EB = load("runs/pulse/t172/t176_emb_bge_small.npz"); EE = load("runs/pulse/t172/t176_emb_e5_small.npz")
p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int); grp = np.array([r["id"].split(":")[1] for r in q] + [r["id"] for r in ct])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
def ev(s, yy, lo, hi):
    yes = s > hi; no = s < lo; return float((yes | no).mean()), 1 - float(np.sum(no & (yy == 1))) / max(int((yy == 1).sum()), 1), float(np.sum(yes & (yy == 0))) / max(int((yy == 0).sum()), 1)
res = {}
for name, X in (("v6b", E6), ("bge_small", EB), ("e5_small", EE), ("v6b+bge+e5", np.hstack([E6, EB, EE]))):
    for C in (1.0,):
        oof = np.zeros(len(y))
        for a, b in GroupKFold(5).split(X, y, grp): oof[b] = LogisticRegression(C=C, max_iter=2000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
        rng = np.random.RandomState(1); R = []
        for k in range(10):
            ug = np.unique(grp); rng.shuffle(ug); ha = set(ug[: len(ug) // 2]); m = np.array([g in ha for g in grp])
            for tr, te in ((m, ~m), (~m, m)): lo, hi = fit(oof[tr], y[tr]); R.append(ev(oof[te], y[te], lo, hi))
        R = np.array(R); res[name] = {"coverage_mean": round(float(R[:, 0].mean()), 3), "coverage_min": round(float(R[:, 0].min()), 3), "eff_tpr_mean": round(float(R[:, 1].mean()), 3), "eff_fpr_mean": round(float(R[:, 2].mean()), 4), "eff_fpr_max": round(float(R[:, 2].max()), 4)}
        print(name, res[name], flush=True)
json.dump(res, open("runs/pulse/t179/t184_combined_encoders_selective.json", "w"), indent=1)
