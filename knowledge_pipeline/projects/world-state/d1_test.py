"""Clear-case wording test for LiquidAI/d1-2B on the same 600 items as the Clef and Jev tests. Run with PYTHONPATH=/workspace/models/liquid-pkgs"""
import json, sys, time, os, numpy as np, torch
os.environ.setdefault("HF_HOME", "/workspace/data/hf")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoModel
from sklearn.metrics import roc_auc_score
H0 = os.getcwd(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t38-d1-2b", where="[5090]", task="T10", state="running", why="Is the Liquid d1-2B decision model a better presence voter than Clef and Jev?", success="Best wording AUC 0.85+", next="Decide whether it earns a lane", need="Nothing", progress="loading model", spent=0.0, cap=0.0)
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; V = {r["id"]: r for r in J("runs/clef_vote.jsonl")}; ids = json.load(open("runs/jev_wording_probs.json"))["ids"]
Q = {"A_original": "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count.",
     "B_changed": "Does this item report that something in the real world has risen, fallen, or changed?", "D_main": "Is a real-world change the main subject of this news item?", "E_specific": "Does this item name a specific thing that changed, such as a price, a count, or a rate?"}
t0 = time.time(); model = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda"); load_s = time.time() - t0
def state(i): d = pool[i]["date"] or "2026-10-25"; return f"News item (published {d}; today is {d}):\n{pool[i]['text'][:700]}"
qs = {k: {"type": "noul", "instructions": v} for k, v in Q.items()}; reqs = [(state(i), qs) for i in ids]; out = []; t0 = time.time()
for s in range(0, len(reqs), 16): out += model.system_one_batch(reqs[s:s + 16]); hb.beat("t38-d1-2b", progress=f"{len(out)}/{len(reqs)} items")
batch_s = time.time() - t0; y = np.array([V[i]["haiku"] for i in ids]); res = {"load_s": round(load_s, 1), "items": len(ids), "seconds_for_600x4_questions": round(batch_s, 1)}
cols = {k: np.array([o["answers"][k]["noul"] for o in out]) for k in Q}
for k, v in cols.items(): res[k] = {"auc_vs_clear_label": round(float(roc_auc_score(y, v)), 3), "agree_at_0.5": round(float(((v > .5).astype(int) == y).mean()), 3), "yes_rate": round(float((v > .5).mean()), 3)}
# single-question latency on the GPU
one = {"A_original": qs["A_original"]}; ts = []
for i in ids[:60]: a = time.perf_counter(); model.system_one(state(i), one); torch.cuda.synchronize(); ts.append((time.perf_counter() - a) * 1000)
res["gpu_single_question_ms"] = {"p50": round(float(np.percentile(ts, 50)), 1), "p95": round(float(np.percentile(ts, 95)), 1)}
json.dump({"ids": ids, "probs": {k: [round(float(x), 4) for x in v] for k, v in cols.items()}}, open("runs/d1_wording_probs.json", "w")); json.dump(res, open("runs/snapshots/d1_wording.json", "w"), indent=1)
# one-thread CPU latency, 3 items, fp32
torch.set_num_threads(1); cpu = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.float32).to("cpu"); cs = []
for i in ids[:3]: a = time.perf_counter(); cpu.system_one(state(i), one); cs.append((time.perf_counter() - a) * 1000)
res["cpu_one_thread_single_question_ms_3_items"] = [round(x) for x in cs]; json.dump(res, open("runs/snapshots/d1_wording.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t38-d1-2b", "done", last="; ".join(f"{k[:1]} {v['auc_vs_clear_label']}" for k, v in res.items() if isinstance(v, dict) and 'auc_vs_clear_label' in v), progress="600 clear items")
