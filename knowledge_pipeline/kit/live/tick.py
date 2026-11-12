"""Per-tick refresh of the Training tab and the heartbeats that describe Kaggle work (monitor_pages.py calls it, so every loop tick runs it).
Mirrors the poller's Kaggle state onto the T68 heartbeat, then rebuilds training/training.json.
    python3 tick.py"""
import json, pathlib, subprocess, sys, datetime as dt
H = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(H)); import heartbeat as hb
L = pathlib.Path("/workspace/knowledge_pipeline/runs-live")
try: k = json.loads((L / "kaggle-kp-t67-ner-bakeoff.json").read_text())
except Exception: k = {}
try: t = json.loads((L / "t68-ner-installs.json").read_text())
except Exception: t = {}
if t and t.get("state") not in ("done", "idle") and k.get("state"):
    st = k["state"]; since = dt.datetime.strptime(t["started"], "%Y-%m-%dT%H:%M:%SZ"); mins = int((dt.datetime.utcnow() - since).total_seconds() // 60)
    if st == "queued": prog, last = f"Kaggle kernel queued for {mins} min, not started (the 45 min cap counts from the start)", "Waiting in Kaggle's queue; one push only, no retry."
    elif st == "running": prog, last = f"Kaggle kernel running ({mins} min since push)", "Running."
    else: prog, last = f"Kaggle kernel reports '{st}'", "Fetch the output and score against L1382."
    hb.beat("t68-ner-installs", every_s=180, state=(st if st in ("queued", "running") else st), progress=prog, last=last)
r = subprocess.run([sys.executable, "build_training.py"], cwd="/workspace/knowledge_pipeline/projects/world-state", capture_output=True, text=True, timeout=120)
print("training tab:", (r.stdout or r.stderr).strip()[-120:])
try: print(subprocess.run([sys.executable, str(H / "loop_beat.py")], capture_output=True, text=True, timeout=60).stdout.strip()[:100])
except Exception as e: print("loop_beat failed:", e)
try: print(subprocess.run([sys.executable, str(H / "sweep.py")], capture_output=True, text=True, timeout=150).stdout.strip()[:200])
except Exception as e: print("sweep failed:", e)
try: print(subprocess.run([sys.executable, str(H / "backlog.py")], capture_output=True, text=True, timeout=150).stdout.strip()[:200])
except Exception as e: print("backlog failed:", e)
try: print(subprocess.run([sys.executable, str(H / "health.py")], capture_output=True, text=True, timeout=60).stdout.strip()[:200])
except Exception as e: print("health failed:", e)
