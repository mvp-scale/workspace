"""Does scoring chunks beat one vector for the whole story? potion-32M, every atom, the same split as eval_potion.py, full-text stories.
  mean:     one vector for title + text (today)
  mean+max: [mean vector | element-wise max over 80-word chunks]
  chunkmax: the mean-trained model applied to each chunk (title + chunk), story score = highest chunk
  blend:    average of mean and chunkmax scores
Cut-offs from the validation slice. Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/eval_pooling.py"""
import json, hashlib, time, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from model2vec import StaticModel
D = "/workspace/data/mm3-train"; first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}
ev = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-evidence-v1.jsonl"))}
ids = sorted(i for i in set(first) & set(ev) if first[i].get("depth") != "teaser"); rows = [first[i] for i in ids]
B = json.load(open("/workspace/newsreader/bitmob/batteries/evidence-v1.json"))
ATOMS = {c: ("first", (f"{c}|states", f"{c}|concrete")) for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up")}
ATOMS.update({c["atom"]: ("ev", (f"{c['atom']}|a", f"{c['atom']}|b")) for c in B["concerns"]})
src = lambda w, i: (first if w == "first" else ev)[i]["answers"]
Y = np.array([[all(src(w, i)[k] >= .5 for k in ks) for (w, ks) in ATOMS.values()] for i in ids])
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); fit, val, test = h >= 2, h == 1, h == 0
pm = StaticModel.from_pretrained("minishlab/potion-base-32M")
Xm = pm.encode([r["title"] + ". " + r["text"] for r in rows])
chunks, owner = [], []
for k, r in enumerate(rows):
    w = r["text"].split()
    for i in range(0, max(1, len(w)), 80): chunks.append(r["title"] + ". " + " ".join(w[i:i + 80])); owner.append(k)
owner = np.array(owner); t = time.perf_counter(); C = pm.encode(chunks); ms = (time.perf_counter() - t) * 1000 / len(rows)
Xmax = np.stack([C[owner == k].max(0) for k in range(len(rows))]); Xmm = np.hstack([Xm, Xmax])
print(f"{len(rows)} full-text stories, {len(chunks)} chunks ({len(chunks)/len(rows):.1f} per story), chunk encoding {ms:.1f} ms/story")
best_cut = lambda y, p: 0.5 if y.sum() < 2 else max(np.linspace(.02, .98, 49), key=lambda t: f1_score(y, p >= t))
res = {m: {} for m in ("mean", "mean+max", "chunkmax", "blend")}
for j, n in enumerate(ATOMS):
    y = Y[:, j]
    if y[fit].sum() < 3 or y[test].sum() < 3: continue
    lr = lambda: LogisticRegression(C=4, class_weight="balanced", max_iter=4000)
    m1 = lr().fit(Xm[fit], y[fit]); m2 = lr().fit(Xmm[fit], y[fit])
    pc = m1.predict_proba(C)[:, 1]; cmax = np.array([pc[owner == k].max() for k in range(len(rows))])
    S = {"mean": m1.predict_proba(Xm)[:, 1], "mean+max": m2.predict_proba(Xmm)[:, 1], "chunkmax": cmax}; S["blend"] = (S["mean"] + S["chunkmax"]) / 2
    for m, s in S.items(): res[m][n] = round(float(f1_score(y[test], s[test] >= best_cut(y[val], s[val]))), 3)
for m, r in res.items(): print(f"{m:9s} median {np.median(list(r.values())):.3f} mean {np.mean(list(r.values())):.3f}  " + json.dumps(r))
json.dump(res, open(f"{D}/results-pooling.json", "w"), indent=1)
