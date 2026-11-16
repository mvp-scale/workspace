"""T35 follow-up: field-level comparison of the pulse reader service and ExpertS.read direct on 1,499 devq items. Core fields (story type answer and status, topic top-2 answer and status, condition present answer and confidence) versus the fields the service adds or changes (condition_present.status, reader_status, per-kind conditions).
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t35_equality_detail.py"""
import json, sys, urllib.request, collections
sys.path.insert(0, ".")
from expert1_runtime import ExpertS
items = [json.loads(l) for l in open("runs/pulse/devq_items.jsonl")][:1499]; e = ExpertS("runs/expert1/expert1_v6b_student.pkl")
def n(x): return json.loads(json.dumps(x, sort_keys=True, default=float))
cnt = collections.Counter(); status_pairs = collections.Counter(); reasons = collections.Counter()
for it in items:
    d = n(e.read(it["text"])); req = urllib.request.Request("http://localhost:8023/v1/pulse", json.dumps({"text": it["text"]}).encode(), {"Content-Type": "application/json"}); j = n(json.load(urllib.request.urlopen(req))["result"])
    cnt["story_type_identical"] += (j["story_type"] == d["story_type"]); cnt["topic_top2_identical"] += (j["topic_top2"] == d["topic_top2"])
    cj, cd = j["condition_present"], d["condition_present"]; cnt["condition_answer_identical"] += (cj.get("answer") == cd.get("answer")); cnt["condition_confidence_identical"] += (cj.get("confidence") == cd.get("confidence"))
    cnt["condition_status_identical"] += (cj.get("status") == cd.get("status")); status_pairs[(cd.get("status"), cj.get("status"))] += 1; reasons[str(cj.get("reader_status"))[:60]] += 1
    cnt["all_other_core_identical"] += (j["story_type"] == d["story_type"] and j["topic_top2"] == d["topic_top2"] and cj.get("answer") == cd.get("answer") and cj.get("confidence") == cd.get("confidence"))
res = {"items": len(items), **dict(cnt), "condition_status_pairs_direct_vs_service": {f"{a} -> {b}": v for (a, b), v in status_pairs.items()}, "reader_status_values": dict(reasons.most_common(3))}
json.dump(res, open("runs/pulse/t35_equality_detail.json", "w"), indent=1); print(json.dumps(res))
