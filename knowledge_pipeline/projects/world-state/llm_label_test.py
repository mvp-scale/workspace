"""Exploratory: can LFM3-1.7B (a small text LLM) reproduce Haiku/Sonnet-style JSON labels from the frozen guideline? Pipeline-only.
Run: PYTHONPATH=/workspace/models/liquid-pkgs HF_HOME=/workspace/data/hf python llm_label_test.py"""
import json, glob, re, sys, time, os, random, numpy as np, torch
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoModelForCausalLM, AutoTokenizer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t41c-lfm3-json-nothink", where="[5090]", task="T10", state="running", why="Can a small text LLM produce Haiku-style JSON labels?", success="Valid JSON 90%+, topic 0.45+", next="Score", need="Nothing", progress="loading", spent=0.0, cap=0.0)
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; TOP = set(sch["topic"]["enum"]); CON = set(sch["conditions"]["items"]["properties"]["condition"]["enum"]); ST = set(sch["story_type"]["enum"])
system = "\n".join(spec["guideline"]); tmpl = spec["input_template"]; PREFILL = '{"topic": "'
def user(i, text): return tmpl.replace("{id}", str(i)).replace("{text}", text)
shots = []
for ex in spec["examples"]: shots += [{"role": "user", "content": user(ex["input"]["id"], ex["input"]["text"])}, {"role": "assistant", "content": json.dumps(ex["output"] if "output" in ex else ex.get("expected"), ensure_ascii=False)}]
hk = {}; sn = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]; random.Random(5).shuffle(vt); S = vt[:400]
tok = AutoTokenizer.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True); tok.padding_side = "left"
t0 = time.time(); model = AutoModelForCausalLM.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval(); load_s = time.time() - t0
prompts = [tok.apply_chat_template([{"role": "system", "content": system}] + shots + [{"role": "user", "content": user(i, pool[i]["text"][:700])}], add_generation_prompt=True, tokenize=False, enable_thinking=False) for i in S]
plen = len(tok(prompts[0]).input_ids); outs = []; t0 = time.time()
for s in range(0, len(S), 8):
    b = tok(prompts[s:s + 8], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad(): g = model.generate(**b, max_new_tokens=220, do_sample=False)
    outs += tok.batch_decode(g[:, b["input_ids"].shape[1]:], skip_special_tokens=True)
    if (s // 8) % 5 == 0: hb.beat("t41c-lfm3-json-nothink", progress=f"{len(outs)}/{len(S)} items, {len(outs) / (time.time() - t0):.2f} items/s")
gen_s = time.time() - t0
def cname(c): return c if isinstance(c, str) else (c.get('condition') if isinstance(c, dict) else None)   # the model sometimes lists plain names
def parse(t):
    m = re.search(r"\{.*\}", t, re.S)
    if not m: return None
    try: j = json.loads(m.group(0))
    except Exception: return None
    return j if isinstance(j, dict) else None
json.dump(outs, open('runs/lfm3_raw_outputs_nothink.json', 'w')); P = [parse(t) for t in outs];
valid = [j is not None and j.get("topic") in TOP and j.get("story_type") in ST and isinstance(j.get("conditions", []), list) for j in P]
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in S]); V = np.array(valid)
topic = np.array([bool(v) and P[k]["topic"] == sn[S[k]]["topic"] for k, v in enumerate(valid)]); story = np.array([bool(v) and P[k]["story_type"] == sn[S[k]]["story_type"] for k, v in enumerate(valid)])
pres_pred = np.array([bool(v) and len(P[k].get("conditions") or []) > 0 for k, v in enumerate(valid)]); pres_true = np.array([bool(sn[i]["conditions"]) for i in S])
pos = [k for k, i in enumerate(S) if sn[i]["conditions"] and valid[k]]; cond1 = np.mean([bool(P[k].get("conditions")) and cname(P[k]["conditions"][0]) in {c["condition"] for c in sn[S[k]]["conditions"]} for k in pos]) if pos else None
res = {"items": len(S), "model_load_s": round(load_s, 1), "prompt_tokens": plen, "seconds": round(gen_s, 1), "items_per_second": round(len(S) / gen_s, 2), "valid_json_share": round(float(V.mean()), 3), "topic_top1_all": round(float(topic.mean()), 3), "story_type_all": round(float(story.mean()), 3),
       "presence_agree_unweighted": round(float((pres_pred == pres_true).mean()), 3), "presence_agree_natural_weighted": round(float((w * (pres_pred == pres_true)).sum() / w.sum()), 3), "condition_top1_on_sonnet_positives": round(float(cond1), 3) if cond1 is not None else None, "n_positives": len(pos), "sample_output": outs[0][:300]}
json.dump(res, open("runs/snapshots/lfm3_json_test_nothink.json", "w"), indent=1); print(json.dumps(res, indent=1)); hb.finish("t41c-lfm3-json-nothink", "done", last=f"valid {res['valid_json_share']}, topic {res['topic_top1_all']}, story {res['story_type_all']}, {res['items_per_second']} items/s", progress=f"{len(S)} items")
