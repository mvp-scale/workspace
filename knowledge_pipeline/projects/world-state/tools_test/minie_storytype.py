"""MinIE features vs story type (balanced accuracy, 5-fold). Run with embed-zs python."""
import json, os, sys, pathlib, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
H0 = pathlib.Path(__file__).resolve().parent.parent; T = H0 / "tools_test"
src = open(H0 / "triage.py").read(); sys.argv = ["x"]; __file__ = str(H0 / "triage.py")
exec(src[:src.index("p = cross_val_predict")])
from sklearn.metrics import balanced_accuracy_score, recall_score
R = json.load(open(T / "minie_feat.json")); M = np.array([R[i] for i in ids], float)[:, :8]
st = np.array([H[i]["story_type"] for i in ids]); cls = sorted(set(st))
cv = StratifiedKFold(5, shuffle=True, random_state=0)
mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, class_weight="balanced"))
out = {"classes": cls, "share": {c: round(float((st == c).mean()), 3) for c in cls}}
for name, X in {"structure+embedding": np.hstack([F, E]), "plus_minie": np.hstack([F, E, M]), "minie_only": M}.items():
    p = cross_val_predict(mk(), X, st, cv=cv); out[name] = {"balanced_acc": round(balanced_accuracy_score(st, p), 4), "recall": {c: round(float(r), 3) for c, r in zip(cls, recall_score(st, p, average=None, labels=cls))}}
json.dump(out, open(T / "minie_storytype.json", "w"), indent=1); print(json.dumps(out, indent=1))
