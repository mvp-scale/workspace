"""F-0110 / R-0181 runner (Kaggle): Clef against itself. Per story, the full battery twice: F1 = the engine's own 20-question blocks again (rerun noise), F2 = the same 328 questions regrouped into shuffled 20-question blocks (block-context effect).
Sequential calls per story (clean latency). Compare to the original answers in data/clef-labels/test.jsonl.
  python3 ceiling_run.py IN.jsonl OUT.jsonl --minutes M"""
import os, sys, json, time, argparse, random, hashlib
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob"]
import classify as C, offline as O, backends
b = backends.BACKENDS["clef-flash-q4km"]; O.set_reader(b["url"], b.get("model", ""), b.get("key", ""), "clef-flash-q4km")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--minutes", type=float, default=30); a = ap.parse_args(); t_end = time.time() + 60 * a.minutes
done = set(json.loads(l)["id"] for l in open(a.out)) if os.path.exists(a.out) else set()
def run(state, groups):
    t = time.time(); P = {}
    for ks in groups:
        r = O.call(state, {k: {"type": "noul", "instructions": C.QS[k]} for k in ks}); P.update({k: r[k]["noul"] for k in r})
    return P, round(time.time() - t, 3)
names = list(C.QS); full = [names[j:j + 20] for j in range(0, len(names), 20)]
def regroup(sid):
    n = list(names); random.Random(int(hashlib.md5(sid.encode()).hexdigest()[:8], 16)).shuffle(n); return [n[j:j + 20] for j in range(0, len(n), 20)]
run(next(json.loads(l) for l in open(a.inp))["state"], [full[0]])      # warm-up
for l in open(a.inp):
    r = json.loads(l)
    if r["id"] in done: continue
    if time.time() > t_end: break
    rec = {"id": r["id"]}
    rec["F1"], rec["t1"] = run(r["state"], full); rec["F2"], rec["t2"] = run(r["state"], regroup(r["id"]))
    open(a.out, "a").write(json.dumps(rec) + "\n")
