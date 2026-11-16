"""T157 (ledger T-0034): learned combiner of the five Jev function noul on CheckThat, fit on dev_en, scored once on test_en_labeled. Saved rows only.
    /workspace/models/embed-zs/.venv/bin/python t157_function_combiner.py -> runs/pulse/t157/t157_function_combiner.json"""
import csv, json, random, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
D = "/workspace/data/anchors/checkthat_subj/"; K = ["function_report", "function_opinion", "function_prediction", "function_request", "function_decision"]
rows = {r["id"]: r for r in json.load(open("runs/pulse/t148/t148_checkthat_function.json"))["rows"] if "error" not in r}
def split(n):
    X, y = [], []
    for r in csv.DictReader(open(D + n + ".tsv", encoding="utf-8"), delimiter="\t"):
        x = rows.get("ct:" + r["sentence_id"])
        if x: X.append([x["noul"][k] for k in K]); y.append(1 if x["gold"] == "SUBJ" else 0)
    return np.array(X), np.array(y)
Xa, ya = split("dev_en"); Xt, yt = split("test_en_labeled"); m = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000).fit(Xa, ya); p = m.predict_proba(Xt)[:, 1]
def ba(y, q): return ((q[y == 1] >= 0.5).mean() + (q[y == 0] < 0.5).mean()) / 2
rng = np.random.default_rng(157); b = sorted(ba(yt[i], p[i]) for i in (rng.integers(0, len(yt), len(yt)) for _ in range(500)) if len(set(yt[i])) == 2)
single = Xt[:, 1]; res = {"n_fit": len(ya), "n_score": len(yt), "coef": dict(zip(K, [round(float(c), 3) for c in m.coef_[0]])), "bal_acc": round(float(ba(yt, p)), 3), "ci95": [round(b[12], 3), round(b[len(b) - 13], 3)], "auroc": round(float(roc_auc_score(yt, p)), 3), "single_opinion_auroc": round(float(roc_auc_score(yt, single)), 3), "single_opinion_bal_acc_at_0_5": round(float(ba(yt, single)), 3), "baseline_line_0_80_bal_acc": 0.743}
json.dump(res, open("runs/pulse/t157/t157_function_combiner.json", "w"), indent=1); print(json.dumps(res, indent=1))
