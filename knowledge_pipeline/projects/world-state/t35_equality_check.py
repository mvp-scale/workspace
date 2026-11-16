"""T35 acceptance check: pulse reader service vs ExpertS.read direct, 1,499 devq items, field-by-field equality and HTTP latency. Prediction in the ledger on T35 (D44). Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t35_equality_check.py"""
import json, sys, time, urllib.request, numpy as np
sys.path.insert(0, ".")
items = [json.loads(l) for l in open("runs/pulse/devq_items.jsonl")][:1499]
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl")
def post(t):
    req = urllib.request.Request("http://localhost:8023/v1/pulse", json.dumps({"text": t}).encode(), {"Content-Type": "application/json"}); t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r: j = json.load(r)
    return j, (time.time() - t0) * 1000
def norm(x): return json.loads(json.dumps(x, sort_keys=True, default=float))
same = 0; diffs = []; lat = []; shape = None
for k, it in enumerate(items):
    j, ms = post(it["text"]); lat.append(ms); d = e.read(it["text"])
    if shape is None: shape = list(j)[:6]
    r = j["result"]
    if norm(r) == norm(d): same += 1
    elif len(diffs) < 3: diffs.append({"id": it["id"], "service_keys": list(r)[:6] if isinstance(r, dict) else str(r)[:80]})
lat = np.array(lat); res = {"items": len(items), "identical": same, "different": len(items) - same, "latency_ms": {"median": round(float(np.median(lat)), 1), "p95": round(float(np.percentile(lat, 95)), 1), "max": round(float(lat.max()), 1)}, "response_keys": shape, "first_diffs": diffs}
json.dump(res, open("runs/pulse/t35_equality_check.json", "w"), indent=1); print(json.dumps(res))
