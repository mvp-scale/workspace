"""Compare two-step (normal Clef) records with the normal-mode records of the same stories. python two_step_compare.py TWO.jsonl OUT.json [WALL_SECONDS]"""
import json, sys, statistics as st
W = "/workspace/data/clef-labels/"; N = {json.loads(l)["id"]: json.loads(l) for l in open(W + "test.jsonl")}
T = [json.loads(l) for l in open(sys.argv[1])]; ks = lambda r: {f"{x['dial']}|{x['direction']}" for x in r["read"]["readings"] if x["direction"] != "conflict"}
tp = fp = fn = same = gate = ptag = cty = 0; reqs = []
for t in T:
    n = N[t["id"]]; a, b = ks(t), ks(n); tp += len(a & b); fp += len(a - b); fn += len(b - a); same += a == b; gate += t["read"]["gate_ok"] == n["read"]["gate_ok"]
    ta = {x["id"] for x in t["place"] if x["tagged"]}; tb = {x["id"] for x in n["place"] if x["tagged"]}; ptag += ta == tb; cty += t["country"] == n["country"]; reqs.append(t["requests_ask"])
p, r = tp / max(tp + fp, 1), tp / max(tp + fn, 1); f1 = 2 * p * r / max(p + r, 1e-9); wall = float(sys.argv[3]) if len(sys.argv) > 3 else None
res = {"n": len(T), "readings": {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "F1": round(f1, 4)}, "identical_reading_set": round(same / len(T), 4), "gate_agreement": round(gate / len(T), 4),
       "place_tags_identical_set": round(ptag / len(T), 4), "country_agreement": round(cty / len(T), 4), "attribute_requests_per_story_two_step": round(st.mean(reqs), 2), "attribute_requests_per_story_full_battery": 17 + 0,
       "stories_per_min": round(len(T) / wall * 60, 1) if wall else None, "median_secs_per_story_per_worker": round(st.median(t["secs"] for t in T), 2), "normal_mode_median_secs_per_story_per_worker": round(st.median(n["secs"] for n in N.values()), 2),
       "bars": {"readings_F1>=0.95": f1 >= .95, "gate>=0.97": gate / len(T) >= .97, "speed>=28/min": (len(T) / wall * 60 >= 28) if wall else None}, "threshold": T[0]["threshold"]}
json.dump(res, open(sys.argv[2], "w"), indent=1); print(json.dumps(res, indent=1))
