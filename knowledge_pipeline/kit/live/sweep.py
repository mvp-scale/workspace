"""Dead-element sweep, run every poll (tick.py calls it). Cleans what is safely ours to clean and reports the rest; nothing is killed.
Acts: moves finished rows (done, failed, lost) still on the Live view for 10 min or more to the history (heartbeat.finish); marks a running or queued row lost when it is overdue by 2.5 times its own promise and 30 min, and has no live pid.
Reports (finding list, no action): processes from the project folder running past 70 min with no live row (orphans, pid shown); predictions without a score note (ledger_pairs.py); stale pages (monitor_pages.py); a Kaggle row queued over 6 h (deleting a kernel needs the owner's yes); the share of scored rounds that missed in 24 h.
Writes the reporter row 'sweep' (Live tab) and appends to runs/sweep_history.jsonl when the findings change.
    python3 sweep.py"""
import json, os, pathlib, re, subprocess, sys, time, datetime as dt
H = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(H)); import heartbeat as hb
ROOT = H.parents[1]; LIVE = ROOT / "runs-live"; LEDGER = ROOT / ".ledger" / "ledger.jsonl"; HIST = ROOT / "projects/world-state/runs/sweep_history.jsonl"; WS = ROOT / "projects/world-state"
now = time.time(); utc = lambda s: dt.datetime.strptime(s[:19].rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()  # accepts 2026-11-10T20:49:41Z and ...41.544Z
acts, finds = [], []
rows = []
for p in LIVE.glob("*.json"):
    try: rows.append(json.loads(p.read_text()))
    except Exception: pass
SKIP = ("poller", "health", "improvement-loop", "sweep")
for r in rows:
    j = r.get("job", ""); st = r.get("state"); age = now - utc(r["updated"]) if r.get("updated") else 0
    if j in SKIP or j.startswith("auto-"): continue
    if st in ("done", "failed", "lost") and age >= 600: (hb.drop(j) if j.endswith("smoke") else hb.finish(j, st)); acts.append(f"moved {j} ({st}) to the history")
    elif st in ("running", "queued") and not r.get("service") and not j.startswith("kaggle-"):
        e = float(r.get("every_s") or 0); lim = max(1800, 2.5 * e)
        alive = bool(r.get("alive_pid")) and os.path.exists(f"/proc/{int(r['alive_pid'])}") if r.get("alive_pid") else False
        if age > lim and not alive: hb.finish(j, "lost", last=f"no update for {int(age // 60)} min and no live process"); acts.append(f"marked {j} lost")
    if st == "queued" and j.startswith("kaggle-") and r.get("started") and now - utc(r["started"]) > 6 * 3600: finds.append(f"{j} queued {int((now - utc(r['started'])) // 3600)} h; deleting the kernel needs the owner's yes")
# orphans: project processes past 70 min with no live row naming them
known = {str(r.get("pid")) for r in rows if r.get("pid")} | {str(r.get("alive_pid")) for r in rows if r.get("alive_pid")}
ps = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True).stdout.splitlines()[1:]
for l in ps:
    m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", l)
    if not m: continue
    pid, et, args = m.group(1), int(m.group(2)), m.group(3)
    if et < 4200 or pid in known or not re.search(r"\b(python3?|\.venv/bin/python)\b.*\b(t\d+_\w+|finetune\w*|run_round|head_\w+|triple_\w+|pool_\w+)\.py", args): continue
    try: cwd = os.readlink(f"/proc/{pid}/cwd")
    except Exception: continue
    if "knowledge_pipeline" in cwd and "poll_live" not in args: finds.append(f"process {pid} running {et // 60} min with no live row: {args[:80]}")
# unscored predictions
r = subprocess.run([sys.executable, str(H / "ledger_pairs.py")], capture_output=True, text=True, timeout=60).stdout.splitlines()
bad = [l for l in r if l and not l.startswith("OK") and not re.match(r"\d+ of \d+", l)]
running = any(x.get("state") == "running" and not x.get("service") and x.get("job") not in SKIP and not str(x.get("job", "")).startswith("auto-") for x in rows)
try: top = int(re.search(r'"id":"L(\d+)"', LEDGER.read_bytes()[-2000:].decode("utf-8", "ignore").strip().splitlines()[-1]).group(1))
except Exception: top = 0
bad = [l for l in bad if not (running and (m := re.search(r"L(\d+)", l)) and top - int(m.group(1)) < 40)]  # a prediction written for a round that is still running is pending, not missing
if bad: finds.append(f"{len(bad)} prediction or correction line(s) without a score: " + "; ".join(b[:60] for b in bad[:3]))
# stale pages
r = subprocess.run([sys.executable, str(H / "monitor_pages.py")], capture_output=True, text=True, timeout=90).stdout.splitlines()
st = [re.sub(r"\s*\(.*", "", l[6:].split(":")[0]) for l in r if l.startswith(("STALE", "DOWN"))]
if st: finds.append("pages stale or down: " + ", ".join(s.strip() for s in st))
# misses in the last 24 h
sc = ms = 0
try:
    for l in LEDGER.read_text().splitlines()[-600:]:
        x = json.loads(l)
        if x.get("kind") == "note" and x.get("text", "").startswith("SCORE ") and now - utc(x["ts"]) < 86400:
            sc += 1; ms += ": MISS" in x["text"][:120]
except Exception: pass
head = f"{len(acts)} cleaned, {len(finds)} to look at" + (f"; {ms} of {sc} scored rounds missed in 24 h" if sc else "")
hb.beat("sweep", where="[CPU]", state="running", every_s=180, why="Cleans finished and dead rows and reports orphans, unscored predictions, stale pages and stuck queues, every poll.", success="No dead row stays on the Live view; every finding is either gone next poll or named for the owner.", progress=head, last="; ".join(acts + finds)[:400] or "nothing to clean")
key = json.dumps([sorted(acts), sorted(finds)])
last = ""
try: last = HIST.read_text().splitlines()[-1]
except Exception: pass
if not last or json.loads(last).get("key") != key:
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with open(HIST, "a") as f: f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "key": key, "cleaned": acts, "findings": finds, "missed": ms, "scored": sc}) + "\n")
print(head + (" | " + "; ".join(acts + finds) if acts or finds else ""))
