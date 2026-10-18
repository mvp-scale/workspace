"""Routing test (same held-out split as train.py / train2.py). BitMob (CPU) decides: (1) skip stories that move nothing; (2) shortlist the top-k of 39
conditions so Clef asks only their questions. Measured: stories skipped and Clef readings lost; share of Clef's readings inside the shortlist; the GPU
work left (share of stories read x share of condition questions asked). Bar: keep >= 85% of Clef's readings."""
import sys, os, json, numpy as np
src = open("/workspace/newsreader/bitmob/train2.py").read(); src = src[:src.index("out = {}")]
ns = {"__file__": "/workspace/newsreader/bitmob/train2.py"}; exec(compile(src, "t2", "exec"), ns)
from sklearn.linear_model import Ridge, LogisticRegression
train, test, Str, Ste, PAIRS, vectors, C = ns["train"], ns["test"], ns["Str"], ns["Ste"], ns["PAIRS"], ns["vectors"], ns["C"]
Xtr, _ = vectors(train, 1); Xte, ms = vectors(test, 1); res = {"train": len(train), "test": len(test), "cpu_ms_per_story": round(ms, 1)}
ytr, yte = (Str >= C.ATTR_MIN).any(1), (Ste >= C.ATTR_MIN).any(1); allr = int((Ste >= C.ATTR_MIN).sum())
p = LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced").fit(Xtr, ytr).predict_proba(Xte)[:, 1]
pred = Ridge(alpha=1.0).fit(Xtr, Str).predict(Xte); conds = sorted({d for d, _ in PAIRS})
cs = np.stack([np.max(pred[:, [i for i, (d, _) in enumerate(PAIRS) if d == c]], 1) for c in conds], 1)
rows = []
for t in (0.0, 0.3, 0.4, 0.45):
    keep = p >= t
    for k in (5, 8, 12, 16, 20):
        got = 0
        for i, r in enumerate(test):
            if not keep[i]: continue
            top = {conds[j] for j in np.argsort(-cs[i])[:k]}; got += sum(1 for x in r["readings"] if x["direction"] != "conflict" and x["dial"] in top)
        work = keep.mean() * k / 39; rows.append({"skip_below": t, "stories_skipped": round(1 - float(keep.mean()), 3), "shortlist": k, "kept": round(got / max(1, allr), 3), "gpu_work_left": round(float(work), 3)})
best = max([r for r in rows if r["kept"] >= .85] or rows, key=lambda r: (r["kept"] >= .85, -r["gpu_work_left"], r["kept"]))
res.update(rows=rows, best=best, PASS=best["kept"] >= .85)
for r in rows: print(r)
print("BEST:", best, "PASS" if res["PASS"] else "below the 85% bar", flush=True)
json.dump(res, open("/workspace/data/newsreader/bitmob/route_results.json", "w"), indent=1)
