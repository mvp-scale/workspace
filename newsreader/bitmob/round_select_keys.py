"""Round 4 selection (overnight window B/C): positives mined for the FAILING qualifiers by script, never the frozen test.
Targets: K2 near-bar condition keys (air_pollution|up, prices|up, food_insecurity|up, trust_institutions|up, civil_unrest|up, energy_fuel|up) and T2 rare type labels (opinion, forecast).
Reader for ranking: e5-small embeddings (cached) + logistic per target on ALL train (training rows only); pool rows ranked by predicted probability; + random drift guard.
  THREADS=4 models/embed-zs/.venv/bin/python newsreader/bitmob/round_select_keys.py <outdir> [n_per_key n_per_type n_random]"""
import os, sys, json, collections, random, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch; torch.set_num_threads(int(os.environ.get("THREADS", "4")))
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sentence_transformers import SentenceTransformer
from emb_cache import EmbCache
OUT = sys.argv[1]; NK, NY, NR = (int(x) for x in sys.argv[2:5]) if len(sys.argv) > 4 else (90, 100, 160); W = "/workspace/data"; os.makedirs(OUT, exist_ok=True)
KEYS = ["air_pollution|up", "prices|up", "food_insecurity|up", "trust_institutions|up", "civil_unrest|up", "energy_fuel|up"]; TYPES = ["opinion", "forecast"]
L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
sets = ("round1", "round2", "loop1", "loop2", "loop3"); train = [night[i] for i in tr_i] + [r for n in sets for r in L(f"{W}/trainset/{n}.jsonl")]
test_ids = {night[i]["id"] for i in te_i} | {r["id"] for r in L(f"{W}/trainset/testA.jsonl")}
have = {r["id"] for r in night} | {r["id"] for n in sets + ("testA",) for r in L(f"{W}/trainset/{n}.jsonl")} | test_ids
for f in ("jclef",):      # J (jury set) ids are inside the frozen test; kept out as well
    if os.path.exists(f"{W}/trainset/{f}.jsonl"): have |= {r["id"] for r in L(f"{W}/trainset/{f}.jsonl")}
pool = [p for p in L(f"{W}/round1/pool.jsonl") if p["id"] not in have]
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); enc = lambda xs: e5.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
cache = EmbCache("e5-small-v2"); cenc = lambda rows: cache.get([r["id"] for r in rows], [r["input"] for r in rows], enc)
Etr, Ep = cenc(train), cenc(pool); print(f"cache: {cache.hits} hits, {cache.miss} encoded; train {len(train)}, pool {len(pool)}", flush=True)
used, picked, per_outlet, CAP, stats = set(), [], collections.Counter(), 30, {}
def mine(name, y, n):
    npos = int(y.sum()); clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Etr, y); p = clf.predict_proba(Ep)[:, 1]; got = 0
    for i in np.argsort(-p):
        if got >= n: break
        o = pool[i]["outlet"]
        if i in used or per_outlet[o] >= CAP: continue
        used.add(i); per_outlet[o] += 1; got += 1; picked.append({"id": pool[i]["id"], "selection": f"mine:{name}"})
    stats[name] = {"train_pos": npos, "picked": got, "min_p_picked": round(float(np.sort(p)[::-1][min(len(p) - 1, n)]), 3)}
for k in KEYS: mine(k, np.array([k in r["target_keys"] for r in train]), NK)
for t in TYPES: mine("type:" + t, np.array([r["P"].get(f"g|{t}", 0) >= 0.5 for r in train]), NY)
rnd = [i for i in range(len(pool)) if i not in used]; random.Random(23).shuffle(rnd); picked += [{"id": pool[i]["id"], "selection": "random"} for i in rnd[:NR]]
assert not ({p["id"] for p in picked} & test_ids), "selection touched the frozen test set"; assert len({p["id"] for p in picked}) == len(picked)
open(f"{OUT}/select.jsonl", "w").write("".join(json.dumps(p) + "\n" for p in picked))
json.dump({"train": len(train), "pool": len(pool), "n_selected": len(picked), "targets": stats, "frozen_test_overlap": 0}, open(f"{OUT}/status.json", "w"), indent=1); print(json.dumps(stats))
