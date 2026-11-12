"""Throwaway (T56): turn finetune_cpu2 chunk logs into demo/mockups/training-curve/curve.json for the curve page. Reads logs only.
    python3 mk_curve.py [pid]"""
import json, glob, re, time, os, sys
W = "/workspace/knowledge_pipeline/projects/world-state/"; pts = []; loss = []; last = None; planned = None
for f in sorted(glob.glob(W + "runs/pulse/finetune_cpu2_chunk*.log")):
    for l in open(f, errors="ignore"):
        m = re.match(r"DEV (\{.*\}) bad (\d+)", l)
        if m: d = json.loads(m.group(1)); pts.append({"epoch": d["epoch"], "step": d["step"], **d["dev"], "composite": d["composite"], "train_loss": d["train_loss"], "bad": int(m.group(2))})
        m = re.match(r"step (\d+)/(\d+) loss ([\d.]+) (\d+)s", l)
        if m: loss.append({"step": int(m.group(1)), "loss": float(m.group(3))}); last = int(m.group(1)); planned = int(m.group(2))
        m = re.search(r"planned steps (\d+)", l)
        if m: planned = int(m.group(1))
best = max(range(len(pts)), key=lambda i: pts[i]["composite"]) if pts else None
alive = bool(len(sys.argv) > 1 and os.path.exists("/proc/" + sys.argv[1]))
res = W + "runs/pulse/finetune_cpu2.json"; stop = json.load(open(res)).get("stop_reason") if os.path.exists(res) else None
json.dump({"updated": time.strftime("%H:%M:%S"), "planned_steps": planned, "steps_per_epoch": 958, "last_step": last, "points": pts, "loss": loss[-400:], "best_index": best, "running": alive, "stop_reason": stop}, open("/workspace/demo/mockups/training-curve/curve.json", "w"))
