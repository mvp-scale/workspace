"""Exploratory: can the d1-2B decision model reproduce Haiku/Sonnet labels from the frozen guideline? Pipeline-only test, nothing ships.
Run: PYTHONPATH=/workspace/models/liquid-pkgs HF_HOME=/workspace/data/hf python d1_label_test.py"""
import json, glob, re, sys, time, os, pathlib, numpy as np, torch
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoModel
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t39-d1-labels", where="[5090]", task="T10", state="running", why="Can a small local decision model reproduce Haiku/Sonnet labels from the frozen guideline?", success="Topic top-1 0.55+, story 0.80+", next="Score, then the LFM3-1.7B JSON test", need="Nothing", progress="loading", spent=0.0, cap=0.0)
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); G = spec["guideline"]; sch = spec["output_schema"]["properties"]; TOP = sch["topic"]["enum"]; CON = sch["conditions"]["items"]["properties"]["condition"]["enum"]
defs = {}
for line in G:
    m = re.match(r"^([a-z_]+): (.*)$", line)
    if m and (m.group(1) in TOP or m.group(1) in CON) and m.group(1) not in defs: defs[m.group(1)] = m.group(2)
topic_crit = {t: defs.get(t, t.replace("_", " "))[:200] for t in TOP}; cond_crit = {c: defs.get(c, c.replace("_", " "))[:230] for c in CON}
story_crit = {"fact": "the item reports something that happened or was announced", "forecast": "the item is mainly a prediction", "opinion": "the item is mainly commentary", "unclear": "none of the above"}
hk = {}; sn = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]
def state(i): d = pool[i]["date"] or "2026-10-25"; return f"News item (published {d}; today is {d}):\n{pool[i]['text'][:700]}"
Qs = {"topic": {"type": "choice", "instructions": "Which topic is this news item mainly about?", "criteria": topic_crit}, "story_type": {"type": "choice", "instructions": "What kind of story is this?", "criteria": story_crit},
      "conditions": {"type": "choice", "multiple": True, "instructions": "Which of these conditions does the item report as moving up or down, or gives a real reason to expect to move? A single event is not a trend.", "criteria": cond_crit}}
t0 = time.time(); model = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda"); load_s = time.time() - t0
reqs = [(state(i), Qs) for i in vt]; out = []; t0 = time.time()
for s in range(0, len(reqs), 8):
    out += model.system_one_batch(reqs[s:s + 8])
    if (s // 8) % 20 == 0: hb.beat("t39-d1-labels", progress=f"{len(out)}/{len(reqs)} items, {len(out) / (time.time() - t0):.1f} items/s")
gen_s = time.time() - t0
tp = np.array([[o_["answers"]["topic"]["probabilities"][t] for t in TOP] for o_ in out]); ST = list(story_crit); sp_ = np.array([[o_["answers"]["story_type"]["probabilities"][t] for t in ST] for o_ in out]); cp = np.array([[o_["answers"]["conditions"]["probabilities"][c] for c in CON] for o_ in out])
np.savez(H0 / "runs/d1_label_probs.npz", ids=np.array(vt), topic=tp, story=sp_, cond=cp)
ys_t = np.array([sn[i]["topic"] for i in vt]); ys_s = np.array([sn[i]["story_type"] for i in vt]); T_ = np.array(TOP); t2 = np.argsort(-tp, 1)[:, :2]
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); sy = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); mx = cp.max(1)
pos = [k for k, i in enumerate(vt) if sn[i]["conditions"]]; sset = {k: {c["condition"] for c in sn[vt[k]]["conditions"]} for k in pos}; C_ = np.array(CON); ct = np.argsort(-cp, 1)[:, :2]
res = {"model_load_s": round(load_s, 1), "items": len(vt), "seconds": round(gen_s, 1), "items_per_second": round(len(vt) / gen_s, 2), "topic": {"top1": round(float(np.mean(T_[t2[:, 0]] == ys_t)), 3), "top2": round(float(np.mean([ys_t[k] in set(T_[t2[k]]) for k in range(len(vt))])), 3)},
       "story_type_agree": round(float(np.mean(np.array(ST)[sp_.argmax(1)] == ys_s)), 3), "presence_weighted_auc_max_condition_prob": round(float(roc_auc_score(sy, mx, sample_weight=w)), 4),
       "condition_top1_on_sonnet_positives": round(float(np.mean([C_[ct[k, 0]] in sset[k] for k in pos])), 3), "condition_top2": round(float(np.mean([bool({C_[ct[k, 0]], C_[ct[k, 1]]} & sset[k]) for k in pos])), 3), "n_sonnet_positives": len(pos),
       "reference": {"haiku_vs_sonnet": {"topic": 0.824, "story_type": 0.923, "presence": 0.72}, "student_cascade_v3_1": {"topic_top1": 0.716, "topic_top2": 0.857, "story_type": 0.912}}}
json.dump(res, open("runs/snapshots/d1_label_test.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t39-d1-labels", "done", last=f"topic {res['topic']['top1']}/{res['topic']['top2']}, story {res['story_type_agree']}, presence AUC {res['presence_weighted_auc_max_condition_prob']}, {res['items_per_second']} items/s", progress=f"{len(vt)} items")
