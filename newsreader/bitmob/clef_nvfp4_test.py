"""Throughput and agreement test: alpha-x-ai/clef-flash-NVFP4 on vLLM (offline, batched) vs llama.cpp Clef Q4.
Same 20 stories, state text and 20-question grouping as data/clef-tune/srv-base-np8-ub16k-P.json (clef_tune.py).
Run with the vLLM 0.30 env:  /workspace/models/cygnet-venv/bin/python newsreader/bitmob/clef_nvfp4_test.py [CHUNK] [GPU_UTIL]"""
import sys, os, json, time, torch
sys.path.insert(0, "/workspace/data/models/clef-flash-nvfp4-alpha")
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
CHUNK = int(sys.argv[1]) if len(sys.argv) > 1 else 68; UTIL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
MODEL = sys.argv[3] if len(sys.argv) > 3 else "/workspace/data/models/clef-flash-nvfp4-alpha"; TAG = sys.argv[4] if len(sys.argv) > 4 else "nvfp4"
ENG = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
QPC = int(os.environ.get("QPC", "20")); REF = os.environ.get("REF", "/workspace/data/clef-tune/bf16.json")      # questions per call; bf16 reference with the same grouping      # extra vLLM engine settings, e.g. {"max_num_batched_tokens": 65536}
import classify as C
from clef_vllm import ClefVLLM
LOG = "/workspace/data/clef-tune/tune.log"
def log(m): line = f"{time.strftime('%F %T')}  {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")
recs = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")][:20]
names = list(C.QS)
reqs, index = [], []
for s, r in enumerate(recs):
    state = f"News item (published 2026-10-19; today is 2026-10-19):\n{r['title']}. {r['text']}"
    for j in range(0, len(names), QPC):
        ks = names[j:j + QPC]
        reqs.append({"state": state, "questions": {k: {"type": "noul", "instructions": C.QS[k]} for k in ks}}); index.append((s, ks))
t0 = time.time(); clef = ClefVLLM(MODEL, gpu_memory_utilization=UTIL, **ENG); log(f"[{TAG}] model loaded in {time.time() - t0:.0f}s (gpu_memory_utilization {UTIL}, {ENG})")
clef.probabilities(reqs[:4])      # warm-up
PIPE = os.environ.get("PIPELINE", "0") == "1"      # overlap: the head scores chunk n on a worker thread while vLLM encodes chunk n+1
t0 = time.time(); probs = []
if not PIPE:
    for i in range(0, len(reqs), CHUNK): probs += clef.probabilities(reqs[i:i + CHUNK])
else:
    import concurrent.futures as cf
    def score(enc, outs):
        return [clef.decide(e, o.outputs.data.to(clef.device, torch.bfloat16)) for e, o in zip(enc, outs)]
    futs = []
    with cf.ThreadPoolExecutor(1) as ex:
        for i in range(0, len(reqs), CHUNK):
            part = reqs[i:i + CHUNK]; enc = [clef.encode(r) for r in part]
            outs = clef.llm.encode([clef._prompt(r, e) for r, e in zip(part, enc)], pooling_task="token_embed", use_tqdm=False)
            futs.append(ex.submit(score, enc, outs))
        for f in futs: probs += f.result()
el = time.time() - t0
P = [dict() for _ in recs]
for (s, ks), p in zip(index, probs):
    for k in ks: P[s][k] = float(p[k]["true"]) if isinstance(p[k], dict) else float(p[k])
base = json.load(open("/workspace/data/clef-tune/srv-base-np8-ub16k-P.json"))
keys = lambda Q: {f"{x['dial']}|{x['direction']}" for x in C.read(Q)["readings"]}
d = sorted(abs(a[k] - b[k]) for a, b in zip(P, base) for k in a)
out = {"qpc": QPC, "tokens_per_story_est": None, "pipeline": PIPE, "tag": TAG, "engine": ENG, "stories": len(recs), "requests": len(reqs), "chunk": CHUNK, "seconds": round(el, 1), "stories_per_min": round(len(recs) / el * 60, 1),
       "dP_median": round(d[len(d) // 2], 4), "dP_p99": round(d[int(len(d) * .99)], 3), "readings_identical": sum(keys(a) == keys(b) for a, b in zip(P, base))}
ref = REF
if not TAG.startswith("bf16") and os.path.exists(ref):
    R = json.load(open(ref))["P"]; d2 = sorted(abs(a[k] - b[k]) for a, b in zip(P, R) for k in a)
    out.update({"vs_bf16_dP_median": round(d2[len(d2) // 2], 4), "vs_bf16_readings_identical": sum(keys(a) == keys(b) for a, b in zip(P, R))})
json.dump({"result": out, "P": P}, open(f"/workspace/data/clef-tune/{TAG}.json", "w")); log(f"[{TAG}] {json.dumps(out)}")
