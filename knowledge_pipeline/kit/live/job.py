"""Run a command as a registered job so the ledger viewer's Live tab shows it while it runs and its result afterwards.
    python3 job.py <job> --task T45 --why '...' --success '...' --next '...' -- <command ...>
Registers the heartbeat (with the child's pid), runs the command with output to runs-live/<job>.log, then finishes the job as done or failed with the last output line."""
import argparse, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import heartbeat as hb
ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--task", default="T42"); ap.add_argument("--where", default="[CPU]"); ap.add_argument("--why", required=True); ap.add_argument("--success", required=True); ap.add_argument("--next", required=True); ap.add_argument("--cwd", default=".")
a, cmd = ap.parse_known_args()[0], sys.argv[sys.argv.index("--") + 1:]
log = hb.DIR / f"{a.job}.log"
with open(log, "w") as f:
    p = subprocess.Popen(cmd, cwd=a.cwd, stdout=f, stderr=subprocess.STDOUT)
    hb.beat(a.job, pid=p.pid, where=a.where, task=a.task, state="running", progress="running", why=a.why, success=a.success, next=a.next, need="Nothing")
    rc = p.wait()
lines = [l for l in log.read_text().splitlines() if l.strip()]
hb.finish(a.job, "done" if rc == 0 else "failed", last=(lines[-1][:200] if lines else "no output"))
sys.exit(rc)
