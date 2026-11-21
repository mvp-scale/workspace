"""chain_windows: ONE end-to-end window, then exit (T158, plan 1e option (b), owner directive L2901: every part RUNS end to end; weak quality is output marked PROVISIONAL, never a blocker). No loop, no daemon, no service: the main session's loop starts one run per window.
Steps, in order, each in its own process, each logged to <window>/logs/<step>.log. A step that fails or is stopped does not stop the later ones (every part must run irrespective of the others), the result says which.
  1 live     live_trace.py  START/DURATION/POLL/PAGE_DIR=<window>        -> <window>/trace/chain.jsonl (+ a/, run.json)
  2 slow     slow_clock.py <window>                                      -> <window>/trace/slow.jsonl, slow_run.json, g4/
  3 consol   slow_consolidate.py --trace <window>/trace                  -> <window>/trace/slow_consolidate/{consolidated,evolved,resource_state,truth,educate_index}.json
  4 align    simulation/check-alignment.py                               -> demo/mockups/knowledge-raw/status.json (or --status-out)
Window = demo/mockups/structure-live/runs-e2e-<n> (new each run; live_trace refuses a folder that already holds a chain). Manifest <window>/window.json (steps, pids, state), heartbeat runs-live/chain-window-<n>.json (job shows on the ledger viewer Live tab), ONE ledger note on T158 at the end.
Hard cap 60 minutes for the whole run (--duration-min default 40, at most 50): a deadline is fixed at launch; slow gets what is left minus 8 minutes for consol and align. A step past its limit, or the runner past the deadline, is stopped by VERIFIED PID: /proc/<pid>/cmdline must name the step's script (and the window, when /proc/<pid>/environ or the cmdline holds it), then SIGTERM, 120 s grace, then SIGKILL. SIGTERM/SIGINT on the runner stops the current step the same way and still writes the manifest, the heartbeat end and the ledger note.
    python3 chain_windows.py [--duration-min 40] [--start-ago-min 0] [--poll 15] [--limit-slow N] [--journal-dir D] [--status-out PATH] [--n N] [--no-ledger]
    python3 chain_windows.py --stop <window dir>           (verified PID of the runner: its command line names chain_windows.py and the pid is the one in window.json and in the lock file; it then stops its current step)
--start-ago-min N: live_trace START = now - N min, so the backlog that became ready in that span is traced first (0 = only what becomes ready after launch). --journal-dir: the durable journal live_trace appends to (default: its own default; a dry run should pass a scratch dir). CPU only, no hosted call, no bench, no console, no GPU."""
import argparse, json, os, pathlib, signal, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent; KP = HERE.parents[1]; WS = KP / "projects" / "world-state"; SIM = KP / "simulation"; LEDGER = KP / ".ledger"
SL = KP.parent / "demo" / "mockups" / "structure-live"; PY = "/workspace/models/embed-zs/.venv/bin/python"; PY = PY if os.path.exists(PY) else sys.executable
sys.path.insert(0, str(HERE)); import heartbeat as hb
VERSION = "chain-windows-v1"; CAP_S = 3600; RESERVE_AFTER_SLOW_S = 480; LOCK = KP / "runs-live" / "chain_windows.lock"; TASK = "T158"
STOP = {"flag": False}; CUR = {"p": None, "marker": None, "window": None}

def now_iso(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def atomic(path, obj):
    tmp = str(path) + ".tmp"; open(tmp, "w").write(json.dumps(obj, ensure_ascii=False, indent=1)); os.replace(tmp, path)
def cmdline(pid):
    try: return open("/proc/%d/cmdline" % pid, "rb").read().decode(errors="replace").replace("\0", " ")
    except Exception: return None
def environ_has(pid, text):
    """True/False when /proc/<pid>/environ is readable, None when it is not"""
    try: return text in open("/proc/%d/environ" % pid, "rb").read().decode(errors="replace")
    except Exception: return None
def verified(pid, script, window=None):
    """the pid is a live process whose command line names `script` (and holds the window in its command line or environment, when one is given)"""
    c = cmdline(pid)
    if c is None or script not in c: return False
    if window and str(window) not in c and environ_has(pid, str(window)) is False: return False
    return True
def stop_pid(p, script, window=None, grace=120):
    """SIGTERM a child we started, only after verifying its pid; SIGKILL after the grace, verified again. Returns how it ended."""
    if p.poll() is not None: return "already exited rc=%s" % p.returncode
    if not verified(p.pid, script, window): return "pid %d not verified as %s: left alone" % (p.pid, script)
    os.kill(p.pid, signal.SIGTERM); t = time.time()
    while time.time() - t < grace:
        if p.poll() is not None: return "SIGTERM, exited rc=%s after %.0f s" % (p.returncode, time.time() - t)
        time.sleep(1)
    if p.poll() is None and verified(p.pid, script, window): os.kill(p.pid, signal.SIGKILL); p.wait(timeout=30); return "SIGTERM ignored for %d s, SIGKILL" % grace
    return "exited"
def lock_holder():
    try: pid = int(LOCK.read_text().strip())
    except Exception: return None
    c = cmdline(pid); return pid if c and "chain_windows.py" in c else None
def other_live_trace():
    me = os.getpid()
    for d in os.listdir("/proc"):
        if d.isdigit() and int(d) != me:
            c = cmdline(int(d))
            if c and ("live_trace.py" in c or "slow_clock.py" in c) and "chain_windows.py" not in c and "pgrep" not in c and "/bin/bash" not in c and "sed " not in c and "grep" not in c: return int(d), c[:140]
    return None
def next_n():
    ns = [int(p.name.split("-")[-1]) for p in SL.glob("runs-e2e-*") if p.name.split("-")[-1].isdigit()]; return max(ns, default=0) + 1
def count_lines(path, key=None):
    n = 0
    try:
        for ln in open(path, encoding="utf-8"):
            if not ln.strip(): continue
            if key is None or key in ln: n += 1
    except OSError: return None
    return n
def jload(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None

def stop_window(w):
    w = pathlib.Path(w).resolve(); m = jload(w / "window.json")
    if not m: print("no window.json in %s" % w); return 1
    pid = m.get("pid")
    if not pid or not verified(pid, "chain_windows.py") or lock_holder() != pid: print("runner pid %s is not this window's chain_windows.py (state %s): nothing to stop" % (pid, m.get("state"))); return 0 if m.get("state") not in ("running",) else 1
    os.kill(pid, signal.SIGTERM); print("SIGTERM sent to verified runner pid %d; it stops its current step by verified pid and writes the manifest" % pid); return 0

def on_signal(sig, fr): STOP["flag"] = True

def run_step(M, win, name, script_name, cmd, env, limit_s, cwd, deadline, beat):
    """start one step, watch it; the result is a dict in M['steps']; never raises for a failing child"""
    left = deadline - time.time(); limit_s = min(limit_s, left)
    st = {"name": name, "cmd": " ".join(cmd), "limit_s": round(limit_s), "state": "starting"}; M["steps"].append(st)
    if limit_s < 20 or STOP["flag"]:
        st["state"] = "skipped: " + ("runner stopped" if STOP["flag"] else "no time left under the 60-min cap (%.0f s)" % left); atomic(win / "window.json", M); return st
    os.makedirs(win / "logs", exist_ok=True); log = open(win / "logs" / ("%s.log" % name), "w")
    p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    CUR.update(p=p, marker=script_name, window=win.name); t0 = time.time(); st.update(pid=p.pid, started=now_iso(), state="running"); M["current"] = name; atomic(win / "window.json", M); last_b = 0.0
    while p.poll() is None:
        t = time.time()
        if STOP["flag"]: st["stop"] = stop_pid(p, script_name, win.name); st["state"] = "stopped: runner stopped"; break
        if t - t0 > limit_s or t > deadline: st["stop"] = stop_pid(p, script_name, win.name); st["state"] = "stopped: limit reached (%d s)" % limit_s; break
        if t - last_b >= 15: last_b = t; beat(name, t - t0)
        time.sleep(2)
    st["rc"] = p.returncode; st["seconds"] = round(time.time() - t0, 1); st["ended"] = now_iso(); log.close(); CUR.update(p=None)
    if st["state"] == "running": st["state"] = "done" if p.returncode == 0 else "failed rc=%s" % p.returncode
    M["current"] = None; atomic(win / "window.json", M); return st

def outputs(win, status_out, t_launch):
    tr = win / "trace"; sc = tr / "slow_consolidate"; sj = jload(tr / "slow_run.json") or {}; lr = jload(tr / "run.json") or {}; st = jload(status_out) if status_out else None
    o = {"chain.jsonl": count_lines(tr / "chain.jsonl"), "traced": None,
         "slow.jsonl": count_lines(tr / "slow.jsonl"), "consolidated.json": (sc / "consolidated.json").exists(), "resource_state.json": (sc / "resource_state.json").exists(),
         "status.json": bool(st) and os.path.getmtime(status_out) >= t_launch, "live_state": lr.get("state"), "slow_state": sj.get("state")}
    if o["chain.jsonl"]:   # each chain.jsonl row holds the traced line as a json string: count by parsing
        n = 0
        for ln in open(tr / "chain.jsonl", encoding="utf-8"):
            try:
                if json.loads(json.loads(ln)["line"]).get("state") == "traced": n += 1
            except Exception: pass
        o["traced"] = n
    o["complete"] = bool(o["chain.jsonl"]) and bool(o["slow.jsonl"] is not None and (o["slow.jsonl"] > 0 or o["traced"] == 0)) and o["consolidated.json"] and o["resource_state.json"]
    return o

def main():
    ap = argparse.ArgumentParser(description="one end-to-end window: live_trace, slow_clock, slow_consolidate, check-alignment (T158)")
    ap.add_argument("--duration-min", type=float, default=40); ap.add_argument("--start-ago-min", type=float, default=0); ap.add_argument("--poll", type=float, default=15); ap.add_argument("--limit-slow", type=int, default=None)
    ap.add_argument("--journal-dir"); ap.add_argument("--status-out"); ap.add_argument("--n", type=int); ap.add_argument("--no-ledger", action="store_true"); ap.add_argument("--stop", metavar="WINDOW")
    a = ap.parse_args()
    if a.stop: sys.exit(stop_window(a.stop))
    if not 1 <= a.duration_min <= 50: sys.exit("--duration-min must be 1..50 (the whole run, with slow, consol and align, has a hard 60-min cap)")
    h = lock_holder()
    if h: sys.exit("refusing: another chain_windows run is alive (pid %d)" % h)
    o = other_live_trace()
    if o: sys.exit("refusing: a live_trace or slow_clock process is already running: pid %d %s" % o)
    n = a.n or next_n(); win = SL / ("runs-e2e-%d" % n); os.makedirs(win)   # fails when the folder exists: a chain never restarts in place
    t_launch = time.time(); deadline = t_launch + CAP_S; job = "chain-window-%d" % n; tr = win / "trace"
    status_out = a.status_out or str(KP.parent / "demo" / "mockups" / "knowledge-raw" / "status.json")
    LOCK.parent.mkdir(exist_ok=True); LOCK.write_text(str(os.getpid()))
    M = {"version": VERSION, "window": str(win), "n": n, "pid": os.getpid(), "cmd": "chain_windows.py", "started": now_iso(), "cap_s": CAP_S, "deadline_epoch": deadline, "duration_min": a.duration_min, "start_ago_min": a.start_ago_min, "state": "running", "steps": [], "current": None, "status_out": status_out}
    atomic(win / "window.json", M)
    for s in (signal.SIGTERM, signal.SIGINT): signal.signal(s, on_signal)
    def beat(step, secs):
        hb.beat(job, pid=os.getpid(), where="[CPU]", task=TASK, state="running", progress="%s %.0f s; trace lines %s; %.0f of %d min used" % (step, secs, count_lines(tr / "chain.jsonl") or 0, (time.time() - t_launch) / 60, CAP_S // 60),
                why="one end-to-end window: live chain, slow clock, consolidation, status check (owner directive L2901)", success="chain.jsonl, slow.jsonl, consolidated.json and resource_state.json all present in %s, within the 60-min cap" % win.name,
                next="status page reads the window; the loop starts the next window", need="Nothing", cap="%d min" % (CAP_S // 60))
    hb.beat(job, pid=os.getpid(), where="[CPU]", task=TASK, state="running", progress="starting", why="one end-to-end window: live chain, slow clock, consolidation, status check (owner directive L2901)", success="chain.jsonl, slow.jsonl, consolidated.json and resource_state.json all present in %s, within the 60-min cap" % win.name, next="status page reads the window; the loop starts the next window", need="Nothing", cap="%d min" % (CAP_S // 60))
    final = "failed"
    try:
        env = dict(os.environ, START=str(t_launch - a.start_ago_min * 60), DURATION=str(a.duration_min * 60), POLL=str(a.poll), PAGE_DIR=str(win), PYTHONHASHSEED="0")
        if a.journal_dir: env["JOURNAL_DIR"] = a.journal_dir
        live_limit = a.duration_min * 60 + 300   # model load happens before the live clock starts, plus the last line and run.json
        run_step(M, win, "live", "live_trace.py", [PY, "live_trace.py"], env, min(live_limit, CAP_S - RESERVE_AFTER_SLOW_S - 60), WS, deadline, beat)
        budget = max(60, deadline - time.time() - RESERVE_AFTER_SLOW_S); cap_min = max(0.5, (budget - 150) / 60)   # its own cap + 90 s watchdog fit inside the step limit
        cmd = [PY, "slow_clock.py", str(win), "--cap-min", "%.2f" % cap_min] + (["--limit", str(a.limit_slow)] if a.limit_slow else [])
        run_step(M, win, "slow", "slow_clock.py", cmd, dict(os.environ), budget, WS, deadline, beat)
        lim = min(600, max(60, deadline - time.time() - 180))
        run_step(M, win, "consol", "slow_consolidate.py", [PY, "slow_consolidate.py", "--trace", str(tr), "--cap-min", "%.2f" % ((lim - 20) / 60)], dict(os.environ), lim, WS, deadline, beat)
        run_step(M, win, "align", "check-alignment.py", [PY, str(SIM / "check-alignment.py"), "--out", status_out], dict(os.environ), min(480, deadline - time.time()), KP, deadline, beat)
        M["outputs"] = outputs(win, status_out, t_launch); bad = [s["name"] for s in M["steps"] if s["state"] != "done"]
        final = "stopped" if STOP["flag"] else ("done" if M["outputs"]["complete"] and not bad else "partial")
        M["problems"] = ["%s: %s" % (s["name"], s["state"]) for s in M["steps"] if s["state"] != "done"]
    except BaseException as e:
        M["error"] = "%s: %s" % (type(e).__name__, str(e)[:300])
        if CUR["p"] is not None: M["stop_on_error"] = stop_pid(CUR["p"], CUR["marker"], CUR["window"])
        final = "failed"
    finally:
        M["state"] = final; M["ended"] = now_iso(); M["seconds"] = round(time.time() - t_launch, 1); M["current"] = None; M["total_min"] = round(M["seconds"] / 60, 1)
        atomic(win / "window.json", M)
        try: LOCK.unlink()
        except OSError: pass
        o = M.get("outputs") or {}; steps = ", ".join("%s %s %ss" % (s["name"], s["state"], s.get("seconds", "-")) for s in M["steps"])
        text = ("[S] WINDOW runs-e2e-%d (kit/live/chain_windows.py, one window, no loop): %s in %.1f of 60 min. Steps: %s. Outputs: chain lines %s (traced %s), slow lines %s, consolidated %s, resource_state %s, status %s. Manifest %s/window.json. All output PROVISIONAL (owner directive L2901)."
                % (n, final, M["seconds"] / 60, steps, o.get("chain.jsonl"), o.get("traced"), o.get("slow.jsonl"), o.get("consolidated.json"), o.get("resource_state.json"), o.get("status.json"), win.relative_to(KP.parent)))
        if not a.no_ledger:
            try:
                r = subprocess.run(["node", "cp.mjs", "note", TASK, text], cwd=str(LEDGER), capture_output=True, text=True, timeout=90); M["ledger"] = (r.stdout + r.stderr).strip()[:300]
            except Exception as e: M["ledger"] = "note failed: %s" % e
            atomic(win / "window.json", M)
        hb.finish(job, "done" if final == "done" else "failed", last=text[:240])
        print(json.dumps({"window": str(win), "state": final, "minutes": M["total_min"], "steps": {s["name"]: s["state"] for s in M["steps"]}, "outputs": o, "ledger": M.get("ledger")}, indent=1))
    sys.exit(0 if final == "done" else 1)

if __name__ == "__main__": main()
