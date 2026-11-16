"""T230 (plan T148-C4 follow-up): tag the 371 Capability pairs of t222 as 'recurring' when the same pair is listed in BOTH the older (before 2018-01-15) and the newer half at MIN_DAYS distinct publication days, else 'candidate'.
Listing rule as t229 (3+ Areas with 3+ articles each, 15+ in total, MIN_DAYS distinct days inside the half). No model. Writes runs/pulse/t230/capability_tiers.json.
    MIN_DAYS=3 python3 t230_tiers.py"""
import os, json, collections
MIN_DAYS = int(os.environ.get("MIN_DAYS", 3)); os.makedirs("runs/pulse/t230", exist_ok=True)
D = "runs/pulse/t99"; SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); d1 = A["depth1_label"]; asg = A["assign_constrained"]
rows = [json.loads(l) for l in open("runs/pulse/t98/queue.jsonl")]
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "today", "yesterday", "tomorrow", "year", "month", "week", "day", "time", "hour", "night", "morning", "afternoon", "evening", "thousand", "million", "hundred", "billion", "people", "man", "woman", "news", "life", "part", "way", "thing", "ap", "information"}
T = [(s["article"], s["key"][1], s["key"][2], d1[a]) for s, a in zip(SUP, asg) if s["key"][1] not in LIGHT and not set(str(s["key"][2]).split()) <= TIME]
def listed(sel):
    po = collections.defaultdict(lambda: collections.defaultdict(set)); dy = collections.defaultdict(set)
    for art, p, o, area in sel: po[(p, o)][area].add(art); dy[(p, o)].add(rows[art]["date"])
    return {k for k, v in po.items() if sum(1 for a in v.values() if len(a) >= 3) >= 3 and sum(len(a) for a in v.values()) >= 15 and len(dy[k]) >= MIN_DAYS}
old = listed([t for t in T if rows[t[0]]["date"] < "2018-01-15"]); new = listed([t for t in T if rows[t[0]]["date"] >= "2018-01-15"]); both = old & new
cand = {(json.loads(l)["predicate"], json.loads(l)["object"]) for l in open("runs/pulse/t222/capability_candidates.jsonl")}
out = {"min_days": MIN_DAYS, "listed_older": len(old), "listed_newer": len(new), "recurring_both_periods": len(both), "t222_pairs": len(cand), "t222_pairs_recurring": len(cand & both), "t222_pairs_candidate_only": len(cand - both),
       "recurring_pairs": sorted(["%s %s" % k for k in both]), "recurring_not_in_t222": sorted(["%s %s" % k for k in both - cand])}
json.dump(out, open("runs/pulse/t230/capability_tiers.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k not in ("recurring_pairs",)}, indent=0)); print(out["recurring_pairs"])
