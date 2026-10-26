"""Learning curve with the right objective (binary-trigger logistic heads, frozen e5-small), R-0188. Random subsets of the training bank (3 seeds per fraction); same tune-chosen cut rule (cell false-alarm rate 0.05%).
The soft-ridge curve in diag_blocker.py used the wrong objective. Features: cache written by diag_objective.py (same bank / tune / test order).
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/mh/diag_curve.py /workspace/data/diag/curve_2026-10-23.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
from sklearn.linear_model import LogisticRegression
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; EC = "/tmp/claude-0/-workspace/92c93ae1-7649-4528-80f3-1f86df44d2d8/scratchpad/obj_emb.npz"; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
A = [k.split("|") for k in json.load(open(f"{W}/kaggle/mh_r6c1/out/mh/keys.json"))["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
bank = {}
for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3", "r5"):
    p = f"{W}/clef-labels/{n}.jsonl"
    for l in (open(p) if os.path.exists(p) else []):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
bids = list(bank); YB = np.stack([ck(bank[i]["P"]) for i in bids]); YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN; Yb = trig(YB)
E = np.load(EC); XB, XT, XS = E["XB"], E["XT"], E["XS"]
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
for frac in (0.125, 0.25, 0.5, 1.0):
    res = []
    for seed in (0, 1, 2) if frac < 1 else (0,):
        idx = np.random.default_rng(seed).permutation(len(bids))[: int(frac * len(bids))]; PT = np.full((len(XT), len(A)), -9.0); PS = np.full((len(XS), len(A)), -9.0)
        for j in range(len(A)):
            if Yb[idx, j].sum() < 2: continue
            m = LogisticRegression(C=10, max_iter=2000).fit(XB[idx], Yb[idx, j]); PT[:, j] = m.decision_function(XT); PS[:, j] = m.decision_function(XS)
        c = cut_for(PT, YT, 0.0005); res.append(((PS >= c) & trig(YS)).sum() / trig(YS).sum())
    n = int(frac * len(bids)); log(f"{frac:.1%} of the bank ({n} stories, {int(Yb[:n].sum())}+ trigger cells): test caught {np.mean(res):.1%} (runs: {', '.join(f'{x:.1%}' for x in res)})")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
