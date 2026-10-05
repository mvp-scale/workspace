"""Smoke test for the running world engine (:8112). Fails loudly instead of hanging.
Covers the case that once froze the service: a story placed only in 'Other' (the handler holds the lock; logging it took the same lock).
Run: /workspace/kev/.venv/bin/python smoke.py   (leaves ledger/unplaced.jsonl untouched by deleting the lines it adds)"""
import json, os, sys, time, urllib.request
EP, LOG = "http://127.0.0.1:8112", "/workspace/probes/world-engine/ledger/unplaced.jsonl"
def post(text, mode="event", timeout=30):
    req = urllib.request.Request(EP + "/request", json.dumps({"text": text, "mode": mode}).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))
def step(name, fn, limit):
    t = time.time()
    try: out = fn()
    except Exception as e: print(f"FAIL {name}: {e} after {time.time() - t:.1f}s"); sys.exit(1)
    dt = time.time() - t; print(f"{'ok  ' if dt <= limit else 'SLOW'} {name}: {dt:.2f}s (limit {limit}s)"); return out, dt <= limit
before = sum(1 for _ in open(LOG)) if os.path.exists(LOG) else 0
ok = [step("state", lambda: urllib.request.urlopen(EP + "/state", timeout=10).read(), 1)[1],
      step("normal story", lambda: post("Fuel prices jump 25% in Brazil as refinery outages spread"), 6)[1],
      step("story placed only in Other", lambda: post("asdf qwer zxcv lorem ipsum dolor sit amet"), 6)[1],
      step("state right after", lambda: urllib.request.urlopen(EP + "/state", timeout=10).read(), 1)[1]]
if os.path.exists(LOG):                                    # remove the test lines we added to the review log
    keep = open(LOG).readlines()[:before]; open(LOG, "w").writelines(keep)
    if not keep: os.remove(LOG)
print("ALL OK" if all(ok) else "SOME STEPS WERE SLOW"); sys.exit(0 if all(ok) else 2)
