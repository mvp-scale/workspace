"""Heartbeat wrapper for router_test.py (T16, B2)."""
import sys, subprocess, pathlib, time, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
JOB = "b2-router-test"; W = pathlib.Path(__file__).resolve().parent
meta = dict(where="[CPU]", task="T16", why="Does a news-versus-other router stop kinds of text it never saw (leave-one-kind-out; READMEs, exam questions, our notes)? Ledger L403.",
            success="Each held-out kind at least 90 percent stopped while at least 98 percent of held-out news is kept", next="Record verdict; if a kind is weak, retrain with real capability-source text (A1/B4); then B3", need="Nothing", cap=1800)
log = W / "runs/tag_head/router.log"; p = subprocess.Popen(["/workspace/models/embed-zs/.venv/bin/python", "router_test.py"], cwd=W, stdout=open(log, "w"), stderr=subprocess.STDOUT, env={**os.environ, "HF_HOME": "/workspace/data/hf"}); (W / "runs/tag_head/router.pid").write_text(str(p.pid)); t0 = time.time()
while p.poll() is None:
    ls = [l for l in open(log, errors="ignore").read().splitlines() if l.startswith(("sparse", "leaf", "{"))]
    hb.beat(JOB, state="running", progress=f"{len(ls)} of 6 cells", last=(ls[-1][:140] if ls else "building test sets"), spent=0.0, **meta); time.sleep(30)
cur = hb.beat(JOB, state="done" if p.returncode == 0 else "failed", progress=f"exit {p.returncode}, {int(time.time() - t0) // 60} min", last="finished" if p.returncode == 0 else "failed: see runs/tag_head/router.log", **meta)
hb.record(JOB, cur["state"], where=meta["where"], task="T16", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
