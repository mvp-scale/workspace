"""Heartbeat for local_voter/gemma_pool.py (T21): every 60 s counts runs/pulse/pool_gemma4_off/raw.jsonl, updates runs-live/t21-pool-labelling.json, records the run when the PID is gone."""
import sys, os, time, json, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
PID = int(sys.argv[1]); JOB = "t21-pool-labelling"; W = pathlib.Path(__file__).resolve().parent; RAW = W / "runs/pulse/pool_gemma4_off/raw.jsonl"
alive = lambda: "gemma_pool.py" in subprocess.run(["ps", "-p", str(PID), "-o", "cmd="], capture_output=True, text=True).stdout
meta = dict(where="[5090] local Gemma 4 26B-A4B (vLLM, thinking off)", task="T21", why="Label the 46,775-item pool with the v3b codebook at 0 USD so the CPU reader has a clean fact base (owner picked v3b).",
            success="46,775 items attempted, under 1% parse failures, finished inside 50 min", next="Score label quality on the 400 items shared with Sonnet v3b; restart Clef", need="Nothing", cap=3300)
t0 = time.time()
cnt = lambda: sum(1 for _ in open(RAW)) if RAW.exists() else 0
while alive():
    n = cnt(); hb.beat(JOB, state="running", progress=f"{n} of 46775 items", last=f"{n} labelled, {int(time.time() - t0) // 60} min in", spent=0.0, **meta); time.sleep(60)
n = cnt(); st = "done" if n > 0 else "failed"  # a run that ends with no progress is a failure, never done
cur = hb.beat(JOB, state=st, progress=f"{n} of 46775 items", last=f"finished with {n} attempted", **meta)
hb.record(JOB, st, where=meta["where"], task="T21", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
