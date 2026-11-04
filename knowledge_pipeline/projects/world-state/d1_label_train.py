"""T44: d1-2B labels the training items (soft labels). Resumable. Run: PYTHONPATH=/workspace/models/liquid-pkgs HF_HOME=/workspace/data/hf python d1_label_train.py"""
import json, glob, re, sys, time, os, numpy as np, torch
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoModel
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); G = spec["guideline"]; sch = spec["output_schema"]["properties"]; TOP = sch["topic"]["enum"]; CON = sch["conditions"]["items"]["properties"]["condition"]["enum"]
defs = {}
for line in G:
    m = re.match(r"^([a-z_]+): (.*)$", line)
    if m and (m.group(1) in TOP or m.group(1) in CON) and m.group(1) not in defs: defs[m.group(1)] = m.group(2)
topic_crit = {t: defs.get(t, t.replace("_", " "))[:200] for t in TOP}; cond_crit = {c: defs.get(c, c.replace("_", " "))[:230] for c in CON}
story_crit = {"fact": "the item reports something that happened or was announced", "forecast": "the item is mainly a prediction", "opinion": "the item is mainly commentary", "unclear": "none of the above"}
Qs = {"topic": {"type": "choice", "instructions": "Which topic is this news item mainly about?", "criteria": topic_crit}, "story_type": {"type": "choice", "instructions": "What kind of story is this?", "criteria": story_crit},
      "conditions": {"type": "choice", "multiple": True, "instructions": "Which of these conditions does the item report as moving up or down, or gives a real reason to expect to move? A single event is not a trend.", "criteria": cond_crit}}
hk = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); trn = sorted(i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start)
OUT = "runs/d1_train_probs"; os.makedirs(OUT, exist_ok=True); CH = 2000; chunks = [trn[s:s + CH] for s in range(0, len(trn), CH)]
hb.beat("t44-d1-train-labels", where="[5090]", task="T10", state="running", why="d1-2B soft labels for the training items so the CPU student can learn from a second family", success="all training items labelled", next="Train soft-label heads", need="Nothing", progress=f"0/{len(trn)}", spent=0.0, cap=0.0)
m = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda"); t0 = time.time(); done = 0
def state(i): d = pool[i]["date"] or "2026-10-25"; return f"News item (published {d}; today is {d}):\n{pool[i]['text'][:700]}"
for ci, ids in enumerate(chunks):
    path = f"{OUT}/chunk{ci:03d}.npz"
    if os.path.exists(path): done += len(ids); continue
    out = []
    for s in range(0, len(ids), 8): out += m.system_one_batch([(state(i), Qs) for i in ids[s:s + 8]])
    np.savez(path, ids=np.array(ids), topic=np.array([[o_["answers"]["topic"]["probabilities"][t] for t in TOP] for o_ in out], dtype=np.float16), story=np.array([[o_["answers"]["story_type"]["probabilities"][t] for t in story_crit] for o_ in out], dtype=np.float16), cond=np.array([[o_["answers"]["conditions"]["probabilities"][c] for c in CON] for o_ in out], dtype=np.float16))
    done += len(ids); hb.beat("t44-d1-train-labels", progress=f"{done}/{len(trn)} items, {done / max(time.time() - t0, 1):.1f} items/s this session")
hb.finish("t44-d1-train-labels", "done", last=f"{done} items labelled", progress=f"{len(chunks)} chunks in {OUT}")
print("done", done)
