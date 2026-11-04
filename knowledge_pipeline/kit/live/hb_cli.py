"""Heartbeat from a shell script: register a process that has no Python starter (for example a model server).
    hb_cli.py start <job> --pid N --where '[5090] ...' --why '...' --success '...' --next '...'
    hb_cli.py finish <job> <done|failed|lost> --last '...'"""
import argparse, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import heartbeat as hb
ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
s = sub.add_parser("start"); s.add_argument("job"); s.add_argument("--pid", type=int); s.add_argument("--where", default="[CPU]"); s.add_argument("--why", required=True); s.add_argument("--success", required=True); s.add_argument("--next", required=True); s.add_argument("--task", default="T21")
f = sub.add_parser("finish"); f.add_argument("job"); f.add_argument("state", choices=["done", "failed", "lost"]); f.add_argument("--last", default="")
a = ap.parse_args()
if a.cmd == "start": hb.beat(a.job, pid=a.pid, where=a.where, task=a.task, state="running", progress="running", why=a.why, success=a.success, next=a.next, need="Nothing")
else: hb.finish(a.job, a.state, last=a.last)
