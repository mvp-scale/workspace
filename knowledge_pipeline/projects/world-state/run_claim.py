"""Heartbeat wrapper for claim_test.py (T17, B2)."""
import sys, subprocess, pathlib, time, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
JOB = "b3-claim-test"; W = pathlib.Path(__file__).resolve().parent
meta = dict(where="[CPU]", task="T17", why="Can a small CPU cross-encoder label agree / contradict / gap on real sentence pairs from different articles that share a tag, as judged by local Clef? Ledger L411.",
            success="Non-neutral calls match Clef 60 percent or more, finds 60 percent or more of Clef agree or contradict pairs, under 50 ms per pair", next="Record verdict; if it misses, test the small and base cross-encoders; then A1 and B4 or the cheap B1 retry", need="Nothing", cap=1800)
log = W / "runs/tag_head/claim.log"; p = subprocess.Popen(["/workspace/models/embed-zs/.venv/bin/python", "claim_test.py"], cwd=W, stdout=open(log, "w"), stderr=subprocess.STDOUT, env={**os.environ, "HF_HOME": "/workspace/data/hf"}); (W / "runs/tag_head/claim.pid").write_text(str(p.pid)); t0 = time.time()
while p.poll() is None:
    ls = [l for l in open(log, errors="ignore").read().splitlines() if l.startswith(("articles", "pairs", "labels", "clef"))]
    hb.beat(JOB, state="running", progress="running", last=(ls[-1][:140] if ls else "building test sets"), spent=0.0, **meta); time.sleep(30)
cur = hb.beat(JOB, state="done" if p.returncode == 0 else "failed", progress=f"exit {p.returncode}, {int(time.time() - t0) // 60} min", last="finished" if p.returncode == 0 else "failed: see runs/tag_head/claim.log", **meta)
hb.record(JOB, cur["state"], where=meta["where"], task="T17", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
