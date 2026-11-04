"""T21: Sonnet v3b ceiling. Rerun the 399 selfcons items once, and label 601 devq items twice (positives from either labeller plus random negatives), batch, headline+description only, cap 4 USD. Heartbeat t21-sonnet-ceiling."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; D = H / "runs/pulse/ceiling_sonnet"
beat("t21-sonnet-ceiling", where="[API] Anthropic batch", task="T21", state="running", progress="3 batches: 399 rerun + 601 twice", cap=4.0, why="Sonnet versus itself on spec v3b gives the ceiling for every Pulse field.", success="At least 1,550 of 1,601 labelled, spend under 4 USD", next="Compute self-agreement per field; set bars from it", need="Nothing")
ps = []
for name, items in (("rerun399", "items399"), ("a601", "items601"), ("b601", "items601")):
    out = D / name; out.mkdir(exist_ok=True)
    ps.append((name, subprocess.Popen([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v3b_nosize_sonnet.json"), "--items", str(D / (items + ".jsonl")), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", ("7" if name == "rerun399" else "10")], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)))
rc = {n: p.wait() for n, p in ps}; n = 0; spend = 0
for name, _ in ps:
    f = D / name / "labels.jsonl"; n += len(open(f).readlines()) if f.exists() else 0
    s = D / name / "spend.jsonl"; spend += sum(json.loads(l).get("usd", 0) for l in open(s)) if s.exists() else 0
finish("t21-sonnet-ceiling", "done" if all(v == 0 for v in rc.values()) and n >= 1550 else "failed", spent=round(spend, 2), last=f"{n} labelled, {spend:.2f} USD, exit {rc}")
