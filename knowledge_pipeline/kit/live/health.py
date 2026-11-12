"""Pipeline health check, run every poll (tick.py calls it). Answers one question: is the pipeline doing work, waiting, idle or broken, and on what.
Verdicts: BROKEN (a core piece is down) > WORKING (a job is running) > ACTIVE (no job running, but the agent wrote to the ledger in the last 30 minutes: between rounds, analysing or writing up) > WAITING (nothing running; queued outside or blocked on the owner) > IDLE (nothing running, nothing waited on: start the next piece).
Writes the heartbeat row 'health' (Live tab, terminal view, alarm strip) and appends one line to runs/health_history.jsonl.
    python3 health.py"""
import json, os, pathlib, shutil, subprocess, sys, time, urllib.request, datetime as dt
H = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(H)); import heartbeat as hb
ROOT = H.parents[1]; LIVE = ROOT / "runs-live"; LEDGER = ROOT / ".ledger" / "ledger.jsonl"; HIST = ROOT / "projects" / "world-state" / "runs" / "health_history.jsonl"
now = time.time(); utc = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
def http(u, t=4):
    try: return urllib.request.urlopen(u, timeout=t).read()
    except Exception: return None
def mins(x): return int(x // 60)
def dur(x): m = mins(x); return f"{m // 60} h {m % 60} min" if m >= 120 else f"{m} min"
# core pieces
core = {"ledger viewer": "http://localhost:18766/data", "console": "http://localhost:8100/", "Clef": "http://localhost:8018/health", "pulse reader": "http://localhost:8023/health"}
down = [n for n, u in core.items() if http(u) is None]
poller = subprocess.run(["pgrep", "-f", "poll_live.py"], capture_output=True, text=True).stdout.strip() != ""
if not poller: down.append("poller")
# jobs
rows = []
for p in LIVE.glob("*.json"):
    try: rows.append(json.loads(p.read_text()))
    except Exception: pass
SKIP = ("poller", "health", "improvement-loop", "sweep")  # reporters, not jobs
working = [r for r in rows if r.get("state") == "running" and not r.get("service") and r.get("job") not in SKIP and not str(r.get("job", "")).startswith("auto-") and not (str(r.get("job", "")).startswith("t68-ner-installs"))]
queued = [r for r in rows if r.get("state") == "queued"]
# a running row whose own update is overdue is not working
def overdue(r):
    e = float(r.get("every_s") or 0); lim = max(600, 2.5 * e) if e else 600
    try: return now - utc(r["updated"]) > lim
    except Exception: return True
def alive(r):  # a row can name a process to watch (alive_pid): a live process counts as reporting even if the row has not been rewritten
    try: return bool(r.get("alive_pid")) and os.path.exists(f"/proc/{int(r['alive_pid'])}")
    except Exception: return False
stalled = [r for r in working if overdue(r) and not alive(r)]
working = [r for r in working if not overdue(r) or alive(r)]
# owner waits
D = http("http://localhost:18766/data"); blocked = []
if D:
    try: blocked = [a["id"] for a in json.loads(D)["attention"] if str(a.get("why", "")).startswith("Blocked")]
    except Exception: pass
# activity: last ledger write
last_w = 0; last_task = ""
try:
    with open(LEDGER, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400000), 0)
        tail = f.read().decode("utf-8", "ignore").strip().splitlines()[-1]
    last_w = utc(json.loads(tail)["ts"][:19] + "Z"); last_task = json.loads(tail).get("task", "")
except Exception: pass
quiet = now - last_w if last_w else None
# failures in the last 24 h (the auto- rows are untracked scripts, not counted)
fails = 0
try:
    for l in open(ROOT / "runs-history.jsonl"):
        r = json.loads(l)
        if r.get("state") == "failed" and not str(r.get("job", "")).startswith("auto-") and now - utc(r["ended"]) < 86400: fails += 1
except Exception: pass
disk_gb = shutil.disk_usage("/workspace").free / 1e9
flags = []
for r in queued:
    age = now - utc(r["started"]) if r.get("started") else 0
    if age > 3600: flags.append(f"{r['job']} queued {dur(age)} and not started")
if stalled: flags.append("overdue: " + ", ".join(r["job"] for r in stalled))
if fails: flags.append(f"{fails} job(s) failed in 24 h")
if disk_gb < 50: flags.append(f"disk low: {disk_gb:.0f} GB free")
if quiet is not None and quiet > 1800 and not working: flags.append(f"no ledger write for {dur(quiet)}")
# reality check: what the machine is doing against what the rows claim
load1 = os.getloadavg()[0]; cores = os.cpu_count() or 1
try:
    mi = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in open("/proc/meminfo"))}; mem_free = mi["MemAvailable"] / mi["MemTotal"]
except Exception: mem_free = 1.0
n_auto = sum(1 for r in rows if str(r.get("job", "")).startswith("auto-") and not r.get("service"))
if working and load1 < 1.0: flags.append(f"a job row says running but the CPU is idle (load {load1:.1f})")
if not working and load1 > 4: flags.append(f"CPU busy (load {load1:.0f} on {cores} cores) with no running job row: an unregistered run")
if load1 > 1.5 * cores: flags.append(f"CPU oversubscribed: load {load1:.0f} on {cores} cores")
if mem_free < 0.10: flags.append(f"memory low: {mem_free * 100:.0f} percent available")
if n_auto > 3: flags.append(f"{n_auto} unregistered rows on the Live view (workers listed as jobs?)")
# verdict
if down: verdict, level = "BROKEN", "bad"; line = "BROKEN: " + ", ".join(down) + " not answering"
elif working: verdict, level = "WORKING", "ok"; line = f"WORKING: {len(working)} running: " + ", ".join(r["job"] for r in working)
elif quiet is not None and quiet < 1800: verdict, level = "ACTIVE", "ok"; line = f"ACTIVE: no job running; the agent wrote to the ledger {mins(quiet)} min ago (task {last_task or '?'}); between rounds"
else:
    waits = []
    ext = [r for r in queued if r.get("job", "").startswith("kaggle-")]
    if ext: waits.append("Kaggle queue " + dur(now - utc(ext[0]["started"])) + " (" + ext[0]["job"] + ")")
    if blocked: waits.append(f"owner: {len(blocked)} blocked ({', '.join(blocked[:6])})")
    if waits: verdict, level = "WAITING", "warn"; line = "NOTHING RUNNING, waiting on: " + "; ".join(waits)
    else: verdict, level = "IDLE", "warn"; line = "NOTHING RUNNING and nothing waited on: start the next piece"
detail = "; ".join(flags) if flags else "no flags"
hb.beat("health", where="[CPU]", state="running", every_s=180, level=level, verdict=verdict, progress=line, last=detail, why="Says whether the pipeline is working, waiting, idle or broken, and on what.", success="The verdict matches reality: WORKING only when a job is running; WAITING names what it waits on.", next="Rechecks every 3 minutes with the poller.", need="Nothing", task=None)
HIST.parent.mkdir(parents=True, exist_ok=True)
with open(HIST, "a") as f: f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verdict": verdict, "working": [r["job"] for r in working], "queued": [r["job"] for r in queued], "blocked": len(blocked), "flags": flags}) + "\n")
print(line + " | " + detail)
