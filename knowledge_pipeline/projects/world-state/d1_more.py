"""T43: d1-2B on direction and size; LFM3-1.7B as a plain yes/no scorer via next-token logits. Local GPU, pipeline-only.
Run: PYTHONPATH=/workspace/models/liquid-pkgs HF_HOME=/workspace/data/hf python d1_more.py"""
import json, glob, re, sys, time, os, numpy as np, torch
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t43-more", where="[5090]", task="T10", state="running", why="d1 on direction and size; the small text LLM as a yes/no scorer", success="direction 0.85+, LLM AUC 0.70+", next="Score", need="Nothing", progress="loading", spent=0.0, cap=0.0)
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; CON = np.array(sch["conditions"]["items"]["properties"]["condition"]["enum"]); defs = {}
for line in spec["guideline"]:
    m = re.match(r"^([a-z_]+): (.*)$", line)
    if m and m.group(1) in set(CON) and m.group(1) not in defs: defs[m.group(1)] = m.group(2)
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; sn = {}
for f in glob.glob("runs/p7/*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
D = np.load("runs/d1_label_probs.npz", allow_pickle=True); ids = list(D["ids"]); d1c = CON[D["cond"].argmax(1)]
def state(i): d = pool[i]["date"] or "2026-10-25"; return f"News item (published {d}; today is {d}):\n{pool[i]['text'][:700]}"
# ---- d1 direction and size where its top condition is in Sonnet's set
sel = [k for k, i in enumerate(ids) if sn[i]["conditions"] and d1c[k] in {c["condition"] for c in sn[i]["conditions"]}]
m = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda"); LV = ["minor", "notable", "major", "severe"]
sizes = {"minor": "the change is real but barely noticeable", "notable": "a clear change that people in the place would notice", "major": "wide disruption, mass casualties or crisis-scale effects", "severe": "extreme, a crisis across the place"}
reqs = []
for k in sel:
    c = d1c[k]; dd = defs.get(c, c); up = re.search(r"up = ([^|]*)", dd); dn = re.search(r"down = ([^|]*)", dd)
    q = {"direction": {"type": "choice", "instructions": f"For the condition '{c}', is it moving up or down in this item?", "criteria": {"up": (up.group(1).strip() if up else "increases"), "down": (dn.group(1).strip() if dn else "decreases")}},
         "size": {"type": "choice", "instructions": f"How big is the change in '{c}' that this item reports?", "criteria": sizes}}
    reqs.append((state(ids[k]), q))
out = []
for s in range(0, len(reqs), 8): out += m.system_one_batch(reqs[s:s + 8])
dirs_ok, size_ok, size_w1 = [], [], []; base_up = []
for k, o_ in zip(sel, out):
    sc = next(c for c in sn[ids[k]]["conditions"] if c["condition"] == d1c[k]); pd = max(o_["answers"]["direction"]["probabilities"], key=o_["answers"]["direction"]["probabilities"].get); ps = max(o_["answers"]["size"]["probabilities"], key=o_["answers"]["size"]["probabilities"].get)
    dirs_ok.append(pd == sc["direction"]); base_up.append(sc["direction"] == "up"); sl = min(LV.index(sc["level"]) if sc["level"] in LV else 3, 3); size_ok.append(LV.index(ps) == sl); size_w1.append(abs(LV.index(ps) - sl) <= 1)
res = {"d1_direction_size": {"n": len(sel), "direction_agree_with_sonnet": round(float(np.mean(dirs_ok)), 3), "majority_class_baseline": round(float(max(np.mean(base_up), 1 - np.mean(base_up))), 3), "size_exact": round(float(np.mean(size_ok)), 3), "size_within_one": round(float(np.mean(size_w1)), 3), "reference_linear_student": {"direction": 0.882, "size_within_one": 0.938}, "reference_haiku_vs_sonnet": {"direction": 0.992, "size_within_one": 0.997}}}
del m; torch.cuda.empty_cache(); hb.beat("t43-more", progress="d1 done; text LLM yes/no")
# ---- LFM3-1.7B as a yes/no scorer
V = {r["id"]: r for r in J("runs/clef_vote.jsonl")}; cids = json.load(open("runs/jev_wording_probs.json"))["ids"]; y = np.array([V[i]["haiku"] for i in cids])
Q = {"A_original": "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count.", "D_main": "Is a real-world change the main subject of this news item?"}
tok = AutoTokenizer.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True); tok.padding_side = "left"; l = AutoModelForCausalLM.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval()
def toks(words): return sorted({tok.encode(w, add_special_tokens=False)[0] for w in words})
yes_ids, no_ids = toks(["yes", "Yes", " yes", " Yes", "YES"]), toks(["no", "No", " no", " No", "NO"])
res["lfm3_yes_no"] = {"yes_token_ids": yes_ids, "no_token_ids": no_ids}
for name, q in Q.items():
    P = [tok.apply_chat_template([{"role": "system", "content": "Answer with one word: yes or no."}, {"role": "user", "content": f"News item:\n{pool[i]['text'][:700]}\n\nQuestion: {q}"}], add_generation_prompt=True, tokenize=False, enable_thinking=False) for i in cids]; pr = []; t0 = time.time()
    for s in range(0, len(P), 16):
        b = tok(P[s:s + 16], return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad(): lg = l(**b).logits[:, -1, :].float()
        lp = torch.log_softmax(lg, -1); py = torch.logsumexp(lp[:, yes_ids], -1); pn = torch.logsumexp(lp[:, no_ids], -1); pr += torch.sigmoid(py - pn).cpu().tolist()
    pr = np.array(pr); res["lfm3_yes_no"][name] = {"auc_vs_clear_label": round(float(roc_auc_score(y, pr)), 3), "agree_at_0.5": round(float(((pr > .5).astype(int) == y).mean()), 3), "yes_rate": round(float((pr > .5).mean()), 3), "seconds_600_items": round(time.time() - t0, 1), "reference": {"clef": 0.774, "jev": 0.804}}
json.dump(res, open("runs/snapshots/d1_more.json", "w"), indent=1); print(json.dumps(res, indent=1)); hb.finish("t43-more", "done", last=f"d1 direction {res['d1_direction_size']['direction_agree_with_sonnet']}; LFM3 yes/no AUC {res['lfm3_yes_no']['A_original']['auc_vs_clear_label']}", progress="done")
