"""T20 traits pilot: Sonnet x2 and Haiku x2 on 150 DEVQ items with the 51-question bare wording (ledger L451). Hosted batch, headline+teaser only. Heartbeat job t20-traits-pilot."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; base = H / "runs/pulse/traits_pilot"
beat("t20-traits-pilot", where="[API] Anthropic batch", task="T20", state="running", progress="4 batches (Sonnet x2, Haiku x2), 150 items each", cap=6.0, why="Test the 51 draft trait questions per model before any bulk labelling (decision D6).", success="Per question: valid replies, self-agreement within one step 0.90+ (Sonnet), Sonnet-Haiku 0.80+", next="Score per question and group; reword failing questions", need="Nothing")
procs = []
for m in ("sonnet", "haiku"):
    for r in (1, 2):
        out = base / f"{m}_r{r}"; out.mkdir(parents=True, exist_ok=True)
        procs.append(subprocess.Popen([str(PY), str(KIT), "--spec", str(H / f"specs/traits_v1_{m}.json"), "--items", str(base / "items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "6"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT))
codes = [p.wait() for p in procs]; spend = 0.0
for d in base.glob("*_r*/spend.jsonl"): spend += sum(json.loads(l).get("usd", 0) for l in open(d))
n = {d.parent.name: sum(1 for _ in open(d)) for d in base.glob("*_r*/labels.jsonl")}
finish("t20-traits-pilot", "done" if all(c == 0 for c in codes) else "failed", spent=round(spend, 2), last=f"labels {n}, {spend:.2f} USD, exit {codes}")
