"""Runs tag_head.py (B1 step 2, ledger L389/L393) with a heartbeat job b1-tag-head; records the run in the history when it ends."""
import sys, subprocess, pathlib, time, threading, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
JOB = "b1-tag-head"; W = pathlib.Path(__file__).resolve().parent
meta = dict(where="[CPU]", task="T15", why="Train a token-level tag head on leaf, bge-small and Granite with the same data and score it on 300 held-out articles (amended rule L393).",
            success="Finder loose F1 0.55+ and 0.08 above the cheap baseline; reranker 0.05 above the proposer; an encoder swap needs +0.05 F1", next="Decide: keep head or keep tags offline; record the encoder verdict; route to B2 router", need="Nothing", cap=3600)
p = subprocess.Popen([os.environ.get("PY", "/workspace/models/embed-zs/.venv/bin/python"), "tag_head.py"], cwd=W, stdout=open(W / "runs/tag_head/head.log", "w"), stderr=subprocess.STDOUT, env={**os.environ, "HF_HOME": "/workspace/data/hf"})
(W / "runs/tag_head/head.pid").write_text(str(p.pid)); t0 = time.time()
while p.poll() is None:
    last = [l for l in open(W / "runs/tag_head/head.log", errors="ignore").read().splitlines() if l.startswith(("leaf", "bge", "granite", "baseline"))]
    hb.beat(JOB, state="running", progress=f"{sum(l.startswith(('leaf', 'bge', 'granite')) for l in last)} of 3 encoders done", last=(last[-1][:140] if last else "loading data and encoding"), spent=0.0, **meta); time.sleep(60)
cur = hb.beat(JOB, state="done" if p.returncode == 0 else "failed", progress=f"exit {p.returncode}, {int(time.time() - t0) // 60} min", last="finished" if p.returncode == 0 else "failed: see runs/tag_head/head.log", **meta)
hb.record(JOB, cur["state"], where=meta["where"], task="T15", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
