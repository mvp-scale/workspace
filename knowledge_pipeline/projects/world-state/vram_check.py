import json, os, sys, time, torch, numpy as np
sys.path.insert(0, "."); os.environ.setdefault("HF_HOME", "/workspace/data/hf")
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; pool = [json.loads(l) for l in open("data/pool_train.jsonl")][:16]
res = {}; base = torch.cuda.memory_allocated()
# d1-2B: weights, then peak during a batch of 8 items x 3 typed questions (same questions as the test)
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; TOP = sch["topic"]["enum"]; CON = sch["conditions"]["items"]["properties"]["condition"]["enum"]
Qs = {"topic": {"type": "choice", "instructions": "Which topic?", "criteria": {t: t for t in TOP}}, "conditions": {"type": "choice", "multiple": True, "instructions": "Which conditions?", "criteria": {c: c for c in CON}}}
m = AutoModel.from_pretrained("LiquidAI/d1-2B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda"); torch.cuda.synchronize(); w = torch.cuda.memory_allocated() - base; torch.cuda.reset_peak_memory_stats()
m.system_one_batch([(r["text"][:700], Qs) for r in pool[:8]]); torch.cuda.synchronize(); res["d1_2B"] = {"weights_gb": round(w / 1e9, 2), "peak_gb_batch8": round((torch.cuda.max_memory_allocated() - base) / 1e9, 2)}
del m; torch.cuda.empty_cache(); base = torch.cuda.memory_allocated()
tok = AutoTokenizer.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True); tok.padding_side = "left"; l = AutoModelForCausalLM.from_pretrained("LiquidAI/LFM3-1.7B", trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval(); torch.cuda.synchronize(); w = torch.cuda.memory_allocated() - base; torch.cuda.reset_peak_memory_stats()
sysmsg = "\n".join(spec["guideline"]); P = [tok.apply_chat_template([{"role": "system", "content": sysmsg}, {"role": "user", "content": r["text"][:700]}], add_generation_prompt=True, tokenize=False, enable_thinking=False) for r in pool[:8]]
b = tok(P, return_tensors="pt", padding=True).to("cuda")
with torch.no_grad(): l.generate(**b, max_new_tokens=60, do_sample=False)
torch.cuda.synchronize(); res["LFM3_1.7B"] = {"weights_gb": round(w / 1e9, 2), "peak_gb_batch8_prompt_%d_tokens" % b["input_ids"].shape[1]: round((torch.cuda.max_memory_allocated() - base) / 1e9, 2)}
res["gpu_total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1); json.dump(res, open("runs/snapshots/vram_check.json", "w"), indent=1); print(json.dumps(res, indent=1))
