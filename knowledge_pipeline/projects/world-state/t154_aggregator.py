"""T154 (ledger T-0032, R4 / A13): the learned aggregator of the 39 dial answers, saved this time. Rows: T137-R, 1,000 engine stories read by hosted Jev (/workspace/data/newsreader/labels/calibration-1000.jsonl). Same folds as t136_calibrate.py (crc32 of id mod 5). Targets: Clef's stored reading present (agreement, not accuracy) and the engine 328-question read. Compared with the any-dial-at-0.7 rule; paired bootstrap of the AUROC and agreement differences.
    /workspace/models/embed-zs/.venv/bin/python t154_aggregator.py -> runs/pulse/t154/t154_aggregator.json"""
import json, zlib, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
R = [json.loads(l) for l in open("/workspace/data/newsreader/labels/calibration-1000.jsonl")]; R = [r for r in R if "error" not in r]
dials = sorted({k[5:] for r in R for k in r["answers_call1"] if k.startswith("cond_")}); X = np.array([[r["answers_call1"].get("cond_" + d, {}).get("noul", 0.0) for d in dials] for r in R])
fold = np.array([zlib.crc32(r["id"].encode()) % 5 for r in R]); ref = {"clef_stored": np.array([1 if r.get("clef_reading") else 0 for r in R]), "engine_read": np.array([1 if r["readings_p328"] else 0 for r in R])}
rule = (X >= 0.7).any(1).astype(int); rng = np.random.default_rng(154); res = {"stories": len(R), "dials": len(dials), "folds": 5, "C": 1.0}; preds = {}
for rn, y in ref.items():
    p = np.zeros(len(R))
    for f in range(5):
        tr = fold != f; te = fold == f; p[te] = LogisticRegression(C=1.0, max_iter=1000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    preds[rn] = p; agr = lambda q, i: float(((q[i] >= 0.5) == y[i]).mean()); ra = lambda i: float((rule[i] == y[i]).mean()); da = []; dc = []
    for _ in range(500):
        i = rng.integers(0, len(R), len(R))
        if len(set(y[i])) < 2: continue
        da.append(agr(p, i) - ra(i)); dc.append(roc_auc_score(y[i], p[i]) - roc_auc_score(y[i], X[i].max(1)))
    ci = lambda b: [round(float(np.percentile(b, 2.5)), 4), round(float(np.percentile(b, 97.5)), 4)]; allr = np.arange(len(R))
    res[rn] = {"auroc": round(float(roc_auc_score(y, p)), 4), "agreement_at_0_5": round(agr(p, allr), 4), "rule_any_at_0_7_agreement": round(ra(allr), 4), "max_dial_auroc": round(float(roc_auc_score(y, X.max(1))), 4),
               "agreement_diff_vs_rule": round(agr(p, allr) - ra(allr), 4), "agreement_diff_ci95": ci(da), "auroc_diff_vs_max_dial": round(float(roc_auc_score(y, p) - roc_auc_score(y, X.max(1))), 4), "auroc_diff_ci95": ci(dc), "positive_share": round(float(y.mean()), 4)}
res["note"] = "Agreement with Clef's stored reading or the engine's own read, not accuracy; no outside truth for condition presence. Bootstrap over stories."
np.savez("runs/pulse/t154/t154_predictions.npz", ids=np.array([r["id"] for r in R]), clef=preds["clef_stored"], engine=preds["engine_read"]); json.dump(res, open("runs/pulse/t154/t154_aggregator.json", "w"), indent=1); print(json.dumps(res, indent=1))
