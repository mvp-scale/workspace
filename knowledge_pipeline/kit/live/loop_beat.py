"""Keeps one heartbeat, job 'improvement-loop', current so the ledger viewer's Live tab shows the self-improvement loop and its results. Reads projects/world-state/runs/pulse/progress.json and opus_review.json (if present) and the blocked owner task T48 via the viewer data. Run at every loop tick (monitor_pages.py calls it).
    python3 loop_beat.py"""
import json, os, pathlib, sys, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import heartbeat as hb
W = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state/runs/pulse")
P = json.load(open(W / "progress.json")); orf = W / "opus_review.json"; import time; O = json.load(open(orf)) if orf.exists() and time.time() - orf.stat().st_mtime < 86400 else None  # an advisor note older than a day is not the current state
LED = pathlib.Path("/workspace/knowledge_pipeline/.ledger/ledger.jsonl"); L = [json.loads(x) for x in LED.read_text().splitlines()[-400:]]
import datetime as _dt; active = (time.time() - _dt.datetime.strptime(L[-1]["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp() < 1800) or any(json.loads(p.read_text()).get("state") == "running" and not json.loads(p.read_text()).get("service") and json.loads(p.read_text()).get("job") not in ("poller", "health", "improvement-loop") and not str(json.loads(p.read_text()).get("job", "")).startswith("auto-") for p in pathlib.Path("/workspace/knowledge_pipeline/runs-live").glob("*.json"))
cur = next((x["task"] for x in reversed(L) if x.get("kind") == "start"), "none"); lastid = L[-1]["id"]
try: needs = json.loads(urllib.request.urlopen("http://localhost:18766/data", timeout=10).read())["counts"]["needsYou"]
except Exception: needs = None
try: blocked = [a["id"] for a in json.loads(urllib.request.urlopen("http://localhost:18766/data", timeout=10).read())["attention"] if str(a.get("why", "")).startswith("Blocked")]
except Exception: blocked = []
moved = [r for r in P["rows"] if r["change"] in ("moved", "new") and r["kind"] != "bookkeeping"]; flat = [r for r in P["rows"] if r["change"] == "flat"]
last = (O["verdict"] + ". " if O else "") + f"{len(moved)} measures moved, {len(flat)} flat ({'; '.join(r['label'] for r in flat)}); bookkeeping not counted"
nxt = (O.get("next_move_now") or O["next_move"]) if O else "Next ready round from the ledger (ch16 section 2); no advisor note in the last day"
hb.beat("improvement-loop", where="[CPU] [SESS]", task=cur, state=("running" if active else "idle" if needs else "running"), every_s=180, progress=f"ledger {lastid}, task {cur}: {len(moved)} measures moved, {len(flat)} flat" + (" (waiting on the owner)" if needs and not active else ""),
        why="Run the loop (pool, live path, teacher labels, retrain, score, advisor) until five Pulse answers are live and accurate on a CPU. Each round has a prediction first and an independent check after.",
        success="Five answers live, each judged by an outside anchor or validator, with the headline measures (answers live, topic score) moving; the Opus reviewer says the loop is moving and not flat.",
        next=nxt, need=(f"Owner: {len(blocked) or needs} blocked task(s): {', '.join(blocked)}. see the Map tab for what each is waiting on" if needs else "Nothing"), last=last)
print("beat:", last)
