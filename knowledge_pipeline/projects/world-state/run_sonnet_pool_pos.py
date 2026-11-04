"""T21 round 9: Sonnet v3b labels for the 3,000 pool items the fine-tuned leaf presence model ranks most likely to show a changing condition. Two sequential 1,500-item batches; owner yes 2026-11-03 for ~4.54 USD est (ledger L632); skips part 2 if part 1 spend passes 4 USD. Heartbeat t21-sonnet-pool-pos."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; D = H / "runs/pulse/sonnet_pool_pos"
items = [l for l in open(D / "items.jsonl")]; spend = lambda: sum(json.loads(l).get("usd", 0) for p in D.glob("part*/spend.jsonl") for l in open(p))
beat("t21-sonnet-pool-pos", where="[API] Anthropic batch", task="T21", state="running", progress="part 1 of 2", cap=6.0, why="Presence alpha rises ~0.06 per doubling of Sonnet-labelled data; targeted positives are the cheapest way to double positives.", success="At least 2,900 of 3,000 labelled, spend under 6 USD", next="Retrain presence head on old + new rows; score on 601 vs Sonnet v3b", need="Nothing")
rc = []
for k in range(2):
    if k == 1 and spend() > 4: break
    out = D / f"part{k+1}"; out.mkdir(exist_ok=True); f = D / f"items_part{k+1}.jsonl"; f.write_text("".join(items[k*1500:(k+1)*1500]))
    r = subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v3b_nosize_sonnet.json"), "--items", str(f), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "40"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT).returncode
    rc.append(r); beat("t21-sonnet-pool-pos", progress=f"part {k+1} of 2 done", last=f"spent {spend():.2f} USD, exit {r}")
n = sum(len(open(p).readlines()) for p in D.glob("part*/labels.jsonl")); s = spend()
finish("t21-sonnet-pool-pos", "done" if n >= 2900 and s < 6 and not any(rc) else "failed", spent=round(s, 2), last=f"{n} labelled, {s:.2f} USD, exits {rc}")
