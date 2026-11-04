import json, glob, time, sys, numpy as np, pathlib
sys.path.insert(0, "."); from expert1_runtime import Expert
from threadpoolctl import threadpool_limits
H0 = pathlib.Path("."); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
e = Expert("runs/expert1/expert1_v2.pkl"); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]
R = {i: e.read(pool[i]["text"]) for i in vt}; ans = [(i, r) for i, r in R.items() if "condition" in r]
prec = np.mean([r["condition"]["answer"][0] in {c["condition"] for c in sn[i]["conditions"]} for i, r in ans])
bad = [i for i, r in R.items() if "condition" in r and r["condition_present"]["status"] != "answered"]
with threadpool_limits(limits=1):
    ts = []
    for i in test[:400]: t0 = time.perf_counter(); e.read(pool[i]["text"]); ts.append((time.perf_counter() - t0) * 1000)
res = {"items": len(vt), "answered_with_condition": len(ans), "top1_precision": round(float(prec), 3), "condition_shown_while_presence_unknown": len(bad), "p50_ms": round(float(np.percentile(ts, 50)), 2), "p95_ms": round(float(np.percentile(ts, 95)), 2)}
json.dump(res, open("runs/expert1/runtime_check.json", "w"), indent=1); print(res)
