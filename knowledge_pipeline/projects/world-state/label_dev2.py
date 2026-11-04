"""T20 step 0: Sonnet (frozen spec ws-v2-frozen, batch) labels the 1,988 DEV2 items. Hosted, headline+description only, cap 6 USD, inside the L119 pre-authorisation. Heartbeat job t20-dev2-labels."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; out = H / "runs/pulse/dev2"; out.mkdir(parents=True, exist_ok=True)
beat("t20-dev2-labels", where="[API] Anthropic batch", task="T20", state="running", progress="Sonnet labelling 1,988 fresh items", cap=6.0, why="A fresh, natural (not condition-enriched) development set so the Pulse rates are measured on the whole stream (ledger L435).", success="At least 1,950 labelled, spend under 6 USD", next="Score the engine end to end on DEV2 (score_end2end.py)", need="Nothing")
r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(H / "runs/pulse/dev2_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "6"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
S = [json.loads(l) for l in open(out / "labels.jsonl")] if (out / "labels.jsonl").exists() else []; spend = sum(json.loads(l).get("usd", 0) for l in open(out / "spend.jsonl")) if (out / "spend.jsonl").exists() else 0
finish("t20-dev2-labels", "done" if r.returncode == 0 and len(S) >= 1950 else "failed", spent=round(spend, 2), last=f"{len(S)} labelled, {spend:.2f} USD, exit {r.returncode}")
