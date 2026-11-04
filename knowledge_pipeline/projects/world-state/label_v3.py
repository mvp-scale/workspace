"""T20 revote: Sonnet or Haiku label the same 400 items with the v3 codebook spec (ledger L537, L538). Hosted batch, headline+description only, inside D12.
Usage: python3 label_v3.py sonnet|haiku   Heartbeat job t20-v3-<model>."""
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
who = sys.argv[1]; assert who in ("sonnet", "haiku"); tag = sys.argv[2] if len(sys.argv) > 2 else ""; assert tag in ("", "nt", "b"); sname = {"": "world_state_v3_codebook", "nt": "world_state_v3_nothink", "b": "world_state_v3b_nosize"}[tag]
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"
out = H / (f"runs/pulse/selfcons_v3{tag}" if who == "sonnet" else f"runs/pulse/selfcons_v3{tag}_haiku"); cap = "8" if who == "sonnet" else "4"; job = f"t20-v3{tag}-{who}"
beat(job, where="[API] Anthropic batch", task="T20", state="running", progress=f"{who} labelling 400 items with the v3 codebook", cap=float(cap), why="Test whether boundary tests in the field definitions raise label agreement (alpha) for story type, condition present and size.", success="At least 390 labelled; alpha re-measured", next="Compare alpha with the v2 votes", need="Nothing")
r = subprocess.run([str(PY), str(KIT), "--spec", str(H / f"specs/{sname}_{who}.json"), "--items", str(out / "items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", cap], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
S = [json.loads(l) for l in open(out / "labels.jsonl")] if (out / "labels.jsonl").exists() else []
spend = sum(json.loads(l).get("usd", 0) for l in open(out / "spend.jsonl")) if (out / "spend.jsonl").exists() else 0
finish(job, "done" if r.returncode == 0 and len(S) >= 390 else "failed", spent=round(spend, 2), last=f"{len(S)} labelled, {spend:.2f} USD, exit {r.returncode}")
