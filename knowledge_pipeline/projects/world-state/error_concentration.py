"""T42 (pre-registered above): do low-confidence items hold the head's errors? MN-DS fresh 1600, topic right within two guesses.
    /workspace/models/embed-zs/.venv/bin/python error_concentration.py   (from projects/world-state)"""
import json, sys
sys.path.insert(0, "."); from expert1_runtime import ExpertS
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = []
for i, t in items.items():
    r = e.read(t)["topic_top2"]; R.append((r["confidence"], any(G[i]["l1"] in M.get(x, []) for x in r["answer"]), G[i]["l1"]))
R.sort(key=lambda x: x[0]); n = len(R); err = sum(1 for r in R if not r[1]); out = {"n": n, "errors": err}
for f in (0.05, 0.10, 0.20, 0.30, 0.50):
    k = int(f * n); out[f"captured_by_least_confident_{int(f*100)}pct"] = round(sum(1 for r in R[:k] if not r[1]) / err, 3)
lo = [r for r in R if r[0] < 0.70]; hi = [r for r in R if r[0] >= 0.70]
out["accuracy_below_700"] = round(sum(r[1] for r in lo) / len(lo), 3); out["accuracy_at_or_above_700"] = round(sum(r[1] for r in hi) / len(hi), 3); out["items_below_700"] = len(lo)
# which gold categories hold the errors
import collections; c = collections.Counter(r[2] for r in R if not r[1]); t = collections.Counter(r[2] for r in R)
out["worst_categories"] = [(k, t[k], round(1 - c[k] / t[k], 2)) for k, _ in c.most_common(6)]
json.dump(out, open("runs/pulse/error_concentration.json", "w"), indent=1); print(json.dumps(out, indent=1))
