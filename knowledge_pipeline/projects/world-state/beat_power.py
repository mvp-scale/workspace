"""Heartbeat for local_voter/power_bench.py (T21 side task): counts ROW lines in the log, records the run when the PID is gone."""
import sys, time, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
PID = int(sys.argv[1]); LOG = pathlib.Path(sys.argv[2]); JOB = "t21-power-sweep"
alive = lambda: "power_bench.py" in subprocess.run(["ps", "-p", str(PID), "-o", "cmd="], capture_output=True, text=True).stdout
meta = dict(where="[5090] local Gemma 4 labeller at 5 power limits", task="T21", why="Find a lower GPU power limit that keeps speed, for long local runs (owner request, ledger L604).",
            success="5 of 5 limits measured, 575 W repeat within 3%", next="Pick the limit, set it, restart Clef", need="Nothing", cap=1800)
rows = lambda: sum(1 for l in open(LOG) if l.startswith("ROW")) if LOG.exists() else 0
while alive():
    n = rows(); hb.beat(JOB, state="running", progress=f"{n} of 5 limits", last=f"{n} measured", spent=0.0, **meta); time.sleep(30)
n = rows(); st = "done" if n == 5 else "failed"
cur = hb.beat(JOB, state=st, progress=f"{n} of 5 limits", last=f"finished with {n} measured", **meta)
hb.record(JOB, st, where=meta["where"], task="T21", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
