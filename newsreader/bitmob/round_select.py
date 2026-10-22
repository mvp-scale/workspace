"""Round selection (D-0013): score where the current CPU reader works, then pick the next 1,000 stories (half random, half aimed at weak and rare keys).

Reader: e5-small + tfidf, logistic regression per condition key (F-0053). Held-out: night1 random 20% (seed 0), never trained on (interim test until the frozen jury set exists).
Key status: working (held-out AP >= 0.70), weak (AP < 0.70), rare (< 30 positives in training: no reliable reader). Targeted picks: weak keys by the reader's highest
probability in the pool; rare keys by nearest neighbours of their known positives (SEALS-style). Round-robin over keys, rarest first.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/round_select.py <train.jsonl,...> <pool.jsonl> <outdir> [n_random n_target]
"""
import os, sys, json, collections, random, numpy as np, torch
torch.set_num_threads(int(os.environ.get("THREADS", "4")))
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer

sets, POOL, OUT = sys.argv[1].split(","), sys.argv[2], sys.argv[3]; NR, NT = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (500, 500); NS = int(sys.argv[6]) if len(sys.argv) > 6 else 0   # NS: stories from under-represented / badly scored sources (thirds: NR random, NT targeted, NS source)
night = [json.loads(l) for l in open(sets[0])]; extra = [json.loads(l) for s in sets[1:] for l in open(s)]
idx_tr, idx_te = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)      # same split as F-0048/F-0053
train = [night[i] for i in idx_tr] + extra; test = [night[i] for i in idx_te]
import os
for f in filter(None, os.environ.get("TEST_SETS", "").split(",")): test += [json.loads(l) for l in open(f)]      # frozen test sets (e.g. testA), never trained on
pool = [json.loads(l) for l in open(POOL)]; have = {r["id"] for r in night + extra + test}; pool = [p for p in pool if p["id"] not in have]
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
enc = lambda xs: e5.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
from emb_cache import EmbCache      # embeddings cached by story id + model: later rounds encode only new stories
cache = EmbCache("e5-small-v2"); cenc = lambda rows: cache.get([r["id"] for r in rows], [r["input"] for r in rows], enc)
Etr, Ete, Ep = cenc(train), cenc(test), cenc(pool); print(f"embedding cache: {cache.hits} hits, {cache.miss} encoded", flush=True)
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit([r["input"] for r in train])
M = lambda E, X: hstack([csr_matrix(E), tf.transform(X)]).tocsr()
Xtr, Xte, Xp = M(Etr, [r["input"] for r in train]), M(Ete, [r["input"] for r in test]), M(Ep, [p["input"] for p in pool])
allkeys = sorted({k for r in night + extra for k in r["target_keys"]}); status, ranked = {}, {}
for k in allkeys:
    ytr = np.array([k in r["target_keys"] for r in train]); yte = np.array([k in r["target_keys"] for r in test]); npos = int(ytr.sum())
    if npos >= 30 and yte.sum() >= 3:
        clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Xtr, ytr)
        ap = float(average_precision_score(yte, clf.predict_proba(Xte)[:, 1])); st = "working" if ap >= 0.70 else "weak"
        if st == "weak": ranked[k] = np.argsort(-clf.predict_proba(Xp)[:, 1])
        status[k] = {"status": st, "train_pos": npos, "test_pos": int(yte.sum()), "AP": round(ap, 3), "noise_sd": round(0.44 / yte.sum() ** 0.5, 3)}      # AP SD ~ 0.44/sqrt(positives), Fable method 4.3
    else:
        pos = Etr[ytr] if npos else np.zeros((0, Etr.shape[1]))
        status[k] = {"status": "rare", "train_pos": npos, "test_pos": int(yte.sum()), "AP": None}
        if npos: ranked[k] = np.argsort(-(Ep @ pos.T).max(1))
order = sorted(ranked, key=lambda k: status[k]["train_pos"]); picked, used, cur = [], set(), {k: 0 for k in order}
while len(picked) < NT and order:
    for k in list(order):
        r = ranked[k]
        while cur[k] < len(r) and r[cur[k]] in used: cur[k] += 1
        if cur[k] >= len(r): order.remove(k); continue
        used.add(r[cur[k]]); picked.append({"id": pool[r[cur[k]]]["id"], "selection": f"target:{status[k]['status']}:{k}"})
        if len(picked) >= NT: break
# source third (round 1 design): weight each outlet by 1/sqrt(train stories + 1) x (1 + badness), badness = mean relative shortfall of the best reader's per-outlet score
# vs its overall score (data/suite/source_analysis.json, outlets with >= 60 test stories; others get 0.1); quota per outlet by largest remainder, cap CAP; random within outlet.
src_picks = []
if NS:
    sa = json.load(open(os.environ.get("SOURCE_ANALYSIS", "/workspace/data/suite/source_analysis.json"))); ntr = sa["counts"]["train"]["by_outlet"]; ov = {a: v["all"] for a, v in sa["overall"].items()}
    byo = collections.defaultdict(list)
    for i, p in enumerate(pool):
        if i not in used: byo[p["outlet"]].append(i)
    def bad(o):
        d = sa["per_outlet"].get(o)
        return 0.1 if not d else float(np.mean([max(0.0, (ov[a] - d[a]) / ov[a]) for a in ov if d.get(a) is not None] or [0.1])) * 5
    wt = {o: (1 + bad(o)) / (ntr.get(o, 0) + 1) ** 0.5 for o in byo}; CAP = int(os.environ.get("SRC_CAP", "15")); quota = {o: 0 for o in byo}
    for _ in range(NS):   # one story at a time to the outlet with the highest weight / (quota + 1), within its cap and its pool
        o = max((o for o in byo if quota[o] < min(CAP, len(byo[o]))), key=lambda o: wt[o] / (quota[o] + 1)); quota[o] += 1
    rg = random.Random(13)
    for o, q in quota.items():
        for i in rg.sample(byo[o], q): used.add(i); src_picks.append({"id": pool[i]["id"], "selection": f"source:{o}"})
picked += src_picks
rnd = [i for i in range(len(pool)) if i not in used]; random.Random(11).shuffle(rnd)
picked += [{"id": pool[i]["id"], "selection": "random"} for i in rnd[:NR]]
test_ids = {r["id"] for r in test}; assert not ({p["id"] for p in picked} & test_ids), "selection touched the frozen test set"
assert len({p["id"] for p in picked}) == len(picked), "duplicate ids in selection"
open(f"{OUT}/select.jsonl", "w").write("".join(json.dumps(p) + "\n" for p in picked))
c = collections.Counter(v["status"] for v in status.values())
summ = {"train": len(train), "test": len(test), "pool": len(pool), "keys": len(allkeys), "status_counts": c, "picked": collections.Counter(p["selection"].split(":")[0] for p in picked), "frozen_test_overlap": 0, "source_outlets": len({p["selection"] for p in picked if p["selection"].startswith("source")}),
        "mean_AP_scored": round(float(np.mean([v["AP"] for v in status.values() if v["AP"] is not None])), 3)}
json.dump({"summary": summ, "keys": status}, open(f"{OUT}/status.json", "w"), indent=1, default=int)
print(json.dumps(summ, default=int))

import subprocess  # end every run with the acceptance scorecard (scorecard.py)
subprocess.run(["python3", "/workspace/newsreader/bitmob/scorecard.py", "round_select " + " ".join(sys.argv[1:])])
