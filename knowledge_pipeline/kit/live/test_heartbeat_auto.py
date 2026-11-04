"""Test: an unregistered (auto-) process that ends is archived as 'lost', a registered job that dies is still 'failed'. Uses a temp dir. python3 test_heartbeat_auto.py"""
import json, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import heartbeat as hb
t = pathlib.Path(tempfile.mkdtemp()); hb.DIR = t; hb.HIST = t / "hist.jsonl"
hb.beat("auto-run-999999", pid=999999, state="running", where="[CPU]", task="?"); hb.beat("real-job", pid=999998, state="running", where="[CPU]", task="T21")
hb.watch_pids(); H = {json.loads(l)["job"]: json.loads(l) for l in open(hb.HIST)}
assert H["auto-run-999999"]["state"] == "lost", H; assert H["real-job"]["state"] == "failed", H; print("PASS: auto- job -> lost, registered job -> failed")
