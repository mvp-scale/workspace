"""T182 (A3-lite): per-attribute selective answering. v6b story embedding (title + body windows, as t165) -> logistic head per attribute with at least 200 Clef positives (P>=0.5), 5-fold grouped by story, thresholds fitted on one half of the out-of-fold scores and applied to the other (L2254 rule: FP at most 0.25% of negatives, FN at most 5% of positives, defer the rest). Prediction in ledger L2258.
Run (from projects/world-state): OUT=runs/pulse/t182 /workspace/models/embed-zs/.venv/bin/python -I t182_attribute_selective.py"""
import json, os, sys, time, pathlib, numpy as np
sys.path.insert(0, ".")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t182")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0))
rows = []
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): rows.append(json.loads(l))
seen = set(); rows = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]; rows = rows[:N] if N else rows
keys = list(rows[0]["P"]); Y = np.array([[r["P"][k] >= 0.5 for k in keys] for r in rows]).astype(int); print("stories", len(rows), "attributes", len(keys), flush=True)
emb = OUT / "t182_embeddings.npy"
if emb.exists() and not N: X = np.load(emb)
else:
    from expert1_runtime import ExpertS; from article_reader import ArticleReader
    e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); A = ArticleReader(e); t0 = time.time(); X = []
    for i, r in enumerate(rows):
        X.append(np.mean([e.student((r["title"] or "") + ". " + w) for w in A.windows(r["text"])], 0))
        if i % 200 == 0: print(i, round(time.time() - t0), flush=True)
    X = np.array(X, dtype=np.float32)
    if not N: np.save(emb, X)
    else: print("smoke embed s", round(time.time() - t0)); sys.exit()
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
grp = np.array([r["id"] for r in rows]); use = [j for j in range(len(keys)) if Y[:, j].sum() >= 200]; res = {"n_stories": len(rows), "attributes_used": [], "summary": {}}
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
def ev(s, yy, lo, hi):
    yes = s > hi; no = s < lo; return float((yes | no).mean()), float(np.mean(~no[yy == 1]) if (yy == 1).any() else 1.0), float(np.mean(yes[yy == 0]) if (yy == 0).any() else 0.0)
for j in use:
    y = Y[:, j]; oof = np.zeros(len(y))
    for a, b in GroupKFold(5).split(X, y, grp): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
    rng = np.random.RandomState(1); cov, tpr, fpr = [], [], []
    for k in range(10):
        ug = np.unique(grp); rng.shuffle(ug); ha = set(ug[: len(ug) // 2]); m = np.array([g in ha for g in grp])
        for tr, te in ((m, ~m), (~m, m)):
            lo, hi = fit(oof[tr], y[tr]); c, t, f = ev(oof[te], y[te], lo, hi); cov.append(c); tpr.append(t); fpr.append(f)
    res["attributes_used"].append({"attribute": keys[j], "positives": int(y.sum()), "coverage_mean": round(float(np.mean(cov)), 3), "coverage_min": round(float(np.min(cov)), 3), "eff_tpr_mean": round(float(np.mean(tpr)), 3), "eff_fpr_mean": round(float(np.mean(fpr)), 4), "eff_fpr_max": round(float(np.max(fpr)), 4)})
c = [a["coverage_mean"] for a in res["attributes_used"]]; res["summary"] = {"n_attributes": len(c), "mean_coverage": round(float(np.mean(c)), 3), "n_above_0_4": int(sum(x > 0.4 for x in c)), "n_zero": int(sum(x < 0.02 for x in c))}
json.dump(res, open(OUT / "t182_attribute_selective.json", "w"), indent=1); print(json.dumps(res["summary"]))
