"""First-lap step 3 scoring (Track C run on session tokens): validate the gist labels, write the sidecar label file, and measure gist-vs-full-text agreement on the 100 held-out articles.
Reads runs/harvest/trackC_prep/labels_part1..4.json and labels_heldout_full.json. Writes runs/label_store/labels_ws_gist_v1.jsonl (new file, strength weak; labels.jsonl is not touched) and runs/pulse/lap_teacher.json.
    python3 lap_teacher.py   (from projects/world-state)"""
import json, math, collections
D = "runs/harvest/trackC_prep/"; spec = json.load(open(D + "prompt_and_schema.json")); props = spec["output_schema"]["properties"]
TOP = set(props["topic"]["enum"]); STORY = set(props["story_type"]["enum"])
items = {x["id"]: x for x in json.load(open(D + "items_1000.json"))["items"]}; lab = {}; bad = []
for k in (1, 2, 3, 4):
    for i, r in json.load(open(D + f"labels_part{k}.json")).items():
        ok = i in items and r.get("topic") in TOP and r.get("story_type") in STORY and isinstance(r.get("claim"), str) and len(r["claim"].split()) <= 25 and isinstance(r.get("conditions"), list)
        (lab.__setitem__(i, r) if ok else bad.append(i))
full = json.load(open(D + "labels_heldout_full.json")); held = [h["id"] for h in json.load(open(D + "heldout_100_ids.json"))]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
both = [i for i in held if i in lab and i in full]; n = len(both)
at = sum(lab[i]["topic"] == full[i]["topic"] for i in both); asr = sum(lab[i]["story_type"] == full[i]["story_type"] for i in both)
with open("runs/label_store/labels_ws_gist_v1.jsonl", "w") as f:
    for i, r in lab.items(): f.write(json.dumps({"item_id": i, "family": "sonnet", "model": "claude-sonnet-5-5", "version": "ws-gist-v1", "run": "runs/harvest/trackC_prep", "input": "title+gist", "strength": "weak", "topic": r["topic"], "story_type": r["story_type"], "claim": r["claim"], "n_conditions": len(r["conditions"]), "conditions": r["conditions"]}) + "\n")
res = {"labels_valid": len(lab), "labels_invalid": len(bad), "invalid_ids": bad[:10], "heldout_compared": n, "topic_agree_gist_vs_full": {"rate": round(at / max(n, 1), 4), "ci95": wil(at, n) if n else None}, "story_agree_gist_vs_full": {"rate": round(asr / max(n, 1), 4), "ci95": wil(asr, n) if n else None},
       "topic_distribution_top5": collections.Counter(r["topic"] for r in lab.values()).most_common(5), "story_distribution": dict(collections.Counter(r["story_type"] for r in lab.values())), "with_condition_share": round(sum(1 for r in lab.values() if r["conditions"]) / max(len(lab), 1), 3)}
json.dump(res, open("runs/pulse/lap_teacher.json", "w"), indent=1); print(json.dumps(res))
