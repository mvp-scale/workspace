"""F-0110 step 2 runner (Kaggle): real Clef calls for the screen-then-check design. Per story, one worker, sequential calls (clean latency):
A = only the shortlisted attribute questions (both wordings); B = the full battery's own 20-question blocks that contain a shortlisted attribute; ctrl = full 17-call battery (first stories only).
  python3 screen_real_run.py IN.jsonl OUT.jsonl --minutes M"""
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
        r = O.call(state, {k: {"type": "noul", "instructions": C.QS[k]} for k in ks}); P.update({k: r[k]["noul"] for k in r})
    return P, round(time.time() - t, 3)
names = list(C.QS); full = [names[j:j + 20] for j in range(0, len(names), 20)]
run(next(json.loads(l) for l in open(a.inp))["state"], [full[0]])      # warm-up
for l in open(a.inp):
    r = json.loads(l)
    if r["id"] in done: continue
    if time.time() > t_end: break
    rec = {"id": r["id"]}
    rec["A"], rec["tA"] = run(r["state"], r["A"]); rec["B"], rec["tB"] = run(r["state"], r["B"])
    if r["ctrl"]: rec["F"], rec["tF"] = run(r["state"], full)
    open(a.out, "a").write(json.dumps(rec) + "\n")
