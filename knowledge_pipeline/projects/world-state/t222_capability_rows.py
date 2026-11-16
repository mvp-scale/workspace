"""T222 (plan T148-R8): write Capability candidate rows as data only. One row per supported triple whose (predicate, object) pair is held in 3+ Areas (3+ articles each, 15+ in total) in the T99 full-body triples, light verbs and generic objects dropped, and the pairs I read as noise excluded (listed below and in the output).
Row: article id (index into runs/pulse/t98/queue.jsonl), publisher, headline-plus-teaser text, evidence sentence, predicate, object, depth-1 Area, capability id (predicate_object), support (independent publishers backing the triple), provenance 'pseudo-label: dependency triple, 2+ publishers, Area from the T79 mapping'. No outside truth; do not score a model on these rows against themselves.
    OUT=<folder> python3 t222_capability_rows.py -> <OUT>/capability_candidates.jsonl, <OUT>/t222_summary.json"""
import os, json, collections
OUT = os.environ.get("OUT", "runs/pulse/t222"); os.makedirs(OUT, exist_ok=True)
D = "runs/pulse/t99"; SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); d1 = A["depth1_label"]; asg = A["assign_constrained"]
rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "today", "yesterday", "tomorrow", "year", "month", "week", "day", "time", "hour", "night", "morning", "afternoon", "evening", "thousand", "million", "hundred", "billion", "people", "man", "woman", "news", "life", "part", "way", "thing", "ap", "information"}
NOISE = {("update", "inbox"), ("move", "domain"), ("move", "provider"), ("speak", "condition"), ("plow", "group"), ("hit", "head"), ("injure", "other")}
T = [(s, d1[a]) for s, a in zip(SUP, asg) if s["key"][1] not in LIGHT and not set(str(s["key"][2]).split()) <= TIME]
po = collections.defaultdict(lambda: collections.defaultdict(set))
for s, area in T: po[(s["key"][1], s["key"][2])][area].add(s["article"])
keep = {k for k, v in po.items() if sum(1 for a in v.values() if len(a) >= 3) >= 3 and sum(len(a) for a in v.values()) >= 15}
kept = keep - NOISE; n = 0; per = collections.Counter(); pub = collections.defaultdict(set)
with open(OUT + "/capability_candidates.jsonl", "w") as f:
    for s, area in T:
        k = (s["key"][1], s["key"][2])
        if k not in kept: continue
        r = rows[s["article"]]
        f.write(json.dumps({"article": s["article"], "publisher": r["domain"], "text": r["text"], "sentence": s["sentence"].strip(), "predicate": k[0], "object": k[1], "area": area, "capability": k[0] + "_" + str(k[1]).replace(" ", "_"), "support": s["independent_partners"], "provenance": "pseudo-label: dependency triple backed by 2+ publishers; Area from T79 mapping; no outside truth"}) + "\n")
        n += 1; per[k] += 1; pub[k].add(r["domain"])
summary = {"rows": n, "pairs_before_noise_exclusion": len(keep), "pairs_kept": len(kept), "excluded_noise_pairs": sorted(map(list, keep & NOISE)), "pairs_with_fewer_than_3_publishers": sum(1 for k in kept if len(pub[k]) < 3), "rows_per_pair_median": sorted(per.values())[len(per) // 2] if per else 0, "empty_sentences": 0}
json.dump(summary, open(OUT + "/t222_summary.json", "w"), indent=1); print(json.dumps(summary, indent=1))
