#!/usr/bin/env python3
"""Free CPU probe 3: what does density clustering (HDBSCAN) of static embeddings add? W7+W8 dev items, topics from Sonnet. Run with embed-zs venv."""
import json, os, pathlib, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from collections import Counter
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_mutual_info_score
from sklearn.preprocessing import normalize
from model2vec import StaticModel
W = pathlib.Path(__file__).resolve().parent / "runs" / "waves"
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
rows = []
for n in (7, 8):
    items = {r["id"]: r["text"] for r in J(W / f"w{n}_items.jsonl")}
    S = {r["item_id"]: r["label"] for r in J(W / f"w{n}/sonnet/labels.jsonl")}
    rows += [(items[i], S[i]["topic"]) for i in items if i in S]
X = normalize(StaticModel.from_pretrained("minishlab/potion-base-8M").encode([t for t, _ in rows])); y = [t for _, t in rows]
for mcs in (8, 15):
    t0 = time.time(); lab = HDBSCAN(min_cluster_size=mcs, metric="euclidean").fit_predict(X); dt = time.time() - t0
    k = lab >= 0; cl = sorted(set(lab[k]))
    pur = sum(Counter(np.array(y)[lab == c]).most_common(1)[0][1] for c in cl) / max(k.sum(), 1)
    print(f"min_cluster_size {mcs}: {len(cl)} clusters, {k.mean():.0%} of items in a cluster, {(~k).mean():.0%} outliers; cluster purity vs Sonnet topic {pur:.2f}; AMI {adjusted_mutual_info_score(np.array(y)[k], lab[k]):.2f}; {dt:.1f}s for {len(y)} items")
    if mcs == 8:
        big = sorted(cl, key=lambda c: -(lab == c).sum())[:6]
        for c in big:
            idx = np.where(lab == c)[0]; top = Counter(np.array(y)[idx]).most_common(2)
            print(f"   cluster {c}: {len(idx)} items, topics {top[0][0]} {top[0][1]/len(idx):.0%}" + (f", {top[1][0]} {top[1][1]/len(idx):.0%}" if len(top) > 1 else "") + f' | e.g. "{rows[idx[0]][0][:70]}"')
        oth = np.array(y) == "other"; print(f"   Sonnet 'other' items that are outliers: {(~k)[oth].mean():.0%} (vs {(~k).mean():.0%} outliers overall)")
