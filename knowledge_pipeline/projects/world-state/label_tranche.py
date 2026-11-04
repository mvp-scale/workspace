"""T20 overnight Phase B: Sonnet labels 10,000 random training-period items in 4 chunks of 2,500, abort if actual spend passes 18 USD. Hosted batch, headline+description only, inside the L119 pre-authorisation (owner told). Heartbeat t20-tranche with pid."""
import json, os, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; base = H / "runs/pulse/tranche"
def spent(): return sum(json.loads(l).get("usd", 0) for d in base.glob("c*/spend.jsonl") for l in open(d))
for c in range(4):
    beat("t20-tranche", pid=os.getpid(), where="[API] Anthropic batch", task="T20", state="running", progress=f"chunk {c + 1} of 4 (2,500 items each); spent {spent():.2f} USD", cap=18.0, why="More Sonnet labels for training: the measured slope is about +0.008 per doubling on story type and the same direction on presence (overnight program, Phase B).", success="10,000 labelled, spend under 18 USD", next="Retrain story, topic, presence heads with 16,000 Sonnet labels and read the learning curve", need="Nothing")
    out = base / f"c{c}"; out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(base / f"c{c}_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "60"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
    if r.returncode != 0 or spent() > 18: finish("t20-tranche", "failed", spent=round(spent(), 2), last=f"stopped after chunk {c + 1}: exit {r.returncode}, spent {spent():.2f} USD"); sys.exit(1)
n = sum(sum(1 for _ in open(d)) for d in base.glob("c*/labels.jsonl")); finish("t20-tranche", "done", spent=round(spent(), 2), last=f"{n} labelled, {spent():.2f} USD")
