"""Slot-level fair comparison: slot score = max over its attributes; cut chosen on tune slots at a false-alarm rate; scored against Clef read keys on the frozen test. Usage: diag_slot_eval.py SCORES.npz NAME[+NAME..]..."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
K = json.load(open(f"{W}/kaggle/mh_t1lg24/out/mh/keys.json"))["cond"]; A = [k.split("|") for k in K]
g = {}
for j, (d, dr, i) in enumerate(A): g.setdefault((d, dr), []).append(j)
sl = list(g); YT = Z["cond"][keep] >= C.ATTR_MIN
YTs = np.stack([YT[:, g[s]].any(1) for s in sl], 1)
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
B = np.zeros((len(T), len(sl)), bool)
for n, rr in enumerate(T):
    for k in keys(rr["read"]):
        if k in g: B[n, sl.index(k)] = True
S = np.load(sys.argv[1])
def get(n, pre): return sum(S[pre + x] for x in n.split("+")) / len(n.split("+"))
for name in sys.argv[2:]:
    ST, SS = get(name, "T_"), get(name, "S_")
    STs = np.stack([ST[:, g[s]].max(1) for s in sl], 1); SSs = np.stack([SS[:, g[s]].max(1) for s in sl], 1); neg = np.sort(STs[~YTs])[::-1]; out = []
    for fpr in (0.0005, 0.001, 0.002, 0.004, 0.008):
        c = neg[max(int(fpr * len(neg)), 1) - 1]; P = SSs >= c
        out.append(f"{fpr:.2%}: {(P & B).sum() / B.sum():.1%} fa {(P & ~B).sum() / (~B).sum():.3%}")
    print(name, "positives", int(B.sum()), "|", " | ".join(out), flush=True)
