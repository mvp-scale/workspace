#!/usr/bin/env python3
"""Claude Code status line: is the training loop working? Color-coded, one line.
green WORKING (suite jobs alive on CPU), yellow WAITING ON YOU / IDLE, red FAILED (a job failed in the last hour).
Reads data/progress/events.jsonl, needs-you.json and loop.json (round counter kept by the captain)."""
import json, os, subprocess, sys, time

ROOT = "/workspace/data/progress"
G, Y, R, D, B, X = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def load(name, default):
    try:
        with open(os.path.join(ROOT, name)) as f:
            return json.load(f)
    except Exception:
        return default


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass
    pids = subprocess.run(["pgrep", "-f", "python .*suite.py"], capture_output=True, text=True).stdout.split()
    last, failed = {}, []
    try:
        with open(os.path.join(ROOT, "events.jsonl")) as f:
            for line in f.readlines()[-400:]:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                last[e.get("job")] = e
                if e.get("state") == "failed" and time.time() - e.get("ts", 0) < 3600:
                    failed.append(e.get("job"))
    except Exception:
        pass
    live = [e for e in last.values() if str(e.get("pid")) in pids and e.get("state") in ("training", "scoring")]
    loop = load("loop.json", {})
    rnd = f"round {loop.get('round', 0)}/{loop.get('of', 5)} {loop.get('phase', '')}".strip()
    needs = load("needs-you.json", [])
    parts = []
    if failed:
        parts.append(f"{R}{B}● FAILED{X} {R}{', '.join(sorted(set(failed)))}{X}")
    if live:
        jobs = " · ".join(f"{e['job']} {e.get('msg', '')[:28]}" for e in sorted(live, key=lambda e: e["job"]))
        parts.append(f"{G}{B}● WORKING{X} {G}CPU {len(live)} jobs{X} {D}{jobs}{X}")
    elif not failed:
        parts.append(f"{Y}{B}● IDLE{X} {Y}no jobs running{X}")
    parts.append(f"{D}{rnd}{X}")
    if needs:
        parts.append(f"{Y}{B}needs you: {len(needs)}{X}")
    print("  ".join(parts))


main()
