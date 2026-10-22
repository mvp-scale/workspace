"""Round 3 selection (D-0029): ~2/3 stories aimed at TOPIC confusions + ~1/3 random.
Confusions come from 5-fold cross-validation on TRAIN only (e5 embeddings + logistic regression); the frozen test set is never read for labels or scores
(only its ids, to keep them out of the pool). Pool stories whose top-2 predicted topics are a confused pair are ranked by margin (p1 - p2, smallest first).
  THREADS=4 models/embed-zs/.venv/bin/python newsreader/bitmob/round_select_topic.py <outdir> [n_topic n_random]"""
import os, sys, json, collections, random, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch; torch.set_num_threads(int(os.environ.get("THREADS", "4")))
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sentence_transformers import SentenceTransformer
from emb_cache import EmbCache
OUT = sys.argv[1]; NT, NR = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (667, 333); W = "/workspace/data"; os.makedirs(OUT, exist_ok=True)
L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + [r for n in ("round1", "round2", "loop1", "loop2") for r in L(f"{W}/trainset/{n}.jsonl")]
test_ids = {night[i]["id"] for i in te_i} | {r["id"] for r in L(f"{W}/trainset/testA.jsonl")}
have = {r["id"] for r in night} | {r["id"] for n in ("round1", "round2", "loop1", "loop2", "testA") for r in L(f"{W}/trainset/{n}.jsonl")} | test_ids
pool = [p for p in L(f"{W}/round1/pool.jsonl") if p["id"] not in have]
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); enc = lambda xs: e5.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
cache = EmbCache("e5-small-v2"); cenc = lambda rows: cache.get([r["id"] for r in rows], [r["input"] for r in rows], enc)
Etr, Ep = cenc(train), cenc(pool); print(f"cache: {cache.hits} hits, {cache.miss} encoded; train {len(train)}, pool {len(pool)}", flush=True)
topics = sorted({r["topic"] for r in train}); ti = {t: i for i, t in enumerate(topics)}; y = np.array([ti[r["topic"]] for r in train])
cnt = collections.Counter(y); strat = np.array([c if cnt[c] >= 5 else -1 for c in y])      # folds need >= 5 per class
cvp = np.zeros(len(train), int)
for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(Etr, strat):
    cvp[b] = LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced").fit(Etr[a], y[a]).predict(Etr[b])
conf = collections.Counter()
for t, p in zip(y, cvp):
    if t != p: conf[tuple(sorted((topics[t], topics[p])))] += 1
pairs = [(k, v) for k, v in conf.most_common(15) if v >= 5]; tot = sum(v for _, v in pairs)
clf = LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced").fit(Etr, y); Pp = clf.predict_proba(Ep); top2 = np.argsort(-Pp, 1)[:, :2]
margin = Pp[np.arange(len(Pp)), top2[:, 0]] - Pp[np.arange(len(Pp)), top2[:, 1]]
pair_of = [tuple(sorted((topics[clf.classes_[a]], topics[clf.classes_[b]]))) for a, b in top2]
used, picked, per_outlet = set(), [], collections.Counter(); CAP = 40
for (pr, v) in pairs:
    quota = max(1, round(NT * v / tot)); cand = sorted((i for i in range(len(pool)) if pair_of[i] == pr and i not in used), key=lambda i: margin[i]); got = 0
    for i in cand:
        if got >= quota: break
        o = pool[i]["outlet"]
        if per_outlet[o] >= CAP: continue
        used.add(i); per_outlet[o] += 1; got += 1; picked.append({"id": pool[i]["id"], "selection": f"topic:{pr[0]}|{pr[1]}"})
rest = sorted((i for i in range(len(pool)) if i not in used), key=lambda i: margin[i])      # fill any shortfall with the smallest margins
for i in rest:
    if len(picked) >= NT: break
    o = pool[i]["outlet"]
    if per_outlet[o] >= CAP: continue
    used.add(i); per_outlet[o] += 1; picked.append({"id": pool[i]["id"], "selection": "topic:margin"})
rnd = [i for i in range(len(pool)) if i not in used]; random.Random(17).shuffle(rnd); picked += [{"id": pool[i]["id"], "selection": "random"} for i in rnd[:NR]]
assert not ({p["id"] for p in picked} & test_ids), "selection touched the frozen test set"; assert len({p["id"] for p in picked}) == len(picked)
open(f"{OUT}/select.jsonl", "w").write("".join(json.dumps(p) + "\n" for p in picked))
summ = {"train": len(train), "pool": len(pool), "cv_accuracy_train": round(float((cvp == y).mean()), 4), "picked": dict(collections.Counter(p["selection"].split(":")[0] for p in picked)),
        "pairs": [{"pair": list(k), "cv_confusions": v} for k, v in pairs], "outlets": len({pool[i]["outlet"] for i in used}), "frozen_test_overlap": 0}
json.dump(summ, open(f"{OUT}/status.json", "w"), indent=1); print(json.dumps(summ)[:900])
