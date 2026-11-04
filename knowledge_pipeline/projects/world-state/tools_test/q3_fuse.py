"""quantulum3 features on top of the L176 CPU model. Features by process: quantities extracted in the extract-venv (python3.14), model fit in embed-zs venv."""
import json, sys, subprocess, os, re, glob, pathlib
H0 = pathlib.Path(__file__).resolve().parent.parent; T = H0 / "tools_test"
if sys.argv[-1] == "extract":
    import math, warnings; warnings.filterwarnings("ignore")
    from quantulum3 import parser
    H = set()
    for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
        for l in open(f): H.add(json.loads(l)["item_id"])
    out = {}
    for l in open(H0 / "data/pool_train.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["id"] not in H: continue
        try: q = parser.parse(r["text"][:1500])
        except Exception: q = []
        names = [x.unit.name for x in q]
        out[r["id"]] = [len(q), sum(n == "euro" or "dollar" in n or "pound" in n or "rupee" in n or "yen" in n for n in names), sum(n == "percentage" for n in names),
                        sum(n == "dimensionless" for n in names), sum(n not in ("dimensionless", "percentage") for n in names), max([math.log10(abs(x.value) + 1) for x in q] or [0])]
    json.dump(out, open(T / "q3_feat.json", "w")); sys.exit()
import warnings, numpy as np; warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
__file__ = str(H0 / "triage.py"); sys.argv = ["x"]; src = open(H0 / "triage.py").read(); exec(src[:src.index("p = cross_val_predict")])
Q = json.load(open(T / "q3_feat.json")); M = np.array([Q[i] for i in ids], float)
cv = StratifiedKFold(5, shuffle=True, random_state=0); mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1))
a = cross_val_predict(mk(), np.hstack([F, E]), y, cv=cv, method="predict_proba")[:, 1]; b = cross_val_predict(mk(), np.hstack([F, E, M]), y, cv=cv, method="predict_proba")[:, 1]
print(json.dumps({"auc_baseline": round(roc_auc_score(y, a), 4), "auc_plus_quantulum3": round(roc_auc_score(y, b), 4)}))
