"""Catch vs cell false-alarm rate for saved reader scores (cell level, same tune-cut rule as score_ens.py). Usage: diag_opoint.py SCORES.npz NAME..."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
K = json.load(open(f"{W}/kaggle/mh_t1lg24/out/mh/keys.json")); A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
S = np.load(sys.argv[1])
for name in sys.argv[2:]:
    ST, SS = S["T_" + name], S["S_" + name]; neg = np.sort(ST[~trig(YT)])[::-1]; out = []
    for fpr in (0.0003, 0.0005, 0.0007, 0.0009, 0.0012):
        c = neg[max(int(fpr * len(neg)), 1) - 1]; out.append(f"{fpr*100:.2f}%: {((SS >= c) & trig(YS)).sum() / trig(YS).sum():.1%} (test fa {((SS >= c) & ~trig(YS)).sum() / (~trig(YS)).sum():.3%})")
    print(name, " | ".join(out))
