"""Footprint of a saved BitMob Expert 1 artefact: peak memory, load time and read speed on one CPU thread, in a fresh process.
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /workspace/models/embed-zs/.venv/bin/python footprint.py [artefact.pkl]      CPU only, no hosted calls"""
import os, sys, json, time, glob, resource, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert3, ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
path = sys.argv[1] if len(sys.argv) > 1 else "runs/expert1/expert1_v31.pkl"
rss = lambda: int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) / 1024
load0 = open("/proc/loadavg").read().split()[0]; base = rss(); t0 = time.time(); e = (ExpertS if "student" in path else Expert3)(path); load_s = time.time() - t0; after_load = rss()
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]
items = [pool[i]["text"] for i in test[:400]]; a = time.perf_counter(); e.read(items[0]); first_encoder_s = time.perf_counter() - a; e.read(items[0]); ms = []   # first encoder use pays a one-time start-up; measured apart
for t in items:
    a = time.perf_counter(); e.read(t); ms.append((time.perf_counter() - a) * 1000)
res = {"artefact": path, "file_mb": round(os.path.getsize(path) / 1e6, 1), "onnx_mb": round(os.path.getsize(e.M["student"]["onnx_path"] if "student" in e.M else e.M.get("onnx_path", "runs/embeds/bge_small.onnx")) / 1e6, 1), "load_s": round(load_s, 1), "ram_mb_before_load": round(base), "ram_mb_after_load": round(after_load), "ram_mb_peak": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
       "first_encoder_use_s": round(first_encoder_s, 1), "items": len(ms), "ms_mean": round(float(np.mean(ms)), 1), "ms_p50": round(float(np.percentile(ms, 50)), 1), "ms_p95": round(float(np.percentile(ms, 95)), 1), "ms_max": round(float(np.max(ms)), 1), "threads": 1, "loadavg_start": float(load0), "loadavg_end": float(open("/proc/loadavg").read().split()[0])}
print(json.dumps(res)); json.dump(res, open("runs/snapshots/footprint_" + os.path.basename(path).replace(".pkl", "") + ".json", "w"), indent=1)
