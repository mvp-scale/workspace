#!/usr/bin/env python3
"""One side-by-side: Haiku, Sonnet, local Clef, a 30 MB embedding model and the short Haiku gate on the SAME 300 W7 dev items. Run with embed-zs venv."""
import json, os, pathlib, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from collections import Counter
from sklearn.linear_model import LogisticRegression
from model2vec import StaticModel
W = pathlib.Path(__file__).resolve().parent / "runs"; J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
items = {r["id"]: r["text"] for r in J(W / "waves/w7_items.jsonl")}
H = {r["item_id"]: r["label"] for r in J(W / "waves/w7/haiku/labels.jsonl")}; S = {r["item_id"]: r["label"] for r in J(W / "waves/w7/sonnet/labels.jsonl")}
Cl = json.load(open(W / "retest/clef300.json")); G = {r["item_id"]: r["label"]["change"] for r in J(W / "retest/gate_haiku/labels.jsonl")}
ids = [i for i in items if i in H and i in S and i in Cl and i in G][:300]
def load(n): 
    it = {r["id"]: r["text"] for r in J(W / f"waves/w{n}_items.jsonl")}; h = {r["item_id"]: r["label"] for r in J(W / f"waves/w{n}/haiku/labels.jsonl")}; s = {r["item_id"]: r["label"] for r in J(W / f"waves/w{n}/sonnet/labels.jsonl")}
    return [(it[i], h[i], s[i]) for i in it if i in h and i in s]
tr = [x for n in range(1, 6) for x in load(n)]; m = StaticModel.from_pretrained("minishlab/potion-base-8M")
def emb(key, extra=lambda h: h[key]):
    keep = [(t, extra(h)) for t, h, s in tr if extra(h) == extra(s)]; c = LogisticRegression(max_iter=500, C=10).fit(m.encode([t for t, _ in keep]), [l for _, l in keep]); return dict(zip(ids, c.predict(m.encode([items[i] for i in ids]))))
E_topic = emb("topic"); E_story = emb("story_type"); E_chg = emb("conditions", lambda l: bool(l["conditions"]))
ans = {"topic": {"Haiku": {i: H[i]["topic"] for i in ids}, "Sonnet": {i: S[i]["topic"] for i in ids}, "Clef": {i: Cl[i]["topic"]["choice"] for i in ids}, "Embedding": E_topic},
       "story type": {"Haiku": {i: H[i]["story_type"] for i in ids}, "Sonnet": {i: S[i]["story_type"] for i in ids}, "Clef": {i: Cl[i]["story"]["choice"] for i in ids}, "Embedding": E_story},
       "anything changing?": {"Haiku (full prompt)": {i: bool(H[i]["conditions"]) for i in ids}, "Sonnet": {i: bool(S[i]["conditions"]) for i in ids}, "Clef": {i: Cl[i]["change"]["choice"] == "yes" for i in ids}, "Haiku (short gate)": {i: G[i] for i in ids}, "Embedding": E_chg}}
print(f"{len(ids)} items, same for every tool. Cell = share of items where the row tool and the column tool give the same answer.\n")
for q, d in ans.items():
    names = list(d); base = Counter(d["Sonnet"].values()).most_common(1)[0][1] / len(ids)
    print(f"{q}   (always guessing the most common answer would match Sonnet {base:.0%})")
    print(" " * 22 + "".join(f"{n[:18]:>19}" for n in names))
    for a in names: print(f"{a:<22}" + "".join(f"{np.mean([d[a][i]==d[b][i] for i in ids]):>19.0%}" if a != b else f"{'-':>19}" for b in names))
    if q == "anything changing?":
        pos = [i for i in ids if d["Sonnet"][i]]; print(f"   of Sonnet's {len(pos)} yeses, found by: " + ", ".join(f"{n} {sum(d[n][i] for i in pos)}" for n in names if n != "Sonnet") + "   | yeses said: " + ", ".join(f"{n} {sum(d[n].values())}" for n in names))
    print()
