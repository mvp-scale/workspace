"""F-0110 job 2 prep: variant C. For each of the 298 stories already answered by real Clef in variants A/B (same stories, same tune-fit 95% shortlist), build calls that send each shortlisted attribute
(both wordings) together with only K neighbouring questions of its usual 20-question block (K = 3 and 7). A shortlisted attribute already inside an earlier call's window of the same story reuses that call's answer (no extra call).
  /workspace/kev/.venv/bin/python newsreader/bitmob/mh/screen_real_prep_c.py"""
import os, sys, json
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
D = "/workspace/data/diag/screen_real"; names = list(C.QS); pos = {k: i for i, k in enumerate(names)}
done = {json.loads(l)["id"] for l in open(f"{D}/clef_answers_all.jsonl")}
S = [json.loads(l) for l in open(f"{D}/stories.jsonl")]; S = [s for s in S if s["id"] in done]
def window(i0, i1, k):      # question indexes i0..i1 (a unit) plus k neighbours, centred, kept inside the unit's 20-question block
    b = i0 // 20 * 20; lo_b, hi_b = b, min(b + 19, len(names) - 1); n = i1 - i0 + 1; extra = k; left = extra // 2; right = extra - left
    lo = i0 - left; hi = i1 + right
    if lo < lo_b: hi += lo_b - lo; lo = lo_b
    if hi > hi_b: lo -= hi - hi_b; hi = hi_b
    return list(range(max(lo, lo_b), hi + 1))
def calls_for(sk, k):
    units = sorted({(pos[q] // 2 * 2) for q in sk}); calls = []; covered = set()
    for u in units:
        if u in covered and u + 1 in covered: continue
        w = window(u, u + 1, k); calls.append([names[j] for j in w]); covered |= set(w)
    return calls
out = []
for s in S:
    sk = {q for g in s["A"] for q in g}
    s = dict(s); s["C3"] = calls_for(sk, 3); s["C7"] = calls_for(sk, 7); s["ctrl"] = False; out.append(s)
open(f"{D}/stories_c.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in out))
import numpy as np
for v in ("A", "B", "C3", "C7"): print(v, "calls/story", np.mean([len(x[v]) for x in out]), "questions/story", np.mean([sum(map(len, x[v])) for x in out]))
