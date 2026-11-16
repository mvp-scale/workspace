"""T182: selective answering for a Place student (8 place_region options) vs the Jev label. e5-small embedding of title + start of body, linear head, out-of-fold probabilities; the answer-line is fitted on one random half (lowest top-probability line with agreement >= 0.95 against Jev), evaluated on the other half, 5 random splits both directions. Also agreement with the text-derived place judge (t167) on the answered decidable stories. Prediction in the card T148-C.
Run (from projects/world-state): OUT=runs/pulse/t182 /workspace/models/embed-zs/.venv/bin/python -u t182_selective_place.py"""
import json, os, sqlite3, pathlib, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t182")); OUT.mkdir(parents=True, exist_ok=True)
L = "/workspace/data/newsreader/labels/"; ans = {}
for f in ("calibration-1000.jsonl", "t144_read.jsonl"):
    for l in open(L + f):
        r = json.loads(l); a = r.get("answers_call1", {}).get("place_region")
        if a and a.get("choice"): ans[r["id"]] = a["choice"].strip()
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); ids, texts = [], []
for i in ans:
    q = db.execute("select title, body from items where id=?", (i,)).fetchone()
    if q and q[1]: ids.append(i); texts.append(((q[0] or "") + ". " + q[1])[:1500])
if os.environ.get("SMALL"): ids, texts = ids[:200], texts[:200]
f = OUT / "t182_emb.npz"
if f.exists() and not os.environ.get("SMALL"): X = np.load(f)["x"]
else:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); m.max_seq_length = 128
    X = m.encode(["query: " + t for t in texts], batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    if not os.environ.get("SMALL"): np.savez(f, x=X)
y = np.array([ans[i] for i in ids]); classes = sorted(set(y)); yi = np.array([classes.index(c) for c in y])
judge = {r["id"]: None for r in []}
import subprocess, sys
jr = json.load(open("runs/pulse/t167/t167_place_judge.json")) if pathlib.Path("runs/pulse/t167/t167_place_judge.json").exists() else {}
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
P = np.zeros((len(yi), len(classes)))
for a, b in KFold(5, shuffle=True, random_state=0).split(X):
    lr = LogisticRegression(C=4.0, max_iter=3000).fit(X[a], yi[a]); P[np.ix_(b, [classes.index(c) for c in [classes[k] for k in lr.classes_]])] = lr.predict_proba(X[b])
conf = P.max(1); pred = P.argmax(1); agree = (pred == yi)
def fit(c, ag, target=0.95):
    best = 1.01
    for t in np.unique(c)[::-1]:
        sel = c >= t
        if sel.sum() >= 20 and ag[sel].mean() >= target: best = t
        elif sel.sum() >= 20 and ag[sel].mean() < target - 0.03: break
    return best
def ev(c, ag, t): s = c >= t; return {"coverage": round(float(s.mean()), 3), "agree": round(float(ag[s].mean()), 3) if s.any() else None}
res = {"n": len(yi), "classes": classes, "overall_agree_with_jev": round(float(agree.mean()), 3), "majority_share": round(float(np.bincount(yi).max() / len(yi)), 3), "splits": []}
rng = np.random.RandomState(1)
for k in range(5):
    idx = rng.permutation(len(yi)); a, b = idx[: len(yi) // 2], idx[len(yi) // 2:]
    for tr, te in ((a, b), (b, a)): res["splits"].append(ev(conf[te], agree[te], fit(conf[tr], agree[tr])))
cov = [s["coverage"] for s in res["splits"]]; ag = [s["agree"] for s in res["splits"] if s["agree"] is not None]
res["mean_coverage"] = round(float(np.mean(cov)), 3); res["worst_agree"] = round(float(min(ag)), 3) if ag else None; res["mean_agree"] = round(float(np.mean(ag)), 3) if ag else None
json.dump(res, open(OUT / "t182_selective_place.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "splits"}))
