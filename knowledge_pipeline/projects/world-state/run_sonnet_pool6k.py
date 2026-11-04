"""T21 main loop: label 6,000 pool items with Sonnet v3b (presence-enriched: 707 Gemma-positive + 2,600 keyword hits + topic-stratified rest). Three sequential 2,000-item batches; spend checked between them; owner-approved ceiling 12 USD (ledger L621), stops if spend passes 7 USD before the last batch. Heartbeat t21-sonnet-pool6k."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; D = H / "runs/pulse/sonnet_pool6k"
items = [l for l in open(D / "items.jsonl")]; spend = lambda: sum(json.loads(l).get("usd", 0) for p in D.glob("part*/spend.jsonl") for l in open(p))
beat("t21-sonnet-pool6k", where="[API] Anthropic batch", task="T21", state="running", progress="part 1 of 3", cap=12.0, why="Presence, size and topic need Sonnet labels; no cheaper labeller tracks Sonnet (ledger L619).", success="At least 5,800 of 6,000 labelled, spend under 12 USD", next="Retrain the reader on Sonnet rows; score on devq", need="Nothing")
rc = []
for k in range(3):
    s = spend()
    if k == 2 and s > 7: break
    out = D / f"part{k+1}"; out.mkdir(exist_ok=True); f = D / f"items_part{k+1}.jsonl"; f.write_text("".join(items[k*2000:(k+1)*2000]))
    r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v3b_nosize_sonnet.json"), "--items", str(f), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "40"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT).returncode
    rc.append(r); beat("t21-sonnet-pool6k", progress=f"part {k+1} of 3 done", last=f"spent {spend():.2f} USD, exit {r}")
n = sum(len(open(p).readlines()) for p in D.glob("part*/labels.jsonl")); s = spend()
finish("t21-sonnet-pool6k", "done" if n >= 5800 and s < 12 and not any(rc) else "failed", spent=round(s, 2), last=f"{n} labelled, {s:.2f} USD, exits {rc}")
