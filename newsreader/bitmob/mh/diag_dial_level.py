"""Where is the loss: detecting that a dial moves at all (ignore direction) vs the slot (dial and direction). Usage: diag_dial_level.py SCORES.npz NAME"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
K = json.load(open(f"{W}/kaggle/mh_t1lg24/out/mh/keys.json"))["cond"]; A = [k.split("|") for k in K]
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
S = np.load(sys.argv[1]); name = sys.argv[2]; ST, SS = S["T_" + name], S["S_" + name]; YT = Z["cond"][keep] >= C.ATTR_MIN
def lvl(keyf):
    g = {}
    for j, a in enumerate(A): g.setdefault(keyf(a), []).append(j)
    ks = list(g); idx = {k: n for n, k in enumerate(ks)}
    Yt = np.stack([YT[:, g[k]].any(1) for k in ks], 1); St = np.stack([ST[:, g[k]].max(1) for k in ks], 1); Ss = np.stack([SS[:, g[k]].max(1) for k in ks], 1)
    B = np.zeros(Ss.shape, bool)
    for n, rr in enumerate(T):
        for (d, dr) in keys(rr["read"]):
            k = keyf((d, dr, 0))
            if k in idx: B[n, idx[k]] = True
    neg = np.sort(St[~Yt])[::-1]; out = []
    for fpr in (0.0005, 0.001, 0.002, 0.004):
        c = neg[max(int(fpr * len(neg)), 1) - 1]; P = Ss >= c; out.append(f"{fpr:.2%}: {(P & B).sum() / B.sum():.1%} fa {(P & ~B).sum() / (~B).sum():.3%}")
    return f"{len(ks)} labels, {int(B.sum())} positives | " + " | ".join(out)
print("slot (dial+direction):", lvl(lambda a: (a[0], a[1])))
print("dial only (direction ignored):", lvl(lambda a: a[0]))
