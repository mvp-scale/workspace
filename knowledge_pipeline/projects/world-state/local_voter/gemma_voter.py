# Local gpt-oss-20b voter (Apache-2.0), vLLM offline, Harmony format. Spec v3b. No hosted calls, no trust_remote_code.
# usage: python gptoss_voter.py N_ITEMS off,on
import hashlib, json, os, re, sys, time
W = "/workspace/knowledge_pipeline/projects/world-state"
N = int(sys.argv[1]); modes = sys.argv[2].split(",")
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json"))
items = [json.loads(l) for l in open(f"{W}/runs/pulse/selfcons/items.jsonl")][:N]
g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
tpl = spec["input_template"]
user_text = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip()
parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
for i, ex in enumerate(spec.get("examples", []), 1):
    parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
system = "\n\n".join(parts) + "\n\nReply with the JSON object only."
spec_sha = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
from vllm import LLM, SamplingParams
llm = LLM(model="/workspace/models/gemma4-26b-nvfp4", max_model_len=16384, gpu_memory_utilization=0.85, trust_remote_code=False, enable_prefix_caching=True, max_num_seqs=64, attention_backend="TRITON_ATTN")
def parse(txt):
    dec = json.JSONDecoder(); best = None; i = txt.find("{")
    while i != -1:
        try:
            o, e = dec.raw_decode(txt, i)
            if isinstance(o, dict) and set(o) == {"topic", "story_type", "claim", "conditions"}: best = o
            i = txt.find("{", e)
        except Exception: i = txt.find("{", i + 1)
    return best
info = {}
for mode in modes:
    mt = 6000 if mode == "on" else 800
    sp = SamplingParams(temperature=0.0, max_tokens=mt, skip_special_tokens=True)
    msgs = [[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in items]
    t0 = time.time()
    outs = llm.chat(msgs, sp, chat_template_kwargs={"enable_thinking": mode == "on"})
    dt = time.time() - t0
    od = f"{W}/runs/pulse/selfcons_gemma4_{mode}" if N >= 400 else f"/tmp/claude-0/-workspace/2536dad8-e9e4-4b9d-8605-e63d48cb5ead/scratchpad/gemma4_{mode}_smoke"
    os.makedirs(od, exist_ok=True)
    date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); fails = trunc = 0; toks = 0
    with open(f"{od}/labels.jsonl", "w") as f, open(f"{od}/raw.jsonl", "w") as fr:
        for it, o in zip(items, outs):
            c = o.outputs[0]; toks += len(c.token_ids)
            fr.write(json.dumps({"item_id": it["id"], "raw": c.text, "finish": c.finish_reason}) + "\n")
            if c.finish_reason == "length": trunc += 1
            lab = parse(c.text)
            if lab is None: fails += 1; continue
            f.write(json.dumps({"item_id": it["id"], "label": lab, "stats": {}, "provenance": {"teacher": "gemma4", "model": "nvidia/Gemma-4-26B-A4B-NVFP4", "prompt_version": spec["prompt_version"], "spec_name": spec["name"], "spec_sha256": spec_sha, "date": date, "text_sha256": hashlib.sha256(it["text"].encode("utf-8")).hexdigest(), "mode": "local-vllm", "thinking": mode}}, ensure_ascii=False) + "\n")
    info[mode] = {"n": len(items), "labelled": len(items) - fails, "parse_fail": fails, "truncated": trunc, "seconds": round(dt), "items_per_s": round(len(items) / dt, 2), "mean_out_tokens": round(toks / len(items))}
    print("RESULT", mode, json.dumps(info[mode]), flush=True)
json.dump(info, open(f"{W}/local_voter/run_info_{N}.json", "w"), indent=1)
