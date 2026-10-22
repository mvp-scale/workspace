"""F-0110 step 2 analysis: readings from real Clef answers on shortlisted attributes + BitMob for the rest, vs stored full-battery readings.
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/screen_real_analyse.py OUT.jsonl"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import classify as C
from mh_common import load
D = "/workspace/data/diag/screen_real"; Z = np.load(f"{D}/prep.npz"); H = Z["H"]; flag = Z["flag"]; idx = Z["idx"]
R = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]
K = json.load(open("/workspace/data/kaggle/mh_r6c1/out/mh/keys.json")) if os.path.exists("/workspace/data/kaggle/mh_r6c1/out/mh/keys.json") else None
if K is None: _, _, K = load("/workspace/data/kaggle/mh_r6c1/out/mh")
A = [k.split("|") for k in K["cond"]]
O = {}
for l in open(sys.argv[1]):
    x = json.loads(l); O[x["id"]] = x
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def rd(n, P_new, newkeys):
    r = R[idx[n]]; P = dict(r["P"])
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(H[n, j])      # BitMob for every attribute...
    for k in newkeys: P[k] = P_new[k]                                                                          # ...then Clef's new answers where asked
    return keys(C.read(P))
def score(name, get):
    tp = fp = pos = neg = same = used = 0; dif = []; secs = []
    for n, i in enumerate(idx):
        r = R[i]
        if r["id"] not in O: continue
        o = O[r["id"]]; P_new, t = get(o); nk = list(P_new); b = keys(r["read"]); m = rd(n, P_new, nk)
        tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b); same += (m == b); used += 1; secs.append(t)
        dif += [abs(P_new[k] - r["P"][k]) for k in nk]
    print(f"{name:34s} stories {used}: readings caught {tp}/{pos} = {tp/max(pos,1):.1%}; false alarms {fp} ({fp/max(neg,1):.4%}); stories with identical readings {same}/{used} = {same/max(used,1):.1%}; Clef seconds/story mean {np.mean(secs):.2f} (median {np.median(secs):.2f}); mean |new-stored| answer {np.mean(dif):.3f}")
score("A shortlisted questions only", lambda o: (o["A"], o["tA"]))
score("B shortlisted 20-question blocks", lambda o: (o["B"], o["tB"]))
# control: Clef's own full-battery rerun (same hardware) vs stored: its run-to-run noise, and the full-battery time
C_ = [o for o in O.values() if "F" in o]
if C_:
    tp = pos = fp = neg = 0
    for o in C_:
        n = int(np.where(np.array([R[i]["id"] for i in idx]) == o["id"])[0][0]); r = R[idx[n]]; P = dict(r["P"]); P.update(o["F"]); m = keys(C.read(P)); b = keys(r["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    print(f"CONTROL full battery rerun on Kaggle vs stored: {len(C_)} stories, readings reproduced {tp}/{pos} = {tp/max(pos,1):.1%}, extra readings {fp}; Clef seconds/story mean {np.mean([o['tF'] for o in C_]):.2f}")
    for nm in ("A", "B"):
        print(f"  same {len(C_)} control stories, variant {nm} seconds/story mean {np.mean([o['t'+nm] for o in C_]):.2f}")
