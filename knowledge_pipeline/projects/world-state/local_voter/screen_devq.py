# Field screen: Gemma 4 (thinking OFF), spec v3b, baseline wording and presence wording B, on the 1,997 devq items. Compared with Sonnet (ws-v2-frozen) devq labels per field. Local, 0 USD.
# usage: VLLM_USE_FLASHINFER_SAMPLER=0 python screen_devq.py
import hashlib, json, os, sys, time, collections
W = "/workspace/knowledge_pipeline/projects/world-state"; sys.path.insert(0, f"{W}/../../kit/live")
import heartbeat as hb
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json")); g0 = spec["guideline"]; g0 = "\n".join(g0) if isinstance(g0, list) else str(g0); anchor = "A condition appears at most once."
RULE = "An item that reports an event of a listed kind having itself occurred (a protest, riot, attack, missile launch, heatwave, flood, storm, fire, outbreak or outage) counts as that condition having changed, because the event is the change; list it. List a condition only if you can point to the words in the item that report it changing."
S = {r["item_id"]: r["label"] for r in J(f"{W}/runs/pulse/devq/labels.jsonl")}; qt = {r["id"]: r["text"] for r in J(f"{W}/runs/pulse/queue_texts.jsonl")}; items = [{"id": i, "text": qt[i]} for i in sorted(S) if i in qt]
hb.beat("t21-field-screen", pid=os.getpid(), where="[5090] local GPU, 450 W", task="T21", state="running", progress=f"{len(items)} items, 2 wordings", why="Field screen at n=2,000: how well does Gemma agree with Sonnet on every Pulse field?", success="A table per field with agreement and 95% range", next="Sonnet rerun for the ceiling; reframe weak fields", need="Nothing", cap=3000)
tpl = spec["input_template"]; ut = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip()
def system(g):
    parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
    for i, ex in enumerate(spec.get("examples", []), 1): parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + ut(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
    return "\n\n".join(parts) + "\n\nReply with the JSON object only."
from vllm import LLM, SamplingParams
llm = LLM(model="/workspace/models/gemma4-26b-nvfp4", max_model_len=16384, gpu_memory_utilization=0.74, trust_remote_code=False, enable_prefix_caching=True, max_num_seqs=64, attention_backend="TRITON_ATTN")
def parse(txt):
    dec = json.JSONDecoder(); best = None; i = txt.find("{")
    while i != -1:
        try:
            o, e = dec.raw_decode(txt, i)
            if isinstance(o, dict) and set(o) == {"topic", "story_type", "claim", "conditions"}: best = o
            i = txt.find("{", e)
        except Exception: i = txt.find("{", i + 1)
    return best
for tag, g in (("base", g0), ("B", g0.replace(anchor, RULE + " " + anchor, 1))):
    sy = system(g); outs = llm.chat([[{"role": "system", "content": sy}, {"role": "user", "content": ut(it)}] for it in items], SamplingParams(temperature=0.0, max_tokens=800, skip_special_tokens=True), chat_template_kwargs={"enable_thinking": False}); OD = f"{W}/runs/pulse/screen_devq_{tag}"; os.makedirs(OD, exist_ok=True); fails = 0
    with open(f"{OD}/labels.jsonl", "w") as f:
        for it, o in zip(items, outs):
            lab = parse(o.outputs[0].text)
            if lab is None: fails += 1; continue
            f.write(json.dumps({"item_id": it["id"], "label": lab, "provenance": {"teacher": "gemma4", "variant": tag, "spec_sha256": hashlib.sha256(sy.encode()).hexdigest(), "thinking": "off"}}, ensure_ascii=False) + "\n")
    print(tag, "done, parse fails", fails, flush=True)
hb.finish("t21-field-screen", "done", last="labels in runs/pulse/screen_devq_base and _B")
