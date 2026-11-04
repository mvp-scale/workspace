"""T20 overnight Phase B: active training-period items in 4 chunks of 2,500, abort if actual spend passes 18 USD. Hosted batch, headline+description only, inside the L119 pre-authorisation (owner told). Heartbeat t20-tranche2 with pid."""
import json, os, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; base = H / "runs/pulse/tranche2"
def spent(): return sum(json.loads(l).get("usd", 0) for d in base.glob("c*/spend.jsonl") for l in open(d))
for c in range(4):
    beat("t20-tranche2", pid=os.getpid(), where="[API] Anthropic batch", task="T20", state="running", progress=f"chunk {c + 1} of 4 (2,500 items each); spent {spent():.2f} USD", cap=18.0, why="Active labelling: the 10,000 training-period items the v6b student most suspects contain a condition or is unsure about, so the real-condition examples in training go from about 1,700 to about 5,000 (ledger L482).", success="10,000 labelled, spend under 18 USD", next="Retrain the student with the extra real conditions and compare on DEVQ2 (v6c)", need="Nothing")
    out = base / f"c{c}"; out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(base / f"c{c}_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "60"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
    if r.returncode != 0 or spent() > 18: finish("t20-tranche2", "failed", spent=round(spent(), 2), last=f"stopped after chunk {c + 1}: exit {r.returncode}, spent {spent():.2f} USD"); sys.exit(1)
n = sum(sum(1 for _ in open(d)) for d in base.glob("c*/labels.jsonl")); finish("t20-tranche2", "done", spent=round(spent(), 2), last=f"{n} labelled, {spent():.2f} USD")
