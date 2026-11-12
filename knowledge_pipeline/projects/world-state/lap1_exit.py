"""First-lap exit check: the whole analyze2 chain, sparse heads off and on, on the 1,600 fresh MN-DS articles, topic two guesses against the human labels (specs/topic_to_iptc_v1.json), as in score_anchor_v6b.py. MN-DS is used for scoring only.
Each article goes in as the title-less text in items_T28b.jsonl (headline plus the start of the article, as in Round 1). Writes runs/pulse/lap1_exit.json.
    /workspace/models/embed-zs/.venv/bin/python lap1_exit.py   (from projects/world-state)"""
import json, math, sys, time, statistics
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p)]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; ids = [i for i in items if i in G]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json"))
X0 = A2.Analyzer(e.S, FT, threads=8); X1 = A2.Analyzer(e.S, FT, threads=8, sparse="runs/expert1/sparse_heads_v1.pkl")
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
def run(X):
    hit = 0; ms = []; sk = 0; ans = 0
    for i in ids:
        o = X.analyze("", items[i], None); ms.append(o["ms"]["total_ms"]); sk += o["evidence"]["encoder_skipped"]
        t = o["fields"]["topic"]; tops = (t["proposed"] or "").split(" / "); ans += t["answer"] is not None
        hit += any(G[i]["l1"] in M.get(x, []) for x in tops)
    n = len(ids); return {"top2": round(hit / n, 4), "ci95": wil(hit, n), "median_ms": round(statistics.median(ms), 1), "encoder_skipped_share": round(sk / n, 3), "decider_answered_share": round(ans / n, 3)}
res = {"n": len(ids), "judge": "MN-DS human labels (fresh 1,600), scoring only", "heads_off": run(X0), "heads_on": run(X1)}
json.dump(res, open("runs/pulse/lap1_exit.json", "w"), indent=1); print(json.dumps(res))
