"""Clef throughput test: same stories, same 328 engine questions, different questions per call (qpc). Measures time, input tokens, and whether answers change.
Stories: the first N records of data/newsreader/labels/clef-q4km.jsonl (the engine's own input: title + up to 1,200 words), read as the labeller does.
A repeat of qpc=20 gives the noise floor (llama.cpp prompt caching is not bit-exact). Concurrency fixed. Local Clef only.
Run from /workspace/probes/world-engine (kev venv): WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/clef_tune.py <tag> [N] [CONC] [qpc ...]"""
import sys, os, json, time, urllib.request, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
TAG = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 40; CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 6
QPCS = [int(x) for x in sys.argv[4:]] or [20, 20, 41, 82, 110]
URL = os.environ.get("CLEF_URL", "http://127.0.0.1:8018") + "/v1/systemone"; OUT = f"/workspace/data/clef-tune/{TAG}.jsonl"; os.makedirs(os.path.dirname(OUT), exist_ok=True)
recs = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")][:N]
names = list(C.QS)
def call(state, keys):
    body = {"state": state, "questions": {k: {"type": "noul", "instructions": C.QS[k]} for k in keys}, "model": "clef-flash-q4km"}
    with urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600) as r: d = json.load(r)
    return {k: v["noul"] for k, v in d["answers"].items()}, d.get("usage", {}).get("input_tokens", 0)
def story(r, qpc):
    state = f"News item (published 2026-10-19; today is 2026-10-19):\n{r['title']}. {r['text']}"; P, tok = {}, 0
    for j in range(0, len(names), qpc):
        a, t = call(state, names[j:j + qpc]); P.update(a); tok += t
    return P, tok
keys = lambda P: {f"{x['dial']}|{x['direction']}" for x in C.read(P)["readings"]}
base = None
for run, qpc in enumerate(QPCS):
    t0 = time.time()
    with cf.ThreadPoolExecutor(CONC) as ex: res = list(ex.map(lambda r: story(r, qpc), recs))
    el = time.time() - t0; toks = sum(t for _, t in res); Ps = [p for p, _ in res]
    row = {"tag": TAG, "run": run, "qpc": qpc, "stories": len(recs), "seconds": round(el, 1), "stories_per_min": round(len(recs) / el * 60, 1),
           "input_tokens_per_story": toks // len(recs), "calls_per_story": -(-len(names) // qpc)}
    if run == 0: json.dump(Ps, open(OUT.replace(".jsonl", "-P.json"), "w"))      # answers, to compare across server settings
    if base is None: base = Ps
    else:
        d = [abs(a[k] - b[k]) for a, b in zip(Ps, base) for k in a]
        row.update({"vs_first_dP_median": round(sorted(d)[len(d) // 2], 4), "vs_first_dP_p99": round(sorted(d)[int(len(d) * .99)], 3),
                    "readings_identical": sum(keys(a) == keys(b) for a, b in zip(Ps, base))})
    print(json.dumps(row), flush=True); open(OUT, "a").write(json.dumps(row) + "\n")
