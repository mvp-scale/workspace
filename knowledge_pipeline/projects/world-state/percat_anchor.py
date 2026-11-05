"""T28: per-category lenient accuracy on the fresh MN-DS sample for v6b-student (top-1 and top-2) and Clef (top-1). Run: /workspace/models/embed-zs/.venv/bin/python percat_anchor.py (from projects/world-state)"""
import json, sys, collections
sys.path.insert(0, "."); from expert1_runtime import ExpertS
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}
cl = {}
for l in open("runs/xtest/B9/runs/clef_A_s0/results.jsonl"):
    x = json.loads(l)
    if x["field"] == "topic" and x["ok"]: cl[x["item"]] = x["label"]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); P = collections.defaultdict(lambda: collections.Counter())
for i, t in items.items():
    c = G[i]["l1"]; a = e.read(t)["topic_top2"]["answer"]; P[c]["n"] += 1
    P[c]["v6b_top1"] += c in M.get(a[0], []); P[c]["v6b_top2"] += any(c in M.get(x, []) for x in a)
    if i in cl: P[c]["clef_n"] += 1; P[c]["clef_top1"] += c in M.get(cl[i], [])
out = {c: {"n": v["n"], "v6b_top1": round(v["v6b_top1"] / v["n"], 2), "v6b_top2": round(v["v6b_top2"] / v["n"], 2), "clef_top1": round(v["clef_top1"] / max(v["clef_n"], 1), 2)} for c, v in sorted(P.items())}
json.dump(out, open("runs/pulse/anchor_mnds_fresh_percategory.json", "w"), indent=1)
for c, v in sorted(out.items(), key=lambda kv: kv[1]["v6b_top2"]): print(f"{v['v6b_top2']:.2f} top2 | {v['v6b_top1']:.2f} top1 | clef {v['clef_top1']:.2f} | n {v['n']} | {c}")
