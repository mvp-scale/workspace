"""Measurement only: topic two-guess accuracy by decider outcome and by confidence threshold, heads off, on the 1,600 MN-DS articles (scoring only). Writes runs/harvest/toolchain_measure/decider_threshold.json.
    /workspace/models/embed-zs/.venv/bin/python -u decider_threshold_measure.py"""
import json, math, sys, collections
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p)]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; ids = [i for i in items if i in G]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); X = A2.Analyzer(e.S, FT, threads=8)
def wil(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
rows = []; st = collections.Counter()
for j, i in enumerate(ids):
    o = X.analyze("", items[i], None); t = o["fields"]["topic"]; tops = (t["proposed"] or "").split(" / ")
    rows.append((t["outcome"], int(1000 * t["confidence"]), any(G[i]["l1"] in M.get(x, []) for x in tops)))
    st[o["fields"]["story_type"]["outcome"]] += 1
    if j % 200 == 0: print(j, flush=True)
def stat(sel):
    n = len(sel); k = sum(r[2] for r in sel); return {"n": n, "share": round(n / len(rows), 4), "hits": k, "acc": round(k / n, 4) if n else None, "ci95": wil(k, n)}
full = stat(rows); res = {"n": len(rows), "heads": "off", "thr_in_use": 700, "full_set": full, "by_outcome": {}, "curve": {}, "story_type_outcome_share": {k: {"n": v, "share": round(v / len(rows), 4)} for k, v in st.items()}, "story_type_note": "no human label for story_type; no accuracy available"}
for oc in sorted({r[0] for r in rows}): res["by_outcome"][oc] = stat([r for r in rows if r[0] == oc])
for thr in range(300, 1000, 100):
    a = [r for r in rows if r[1] >= thr]; w = [r for r in rows if r[1] < thr]; res["curve"][str(thr)] = {"answered": stat(a), "withheld": stat(w)}
# finer sweep for the lowest threshold whose answered acc >= full-set acc
fine = {}
for thr in range(0, 1001, 10):
    a = [r for r in rows if r[1] >= thr]
    if a: fine[thr] = (len(a), sum(r[2] for r in a) / len(a))
ok = [t for t, (n, acc) in fine.items() if acc >= 0.793 and t > 0]
res["lowest_thr_answered_acc_ge_0.793"] = {"coarse_100_step": next((int(t) for t, v in res["curve"].items() if v["answered"]["acc"] and v["answered"]["acc"] >= 0.793), None), "fine_10_step": min(ok) if ok else None, "full_set_acc_used": 0.793, "full_set_acc_computed": full["acc"]}
json.dump(res, open("runs/harvest/toolchain_measure/decider_threshold.json", "w"), indent=1); print(json.dumps(res, indent=1))
