"""Runs tag_head.py (B1 step 2, ledger L389/L393) with a heartbeat job b1b-tag-head-mlp; records the run in the history when it ends."""
import sys, subprocess, pathlib, time, threading, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
JOB = "b1b-tag-head-mlp"; W = pathlib.Path(__file__).resolve().parent
meta = dict(where="[CPU]", task="T19", why="Does a small neural head with neighbour and article context find tags better than the linear head (T15)? Ledger T19 prediction.",
            success="Best encoder finder loose F1 0.55 or more and 0.08 above the cheap baseline, under 10 ms per article", next="Record verdict; if it misses, tags stay offline and the question of tags at serving goes to the owner", need="Nothing", cap=3600)
p = subprocess.Popen([os.environ.get("PY", "/workspace/models/embed-zs/.venv/bin/python"), "tag_head2.py"], cwd=W, stdout=open(W / "runs/tag_head/head2.log", "w"), stderr=subprocess.STDOUT, env={**os.environ, "HF_HOME": "/workspace/data/hf"})
(W / "runs/tag_head/head2.pid").write_text(str(p.pid)); t0 = time.time()
while p.poll() is None:
    last = [l for l in open(W / "runs/tag_head/head2.log", errors="ignore").read().splitlines() if l.startswith(("leaf", "bge", "granite", "baseline"))]
    hb.beat(JOB, state="running", progress=f"{sum(l.startswith(('leaf', 'bge', 'granite')) for l in last)} of 3 encoders done", last=(last[-1][:140] if last else "loading data and encoding"), spent=0.0, **meta); time.sleep(60)
cur = hb.beat(JOB, state="done" if p.returncode == 0 else "failed", progress=f"exit {p.returncode}, {int(time.time() - t0) // 60} min", last="finished" if p.returncode == 0 else "failed: see runs/tag_head/head2.log", **meta)
hb.record(JOB, cur["state"], where=meta["where"], task="T19", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
