"""T87: learning curve for the presence head. Same data, labels and sparse head as head_factory.py (label = at least one condition), trained on 12.5, 25, 50 and 100 percent of the training items, 3 subsample seeds per fraction (the 100 percent point varies only the model seed), scored on a 15 percent dev slice at threshold 0.5, and on the sealed set once (full data, seed 1). Writes runs/pulse/t87/t87_curve.json; does not touch the registered head files. Prediction at the ledger T87.
    /workspace/models/embed-zs/.venv/bin/python -u t87_curve.py   (from projects/world-state)"""
import json, glob, math, pickle, random, sys, time
import numpy as np
from admit_mirror import stamp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = {"kind": "presence", "label_field": "conditions", "class_weight": "balanced"}
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    v = r.get(spec["label_field"]) if spec["kind"] == "single" else (r.get("n_conditions") or 0) > 0
    if spec["kind"] == "single" and not v: continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, v)
ids = sorted(best); random.Random(20261109).shuffle(ids); nd = int(0.15 * len(ids)); dv = sorted(ids[:nd]); tr_all = sorted(ids[nd:]); y_all = np.array([best[i][1] for i in tr_all]); yd = np.array([best[i][1] for i in dv]); gold = np.array([bool(S[i]["conditions"]) for i in sid]); import os; os.makedirs("runs/pulse/t87", exist_ok=True); t0 = time.time()
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = vec.fit_transform([txt[i] for i in tr_all]); Xs = vec.transform([txt[i] for i in sid]); Xd = vec.transform([txt[i] for i in dv]); out = {"dev_items": len(dv), "train_items": len(tr_all), "positives": int(y_all.sum()), "sealed_n": len(sid), "points": []}
for frac in (0.125, 0.25, 0.5, 1.0):
    f1s = []
    for seed in (1, 2, 3):
        ix = np.random.RandomState(seed).permutation(len(tr_all))[: int(frac * len(tr_all))]
        m = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=seed, class_weight="balanced").fit(A[ix], y_all[ix]); pred = m.predict_proba(Xd)[:, 1] >= 0.5
        tp = int((pred & yd).sum()); fp = int((pred & ~yd).sum()); fn = int((~pred & yd).sum()); p_ = tp / max(tp + fp, 1); r_ = tp / max(tp + fn, 1); f1s.append(round(2 * p_ * r_ / max(p_ + r_, 1e-9), 4))
        if frac == 1.0 and seed == 1:   # the one sealed read
            ps = m.predict_proba(Xs)[:, 1] >= 0.5; tp = int((ps & gold).sum()); fp = int((ps & ~gold).sum()); fn = int((~ps & gold).sum()); p2 = tp / max(tp + fp, 1); r2 = tp / max(tp + fn, 1); out["sealed_f1_full_data"] = round(2 * p2 * r2 / max(p2 + r2, 1e-9), 4)
    out["points"].append({"fraction": frac, "items": int(frac * len(tr_all)), "f1": f1s, "mean": round(float(np.mean(f1s)), 4), "spread": round(max(f1s) - min(f1s), 4)}); print(out["points"][-1], flush=True)
out["seconds"] = round(time.time() - t0, 1); json.dump(out, open("runs/pulse/t87/t87_curve.json", "w"), indent=1); print(json.dumps(out))
