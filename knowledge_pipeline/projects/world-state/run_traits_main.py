"""T20 traits step: Sonnet labels the 51 traits on 1,500 training-period pool items (TRAIN) and 1,000 DEVQ items (EVAL). Hosted batch, headline+teaser only (ledger L454). Heartbeat job t20-traits-main."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; base = H / "runs/pulse/traits_main"
beat("t20-traits-main", where="[API] Anthropic batch", task="T20", state="running", progress="Sonnet 51-trait labels: 1,500 train + 1,000 eval", cap=25.0, why="Train and score CPU heads for the 51 trait questions against Sonnet (ledger L454).", success="At least 2,400 labelled, spend under 10 USD", next="Train heads, score per question against the 0.80 and majority-baseline bar", need="Nothing")
procs = []
for part in ("train", "eval"):
    out = base / part; out.mkdir(parents=True, exist_ok=True)
    procs.append(subprocess.Popen([str(PY), str(KIT), "--spec", str(H / "specs/traits_v1_sonnet.json"), "--items", str(base / f"{part}_items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "25"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT))
codes = [p.wait() for p in procs]; spend = sum(json.loads(l).get("usd", 0) for d in base.glob("*/spend.jsonl") for l in open(d)); n = {d.parent.name: sum(1 for _ in open(d)) for d in base.glob("*/labels.jsonl")}
finish("t20-traits-main", "done" if all(c == 0 for c in codes) else "failed", spent=round(spend, 2), last=f"labels {n}, {spend:.2f} USD, exit {codes}")
