"""T158 (ledger T-0035): Place sanity floor, Jev place_region vs the feed region tag (a proxy for where the source is). Saved rows only.
    python3 t158_place_floor.py (from projects/world-state) -> runs/pulse/t158/t158_place_floor.json"""
import json, math, collections
R = [json.loads(l) for l in open("/workspace/data/newsreader/labels/calibration-1000.jsonl")]; C = {}
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): r = json.loads(l); C[r["id"]] = r.get("region")
NA, EU, SSA, MENA, LA, EAP, SA = "North America", "Europe & Central Asia", "Sub-Saharan Africa ", "Middle East, North Africa, Afghanistan & Pakistan", "Latin America & Caribbean ", "East Asia & Pacific", "South Asia"
OK = {"North America": {NA}, "US-MA": {NA}, "Europe": {EU}, "Africa": {SSA, MENA}, "Latin America": {LA}, "Oceania": {EAP}, "Asia": {EAP, SA, MENA}}
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
per = collections.defaultdict(lambda: [0, 0, collections.Counter()]); k = n = 0
for r in R:
    g = C.get(r["id"])
    if g not in OK: continue
    ch = r["answers_call1"]["place_region"]["choice"]; hit = ch in OK[g]; n += 1; k += hit; per[g][0] += hit; per[g][1] += 1; per[g][2][ch] += 1
res = {"n": n, "in_allowed_set": k, "share": round(k / n, 3), "ci95": wil(k, n), "excluded_world_or_other": len(R) - n, "per_feed_region": {g: {"share": round(v[0] / v[1], 3), "n": v[1], "top_answers": v[2].most_common(3)} for g, v in per.items()}, "caveat": "feed region = where the source is, a proxy; a US feed covering Ukraine counts as a miss, so the share understates accuracy. This is a sanity floor, not a judge."}
json.dump(res, open("runs/pulse/t158/t158_place_floor.json", "w"), indent=1); print(json.dumps(res, indent=1))
