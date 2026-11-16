"""T229 (plan T148-C3; copy of t228 that RANKS and LISTS pairs by distinct publication days instead of article counts: a pair is listed when it holds 3+ Areas with 3+ articles each and appears on at least MIN_DAYS distinct days inside the half; ranked by distinct days).
T228 (plan T148-C2; copy of t221 with a date split at 2018-01-15 instead of a publisher split)
T221 (plan T148-R7): is the cross-Area verb-object list stable across two disjoint sets of publishers?
Reads the T99 supported triples (full article bodies, 2+ independent publishers back each) and the Area assignment; no model.
A pair (predicate, object) is listed when it holds 3+ articles in each of 3+ Areas and 15+ articles in total; light verbs and generic objects are dropped.
Compares the top TOP pairs of two publisher halves (Jaccard), the same for a random article split, and a shuffled control.
    OUT=<folder> python3 t229_days.py -> <OUT>/t229_days.json"""
import os, json, random, collections, hashlib
OUT = os.environ.get("OUT", "runs/pulse/t229"); os.makedirs(OUT, exist_ok=True); TOP = int(os.environ.get("TOP", 100))
D = "runs/pulse/t99"; SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); d1 = A["depth1_label"]; asg = A["assign_constrained"]
rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "today", "yesterday", "tomorrow", "year", "month", "week", "day", "time", "hour", "night", "morning", "afternoon", "evening", "thousand", "million", "hundred", "billion", "people", "man", "woman", "news", "life", "part", "way", "thing", "ap", "information"}
T = [(s["article"], s["key"][1], s["key"][2], d1[a]) for s, a in zip(SUP, asg) if s["key"][1] not in LIGHT and not set(str(s["key"][2]).split()) <= TIME]
MIN_DAYS = int(os.environ.get("MIN_DAYS", 8))
def top_pairs(sel):
    po = collections.defaultdict(lambda: collections.defaultdict(set)); dy = collections.defaultdict(set)
    for art, p, o, area in sel: po[(p, o)][area].add(art); dy[(p, o)].add(rows[art]["date"])
    sh = {k: len(dy[k]) for k, v in po.items() if sum(1 for a in v.values() if len(a) >= 3) >= 3 and sum(len(a) for a in v.values()) >= 15 and len(dy[k]) >= MIN_DAYS}
    return dict(sorted(sh.items(), key=lambda kv: -kv[1])[:TOP]), len(sh)
jac = lambda a, b: len(set(a) & set(b)) / max(1, len(set(a) | set(b)))
def spear(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 5: return None
    ra = {k: r for r, k in enumerate(sorted(ks, key=lambda k: a[k]))}; rb = {k: r for r, k in enumerate(sorted(ks, key=lambda k: b[k]))}; n = len(ks)
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in ks) / (n * (n * n - 1))
def pub_half(art): return 0 if rows[art]["date"] < "2018-01-15" else 1
def art_half(art, seed): return int(hashlib.md5(f"{seed}:{art}".encode()).hexdigest(), 16) % 2
res = {"triples_after_filters": len(T), "top": TOP}
h = [top_pairs([t for t in T if pub_half(t[0]) == k]) for k in (0, 1)]
res["time_halves"] = {"sizes": [sum(1 for t in T if pub_half(t[0]) == k) for k in (0, 1)], "listed_pairs": [h[0][1], h[1][1]], "jaccard_top": jac(h[0][0], h[1][0]), "spearman_shared": spear(h[0][0], h[1][0])}
hp = [top_pairs([t for t in T if int(hashlib.md5(rows[t[0]]["domain"].encode()).hexdigest(), 16) % 2 == k]) for k in (0, 1)]
res["publisher_halves_same_ranking"] = {"listed_pairs": [hp[0][1], hp[1][1]], "jaccard_top": jac(hp[0][0], hp[1][0])}
rs = []
for seed in range(20):
    r = [top_pairs([t for t in T if art_half(t[0], seed) == k]) for k in (0, 1)]; rs.append(jac(r[0][0], r[1][0]))
res["random_article_split"] = {"jaccard_mean": sum(rs) / len(rs), "jaccard_min": min(rs), "jaccard_max": max(rs)}
random.seed(2); keys = list(h[0][0]); allk = [k for k in {(t[1], t[2]) for t in T}]; cj = []
for _ in range(200): cj.append(jac(keys, random.sample(allk, len(h[1][0]))))
res["shuffled_control_jaccard_mean"] = sum(cj) / len(cj)
res["both_halves_top10"] = [list(k) for k in list(set(h[0][0]) & set(h[1][0]))[:10]]
json.dump(res, open(OUT + "/t229_days.json", "w"), indent=1); print(json.dumps(res, indent=1))
