# Pool labeller: Qwen3.6 27B NVFP4 (thinking OFF), only pool items that have NO Sonnet label (label store), as the second local voter, spec v3b, over data/pool.jsonl. Resumable, appends to labels.jsonl, stops itself after BUDGET_S (1-hour cap).
# usage: python gemma_pool.py
import hashlib, json, os, re, sys, time
W = "/workspace/knowledge_pipeline/projects/world-state"
BUDGET_S = 3000; CHUNK = 2000
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json"))
OD = f"{W}/runs/pulse/suiteM/{os.environ['LV_OUT']}"; os.makedirs(OD, exist_ok=True)
done = {json.loads(l)["item_id"] for l in open(f"{OD}/raw.jsonl")} if os.path.exists(f"{OD}/raw.jsonl") else set()
sn = {json.loads(l)["item_id"] for l in open(f"{W}/runs/label_store/labels.jsonl") if '"family": "sonnet"' in l}
items = [it for it in map(json.loads, open(f"{W}/runs/pulse/suiteM/items.jsonl")) if it["id"] not in done]
g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
tpl = spec["input_template"]
user_text = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip()
parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
for i, ex in enumerate(spec.get("examples", []), 1):
    parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
system = "\n\n".join(parts) + "\n\nReply with the JSON object only."
spec_sha = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
def main():
    from vllm import LLM, SamplingParams
    llm = LLM(model=os.environ["LV_MODEL"], max_model_len=12288, gpu_memory_utilization=0.80, trust_remote_code=False, enable_prefix_caching=True, max_num_seqs=32, attention_backend="TRITON_ATTN")
    def parse(txt):
        dec = json.JSONDecoder(); best = None; i = txt.find("{")
        while i != -1:
            try:
                o, e = dec.raw_decode(txt, i)
                if isinstance(o, dict) and set(o) == {"topic", "story_type", "claim", "conditions"}: best = o
                i = txt.find("{", e)
            except Exception: i = txt.find("{", i + 1)
        return best
    sp = SamplingParams(temperature=0.0, max_tokens=800, skip_special_tokens=True)
    t0 = time.time(); n = fails = 0
    print("TODO", len(items), "already", len(done), flush=True)
    for s in range(0, len(items), CHUNK):
        if time.time() - t0 > BUDGET_S: print("BUDGET STOP", flush=True); break
        ch = items[s:s + CHUNK]
        outs = llm.chat([[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in ch], sp, chat_template_kwargs={"enable_thinking": False})
        date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(f"{OD}/labels.jsonl", "a") as f, open(f"{OD}/raw.jsonl", "a") as fr:
            for it, o in zip(ch, outs):
                c = o.outputs[0]
                fr.write(json.dumps({"item_id": it["id"], "raw": c.text, "finish": c.finish_reason}) + "\n")
                lab = parse(c.text)
                if lab is None: fails += 1; continue
                f.write(json.dumps({"item_id": it["id"], "label": lab, "stats": {}, "provenance": {"teacher": "qwen", "model": "nvidia/Qwen3.6-27B-NVFP4", "prompt_version": spec["prompt_version"], "spec_name": spec["name"], "spec_sha256": spec_sha, "date": date, "text_sha256": hashlib.sha256(it["text"].encode("utf-8")).hexdigest(), "mode": "local-vllm", "thinking": "off"}}, ensure_ascii=False) + "\n")
        n += len(ch); print("PROGRESS", n, "of", len(items), "fails", fails, "s", round(time.time() - t0), flush=True)
    print("DONE", n, "fails", fails, flush=True)

if __name__ == '__main__':
    main()