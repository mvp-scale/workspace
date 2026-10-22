"""Country stability check (T-0023, D-0018): the country checker vs a reviewer's named-country labels, on the dev set (pilot50, where the checker
was built) and on fresh stories (random + probes). A criterion is stable when the fresh result is within noise of dev (two-proportion, 2 SE).
  python3 newsreader/bitmob/country_val.py
"""
import json, math, collections

D = "/workspace/data/country-val/"
L = lambda f: [json.loads(l) for l in open(f)]
LOOK = [("ner", "nga"), ("sdn", "ssd"), ("cod", "cog"), ("prk", "kor"), ("gin", "png"), ("dom", "dma")]


def score(script, review, sets):
    S = {r["n"]: r for r in script}; R = {r["n"]: r for r in review}; out = collections.defaultdict(lambda: collections.Counter())
    for n, rv in R.items():
        s = set(S[n]["countries"]); r = set(rv["countries"]); g = sets.get(n, "dev")
        for grp in ("all", g):
            c = out[grp]; c["tp"] += len(s & r); c["fn"] += len(r - s); c["fp"] += len(s - r); c["stories"] += 1; c["clean"] += not (s - r)
            if rv.get("other"): c["off"] += 1; c["off_ok"] += bool(S[n]["out_of_list"]) and not (s - r)
            c["swap"] += any((a in r and b in s and b not in r) or (b in r and a in s and a not in r) for a, b in LOOK)
    res = {}
    for grp, c in out.items():
        res[grp] = {"recall": c["tp"] / max(1, c["tp"] + c["fn"]), "n_recall": c["tp"] + c["fn"], "precision": c["tp"] / max(1, c["tp"] + c["fp"]), "n_precision": c["tp"] + c["fp"],
                    "clean_share": c["clean"] / max(1, c["stories"]), "stories": c["stories"], "off_list": c["off"], "off_list_ok": c["off_ok"], "swaps": c["swap"]}
    return res


def stable(p1, n1, p2, n2):
    if not n1 or not n2: return None
    p = (p1 * n1 + p2 * n2) / (n1 + n2); se = math.sqrt(max(p * (1 - p), 1e-9) * (1 / n1 + 1 / n2)); return abs(p1 - p2) <= 2 * se


fresh = L(D + "stories.jsonl"); sets = {r["n"]: r["set"] for r in fresh}
dev = score(L("/workspace/data/jury/pilot50/country-script-v2.jsonl"), L(D + "review-dev.jsonl"), {})["all"]
fr = score(L(D + "script.jsonl"), L(D + "review-a.jsonl") + L(D + "review-b.jsonl"), sets)
rnd = fr["random"]
res = {"dev": dev, "fresh": fr,
       "C1": {"dev": dev["recall"], "fresh_random": rnd["recall"], "stable": stable(dev["recall"], dev["n_recall"], rnd["recall"], rnd["n_recall"])},
       "C2": {"dev": dev["precision"], "fresh_all": fr["all"]["precision"], "stable": stable(dev["precision"], dev["n_precision"], fr["all"]["precision"], fr["all"]["n_precision"])},
       "C4": {k: fr.get(f"probe:{k}", {}).get("recall") for k in ("demonym", "city")},
       "C5": {"swaps": fr.get("probe:lookalike", {}).get("swaps"), "stories": fr.get("probe:lookalike", {}).get("stories")},
       "C6": {"club_clean": fr.get("probe:club", {}).get("clean_share"), "ambiguous_clean": fr.get("probe:ambiguous", {}).get("clean_share")},
       "C8": {"off_list_stories": fr["all"]["off_list"], "handled": fr["all"]["off_list_ok"]}}
json.dump(res, open(D + "country-val.json", "w"), indent=1)
for k in ("C1", "C2", "C4", "C5", "C6", "C8"): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in res[k].items()})
for g, v in fr.items(): print(f"  {g:18s}", {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
