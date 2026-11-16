"""T232 (plan T148-X3; X5 adds HYBRID=1: the Domain top K/2 followed by the global ranking until K unique pairs)
T232 (plan T148-X3): does a Domain-conditioned candidate list cover more of a newer article's established capability pairs than a global list of the same length?
Lists from the older half (before 2018-01-15); targets = a newer-half article's (verb, object) pairs that are established in the newer half (3+ articles, 3+ distinct days). Domain = IPTC top-level label (t79_assign top_label) of the article's most common triple assignment.
    OUT=runs/pulse/t232 python3 t232_router_coverage.py -> <OUT>/t232_router_coverage.json"""
import os, json, collections, numpy as np
OUT = os.environ.get("OUT", "runs/pulse/t232"); os.makedirs(OUT, exist_ok=True); K = int(os.environ.get("K", 60))
D = "runs/pulse/t99"; SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); top = A["top_label"]; asg = A["assign_constrained"]
rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "today", "yesterday", "tomorrow", "year", "month", "week", "day", "time", "hour", "night", "morning", "afternoon", "evening", "thousand", "million", "hundred", "billion", "people", "man", "woman", "news", "life", "part", "way", "thing", "ap", "information"}
BOILER = {("update", "inbox"), ("move", "domain"), ("move", "provider"), ("speak", "condition"), ("plow", "group"), ("hit", "head"), ("injure", "other")}
T = [(s["article"], (s["key"][1], s["key"][2]), top[a]) for s, a in zip(SUP, asg) if s["key"][1] not in LIGHT and not set(str(s["key"][2]).split()) <= TIME and (s["key"][1], s["key"][2]) not in BOILER]
half = lambda art: 0 if rows[art]["date"] < "2018-01-15" else 1
def established(sel):
    arts = collections.defaultdict(set); days = collections.defaultdict(set)
    for art, k, _ in sel: arts[k].add(art); days[k].add(rows[art]["date"])
    return {k: len(days[k]) for k in arts if len(arts[k]) >= 3 and len(days[k]) >= 3}
old = [t for t in T if half(t[0]) == 0]; new = [t for t in T if half(t[0]) == 1]
gl = [k for k, _ in sorted(established(old).items(), key=lambda kv: -kv[1])]; glob = set(gl[:K]); HY = os.environ.get("HYBRID") == "1"
dom = {}
for d in {t[2] for t in old}:
    e = established([t for t in old if t[2] == d]); dl = [k for k, _ in sorted(e.items(), key=lambda kv: -kv[1])]
    if HY:
        L = list(dl[:K // 2])
        for k in gl:
            if len(L) >= K: break
            if k not in L: L.append(k)
        dom[d] = set(L)
    else: dom[d] = set(dl[:K])
est_new = established(new)
perart = collections.defaultdict(list); dcount = collections.defaultdict(collections.Counter)
for art, k, d in new: perart[art].append(k); dcount[art][d] += 1
hit_g = []; hit_d = []; n_t = []
for art, ks in perart.items():
    targets = {k for k in ks if k in est_new}
    if not targets: continue
    d = dcount[art].most_common(1)[0][0]; L = dom.get(d, set())
    hit_g.append(len(targets & glob)); hit_d.append(len(targets & L)); n_t.append(len(targets))
hg, hd, nt = map(np.array, (hit_g, hit_d, n_t)); rng = np.random.default_rng(2); idx = np.arange(len(nt)); ratios = []
for _ in range(1000):
    s = rng.choice(idx, len(idx)); ratios.append(hd[s].sum() / max(1, hg[s].sum()))
res = {"hybrid": HY, "k": K, "older_triples": len(old), "newer_triples": len(new), "articles_with_targets": len(nt), "targets": int(nt.sum()), "domains_with_lists": len(dom),
       "global": {"list": len(glob), "recall": float(hg.sum() / nt.sum())}, "domain_conditioned": {"recall": float(hd.sum() / nt.sum())}, "ratio_domain_over_global": float(hd.sum() / max(1, hg.sum())), "ratio_ci95": [float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))]}
json.dump(res, open(OUT + "/t232_router_coverage.json", "w"), indent=1); print(json.dumps(res, indent=1))
