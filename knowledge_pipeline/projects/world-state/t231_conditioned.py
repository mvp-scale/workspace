"""T231 (plan T148-X1; X2 adds LEVEL=top|depth1 and a size-matched global list)
T231 (plan T148-X1): is a capability list conditioned on the Area more stable over time than a global list?
Reads the T99 supported triples and Area assignment (full bodies), article dates from runs/pulse/t98/queue.jsonl; filters as t221. Time split at 2018-01-15.
Global: (verb, object) pairs pooled over all Areas, listed with 3+ articles and 3+ distinct days in the half, top 100 by distinct days.
Conditioned: (Area, verb, object) listed per Area with 3+ articles and 3+ distinct days inside that Area and half, top 30 per Area by distinct days.
    OUT=runs/pulse/t231 python3 t231_conditioned.py -> <OUT>/t231_conditioned.json"""
import os, json, collections
OUT = os.environ.get("OUT", "runs/pulse/t231"); os.makedirs(OUT, exist_ok=True)
D = "runs/pulse/t99"; SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); LEVEL = os.environ.get("LEVEL", "depth1"); d1 = A["top_label"] if LEVEL == "top" else A["depth1_label"]; PER = int(os.environ.get("PER", 60 if LEVEL == "top" else 30)); asg = A["assign_constrained"]
rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "today", "yesterday", "tomorrow", "year", "month", "week", "day", "time", "hour", "night", "morning", "afternoon", "evening", "thousand", "million", "hundred", "billion", "people", "man", "woman", "news", "life", "part", "way", "thing", "ap", "information"}
BOILER = {("update", "inbox"), ("move", "domain"), ("move", "provider"), ("speak", "condition"), ("plow", "group"), ("hit", "head"), ("injure", "other")}
T = [(s["article"], s["key"][1], s["key"][2], d1[a]) for s, a in zip(SUP, asg) if s["key"][1] not in LIGHT and not set(str(s["key"][2]).split()) <= TIME and (s["key"][1], s["key"][2]) not in BOILER]
half = lambda t: 0 if rows[t[0]]["date"] < "2018-01-15" else 1
def listed(sel, keyf, top):
    arts = collections.defaultdict(set); days = collections.defaultdict(set)
    for t in sel: k = keyf(t); arts[k].add(t[0]); days[k].add(rows[t[0]]["date"])
    ok = {k: len(days[k]) for k in arts if len(arts[k]) >= 3 and len(days[k]) >= 3}
    return ok
jac = lambda a, b: len(a & b) / max(1, len(a | b))
res = {"triples": len(T), "boilerplate_pairs_dropped": len(BOILER)}
g = [listed([t for t in T if half(t) == h], lambda t: (t[1], t[2]), 100) for h in (0, 1)]
gt = [set(k for k, _ in sorted(x.items(), key=lambda kv: -kv[1])[:100]) for x in g]
res["global"] = {"listed": [len(g[0]), len(g[1])], "top100_jaccard": jac(gt[0], gt[1]), "shared": len(gt[0] & gt[1])}
areas = sorted({t[3] for t in T}); pooled = [set(), set()]; per = []
for ar in areas:
    sets = []
    for h in (0, 1):
        x = listed([t for t in T if half(t) == h and t[3] == ar], lambda t: (t[1], t[2]), PER)
        top = set(k for k, _ in sorted(x.items(), key=lambda kv: -kv[1])[:PER]); sets.append(top); pooled[h] |= {(ar,) + k for k in top}
    if len(sets[0]) >= 10 and len(sets[1]) >= 10: per.append({"area": ar, "listed": [len(sets[0]), len(sets[1])], "jaccard": jac(sets[0], sets[1]), "shared": len(sets[0] & sets[1])})
res["conditioned"] = {"areas_total": len(areas), "pooled_lists": [len(pooled[0]), len(pooled[1])], "pooled_jaccard": jac(pooled[0], pooled[1]), "pooled_shared": len(pooled[0] & pooled[1]), "areas_with_10plus_both_halves": len(per),
                      "mean_per_area_jaccard": sum(x["jaccard"] for x in per) / max(1, len(per)), "per_area_best": sorted(per, key=lambda x: -x["jaccard"])[:8]}
gm = [set(k for k, _ in sorted(g[h].items(), key=lambda kv: -kv[1])[:len(pooled[h])]) for h in (0, 1)]
res["global_matched"] = {"list_sizes": [len(gm[0]), len(gm[1])], "jaccard": jac(gm[0], gm[1]), "shared": len(gm[0] & gm[1])}
res["level"] = LEVEL; res["difference_conditioned_minus_global_matched"] = res["conditioned"]["pooled_jaccard"] - res["global_matched"]["jaccard"]
res["difference_conditioned_minus_global"] = res["conditioned"]["pooled_jaccard"] - res["global"]["top100_jaccard"]
json.dump(res, open(OUT + "/t231_conditioned.json", "w"), indent=1); print(json.dumps(res, indent=1))
