"""T20 round 1a: chain frontier from the raw scores (reach_curve.py). Cuts chosen on half A of DEVQ, reported on half B and on the old 1,466 (re-weighted); 20 random splits. Local, CPU.
    python3 frontier.py runs/pulse/raw_v5-leaf.json"""
import json, sys, numpy as np
LV = ["minor", "notable", "major", "severe", "extreme"]; D = json.load(open(sys.argv[1]))
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def arr(rows):
    pp = 1 / (1 + np.exp(-(lg(np.array([r["ph"] for r in rows])) + lg(np.array([r["ps"] for r in rows]))) / 2)); cc = np.array([r["cconf"] for r in rows]); ok = np.zeros(len(rows), bool); pos = np.zeros(len(rows), bool)
    for k, r in enumerate(rows):
        s = r["S"]["conditions"]; pos[k] = bool(s)
        if s:
            x = next((x for x in s if x["condition"] == r["top1"]), None)
            if x: ok[k] = (r["dir"] == x["direction"]) and abs(LV.index(r["size"]) - LV.index(x["level"])) <= 1
    return pp, cc, ok, pos, np.array([r.get("w", 1.0) for r in rows])
CP = np.round(np.arange(0.10, 0.91, 0.05), 2); CC = np.round(np.arange(0.05, 0.71, 0.05), 2)
def grid(pp, cc, ok, pos, w, idx):
    """-> emitted, correct, positives weights for every (cp, cc)"""
    E = np.zeros((len(CP), len(CC))); C = np.zeros_like(E); ww = w[idx]
    for a, p in enumerate(CP):
        for b, c in enumerate(CC):
            em = (pp[idx] >= p) & (cc[idx] >= c); E[a, b] = ww[em].sum(); C[a, b] = ww[em & ok[idx]].sum()
    return E, C, ww[pos[idx]].sum()
dv = arr(D["devq"]); old = arr(D["old"]); n = len(D["devq"]); res = {}
def pick(E, C, P, target, minE):
    prec = np.where(E > minE, C / np.maximum(E, 1e-9), 0); rec = C / P; m = prec >= target
    if not m.any(): return None
    k = np.unravel_index(np.argmax(np.where(m, rec, -1)), rec.shape); return k
for target in (0.8, 0.7, 0.6):
    rb, pb, ro, po = [], [], [], []
    for s in range(20):
        perm = np.random.RandomState(s).permutation(n); A, B = perm[: n // 2], perm[n // 2:]
        for X, Y in ((A, B), (B, A)):
            E, C, P = grid(*dv, X); k = pick(E, C, P, target, 8)
            if k is None: continue
            E2, C2, P2 = grid(*dv, Y); rb.append(C2[k] / P2); pb.append(C2[k] / max(E2[k], 1e-9))
            E3, C3, P3 = grid(*old, np.arange(len(D["old"]))); ro.append(C3[k] / P3); po.append(C3[k] / max(E3[k], 1e-9))
    q = lambda x: [round(float(np.mean(x)), 3), round(float(np.percentile(x, 2.5)), 3), round(float(np.percentile(x, 97.5)), 3)]
    res[f"precision_target_{target}"] = {"n_picks": len(rb), "devq_halfB_recall": q(rb), "devq_halfB_precision": q(pb), "old_recall": q(ro), "old_precision": q(po)}
    print(target, json.dumps(res[f"precision_target_{target}"]))
E, C, P = grid(*dv, np.arange(n)); cur = (np.where(CP == 0.75)[0][0] if 0.75 in CP else 0, np.where(CC == 0.20)[0][0]); print("devq all: positives", round(P), "at presence>=0.75 and cond>=0.20: emitted", round(E[cur]), "correct", round(C[cur]), "precision", round(C[cur] / max(E[cur], 1), 3), "recall", round(C[cur] / P, 3))
print("max recall at any cuts, devq all (optimistic):", [(float(CP[a]), float(CC[b]), round(float(C[a, b] / P), 3), round(float(C[a, b] / max(E[a, b], 1e-9)), 3)) for a, b in [np.unravel_index(np.argmax(np.where(C / np.maximum(E, 1e-9) >= t, C / P, -1)), C.shape) for t in (0.8, 0.7, 0.6)]])
json.dump(res, open("runs/pulse/reach_frontier_v5-leaf.json", "w"), indent=1)
