"""T200: fit and save the Place student (e5-small embedding of title + body start, linear head, 8 place_region options) on all 1,600 queue stories with a Jev place_region label, and save the answer line (lowest top-probability line with 0.95 out-of-fold agreement vs Jev). Same inputs as t182_selective_place.py (its cached embeddings are reused when the story count matches). Saved for the simulation bench; an experiment head, not the engine's reader.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -u t200_place_student.py -> runs/pulse/t200/place_student.pkl"""
import json, pickle, sqlite3, pathlib, numpy as np
OUT = pathlib.Path("runs/pulse/t200"); OUT.mkdir(parents=True, exist_ok=True)
L = "/workspace/data/newsreader/labels/"; ans = {}
for f in ("calibration-1000.jsonl", "t144_read.jsonl"):
    for l in open(L + f):
        r = json.loads(l); a = r.get("answers_call1", {}).get("place_region")
        if a and a.get("choice"): ans[r["id"]] = a["choice"].strip()
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); ids = []
for i in ans:
    q = db.execute("select title, body from items where id=?", (i,)).fetchone()
    if q and q[1]: ids.append(i)
X = np.load("runs/pulse/t182/t182_emb.npz")["x"]; assert len(X) == len(ids), (len(X), len(ids))
y = np.array([ans[i] for i in ids]); classes = sorted(set(y)); yi = np.array([classes.index(c) for c in y])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
P = np.zeros((len(yi), len(classes)))
for a, b in KFold(5, shuffle=True, random_state=0).split(X): P[b] = LogisticRegression(C=4.0, max_iter=3000).fit(X[a], yi[a]).predict_proba(X[b])
conf, agree = P.max(1), P.argmax(1) == yi; line = 1.01
for t in np.unique(conf)[::-1]:
    s = conf >= t
    if s.sum() >= 20 and agree[s].mean() >= 0.95: line = t
    elif s.sum() >= 20 and agree[s].mean() < 0.92: break
m = LogisticRegression(C=4.0, max_iter=3000).fit(X, yi)
pickle.dump({"model": m, "classes": classes, "line": float(line), "encoder": "e5-small-v2 ('query: ' + title. body, first 1500 chars, 128 tokens)", "trained_on": len(yi), "oof_coverage_at_line": round(float((conf >= line).mean()), 3), "oof_agree_at_line": round(float(agree[conf >= line].mean()), 3)}, open(OUT / "place_student.pkl", "wb"))
print({"line": round(float(line), 3), "coverage": round(float((conf >= line).mean()), 3), "agree": round(float(agree[conf >= line].mean()), 3), "n": len(yi), "classes": classes})
