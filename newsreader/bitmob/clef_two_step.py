"""Clef two-step screen test (design: docs/research/2026-10-20 Clef two-step screen.md, ledger T-0009).
Model: alpha-x-ai Clef-Flash NVFP4 on vLLM (cygnet-venv). Stories: 100 random (seed 7) + up to 60 enriched for rare keys + the 20 bf16-anchor stories.
Reference A = full 328-question battery, 20/call, same model. Two-step = 88 questions in one call, then flagged keys' attribute questions 20/call.
Run: /workspace/models/cygnet-venv/bin/python newsreader/bitmob/clef_two_step.py [THRESHOLD] [GPU_UTIL]"""
import sys, os, json, time, random, math, collections, torch, concurrent.futures as cf
sys.path.insert(0, "/workspace/data/models/clef-flash-nvfp4-alpha")
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
from clef_vllm import ClefVLLM
TH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.20; UTIL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.70
OUT = f"/workspace/data/clef-tune/two-step-v2-{TH}.json"; LOG = "/workspace/data/clef-tune/tune.log"
def log(m): line = f"{time.strftime('%F %T')}  {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")
ALL = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
kk = lambda rd: {f"{x['dial']}|{x['direction']}" for x in rd if x["direction"] in ("up", "down")}
anchor = ALL[:20]; rest = ALL[20:]; random.Random(7).shuffle(rest); rnd = rest[:100]
cnt = collections.Counter(k for r in rnd for k in kk(r["readings"])); rare = {k for k in map(lambda t: f"{t[0]}|{t[1]}", C.ATTRS) if cnt[k] < 5}
enr = []
for r in rest[100:]:
    if len(enr) >= 60: break
    hit = kk(r["readings"]) & rare
    if hit: enr.append(r); [cnt.update([k]) for k in hit]; rare -= {k for k in rare if cnt[k] >= 5}
stories = [("anchor", r) for r in anchor] + [("random", r) for r in rnd] + [("enriched", r) for r in enr]
META = [k for k in C.QS if not k.startswith("a|")]; ATTRQ = [k for k in C.QS if k.startswith("a|")]
def screen_q(d, dirn): return "Does the story report any of these: " + "; ".join(f"{a['attribute']} ({a['definition'].strip().rstrip('.')})" for a in C.ATTRS[(d, dirn)]) + "?"
SCREEN = {f"s2|{d}|{dirn}": screen_q(d, dirn) for (d, dirn) in C.ATTRS}
state = lambda r: f"News item (published 2026-10-19; today is 2026-10-19):\n{r['title']}. {r['text']}"
req = lambda st, qs: {"state": st, "questions": {k: {"type": "noul", "instructions": q} for k, q in qs.items()}}
clef = ClefVLLM("/workspace/data/models/clef-flash-nvfp4-alpha", gpu_memory_utilization=UTIL)
def run(reqs, chunk=34):      # pipelined: head scores chunk n while vLLM encodes chunk n+1
    out, futs = [], []
    def score(enc, outs): return [clef.decide(e, o.outputs.data.to(clef.device, torch.bfloat16)) for e, o in zip(enc, outs)]
    with cf.ThreadPoolExecutor(1) as ex:
        for i in range(0, len(reqs), chunk):
            part = reqs[i:i + chunk]; enc = [clef.encode(r) for r in part]
            futs.append(ex.submit(score, enc, clef.llm.encode([clef._prompt(r, e) for r, e in zip(part, enc)], pooling_task="token_embed", use_tqdm=False)))
            while len(futs) > 1: out += futs.pop(0).result()      # backpressure: at most 2 chunks of hidden states in host memory (an unbounded queue was OOM-killed)
        for f in futs: out += f.result()
    return [{k: v["true"] for k, v in p.items()} for p in out]
run([req(state(stories[0][1]), {k: C.QS[k] for k in ATTRQ[:20]})])      # warm-up
# Reference A: full battery, 20 per call
t0 = time.time(); reqsA, idxA = [], []
for s, (_, r) in enumerate(stories):
    for j in range(0, len(C.QS), 20): ks = list(C.QS)[j:j + 20]; reqsA.append(req(state(r), {k: C.QS[k] for k in ks})); idxA.append(s)
PA = [dict() for _ in stories]
for s, p in zip(idxA, run(reqsA)): PA[s].update(p)
tA = time.time() - t0
# Two-step
t0 = time.time()
step1 = run([req(state(r), {**{k: C.QS[k] for k in META}, **SCREEN}) for _, r in stories])
reqsB, idxB = [], []
for s, (_, r) in enumerate(stories):
    flagged = [k for k in SCREEN if step1[s][k] >= TH]
    qs = {q for k in flagged for q in ATTRQ if q.startswith("a|" + k[3:] + "|")}
    names = list(C.QS)
    for j in range(0, len(names), 20):      # v2: resend the full battery's own 20-question blocks that hold a flagged attribute (grouping preserved)
        block = names[j:j + 20]
        if qs & set(block): reqsB.append(req(state(r), {k: C.QS[k] for k in block})); idxB.append(s)
PB = [{**{k: step1[s][k] for k in META}, **{k: 0.0 for k in ATTRQ}} for s in range(len(stories))]
for s, p in zip(idxB, run(reqsB)): PB[s].update(p)
tB = time.time() - t0
keys = lambda P: {f"{x['dial']}|{x['direction']}" for x in C.read(P)["readings"] if x["direction"] in ("up", "down")}
def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n); return [round(c - h, 3), round(c + h, 3)]
res = {"threshold": TH, "stories": {g: sum(1 for x, _ in stories if x == g) for g in ("anchor", "random", "enriched")}}
for g in ("random", "enriched", "anchor"):
    ix = [i for i, (x, _) in enumerate(stories) if x == g]
    pos = [(i, k) for i in ix for k in keys(PA[i])]; hit = sum(1 for i, k in pos if step1[i]["s2|" + k] >= TH)
    res[g] = {"positives_A": len(pos), "screen_recall": round(hit / len(pos), 3) if pos else None, "recall_ci95": wilson(hit, len(pos)),
              "readings_identical_A": sum(keys(PA[i]) == keys(PB[i]) for i in ix), "of": len(ix)}
miss = collections.Counter(); per = collections.Counter()
for i, (x, _) in enumerate(stories):
    for k in keys(PA[i]):
        per[k] += 1
        if step1[i]["s2|" + k] < TH: miss[k] += 1
res["missed"] = [{"key": k, "missed": m, "of": per[k]} for k, m in miss.most_common()]
n = len(stories); res["speed"] = {"full_stories_per_min": round(n / tA * 60, 1), "two_step_stories_per_min": round(n / tB * 60, 1),
    "requests_full": len(reqsA), "requests_two_step": n + len(reqsB), "flagged_keys_per_story": round(sum(1 for s in range(n) for k in SCREEN if step1[s][k] >= TH) / n, 1)}
bf = json.load(open("/workspace/data/clef-tune/bf16.json"))["P"]
res["anchor_vs_bf16"] = {"two_step_identical": sum(keys(PB[i]) == keys(bf[i]) for i in range(20)), "full_identical": sum(keys(PA[i]) == keys(bf[i]) for i in range(20)), "of": 20}
json.dump({"result": res, "PA": PA, "PB": PB, "step1": step1}, open(OUT, "w"))
log(f"[two-step v2 {TH}] {json.dumps({k: v for k, v in res.items() if k != 'missed'})}"); log(f"[two-step v2 {TH}] missed: {json.dumps(res['missed'][:12])}")
