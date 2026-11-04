"""P7b: second-family vote. Sonnet re-labels a stratified slice of items Haiku already labelled, then scores agreement. usage: p7b_vote.py <slice 0|1|2> """
import json, pathlib, random, subprocess, sys, glob, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"; k = int(sys.argv[1])
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk = {}
for f in glob.glob(str(H / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
fl = set((H / "runs/p4/gate_flagged_ids.txt").read_text().split()); rnd = random.Random(20261031)
A = sorted(i for i, l in hk.items() if l["conditions"]); B = sorted(i for i, l in hk.items() if not l["conditions"] and i in fl); C = sorted(i for i, l in hk.items() if not l["conditions"] and i not in fl)
for g in (A, B, C): rnd.shuffle(g)
ids = A[:600] + B[:600] + C[:600]; mine = ids[k * 600:(k + 1) * 600] if False else A[k * 200:(k + 1) * 200] + B[k * 200:(k + 1) * 200] + C[k * 200:(k + 1) * 200]
out = H / f"runs/p7b/slice{k}"; out.mkdir(parents=True, exist_ok=True); pool = {r["id"]: r for r in J(H / "data/pool_train.jsonl")}
(out / "items.jsonl").write_text("".join(json.dumps(pool[i]) + "\n" for i in mine))
beat(f"p7b-slice{k}", where="[CPU]+[API]", task="T8", state="running", progress="Sonnet re-labelling 600 items Haiku already labelled", cap=10.0, why="A second model family checks Haiku's labels; labels both agree on are the safest to train on", success="Rejects under 2%; topic agreement 0.82-0.87, story type 0.90-0.95, condition overlap 0.60-0.75", next="Score agreement on all slices, then export agreed labels", need="Nothing")
subprocess.run([str(PY), str(KIT), "--spec", str(H / "specs/world_state_v2_frozen_sonnet.json"), "--items", str(out / "items.jsonl"), "--out", str(out), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "10"], stdout=open(out / "run.log", "w"), stderr=subprocess.STDOUT)
S = {r["item_id"]: r["label"] for r in J(out / "labels.jsonl")}; spend = sum(r.get("usd", 0) for r in J(out / "spend.jsonl")); ids_ = [i for i in mine if i in S]
cs = lambda l: {c["condition"] for c in l["conditions"]}
y = {"requested": len(mine), "labelled": len(S), "spend_usd": round(spend, 3), "topic_same": round(sum(hk[i]["topic"] == S[i]["topic"] for i in ids_) / max(len(ids_), 1), 3), "story_same": round(sum(hk[i]["story_type"] == S[i]["story_type"] for i in ids_) / max(len(ids_), 1), 3)}
u = [i for i in ids_ if cs(hk[i]) or cs(S[i])]; y["condition_overlap_either_has"] = round(sum(len(cs(hk[i]) & cs(S[i])) / len(cs(hk[i]) | cs(S[i])) for i in u) / max(len(u), 1), 3); y["n_either_has"] = len(u)
(out / "yield.json").write_text(json.dumps(y, indent=1)); finish(f"p7b-slice{k}", "done", spent=round(spend, 2), last=f"topic {y['topic_same']}, story {y['story_same']}, cond {y['condition_overlap_either_has']}"); print(json.dumps(y))
