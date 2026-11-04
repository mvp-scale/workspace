# T21 reframing C: Gemma 4 (thinking OFF) answers a per-condition checklist (none/up/down for every condition id) using the v3b guideline text; presence = any non-none. Scored on the 601 devq items vs Sonnet v3b (a601, b601).
# usage: VLLM_USE_FLASHINFER_SAMPLER=0 python reframe_checklist.py
import hashlib, json, os, sys
W = "/workspace/knowledge_pipeline/projects/world-state"; sys.path.insert(0, f"{W}/../../kit/live")
import heartbeat as hb
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json")); g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
KINDS = spec["output_schema"]["properties"]["conditions"]["items"]["properties"]["condition"]["enum"]
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; items = J(f"{W}/runs/pulse/ceiling_sonnet/items601.jsonl")
A = {r["item_id"]: bool(r["label"]["conditions"]) for r in J(f"{W}/runs/pulse/ceiling_sonnet/a601/labels.jsonl")}; B = {r["item_id"]: bool(r["label"]["conditions"]) for r in J(f"{W}/runs/pulse/ceiling_sonnet/b601/labels.jsonl")}
items = [it for it in items if it["id"] in A and it["id"] in B]; OD = f"{W}/runs/pulse/reframe_C"; os.makedirs(OD, exist_ok=True)
hb.beat("t21-presence-reframe-C", pid=os.getpid(), where="[5090] local GPU, 450 W", task="T21", state="running", progress=f"{len(items)} items", why="Does a per-condition checklist (definitions injected per kind) lift Gemma's presence agreement with Sonnet above 0.52?", success="alpha vs Sonnet v3b at or above 0.65", next="If yes, label the pool with it; if no, close the reframing lever", need="Nothing", cap=3600)
system = g.strip() + "\n\nOUTPUT OVERRIDE: do not reply with the four fields above. Reply with ONLY a JSON object that has one key for every condition id in the list: " + ", ".join(KINDS) + ". Each value is 'none', 'up' or 'down'. Use 'none' unless the item reports that condition itself has already changed, as defined above. Most items have all values 'none'."
from vllm import LLM, SamplingParams
llm = LLM(model="/workspace/models/gemma4-26b-nvfp4", max_model_len=16384, gpu_memory_utilization=0.74, trust_remote_code=False, enable_prefix_caching=True, max_num_seqs=64, attention_backend="TRITON_ATTN")
outs = llm.chat([[{"role": "system", "content": system}, {"role": "user", "content": "Item:\n" + it["text"]}] for it in items], SamplingParams(temperature=0.0, max_tokens=600, skip_special_tokens=True), chat_template_kwargs={"enable_thinking": False})
def parse(txt):
    dec = json.JSONDecoder(); i = txt.find("{")
    while i != -1:
        try:
            o, e = dec.raw_decode(txt, i)
            if isinstance(o, dict) and len(o) >= 10: return o
            i = txt.find("{", e)
        except Exception: i = txt.find("{", i + 1)
    return None
def alpha(a, b):
    n = len(a); d = sum(x != y for x, y in zip(a, b)); ny = sum(a) + sum(b); nn = 2 * n - ny; De = 2 * ny * nn / (2 * n * (2 * n - 1)); return round(1 - (d / n) / De, 3)
P = []; ids = []; fails = 0
with open(f"{OD}/labels.jsonl", "w") as f:
    for it, o in zip(items, outs):
        lab = parse(o.outputs[0].text)
        if lab is None: fails += 1; continue
        yes = [k for k, v in lab.items() if v in ("up", "down")]; ids.append(it["id"]); P.append(bool(yes)); f.write(json.dumps({"item_id": it["id"], "kinds": yes}) + "\n")
a = [A[i] for i in ids]; b = [B[i] for i in ids]
res = {"n": len(ids), "parse_fails": fails, "yes_rate": round(sum(P) / len(P), 3), "alpha_vs_A": alpha(P, a), "alpha_vs_B": alpha(P, b), "disagree_A_pct": round(100 * sum(x != y for x, y in zip(P, a)) / len(P), 1), "sonnet_yes_rate": round(sum(a) / len(a), 3)}
json.dump(res, open(f"{OD}/score.json", "w"), indent=1); print(json.dumps(res), flush=True); hb.finish("t21-presence-reframe-C", "done", last=f"alpha {res['alpha_vs_A']}, disagree {res['disagree_A_pct']}%")
