"""Seed the e5 cache from the suite caches (cache-e5-train/test.npy, same encoding as round_select: 'query: ' + input, normalised). Train order = night1 train + round1 + round2; test = night1 held-out + testA."""
import sys, json, numpy as np
sys.path.insert(0, "/workspace/newsreader/bitmob"); from emb_cache import EmbCache
from sklearn.model_selection import train_test_split
W = "/workspace/data"; L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr, te = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr] + L(f"{W}/trainset/round1.jsonl") + L(f"{W}/trainset/round2.jsonl"); test = [night[i] for i in te] + L(f"{W}/trainset/testA.jsonl")
c = EmbCache("e5-small-v2"); add_ids, add_E = [], []
for rows, f in ((train, "e5-train"), (test, "e5-test")):
    E = np.load(f"{W}/suite/cache-{f}.npy"); assert len(E) == len(rows)
    for r, e in zip(rows, E):
        if r["id"] not in c.idx and r["id"] not in add_ids: add_ids.append(r["id"]); add_E.append(e)
for i in add_ids: c.idx[i] = len(c.idx)
c.E = np.vstack([c.E, np.asarray(add_E, np.float32)]) if add_E else c.E; c.save(); print("seeded", len(add_ids), "total", len(c.idx))
