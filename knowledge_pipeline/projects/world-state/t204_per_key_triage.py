"""T204 (next_steps 11): per-key triage of the engine's 328 questions. For every key with at least 10 Clef positives (P >= 0.5) in the 2,488 stories, a logistic head on the cached v6b story embedding (t182_embeddings.npy, reduced to 256 dimensions by PCA fitted without labels), 5-fold grouped by story, answer-when-sure lines fitted on one random half of the out-of-fold scores and tested on the other (false positives at most 0.25% of negatives, misses at most 5% of positives, 10 random half-splits). Reports per-key coverage and the share of all 328 x stories questions the CPU would answer (conservative: keys with under 10 positives and keys not tested count as not answered). Prediction in card T148-G.
Run (from projects/world-state): OUT=runs/pulse/t204 /workspace/models/embed-zs/.venv/bin/python -u t204_per_key_triage.py   (N=5 for a smoke run)"""
import json, os, pathlib, time, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t204")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0)); T0 = time.time()
rows = []
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): rows.append(json.loads(l))
seen = set(); rows = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
keys = list(rows[0]["P"]); Y = np.array([[r["P"][k] >= 0.5 for k in keys] for r in rows]).astype(int); grp = np.array([r["id"] for r in rows])
X = np.load("runs/pulse/t182/t182_embeddings.npy"); assert len(X) == len(rows)
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
X = PCA(256, random_state=0).fit_transform(X - X.mean(0)).astype(np.float32); X /= X.std(0) + 1e-6
FPQ = float(os.environ.get("FPQ", 0.0025)); use = [j for j in range(len(keys)) if Y[:, j].sum() >= 10]; use = use[:N] if N else use
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
def ev(s, yy, lo, hi):
    yes = s > hi; no = s < lo; return float((yes | no).mean()), float(np.mean(~no[yy == 1]) if (yy == 1).any() else 1.0), float(np.mean(yes[yy == 0]) if (yy == 0).any() else 0.0)
ug = np.unique(grp); per = []
for n, j in enumerate(use):
    y = Y[:, j]; oof = np.zeros(len(y))
    for a, b in GroupKFold(5).split(X, y, grp): oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
    rng = np.random.RandomState(1); cov, tpr, fpr = [], [], []
    for k in range(10):
        rng.shuffle(ug); ha = set(ug[: len(ug) // 2]); m = np.array([g in ha for g in grp])
        for tr, te in ((m, ~m), (~m, m)):
            lo, hi = fit(oof[tr], y[tr], fp=FPQ); c, t, f = ev(oof[te], y[te], lo, hi); cov.append(c); tpr.append(t); fpr.append(f)
    p = int(y.sum()); per.append({"key": keys[j], "positives": p, "bucket": "30+" if p >= 30 else "10 to 29", "coverage_mean": round(float(np.mean(cov)), 3), "coverage_min": round(float(np.min(cov)), 3), "eff_tpr_mean": round(float(np.mean(tpr)), 3), "eff_fpr_mean": round(float(np.mean(fpr)), 4), "eff_fpr_max": round(float(np.max(fpr)), 4)})
    if n % 20 == 0: print(n, len(use), round(time.time() - T0), flush=True)
tot = len(keys); cons = sum(p["coverage_mean"] for p in per) / tot
def part(b): L = [p["coverage_mean"] for p in per if p["bucket"] == b]; return {"keys": len(L), "mean_coverage": round(float(np.mean(L)), 3) if L else None, "keys_above_0_5": int(sum(x > 0.5 for x in L)), "keys_near_zero": int(sum(x < 0.02 for x in L))}
res = {"stories": len(rows), "keys_total": tot, "keys_tested": len(per), "keys_under_10_positives": int(sum(Y.sum(0) < 10)), "positive_share_of_all_answers": round(float(Y.mean()), 4),
       "engine_share_answered_conservative": round(cons, 3), "bucket_30_plus": part("30+"), "bucket_10_to_29": part("10 to 29"), "seconds": round(time.time() - T0), "per_key": per}
tp = np.array([p["eff_tpr_mean"] for p in per]); fp_ = np.array([p["eff_fpr_mean"] for p in per]); cv = np.array([p["coverage_mean"] for p in per]); ok = (tp >= 0.90) & (fp_ <= 0.0025)
res["fit_fp_quota"] = FPQ; res["mean_eff_tpr"] = round(float(tp.mean()), 3); res["mean_eff_fpr"] = round(float(fp_.mean()), 4); res["tolerance_keys"] = int(ok.sum()); res["tolerance_saving"] = round(float(cv[ok].sum() / tot), 3)
json.dump(res, open(OUT / ("t204_smoke.json" if N else "t204_per_key_triage.json"), "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "per_key"}))
