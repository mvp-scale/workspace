"""One heartbeat file per running job: knowledge_pipeline/runs-live/<job>.json. The ledger viewer reads them (Story, Live runs).
Fields: why, success (the threshold that counts as a pass), next (what happens after), need (what the owner must do, or 'Nothing'): every job that costs money or runs over 5 minutes sets all four, because the viewer's Running now table shows them. where (tag: [SESS] [API] [CON] [KAG] [5090] [CPU] [HOST], see playbook/08), task (ledger id), state (queued running done failed
stopped idle), progress, spent, cap, last (one line), started, updated (set here). A running job whose file is older than 10 min shows stale."""
import calendar, json, os, pathlib, subprocess, time

DIR = pathlib.Path(__file__).resolve().parents[2] / "runs-live"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def beat(job, **fields):
    DIR.mkdir(exist_ok=True)
    p = DIR / f"{job}.json"
    try: cur = json.loads(p.read_text())
    except Exception: cur = {}
    cur.update({k: v for k, v in fields.items() if v is not None})
    cur.setdefault("started", now()); cur["job"] = job; cur["updated"] = now()
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(cur)); os.replace(tmp, p)
    return cur


HIST = DIR.parent / "runs-history.jsonl"        # append-only, one compact record per finished run
KEEP = ("job", "where", "task", "state", "started", "ended", "spent", "progress", "last", "why", "success", "next")


def seen(job, started):
    try: tail = HIST.read_text().splitlines()[-2000:]
    except Exception: return False
    return any((r := json.loads(l)).get("job") == job and r.get("started") == started for l in tail if l.strip())


def record(job, state="done", **fields):
    """Append one finished run to the history (once per job+started). No active file is touched."""
    r = {"job": job, "state": state, "ended": now(), **{k: v for k, v in fields.items() if v is not None}}
    r.setdefault("started", r["ended"])
    if seen(job, r["started"]): return False
    with open(HIST, "a", encoding="utf-8") as f: f.write(json.dumps({k: r[k] for k in KEEP if k in r}) + "\n")
    return True


def finish(job, state="done", **fields):
    """A job ended: move it from active (runs-live/<job>.json) to the history."""
    p = DIR / f"{job}.json"
    try: cur = json.loads(p.read_text())
    except Exception: cur = {"job": job}
    cur.update({k: v for k, v in fields.items() if v is not None})
    record(job, state, **{k: v for k, v in cur.items() if k not in ("job", "state", "updated")})
    p.unlink(missing_ok=True)


def drop(job):
    (DIR / f"{job}.json").unlink(missing_ok=True)


def prune(hours=24):
    """Active files silent for more than `hours` are archived as 'lost' so nothing stays active forever."""
    for p in DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text())
            if time.time() - calendar.timegm(time.strptime(r["updated"], "%Y-%m-%dT%H:%M:%SZ")) > hours * 3600:
                finish(r["job"], "lost", last=f"no update for {hours} h (was {r.get('state')})")
        except Exception: pass


def watch_pids():
    """Jobs that record a pid: refresh their heartbeat while the process lives; if it is gone and the job never reported an end, mark it failed."""
    for p in DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text()); pid = r.get("pid")
            if not pid or r.get("state") not in ("running", "queued"): continue
            if os.path.exists(f"/proc/{pid}"): beat(r["job"])
            elif str(r["job"]).startswith("auto-"): finish(r["job"], "lost", last="ended; exit status unknown (the starter never registered it, so this is not a failure signal; see its own outputs)")
            else: finish(r["job"], "failed", last="process ended without reporting a result")
        except Exception: pass


# ---- watchdog: no project job may run unseen (owner rule 2026-11-02: the knowledge pipeline page is the real-time view of everything running)
ROOT = DIR.parent                                           # /workspace/knowledge_pipeline
IGNORE = ("cp.mjs serve", "poll_live.py", "kit/live", "http.server", "-m nr.serve", "world_service2.py", "server.py", "cpu_engine.py", "engine_reader.py")


def _procs():
    out = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True).stdout.splitlines()[1:]
    for l in out:
        try: pid, et, args = l.strip().split(None, 2); yield int(pid), int(et), args
        except Exception: pass


def _ppid_chain(pid):
    """Parent process ids of pid, nearest first (reads /proc)."""
    out = []
    try:
        while pid > 1 and len(out) < 12:
            pp = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1]); out.append(pp); pid = pp
    except Exception: pass
    return out


def _is_child_process(pid):
    """A pool worker or a command run by a round card is part of its parent's job, not a separate unregistered job."""
    for pp in _ppid_chain(pid):
        try: a = open(f"/proc/{pp}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "ignore")
        except Exception: continue
        if "run_round.py" in a: return True
        try:
            if os.readlink(f"/proc/{pp}/cwd").startswith(str(ROOT)) and ("python" in a.split(" ")[0] or "/python" in a.split(" ")[0]) and "poll_live" not in a: return True
        except Exception: pass
    return False


def watch_untracked():
    """Any python or node process whose working directory is inside knowledge_pipeline and that has run for over 60 s, and that no heartbeat file names by pid, gets an automatic 'not registered by its starter' row; when it ends the row is closed."""
    known = {}
    for p in DIR.glob("*.json"):
        try: r = json.loads(p.read_text()); known[r.get("pid")] = r
        except Exception: pass
    live = set()
    for pid, et, args in _procs():
        if et < 60 or not (" python" in " " + args or "/python" in args.split()[0] or args.startswith(("node ", "python"))) or any(x in args for x in IGNORE) or "bash -c" in args or args.startswith("sh -c"): continue
        try: cwd = os.readlink(f"/proc/{pid}/cwd")
        except Exception: continue
        if not cwd.startswith(str(ROOT)): continue
        if _is_child_process(pid):  # part of a registered round or of its parent job: no row of its own
            drop(f"auto-{os.path.basename(next((a for a in args.split() if a.endswith(('.py', '.mjs', '.js', '.sh'))), 'process')).rsplit('.', 1)[0]}-{pid}"); continue
        live.add(pid)
        if pid in known:
            if str(known[pid].get("job", "")).startswith("auto-"):  # keep the unregistered row honest: real uptime, and a process up over an hour is a service, not a job
                up = f"{et // 86400} d {et % 86400 // 3600} h" if et >= 86400 else f"{et // 3600} h {et % 3600 // 60} min" if et >= 3600 else f"{et // 60} min"
                beat(known[pid]["job"], progress=f"up {up}", service=(True if et >= 3600 else None), every_s=(None if et >= 3600 else 180))
            continue
        script = next((a for a in args.split() if a.endswith((".py", ".mjs", ".js", ".sh"))), "process")
        job = f"auto-{os.path.basename(script).rsplit('.', 1)[0]}-{pid}"
        beat(job, pid=pid, where="[CPU]", task="?", state="running", progress=f"running {et // 60} min", last=f"UNREGISTERED: {args[:110]}", why="Started without a heartbeat; the starter should register it with why / success / next (GO.md rule: the page is the truth).", success="unknown (not registered)", next="unknown (not registered)", need="Nothing")
    for p in DIR.glob("auto-*.json"):
        try:
            r = json.loads(p.read_text())
            if r.get("state") == "running" and r.get("pid") not in live and not os.path.exists(f"/proc/{r.get('pid')}"): finish(r["job"], "done", last="ended; exit status unknown (it was never registered by its starter)")
        except Exception: pass
