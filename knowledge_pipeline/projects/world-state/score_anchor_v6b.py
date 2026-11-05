"""T28: score the CPU engine (ExpertS) on the MN-DS anchor items through the topic mapping. Pre-registered at ledger L749.
    /workspace/models/embed-zs/.venv/bin/python score_anchor_v6b.py [items gold out]   (run from projects/world-state; defaults = the dev sample)"""
import json, math, time, sys
sys.path.insert(0, "."); from expert1_runtime import ExpertS
ITEMS = sys.argv[1] if len(sys.argv) > 1 else "/workspace/data/anchors/mn_ds/items_T28.jsonl"; GOLD = sys.argv[2] if len(sys.argv) > 2 else "/workspace/data/anchors/mn_ds/gold_T28_clean.json"; OUT = sys.argv[3] if len(sys.argv) > 3 else "runs/pulse/anchor_mnds_v6b-student.json"
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open(GOLD))
items = {}
for l in open(ITEMS):
    x = json.loads(l); items[x["id"]] = x["text"]
ids = [i for i in items if i in G]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); out = {}; ms = []
for i in ids:
    t0 = time.perf_counter(); r = e.read(items[i]); ms.append((time.perf_counter() - t0) * 1000); out[i] = r["topic_top2"]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(ids); ans = [i for i in ids if out[i]["answer"]]
top1 = lambda i: out[i]["answer"][0]
l1 = sum(1 for i in ids if out[i]["answer"] and G[i]["l1"] in M.get(top1(i), []))
s1 = sum(1 for i in ids if out[i]["answer"] and M.get(top1(i)) and G[i]["l1"] == M[top1(i)][0])
l2 = sum(1 for i in ids if out[i]["answer"] and any(G[i]["l1"] in M.get(t, []) for t in out[i]["answer"]))
unk = sum(1 for i in ids if out[i]["status"] == "unknown")
ls_ans = sum(1 for i in ans if out[i]["status"] == "answered" and G[i]["l1"] in M.get(top1(i), []))
n_ans = sum(1 for i in ans if out[i]["status"] == "answered")
res = {"engine": "v6b-student", "n": n, "top1_lenient": l1, "top1_lenient_rate": round(l1 / n, 3), "top1_lenient_ci95": wil(l1, n), "top1_strict_rate": round(s1 / n, 3), "top2_lenient": l2, "top2_lenient_rate": round(l2 / n, 3), "top2_lenient_ci95": wil(l2, n), "unknown_share": round(unk / n, 3), "answered_only_top1_lenient": [ls_ans, n_ans, round(ls_ans / max(n_ans, 1), 3)], "ms_p50": round(sorted(ms)[len(ms) // 2], 1), "ms_p95": round(sorted(ms)[int(len(ms) * .95)], 1)}
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res))
