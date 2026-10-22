"""Suite ensemble (T-0025): 50/50 mean of e5tfidf and e5ft probabilities for one area, same frozen test. Built only if both parts exist.
  THREADS=1 python3 newsreader/bitmob/ensemble_suite.py <area>   -> data/suite/ensemble/<area>.json|.npz"""
import sys, os, json, numpy as np
from sklearn.metrics import average_precision_score, f1_score
import os as _o; W = "/workspace/data/suite" + _o.environ.get("SUITE_TAG", ""); area = sys.argv[1]; os.makedirs(f"{W}/ensemble", exist_ok=True)
a, b = np.load(f"{W}/e5tfidf/{area}.npz", allow_pickle=True), np.load(f"{W}/e5ft/{area}.npz", allow_pickle=True)
assert (a["keys"] == b["keys"]).all() and (a["Y"] == b["Y"]).all() and int(a["n_night"]) == int(b["n_night"]), "parts differ in keys/labels/test"
P, Y, keys = (a["P"] + b["P"]) / 2, a["Y"].astype(bool), list(a["keys"])
res = {"model": "ensemble", "area": area, "parts": ["e5tfidf", "e5ft"], "weights": [0.5, 0.5], "test": int(len(Y)), "ms_per_story": None}
if json.load(open(f"{W}/e5ft/{area}.json"))["kind"] == "multilabel":
    ap = {k: float(average_precision_score(Y[:, i], P[:, i])) for i, k in enumerate(keys) if Y[:, i].sum() >= 3}
    res |= {"kind": "multilabel", "mean_AP": round(float(np.mean(list(ap.values()))), 4), "per_key_AP": {k: round(v, 4) for k, v in ap.items()}, "test_pos": {k: int(Y[:, i].sum()) for i, k in enumerate(keys)}}
else:
    y, pr = Y.argmax(1), P.argmax(1); res |= {"kind": "multiclass", "accuracy": round(float((y == pr).mean()), 4), "macroF1": round(float(f1_score(y, pr, average="macro")), 4)}
json.dump(res, open(f"{W}/ensemble/{area}.json", "w"), indent=1)
np.savez_compressed(f"{W}/ensemble/{area}.npz", P=P.astype(np.float32), Y=a["Y"], keys=a["keys"], n_night=a["n_night"])
print({k: v for k, v in res.items() if k in ("mean_AP", "accuracy", "per_key_AP")})
