"""T52: does picking unsure items beat random labels? Seed 5,000 Sonnet-labelled items, add 2,000 chosen (a) at random, (b) by lowest top-two margin, text-only sparse head (same recipe as head_factory.py), score on the sealed set, 3 seeds. Judge: agreement with Sonnet, not outside truth. Sealed ids never train.
    /workspace/models/embed-zs/.venv/bin/python -u active_sim.py  -> runs/pulse/active_sim.json"""
import json, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = vec.fit_transform([txt[i] for i in ids]); B = vec.transform([txt[i] for i in sid])
Y = {"story_type": np.array([best[i][1]["story_type"] for i in ids]), "topic": np.array([best[i][1]["topic"] for i in ids]), "condition_presence": np.array([(best[i][1].get("n_conditions") or 0) > 0 for i in ids])}
G = {"story_type": np.array([S[i]["story_type"] for i in sid]), "topic": np.array([S[i]["topic"] for i in sid]), "condition_presence": np.array([bool(S[i]["conditions"]) for i in sid])}
def fit(ix, h): return SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7, class_weight="balanced" if h == "condition_presence" else None).fit(A[ix], Y[h][ix])
def score(m, h):
    p = m.predict(B); g = G[h]
    if h == "condition_presence": tp = (p & g).sum(); fp = (p & ~g).sum(); fn = (~p & g).sum(); pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1); return 2 * pr * rc / max(pr + rc, 1e-9)
    return float((p == g).mean())
out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "seed_items": 5000, "added": 2000, "pool_items": len(ids), "heads": {}}
for h in Y:
    d = []; rows = []
    for s in (1, 2, 3):
        rng = np.random.default_rng(s); perm = rng.permutation(len(ids)); seed, rest = perm[:5000], perm[5000:]
        m0 = fit(seed, h); P = np.sort(m0.predict_proba(A[rest]), 1); marg = P[:, -1] - P[:, -2]
        pick = rest[np.argsort(marg)[:2000]]; rnd = rng.choice(rest, 2000, replace=False)
        a, b, c = score(m0, h), score(fit(np.concatenate([seed, rnd]), h), h), score(fit(np.concatenate([seed, pick]), h), h); rows.append({"seed": s, "seed_only": round(a, 4), "plus_random": round(b, 4), "plus_picked": round(c, 4)}); d.append(c - b)
    out["heads"][h] = {"runs": rows, "mean_gain_picked_over_random": round(float(np.mean(d)), 4), "gain_min": round(float(min(d)), 4), "gain_max": round(float(max(d)), 4), "all_three_positive": bool(min(d) > 0)}
json.dump(out, open("runs/pulse/active_sim.json", "w"), indent=1); print(json.dumps(out, indent=1))
