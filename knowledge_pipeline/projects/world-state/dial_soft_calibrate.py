"""T35 (pre-registered L928): Platt-calibrate the out-of-fold all-dial scores, two-fold across stories (fit on one half, apply to the other, and the reverse).
    /workspace/models/embed-zs/.venv/bin/python dial_soft_calibrate.py   (from projects/world-state)"""
import numpy as np
from sklearn.linear_model import LogisticRegression
Z = np.load("runs/pulse/dial_heads_cv_scores.npz"); S, Y = Z["S"], Z["Y"]; N, H = S.shape
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))[:, None]
perm = np.random.RandomState(3).permutation(N); halves = [perm[: N // 2], perm[N // 2:]]; P = np.zeros_like(S)
for j in range(H):
    for a, b in (halves, halves[::-1]):
        P[b, j] = LogisticRegression(C=100.0).fit(lg(S[a, j]), Y[a, j]).predict_proba(lg(S[b, j]))[:, 1]
np.savez("runs/pulse/dial_soft_p.npz", P=P, Y=Y, ids=Z["ids"], keys=Z["keys"])
print("calibrated", P.shape, "mean predicted", round(float(P.mean()), 5), "mean true", round(float(Y.mean()), 5))
