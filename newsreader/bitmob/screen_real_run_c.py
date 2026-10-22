"""F-0110 job 2 runner (Kaggle): variant C, real Clef calls. Per story, sequential calls on one worker (clean latency): C3 and C7 = shortlisted attribute plus 3 / 7 neighbouring questions of its 20-question block.
  python3 screen_real_run_c.py IN.jsonl OUT.jsonl --minutes M"""
import os, sys, json, time, argparse
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob"]
import classify as C, offline as O, backends
b = backends.BACKENDS["clef-flash-q4km"]; O.set_reader(b["url"], b.get("model", ""), b.get("key", ""), "clef-flash-q4km")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--minutes", type=float, default=30); a = ap.parse_args(); t_end = time.time() + 60 * a.minutes
done = set(json.loads(l)["id"] for l in open(a.out)) if os.path.exists(a.out) else set()
def run(state, groups):
    t = time.time(); P = {}
    for ks in groups:
        r = O.call(state, {k: {"type": "noul", "instructions": C.QS[k]} for k in ks})
        for k in r: P.setdefault(k, r[k]["noul"])      # first call that contains a question gives its answer
    return P, round(time.time() - t, 3)
names = list(C.QS)
run(next(json.loads(l) for l in open(a.inp))["state"], [names[:20]])      # warm-up
for l in open(a.inp):
    r = json.loads(l)
    if r["id"] in done: continue
    if time.time() > t_end: break
    rec = {"id": r["id"]}
    rec["C3"], rec["tC3"] = run(r["state"], r["C3"]); rec["C7"], rec["tC7"] = run(r["state"], r["C7"])
    open(a.out, "a").write(json.dumps(rec) + "\n")
