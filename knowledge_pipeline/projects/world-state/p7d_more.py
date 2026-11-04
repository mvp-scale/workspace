"""P7 chunk: label a random slice of the P4 sample with Haiku under the frozen guideline, then score it. usage: p7_chunk.py <n> <name> [cap_usd] [offset]  (chunks with different offsets are disjoint and can run in parallel). More-items variant: draws from ALL unlabelled pool_train items."""
import json, pathlib, random, subprocess, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"
n, name = int(sys.argv[1]), sys.argv[2]; cap = sys.argv[3] if len(sys.argv) > 3 else "2"; off = int(sys.argv[4]) if len(sys.argv) > 4 else 0; out = H / "runs/p7" / name; out.mkdir(parents=True, exist_ok=True)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
ids = [json.loads(l)["id"] for l in open(H / "data/pool_train.jsonl", encoding="utf-8")]; ids = list(dict.fromkeys(ids)); done = set()
for d in (H / "runs/p7").glob("*/labels.jsonl"): done |= {r["item_id"] for r in J(d)}
todo = [i for i in ids if i not in done]; random.Random(20261031).shuffle(todo); pick = todo[off:off + n]
pool = {r["id"]: r for r in J(H / "data/pool_train.jsonl")}; (out / "items.jsonl").write_text("".join(json.dumps(pool[i]) + "\n" for i in pick))
beat(f"p7-{name}", where="[CPU]+[API]", task="T10", state="running", progress=f"Haiku labelling {n} sample items (one batch)", cap=float(cap), why="Bulk labels are what the student model learns from; this chunk also proves 30-per-condition for T5", success="Cost 0.40-0.60 USD, rejects at most 2%, at least 30 of 38 conditions on track for 30 examples in the full 25,000", next="Score it, then label the rest in chunks and start the export", need="Nothing")
subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_haiku.json"), "--items", str(out / "items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", cap], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
L = J(out / "labels.jsonl"); spend = sum(r.get("usd", 0) for r in J(out / "spend.jsonl")); rej = len(J(out / "rejects.jsonl")) if (out / "rejects.jsonl").exists() else 0
cc = collections.Counter(c["condition"] for r in L for c in r["label"]["conditions"]); wc = sum(1 for r in L if r["label"]["conditions"])
scale = 25000 / max(len(L), 1); on_track = sum(1 for k, v in cc.items() if v * scale >= 30)
y = {"labelled": len(L), "requested": n, "spend_usd": round(spend, 3), "rejects": rej, "reject_rate": round(rej / n, 4), "with_condition": round(wc / max(len(L), 1), 3),
     "per_condition": dict(cc.most_common()), "conditions_seen": len(cc), "conditions_with_30_in_chunk": sum(1 for v in cc.values() if v >= 30), "conditions_on_track_for_30_in_25k": on_track}
(out / "yield.json").write_text(json.dumps(y, indent=1)); finish(f"p7-{name}", "done", spent=round(spend, 2), last=f"{len(L)} labelled; {on_track} of 38 conditions on track for 30 in 25k")
print(json.dumps({k: v for k, v in y.items() if k != "per_condition"}, indent=1))
