"""T31 step 4: Sonnet (frozen spec ws-v2-frozen, batch) labels the 1,500 SEALED items (ids hash a455c630 verified, ledger L440 and L765). Hosted, headline+description only, expected about 2.1 USD, inside the L119 pre-authorisation. Heartbeat job t31-sealed-labels."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; out = H / "runs/pulse/sealed"; out.mkdir(parents=True, exist_ok=True)
beat("t31-sealed-labels", where="[API] Anthropic batch", task="T20", state="running", progress="Sonnet labelling the 1,500 sealed items", cap=24.0, why="A fresh, natural (not condition-enriched) development set so the Pulse rates are measured on the whole stream (ledger L439).", success="At least 1,950 labelled, spend under 4 USD", next="Score the engine end to end on DEVQ (score_end2end.py devq)", need="Nothing")
r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(H / "runs/pulse/sealed_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "24"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
S = [json.loads(l) for l in open(out / "labels.jsonl")] if (out / "labels.jsonl").exists() else []; spend = sum(json.loads(l).get("usd", 0) for l in open(out / "spend.jsonl")) if (out / "spend.jsonl").exists() else 0
finish("t31-sealed-labels", "done" if r.returncode == 0 and len(S) >= 1450 else "failed", spent=round(spend, 2), last=f"{len(S)} labelled, {spend:.2f} USD, exit {r.returncode}")
