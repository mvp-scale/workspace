"""A1 re-score from saved scores after the value_eval.py fix, plus the pair model with atom intercepts (deviation recorded in docs/value-indicators.md)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
import attack_a1_shared as S1
from sklearn.linear_model import LogisticRegression
S = np.load(f"{V.D}/proof/a1-scores.npz"); A = V.ATOMS; E = np.eye(len(A), dtype=np.float32)
def pair_onehot(rows, outs):
    X = lambda r: np.hstack([np.repeat(S1.G[r], len(A), 0), np.tile(S1.Qv, (len(r), 1)), np.repeat(S1.G[r], len(A), 0) * np.tile(S1.Qv, (len(r), 1)), np.tile(E, (len(r), 1))])
    y = S1.Yall[rows].reshape(-1); w = np.where(y > 0, (1 - y.mean()) / max(y.mean(), 1e-3), 1.0)
    m = LogisticRegression(C=2, max_iter=3000).fit(X(rows), y, sample_weight=w); return [m.predict_proba(X(r))[:, 1].reshape(len(r), len(A)) for r in outs]
Sa2 = S1.cross(pair_onehot); np.save(f"{V.D}/proof/a1-scores-pair-onehot.npy", Sa2)
rank = lambda x: np.argsort(np.argsort(x)) / max(1, len(x) - 1)
single = {n: V.PP[n]["glance_full", "agreed"] for n in A}
opts = {"A1a pair model (no atom intercept)": {n: S["Sa"][:, k] for k, n in enumerate(A)}, "A1a' pair model + atom intercepts": {n: Sa2[:, k] for k, n in enumerate(A)},
        "A1b multi-task network": {n: S["Sb"][:, k] for k, n in enumerate(A)}, "A1c blend (per-atom head + multi-task)": {n: (rank(single[n]) + rank(S["Sb"][:, k])) / 2 for k, n in enumerate(A)},
        "A1d nearest neighbours": {n: S["Sd"][:, k] for k, n in enumerate(A)}}
V.evaluate(opts, out_file=f"{V.D}/proof/a1-results.json")
