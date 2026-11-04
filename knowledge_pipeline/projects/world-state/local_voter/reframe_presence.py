# Presence reframing test: Gemma 4 (thinking OFF) on the 399 selfcons items with spec v3b plus ONE guideline change (variant name in argv[1]). Scores presence against Sonnet v3b on the same items.
# usage: VLLM_USE_FLASHINFER_SAMPLER=0 python reframe_presence.py A
import hashlib, json, os, sys, time
W = "/workspace/knowledge_pipeline/projects/world-state"; V = sys.argv[1]; sys.path.insert(0, f"{W}/../../kit/live")
import heartbeat as hb
EVID = " List a condition only if you can point to the words in the item that report it changing."
RULES = {"B": None, "A": " An item that reports an event of a listed kind having itself occurred (a protest, riot, attack, missile launch, heatwave, flood, storm, fire, outbreak or outage) counts as that condition having changed, because the event is the change; list it."}
spec = json.load(open(f"{W}/specs/world_state_v3b_nosize_sonnet.json")); g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
anchor = "A condition appears at most once."; assert anchor in g; rule = RULES["A"].strip() + (EVID if V == "B" else ""); g = g.replace(anchor, rule + " " + anchor, 1)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; S = {r["item_id"]: r["label"] for r in J(f"{W}/runs/pulse/selfcons_v3b/labels.jsonl")}; G0 = {r["item_id"]: r["label"] for r in J(f"{W}/runs/pulse/selfcons_gemma4_off/labels.jsonl")}
pool = {}
for r in J(f"{W}/data/pool.jsonl"): pool.setdefault(r["id"], r)
items = [pool[i] for i in S if i in pool and i in G0]; OD = f"{W}/runs/pulse/reframe_{V}"; os.makedirs(OD, exist_ok=True)
hb.beat("t21-presence-reframe-" + V, pid=os.getpid(), where="[5090] local GPU, 450 W", task="T21", state="running", progress=f"{len(items)} items", why="Does an explicit event-counts rule raise presence agreement with Sonnet?", success="disagreement under 10% and alpha >= 0.667", next="Score on ledger; next reframing", need="Nothing", cap=1800)
tpl = spec["input_template"]; user_text = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip(); parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
for i, ex in enumerate(spec.get("examples", []), 1): parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
system = "\n\n".join(parts) + "\n\nReply with the JSON object only."
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
outs = llm.chat([[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in items], SamplingParams(temperature=0.0, max_tokens=800, skip_special_tokens=True), chat_template_kwargs={"enable_thinking": False})
L = {}; fails = 0
with open(f"{OD}/labels.jsonl", "w") as f:
    for it, o in zip(items, outs):
        lab = parse(o.outputs[0].text)
        if lab is None: fails += 1; continue
        L[it["id"]] = lab; f.write(json.dumps({"item_id": it["id"], "label": lab, "provenance": {"teacher": "gemma4", "variant": V, "spec_sha256": hashlib.sha256(system.encode()).hexdigest(), "thinking": "off"}}, ensure_ascii=False) + "\n")
P = lambda l: bool(l["conditions"])
def alpha(a, b):
    n = len(a); d = sum(x != y for x, y in zip(a, b)); ny = sum(a) + sum(b); nn = 2 * n - ny; De = 2 * ny * nn / (2 * n * (2 * n - 1)); return round(1 - (d / n) / De, 3)
res = {"variant": V, "n": 0, "parse_fails": fails}
for name, A in (("reframed", L), ("baseline", G0)):
    ids = [i for i in L if i in S]; a = [P(A[i]) for i in ids]; b = [P(S[i]) for i in ids]; d = sum(x != y for x, y in zip(a, b)); res[name] = {"n": len(ids), "disagree": d, "disagree_pct": round(100 * d / len(ids), 1), "alpha_vs_sonnet": alpha(a, b), "yes_rate": round(sum(a) / len(a), 3), "missed_vs_sonnet": sum((not x) and y for x, y in zip(a, b)), "extra_vs_sonnet": sum(x and (not y) for x, y in zip(a, b))}
json.dump(res, open(f"{OD}/score.json", "w"), indent=1); print(json.dumps(res), flush=True); hb.finish("t21-presence-reframe-" + V, "done", last=f"disagree {res['reframed']['disagree_pct']}%, alpha {res['reframed']['alpha_vs_sonnet']}")
