"""T38: exact-step and within-one size agreement of v6b-student with Sonnet on DEVQ and DEVQ2 (natural, held out), on items where the engine found and named a condition Sonnet also lists, with majority-level baselines.
    /workspace/models/embed-zs/.venv/bin/python size_exact.py   (from projects/world-state)"""
import json, math, sys, collections, numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]
TX = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}
for r in J("runs/pulse/more/devq2_items.jsonl"): TX[r["id"]] = r["text"]
SN = {}
for f in ("runs/pulse/devq/labels.jsonl", "runs/pulse/more/devq2/labels.jsonl"):
    for r in J(f): SN[r["item_id"]] = r["label"]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); rows = []
for i, L in SN.items():
    if i not in TX or not L.get("conditions"): continue
    r = e.read(TX[i]); c = r.get("condition_present", {}); cq = r.get("condition")
    if not (c.get("status") == "answered" and c.get("answer") and cq and cq.get("status") == "answered"): continue
    names = {x["condition"]: x for x in L["conditions"]}
    if cq["answer"][0] not in names or "size" not in cq: continue
    x = names[cq["answer"][0]]; rows.append((LV.index(x["level"]), LV.index(cq["size"]), cq.get("direction") == x["direction"], x["direction"]))
n = len(rows); gold = np.array([g for g, p, d, dd in rows]); pred = np.array([p for g, p, d, dd in rows])
def wil(k, m, z=1.96):
    q = k / m; d = 1 + z * z / m; c = (q + z * z / (2 * m)) / d; h = z * math.sqrt(q * (1 - q) / m + z * z / (4 * m * m)) / d; return [round(c - h, 3), round(c + h, 3)]
maj = int(collections.Counter(gold).most_common(1)[0][0])
ex = int((gold == pred).sum()); w1 = int((abs(gold - pred) <= 1).sum()); bex = int((gold == maj).sum()); bw1 = int((abs(gold - maj) <= 1).sum())
res = {"n": n, "gold_level_counts": {LV[k]: int(v) for k, v in sorted(collections.Counter(gold).items())}, "majority_level": LV[maj], "exact": [ex, n, round(ex / n, 3), wil(ex, n)], "within_one": [w1, n, round(w1 / n, 3), wil(w1, n)], "baseline_exact_majority": [bex, n, round(bex / n, 3), wil(bex, n)], "baseline_within_one_majority": [bw1, n, round(bw1 / n, 3), wil(bw1, n)]}
res["informative_exact"] = bool(wil(ex, n)[0] >= round(bex / n, 3) + 0.10); res["informative_within_one"] = bool(wil(w1, n)[0] >= round(bw1 / n, 3) + 0.10)
dg = [d for g, p, d, dd in rows]; dn = collections.Counter(dd for g, p, d, dd in rows); res["direction"] = {"agree": [int(sum(dg)), n, round(sum(dg) / n, 3), wil(int(sum(dg)), n)], "baseline_majority": [int(max(dn.values())), n, round(max(dn.values()) / n, 3)]}
json.dump(res, open("runs/pulse/size_exact.json", "w"), indent=1); print(json.dumps(res))
