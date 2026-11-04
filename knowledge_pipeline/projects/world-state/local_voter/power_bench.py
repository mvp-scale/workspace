# POWER SWEEP (not a labeller; writes no labels). Derived from gemma_pool.py: Gemma 4 26B-A4B (thinking OFF), spec v3b, over data/pool.jsonl. Resumable, appends to labels.jsonl, stops itself after BUDGET_S (1-hour cap).
# usage: python gemma_pool.py
import hashlib, json, os, re, sys, time
W = "/workspace/knowledge_pipeline/projects/world-state"
CHUNK = 2000; LIMITS = [575, 525, 500, 450, 575]
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json"))
items = [json.loads(l) for _, l in zip(range(CHUNK * len(LIMITS)), open(f"{W}/data/pool.jsonl"))]
g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
tpl = spec["input_template"]
user_text = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip()
parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
for i, ex in enumerate(spec.get("examples", []), 1):
    parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
system = "\n\n".join(parts) + "\n\nReply with the JSON object only."
spec_sha = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
import subprocess, threading, statistics
from vllm import LLM, SamplingParams
llm = LLM(model="/workspace/models/gemma4-26b-nvfp4", max_model_len=16384, gpu_memory_utilization=0.74, trust_remote_code=False, enable_prefix_caching=True, max_num_seqs=64, attention_backend="TRITON_ATTN")
sp = SamplingParams(temperature=0.0, max_tokens=800, skip_special_tokens=True)
llm.chat([[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in items[:64]], sp, chat_template_kwargs={"enable_thinking": False})  # warm-up, not counted
q = lambda: [float(x) for x in subprocess.run(["nvidia-smi", "--query-gpu=power.draw,clocks.sm,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split(",")]
res = []
for k, lim in enumerate(LIMITS):
    r = subprocess.run(["nvidia-smi", "-pl", str(lim)], capture_output=True, text=True); print("SET", lim, r.returncode, r.stdout.strip()[:80], r.stderr.strip()[:120], flush=True)
    if r.returncode: break
    ch = items[k * CHUNK:(k + 1) * CHUNK]; samples = []; stop = threading.Event()
    def sample():
        while not stop.is_set(): samples.append(q()); time.sleep(0.5)
    th = threading.Thread(target=sample); th.start(); t0 = time.time()
    outs = llm.chat([[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in ch], sp, chat_template_kwargs={"enable_thinking": False})
    dt = time.time() - t0; stop.set(); th.join()
    busy = [s for s in samples if s[0] > 100]
    toks = sum(len(o.outputs[0].token_ids) for o in outs)
    row = {"limit_w": lim, "items": len(ch), "seconds": round(dt, 1), "items_per_s": round(len(ch) / dt, 2), "out_tok_per_s": round(toks / dt), "mean_w": round(statistics.mean(s[0] for s in busy), 1), "max_w": max(s[0] for s in busy), "mean_sm_mhz": round(statistics.mean(s[1] for s in busy)), "max_temp_c": max(s[2] for s in busy)}
    row["items_per_kj"] = round(len(ch) / (row["mean_w"] * dt / 1000), 2); res.append(row); print("ROW", json.dumps(row), flush=True)
subprocess.run(["nvidia-smi", "-pl", "575"], capture_output=True)
json.dump(res, open(f"{W}/local_voter/power_sweep.json", "w"), indent=1); print("DONE", flush=True)
