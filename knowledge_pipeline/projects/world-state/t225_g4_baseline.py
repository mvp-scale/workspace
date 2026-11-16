"""T225 (plan T148 step 30, G4 alignment baseline): group the T99 supported triples by exact (subject key, predicate lemma, object key) and count articles and publishers per group.
Reads runs/pulse/t99/t76_supported_triples.json and the article index runs/pulse/t98/queue.jsonl (domain = publisher). Every triple was already kept because 2+ publishers back it somewhere (T76), so the shares are higher than for raw triples.
    python3 t225_g4_baseline.py -> runs/pulse/t225/t225_g4_baseline.json"""
import json, os, collections
os.makedirs("runs/pulse/t225", exist_ok=True)
SUP = json.load(open("runs/pulse/t99/t76_supported_triples.json")); rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
g = collections.defaultdict(lambda: {"art": set(), "pub": set()})
for s in SUP:
    k = tuple(s["key"]); g[k]["art"].add(s["article"]); g[k]["pub"].add(rows[s["article"]]["domain"])
n = len(g); share = lambda f: sum(1 for v in g.values() if f(v)) / n
res = {"triples": len(SUP), "distinct_keys": n, "keys_per_triple": n / len(SUP), "share_2plus_articles": share(lambda v: len(v["art"]) >= 2), "share_2plus_publishers": share(lambda v: len(v["pub"]) >= 2), "share_3plus_publishers": share(lambda v: len(v["pub"]) >= 3),
       "keys_3plus_publishers": sum(1 for v in g.values() if len(v["pub"]) >= 3), "max_publishers": max(len(v["pub"]) for v in g.values()),
       "top_by_publishers": [{"key": list(k), "publishers": len(v["pub"]), "articles": len(v["art"])} for k, v in sorted(g.items(), key=lambda kv: -len(kv[1]["pub"]))[:15]]}
json.dump(res, open("runs/pulse/t225/t225_g4_baseline.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "top_by_publishers"}, indent=1))
for x in res["top_by_publishers"][:10]: print(x)
