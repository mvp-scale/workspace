"""T189 (A1'): answer-when-sure for Condition presence from the label store and the cached e5-small embeddings (L2279 prediction). Random half-split thresholds, 10 repeats, per teacher family. Teacher-vs-teacher agreement as a noise floor.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t189_condition_selective.py"""
import json, numpy as np, collections
M = np.load("/workspace/data/emb_cache/e5-small-v2.npy"); IX = json.load(open("/workspace/data/emb_cache/e5-small-v2.json"))
rows = collections.defaultdict(dict)
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    try: n = int(r.get("n_conditions"))
    except Exception: continue
    if r["item_id"] in IX: rows[r["family"]][r["item_id"]] = int(n > 0)
print({f: len(d) for f, d in rows.items()}, flush=True)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
res = {"families": {}, "teacher_agreement": {}}
for fam, d in rows.items():
    if len(d) < 5000: continue
    ids = list(d); X = M[[IX[i] for i in ids]]; y = np.array([d[i] for i in ids]); oof = np.zeros(len(y))
    for a, b in KFold(5, shuffle=True, random_state=0).split(X): oof[b] = LogisticRegression(C=1.0, max_iter=2000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
    rng = np.random.RandomState(1); R = []
    for k in range(10):
        idx = rng.permutation(len(y)); a, b = idx[: len(y) // 2], idx[len(y) // 2:]
        for tr, te in ((a, b), (b, a)):
            lo, hi = fit(oof[tr], y[tr]); yes = oof[te] > hi; no = oof[te] < lo; yy = y[te]
            R.append(((yes | no).mean(), 1 - np.sum(no & (yy == 1)) / max((yy == 1).sum(), 1), np.sum(yes & (yy == 0)) / max((yy == 0).sum(), 1)))
    R = np.array(R); res["families"][fam] = {"items": int(len(y)), "positive_share": round(float(y.mean()), 3), "coverage_mean": round(float(R[:, 0].mean()), 3), "coverage_min": round(float(R[:, 0].min()), 3), "eff_tpr_mean": round(float(R[:, 1].mean()), 3), "eff_fpr_mean": round(float(R[:, 2].mean()), 4), "eff_fpr_max": round(float(R[:, 2].max()), 4)}
    print(fam, res["families"][fam], flush=True)
fams = [f for f in rows if len(rows[f]) >= 2000]
for i, f1 in enumerate(fams):
    for f2 in fams[i + 1:]:
        common = [k for k in rows[f1] if k in rows[f2]]
        if len(common) >= 500: a = np.array([rows[f1][k] for k in common]); b = np.array([rows[f2][k] for k in common]); res["teacher_agreement"][f"{f1} vs {f2}"] = {"common_items": len(common), "agreement": round(float((a == b).mean()), 3), "positive_share_1": round(float(a.mean()), 3), "positive_share_2": round(float(b.mean()), 3)}
json.dump(res, open("runs/pulse/t179/t189_condition_selective.json", "w"), indent=1); print(json.dumps(res["teacher_agreement"]))
