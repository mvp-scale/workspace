"""Heartbeat wrapper for claim_test.py (T18, B2)."""
import sys, subprocess, pathlib, time, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
JOB = "b3b-claim-pairs"; W = pathlib.Path(__file__).resolve().parent
meta = dict(where="[CPU]", task="T18", why="Do claim-aware similar sentence pairs give real agree / contradict cases, and does an int8 xsmall cross-encoder label them like Clef, fast? Ledger L419.",
            success="HIGH band precision and recall 0.60 or more, unrelated pairs 5 percent or less called contradiction, int8 under 50 ms, flips under 5 percent", next="Record verdict; if it misses, claim pairs go to Clef offline and the CPU only finds them; then cheap tag-head retry", need="Nothing", cap=1800)
log = W / "runs/tag_head/pairs.log"; p = subprocess.Popen(["/workspace/models/embed-zs/.venv/bin/python", "claim_pairs.py"], cwd=W, stdout=open(log, "w"), stderr=subprocess.STDOUT, env={**os.environ, "HF_HOME": "/workspace/data/hf"}); (W / "runs/tag_head/pairs.pid").write_text(str(p.pid)); t0 = time.time()
while p.poll() is None:
    ls = [l for l in open(log, errors="ignore").read().splitlines() if l.startswith(("claim", "candidate", "pairs", "clef"))]
    hb.beat(JOB, state="running", progress="running", last=(ls[-1][:140] if ls else "building test sets"), spent=0.0, **meta); time.sleep(30)
cur = hb.beat(JOB, state="done" if p.returncode == 0 else "failed", progress=f"exit {p.returncode}, {int(time.time() - t0) // 60} min", last="finished" if p.returncode == 0 else "failed: see runs/tag_head/pairs.log", **meta)
hb.record(JOB, cur["state"], where=meta["where"], task="T18", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
