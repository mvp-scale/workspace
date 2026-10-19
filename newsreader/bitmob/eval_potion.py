"""Quick progress check for the overnight loop: potion-32M frozen + logistic on every atom, trained on all labelled stories (full text and
teasers) outside the test split, scored on full-text test stories (id hash % 5 == 0, comparable across the night) and on teaser test stories.
Cut-offs per atom from a validation slice (hash % 5 == 1). Appends one JSON line to data/mm3-train/progress.jsonl.
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/eval_potion.py"""
import json, hashlib, time, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from model2vec import StaticModel

D = "/workspace/data/mm3-train"; first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}
ev = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-evidence-v1.jsonl"))}
ids = sorted(set(first) & set(ev)); rows = [first[i] for i in ids]
B = json.load(open("/workspace/newsreader/bitmob/batteries/evidence-v1.json"))
ATOMS = {c: ("first", (f"{c}|states", f"{c}|concrete")) for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up")}
ATOMS.update({c["atom"]: ("ev", (f"{c['atom']}|a", f"{c['atom']}|b")) for c in B["concerns"]})
src = lambda w, i: (first if w == "first" else ev)[i]["answers"]
Y = np.array([[all(src(w, i)[k] >= .5 for k in ks) for (w, ks) in ATOMS.values()] for i in ids])
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); teaser = np.array([r.get("depth") == "teaser" for r in rows])
fit, val = h >= 2, h == 1; test_full, test_teaser = (h == 0) & ~teaser, (h == 0) & teaser
X = StaticModel.from_pretrained("minishlab/potion-base-32M").encode([r["title"] + ". " + r["text"] for r in rows])
best_cut = lambda y, p: 0.5 if y.sum() < 2 else max(np.linspace(.05, .95, 37), key=lambda t: f1_score(y, p >= t))
out = {"ts": time.strftime("%Y-%m-%d %H:%M"), "stories": len(ids), "teasers": int(teaser.sum()), "test_full": int(test_full.sum()), "test_teaser": int(test_teaser.sum()),
       "yes_fit": {}, "f1_full": {}, "f1_teaser": {}}
for j, n in enumerate(ATOMS):
    out["yes_fit"][n] = int(Y[fit, j].sum())
    if Y[fit, j].sum() < 3: continue
    m = LogisticRegression(C=4, class_weight="balanced", max_iter=4000).fit(X[fit], Y[fit, j]); c = best_cut(Y[val, j], m.predict_proba(X[val])[:, 1])
    for name, T in (("f1_full", test_full), ("f1_teaser", test_teaser)):
        if Y[T, j].sum() >= 3: out[name][n] = round(float(f1_score(Y[T, j], m.predict_proba(X[T])[:, 1] >= c)), 3)
for name in ("f1_full", "f1_teaser"):
    v = list(out[name].values()); out[name.replace("f1", "median")] = round(float(np.median(v)), 3) if v else None
open(f"{D}/progress.jsonl", "a").write(json.dumps(out) + "\n"); print(json.dumps(out))
