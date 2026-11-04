#!/usr/bin/env python3
"""Close a ledger task in the right order: every step line first, then done. The ledger refuses steps after done, so this is the only way to close a task.
usage: close_task.py <task> --evidence <ref> --step "1|what was done|evidence ref" --step "2|..." ...   (one --step per listed step; refuses if a step is missing)"""
import argparse, subprocess, sys, re
a = argparse.ArgumentParser(); a.add_argument("task"); a.add_argument("--evidence", required=True); a.add_argument("--step", action="append", default=[]); a.add_argument("--who", default="claude"); a = a.parse_args()
run = lambda *c: subprocess.run(["node", "cp.mjs", *c], capture_output=True, text=True)
brief = run("brief", a.task).stdout; n = len(re.findall(r"^\s*(?:steps)?\s+\d+\. ", brief.split("accept")[0], re.M))
given = sorted(int(s.split("|")[0]) for s in a.step)
if n and given != list(range(1, n + 1)): sys.exit(f"refused: {a.task} has {n} steps, you gave {given}. Give one --step per step, in order.")
for s in sorted(a.step, key=lambda s: int(s.split("|")[0])):
    i, text, ev = (s.split("|") + ["", ""])[:3]
    r = run("step", a.task, f"{i} {text}", "--who", a.who, "--evidence", ev); print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())
r = run("done", a.task, "--who", a.who, "--evidence", a.evidence); print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())
