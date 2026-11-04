"""Heartbeat for tag_label.py (B1): every 60 s reads runs/tag_head/label.log and the labels file, updates runs-live/b1-tag-labelling.json, and records the run in the history when the PID is gone."""
import sys, os, time, json, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live")); import heartbeat as hb
PID = int(sys.argv[1]); JOB = "b1-tag-labelling"; W = pathlib.Path(__file__).resolve().parent; LAB = W / "runs/tag_head/labels.jsonl"
alive = lambda: "tag_label.py" in subprocess.run(["ps", "-p", str(PID), "-o", "cmd="], capture_output=True, text=True).stdout
meta = dict(where="[5090] local Clef + [CPU] spaCy", task="T15", why="Label 1,500 full news articles with propose-and-verify so a tag head can be trained and the three encoders compared (ledger L389).",
            success="1,300+ articles labelled, 0 Clef errors; later: tag head loose F1 0.55+ and 0.08 above the plain proposer", next="Train the tag head on leaf, bge-small and Granite (tag_head.py) and score on 300 held-out articles", need="Nothing", cap=3300)
t0 = time.time()
while alive():
    n = sum(1 for _ in open(LAB)) if LAB.exists() else 0
    hb.beat(JOB, state="running", progress=f"{n} of 1500 articles", last=f"{n} labelled, {int(time.time() - t0) // 60} min in", spent=0.0, **meta); time.sleep(60)
n = sum(1 for _ in open(LAB)) if LAB.exists() else 0; cur = hb.beat(JOB, state="done", progress=f"{n} of 1500 articles", last=f"finished with {n} labelled", **meta)
hb.record(JOB, "done", where=meta["where"], task="T10", started=cur["started"], progress=cur["progress"], last=cur["last"], why=meta["why"], success=meta["success"], next=meta["next"], spent=0.0)
