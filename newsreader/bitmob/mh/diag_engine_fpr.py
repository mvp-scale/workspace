"""Engine-reading catch and false alarms at several tune false-alarm rates, from saved scores. Usage: diag_engine_fpr.py SCORES.npz NAME..."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
K = json.load(open(f"{W}/kaggle/mh_t1lg24/out/mh/keys.json")); A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
S = np.load(sys.argv[1])
for name in sys.argv[2:]:
    ST, SS = S["T_" + name] if "T_" + name in S else sum(S["T_" + n] for n in name.split("+")) / len(name.split("+")), S["S_" + name] if "S_" + name in S else sum(S["S_" + n] for n in name.split("+")) / len(name.split("+"))
    neg = np.sort(ST[~trig(YT)])[::-1]
    for fpr in (0.0005, 0.0007, 0.0009, 0.0011, 0.0013):
        c = neg[max(int(fpr * len(neg)), 1) - 1]; tp = fp = pos = nn = 0
        for n, rr in enumerate(T):
            P = dict(rr["P"])
            for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(SS[n, j] - c + C.ATTR_MIN)
            m = keys(C.read(P)); b = keys(rr["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); nn += 78 - len(b)
        print(f"{name} tune fpr {fpr:.2%}: engine caught {tp/pos:.1%} ({tp}/{pos}) false alarms {fp/nn:.4%}", flush=True)
