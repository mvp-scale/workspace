"""Free learning curve on labels we already hold: Sonnet topic (49) and story type (4) from the label store, frozen bge-small embeddings, logistic regression, test = unseen publisher domains. Agreement with the teacher, not accuracy.
    /workspace/models/embed-zs/.venv/bin/python label_curve.py -> runs/harvest/label_curve.json"""
import json, re, random, time, collections, warnings, numpy as np; warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from urllib.parse import urlparse
ids = json.load(open("runs/embeds/bge_small_ids.json")); E = np.load("runs/embeds/bge_small.npy").astype(np.float32); pos = {i: k for k, i in enumerate(ids)}
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] != "sonnet" or not r.get("topic") or r["item_id"] not in pos: continue
    rk = RANK.get(r["version"], 2)
    if r["item_id"] not in best or rk < best[r["item_id"]][0]: best[r["item_id"]] = (rk, r)
items = sorted(best); dom = lambda i: (urlparse(i.split("cc:", 1)[-1]).netloc or i.split(":")[0]) if i.startswith("cc:") else i.split(":")[0]
domains = sorted({dom(i) for i in items}); rng = random.Random(20261108); test_dom = set(rng.sample(domains, max(1, int(0.12 * len(domains)))))
test = [i for i in items if dom(i) in test_dom]; pool = [i for i in items if dom(i) not in test_dom]; print("domains", len(domains), "test items", len(test), "pool items", len(pool), flush=True)
X = lambda ii: E[[pos[i] for i in ii]]; Xt = X(test); T = {"topic": [best[i][1]["topic"] for i in test], "story": [best[i][1]["story_type"] for i in test]}
res = {"v": "label-curve-v0", "test_items": len(test), "pool_items": len(pool), "test_domains": len(test_dom), "curves": {}}
for task, key in (("topic", "topic"), ("story", "story_type")):
    yt = np.array(T[task]); always = collections.Counter(yt).most_common(1)[0]; res["curves"][task] = {"always_most_common": [always[0], round(always[1] / len(yt), 3)], "points": []}
    for n in (500, 1000, 2000, 4000, 8000, 16000, len(pool)):
        n = min(n, len(pool)); reps = 3 if n <= 8000 else (2 if n < len(pool) else 1); accs = []; top2 = []; f1s = []
        for r in range(reps):
            sub = random.Random(100 + r).sample(pool, n); y = np.array([best[i][1][key] for i in sub]); t0 = time.time()
            m = LogisticRegression(C=1.0, max_iter=300).fit(X(sub), y); P = m.predict_proba(Xt); cl = m.classes_; pred = cl[P.argmax(1)]
            accs.append(float((pred == yt).mean())); f1s.append(float(f1_score(yt, pred, average="macro"))); top2.append(float(np.mean([yt[k] in cl[np.argsort(-P[k])[:2]] for k in range(len(yt))])))
        res["curves"][task]["points"].append({"train_items": n, "subsets": reps, "top1": round(float(np.mean(accs)), 3), "top1_range": [round(min(accs), 3), round(max(accs), 3)], "top2": round(float(np.mean(top2)), 3), "macro_f1": round(float(np.mean(f1s)), 3)})
        print(task, res["curves"][task]["points"][-1], f"{time.time()-t0:.0f}s", flush=True)
json.dump(res, open("runs/harvest/label_curve.json", "w"), indent=1)
