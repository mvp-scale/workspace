"""T20: Sonnet labels DEVQ2 (1,593 fresh natural queue items) and HF334 (334 untouched Haiku-flagged pool items). Hosted batch, headline+teaser only (ledger note 'MORE REAL CONDITIONS'). Registers its own heartbeat with pid."""
import json, os, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; base = H / "runs/pulse/more"
beat("t20-more-labels", pid=os.getpid(), where="[API] Anthropic batch", task="T20", state="running", progress="Sonnet labelling 1,593 fresh + 334 flagged items", cap=12.0, why="More real conditions in untouched development data so the which / direction / size rows rest on over 1,000 cases, not 44 (owner question 2026-11-02).", success="At least 1,900 labelled, spend under 5 USD", next="Score the engine on all real conditions (given a real condition), refresh the page rows", need="Nothing")
procs = []
for part in ("devq2", "hf334"):
    out = base / part; out.mkdir(parents=True, exist_ok=True)
    procs.append(subprocess.Popen([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(base / f"{part}_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "40"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT))
codes = [p.wait() for p in procs]; spend = sum(json.loads(l).get("usd", 0) for d in base.glob("*/spend.jsonl") for l in open(d)); n = {d.parent.name: sum(1 for _ in open(d)) for d in base.glob("*/labels.jsonl")}
finish("t20-more-labels", "done" if all(c == 0 for c in codes) else "failed", spent=round(spend, 2), last=f"labels {n}, {spend:.2f} USD, exit {codes}")
