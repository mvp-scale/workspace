"""M1: score the fresh MN-DS slice ONCE with the whole analyze2 chain (sparse heads off): topic two guesses against the human category (specs/topic_to_iptc_v1.json), all articles, and the answered set at confidence thresholds 500 and 700 (the decider rule: answered when the top-two mass, in thousandths, is at or above the threshold). MN-DS is used for scoring only.
    /workspace/models/embed-zs/.venv/bin/python -u m1_score.py   (from projects/world-state)  -> runs/pulse/m1_fresh.json"""
import json, math, sys
import numpy as np
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
D = "/workspace/data/anchors/mn_ds/"; J = lambda p: [json.loads(l) for l in open(p)]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open(D + "gold_fresh.json")); items = {x["id"]: x["text"] for x in J(D + "items_fresh.jsonl")}; ids = sorted(items)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X = A2.Analyzer(e.S, json.load(open("runs/pulse/field_table.json")), threads=8)
conf = []; hit = []
for i in ids:
    t = X.analyze("", items[i], None)["fields"]["topic"]; conf.append(int(round(1000 * (t["confidence"] or 0)))); hit.append(any(G[i]["l1"] in M.get(x, []) for x in (t["proposed"] or "").split(" / ")))
conf = np.array(conf); hit = np.array(hit); n = len(ids)
def wil(k, m, z=1.96):
    if m == 0: return [None, None]
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - h, 3), round(c + h, 3)]
def at(t):
    a = conf >= t; m = int(a.sum()); k = int(hit[a].sum()); return {"thr": t, "answered_share": round(m / n, 3), "answered_acc": round(k / max(m, 1), 4), "ci95": wil(k, m)}
res = {"n": n, "judge": "MN-DS human labels, fresh slice (titles not in T28 or T28b), scoring only", "all_articles_top2": {"rate": round(float(hit.mean()), 4), "ci95": wil(int(hit.sum()), n)}, "thr_500": at(500), "thr_700": at(700), "curve": {str(t): at(t) for t in range(300, 901, 100)}}
json.dump(res, open("runs/pulse/m1_fresh.json", "w"), indent=1); print(json.dumps({k: res[k] for k in ("n", "all_articles_top2", "thr_500", "thr_700")}))
