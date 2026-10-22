#!/usr/bin/env python3
"""Kaggle run ledger: one JSON line per Kaggle run (boot, warm-up, work, shutdown, how it ended, GPU hours).

Standard library only. Ledger file: --ledger PATH, else $KAGGLE_RUNS_LEDGER, else ./kaggle-runs.jsonl.

    runs.py add --kernel owner/slug [--log run.log] [--pushed T] [--running T] [--done T] [--status S]
                [--gpu-used-before H] [--gpu-used-after H] [--note ".."]      # watch.sh calls this for you
    runs.py backfill <dir> [--owner NAME]     # add runs from Kaggle kernel logs (<slug>.log) found under <dir>
    runs.py summary                            # medians / worst per phase, how runs ended, suggested guard settings
    runs.py query [--kernel TEXT] [--since YYYY-MM-DD] [--ended REASON] [--fields a,b,..] [--json]
    runs.py quota                              # Kaggle's own GPU meter vs what the ledger recorded this quota week

Phases (seconds):
  boot      pushed -> Kaggle first reports RUNNING (watcher side, accurate to its poll interval)
  warmup    guard on -> first beat() of real work (imports, model and data load)
  max_gap   longest pause between two beat() calls
  work      the script's first log line -> its last
  shutdown  script end -> watcher sees COMPLETE (an upper bound: poll interval)
GPU hours: gpu_h_meter = change in Kaggle's "used" meter across the run (may lag); gpu_h_wall = RUNNING -> COMPLETE seen.
T values: epoch seconds or HH:MM:SS (today, local time).
"""
import argparse, datetime, glob, json, math, os, re, statistics, subprocess, sys


def ledger_path(arg=None):
    return arg or os.environ.get("KAGGLE_RUNS_LEDGER") or os.path.join(os.getcwd(), "kaggle-runs.jsonl")


def load(path):
    if not os.path.exists(path): return []
    return [json.loads(l) for l in open(path) if l.strip()]


def _t(v):
    if v in (None, ""): return None
    if re.fullmatch(r"\d+(\.\d+)?", str(v)): return float(v)
    return datetime.datetime.combine(datetime.date.today(), datetime.time.fromisoformat(v)).timestamp()


def parse_log(path):
    """Phase numbers from one Kaggle kernel log (JSON list of {"time": s since script start, "data": text})."""
    try: L = json.load(open(path))
    except Exception: return {"log": path, "log_error": "unreadable"}
    times = [x.get("time", 0.0) for x in L]
    out = {"log": os.path.abspath(path), "work_s": round(times[-1] - times[0], 1) if times else None}
    evs = []
    for x in L:
        for line in x.get("data", "").splitlines():
            if line.startswith("[guard-ev] "):
                try: evs.append(json.loads(line[11:]))
                except ValueError: pass
    if evs:
        out["source"] = "guard events"
        for e in evs:
            if e["ev"] == "start": out.update({k: e.get(k) for k in ("max_min", "idle_min", "machine_up_s", "process_up_s")}, started_at=e.get("t"))
            elif e["ev"] == "first_beat": out["warmup_s"] = e.get("warmup_s")
            elif e["ev"] == "end": out.update(ended=e.get("reason"), beats=e.get("beats"), max_gap_s=e.get("max_gap_s"))
        out.setdefault("ended", "killed (no end event: error, out of memory or Kaggle stopped it)")
    else:                                                       # older logs: only "[guard HH:MM:SS] ..." heartbeat lines
        g = [x["time"] for x in L if "[guard " in x.get("data", "")]
        if len(g) > 1:
            out.update(warmup_s=round(g[1] - g[0], 1), beats=len(g), max_gap_s=round(max(b - a for a, b in zip(g, g[1:])), 1), source="guard heartbeat lines")
        else:
            out["source"] = "no guard"
        stop = [x["data"] for x in L if "idle stop:" in x.get("data", "") or "hard stop:" in x.get("data", "")]
        out["ended"] = ("idle_stop" if "idle stop:" in stop[0] else "hard_stop") if stop else "normal (inferred)"
    return out


def add(path, kernel, log=None, pushed=None, running=None, done=None, status=None, used_before=None, used_after=None, note=None, when=None):
    when = datetime.datetime.fromtimestamp(when) if when else datetime.datetime.now()
    r = {"kernel": kernel, "recorded": when.astimezone().isoformat(timespec="seconds"), "status": status}
    if pushed: r["pushed_at"] = pushed
    if log: r.update(parse_log(log))
    if pushed and running: r["boot_s"] = round(running - pushed, 1)
    if running and done:
        r["gpu_h_wall"] = round((done - running) / 3600, 3)
        if r.get("work_s") is not None: r["shutdown_s_max"] = round(max(0.0, done - running - r["work_s"]), 1)
    if used_before is not None and used_after is not None: r["gpu_h_meter"] = round(used_after - used_before, 3)
    if note: r["note"] = note
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a") as f: f.write(json.dumps(r) + "\n")
    return r


def backfill(path, root, owner=None):
    have = {r["kernel"] for r in load(path)}
    owner = owner or os.environ.get("KAGGLE_USERNAME") or "unknown-owner"
    n = 0
    for log in sorted(glob.glob(os.path.join(root, "**", "*.log"), recursive=True)):
        try: json.load(open(log))
        except Exception: continue                               # not a Kaggle kernel log
        k = f"{owner}/{os.path.basename(log)[:-4]}"
        if k in have: continue
        add(path, k, log, status="complete", when=os.path.getmtime(log), note="backfilled from the kernel log (recorded = log file time); boot, shutdown and GPU meter unknown")
        have.add(k); n += 1
    print(f"backfilled {n} runs into {path}")


def _num(rows, key):
    return [r[key] for r in rows if isinstance(r.get(key), (int, float))]


def summary(path):
    rows = load(path)
    if not rows: print(f"no runs in {path}"); return
    print(f"{len(rows)} runs in {path}\n")
    print(f"{'phase':<16}{'median':>9}{'worst':>9}{'runs':>6}")
    for k, lab, unit in [("boot_s", "boot", "s"), ("warmup_s", "warm-up", "s"), ("max_gap_s", "longest pause", "s"),
                         ("work_s", "whole run", "s"), ("shutdown_s_max", "shutdown (<=)", "s"), ("gpu_h_wall", "GPU h (wall)", "h")]:
        v = _num(rows, k)
        f = (lambda x: f"{x:.1f}") if unit == "s" else (lambda x: f"{x:.3f}")
        print(f"{lab:<16}{f(statistics.median(v)) if v else '-':>9}{f(max(v)) if v else '-':>9}{len(v):>6}")
    ends = {}
    for r in rows: ends[r.get("ended", "unknown")] = ends.get(r.get("ended", "unknown"), 0) + 1
    print("\nhow runs ended: " + ", ".join(f"{k} {v}" for k, v in ends.items()))
    gaps, works, boots = _num(rows, "max_gap_s"), _num(rows, "work_s"), _num(rows, "boot_s")
    if gaps:
        line = f"\nsuggested guard: idle_min={max(2, math.ceil(3 * max(gaps) / 60))} (3x the longest pause, {max(gaps):.0f} s)"
        if works: line += f", max_min={max(10, math.ceil(2 * max(works) / 60))} (2x the longest run, {max(works) / 60:.1f} min)"
        print(line)
    if boots: print(f"cost of a fresh start: up to {max(boots):.0f} s boot + {max(_num(rows, 'warmup_s') or [0]):.0f} s warm-up")


def query(path, kernel=None, since=None, ended=None, fields=None, as_json=False):
    rows = [r for r in load(path)
            if (not kernel or kernel in r["kernel"]) and (not ended or ended in str(r.get("ended")))
            and (not since or r.get("recorded", "") >= since)]
    if as_json:
        for r in rows: print(json.dumps(r))
        return
    fields = (fields or "kernel,recorded,boot_s,warmup_s,work_s,ended,gpu_h_wall").split(",")
    w = {f: max([len(f)] + [len(str(r.get(f, "-"))) for r in rows]) for f in fields}
    print("  ".join(f.ljust(w[f]) for f in fields))
    for r in rows: print("  ".join(str(r.get(f, "-")).ljust(w[f]) for f in fields))
    print(f"\n{len(rows)} runs")


def kaggle_quota():
    """Kaggle's GPU meter as {'used': h, 'remaining': h, 'total': h, 'refresh': datetime}, or None if the CLI fails."""
    try: out = subprocess.run(["kaggle", "quota"], capture_output=True, text=True, timeout=60).stdout
    except Exception: return None
    for line in out.splitlines():
        p = line.split()
        if p and p[0] == "GPU" and len(p) >= 5:
            h = lambda s: float(s.rstrip("h"))
            return {"used": h(p[1]), "remaining": h(p[2]), "total": h(p[3]), "refresh": datetime.datetime.fromisoformat(p[4])}
    return None


def quota(path):
    q = kaggle_quota()
    if not q: print("kaggle quota failed (CLI missing or not authenticated)"); return
    week0 = q["refresh"] - datetime.timedelta(days=7)
    rows = [r for r in load(path) if datetime.datetime.fromisoformat(r["recorded"]).replace(tzinfo=None) >= week0]
    wall, meter = sum(_num(rows, "gpu_h_wall")), sum(_num(rows, "gpu_h_meter"))
    unmeasured = [r for r in rows if not isinstance(r.get("gpu_h_wall"), (int, float))]
    floor = sum(_num(unmeasured, "work_s")) / 3600                  # script time only: a lower bound for runs the watcher did not time
    wall += floor
    print(f"Kaggle meter this week: {q['used']:.2f} h used, {q['remaining']:.2f} h left of {q['total']:.0f} h (resets {q['refresh']:%Y-%m-%d %H:%M})")
    print(f"ledger this week: {len(rows)} runs, {wall:.2f} h" + (f" (of which {floor:.2f} h is script time only, for {len(unmeasured)} runs not timed by the watcher: a lower bound)" if unmeasured else "")
          + (f"; meter change across watched runs {meter:.2f} h" if meter else ""))
    gap = q["used"] - wall
    print(f"unaccounted: {gap:+.2f} h (Kaggle meter minus ledger: boot/shutdown of untimed runs, interactive sessions, runs not in the ledger, or meter lag)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Kaggle run ledger"); ap.add_argument("--ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("--kernel", required=True)
    for o in ("--log", "--pushed", "--running", "--done", "--status", "--note"): a.add_argument(o)
    a.add_argument("--gpu-used-before", type=float); a.add_argument("--gpu-used-after", type=float)
    b = sub.add_parser("backfill"); b.add_argument("dir"); b.add_argument("--owner")
    sub.add_parser("summary"); sub.add_parser("quota")
    q = sub.add_parser("query")
    for o in ("--kernel", "--since", "--ended", "--fields"): q.add_argument(o)
    q.add_argument("--json", action="store_true")
    x = ap.parse_args(); L = ledger_path(x.ledger)
    if x.cmd == "add": print(json.dumps(add(L, x.kernel, x.log, _t(x.pushed), _t(x.running), _t(x.done), x.status, x.gpu_used_before, x.gpu_used_after, x.note)))
    elif x.cmd == "backfill": backfill(L, x.dir, x.owner)
    elif x.cmd == "summary": summary(L)
    elif x.cmd == "query": query(L, x.kernel, x.since, x.ended, x.fields, x.json)
    else: quota(L)
