"""T21 fair re-estimate of cross-family presence agreement (ledger L674-L675): population-weighted by the sampling design (certainty stratum of 275 items all included, sampled stratum weighted), every pair, and the 4-rater panel, bootstrap by stratum. Raters: Sonnet A, Sonnet B, Qwen3.6-27B, Gemma 4 26B, Jev with the same instructions and full text. python3-free: run with the numpy venv."""
import json, numpy as np
J = lambda p: [json.loads(l) for l in open(p)]
L = lambda d: {r["item_id"]: bool(r["label"]["conditions"]) for r in J(f"runs/pulse/{d}/labels.jsonl")}
A, B, G, Q, gB, v2 = L("ceiling_sonnet/a601"), L("ceiling_sonnet/b601"), L("screen_devq_base"), L("devq601_qwen36_27b_off"), L("screen_devq_B"), L("devq")
JV = {r["id"]: r["answers"]["presence"]["noul"] >= 0.5 for r in J("runs/pulse/jev_same_prompt/raw.jsonl") if "answers" in r}
ids = sorted(i for i in A if i in B and i in G and i in Q and i in JV); cert = np.array([bool(v2[i] or gB[i]) for i in ids]); Nrest = len(v2) - sum(1 for i in v2 if v2[i] or gB.get(i)); w = np.where(cert, 1.0, Nrest / (~cert).sum())
R = {"Sonnet A": np.array([A[i] for i in ids]), "Sonnet B": np.array([B[i] for i in ids]), "Qwen3.6-27B": np.array([Q[i] for i in ids]), "Gemma 4 26B": np.array([G[i] for i in ids]), "Jev (same prompt)": np.array([JV[i] for i in ids])}
def walpha(M, ww):
    M = np.asarray(M, int); m = M.shape[1]; y = M.sum(1); n = m - y; o01 = (ww * y * n / (m - 1)).sum(); Wt = ww.sum() * m; Y = (ww * y).sum(); Nn = Wt - Y
    return 1 - (2 * o01 / Wt) / (2 * Y * Nn / (Wt * (Wt - 1)))
rng = np.random.RandomState(7); ic, ir = np.where(cert)[0], np.where(~cert)[0]
def boot(cols):
    M = np.stack([R[c] for c in cols], 1); v = []
    for _ in range(1000):
        s = np.concatenate([rng.choice(ic, len(ic)), rng.choice(ir, len(ir))]); v.append(walpha(M[s], w[s]))
    return np.percentile(v, [2.5, 97.5])
names = list(R); print("population-weighted pairwise alpha [95% interval]; n items", len(ids))
for i, a in enumerate(names):
    for b in names[i + 1:]:
        lo, hi = boot([a, b]); print(f"  {a:18s} vs {b:18s} {walpha(np.stack([R[a], R[b]], 1), w):.3f} [{lo:.2f},{hi:.2f}]")
for panel in (["Sonnet A", "Jev (same prompt)", "Qwen3.6-27B", "Gemma 4 26B"], ["Jev (same prompt)", "Qwen3.6-27B", "Gemma 4 26B"]):
    lo, hi = boot(panel); print(f"PANEL {' + '.join(panel)}: alpha {walpha(np.stack([R[c] for c in panel], 1), w):.3f} [{lo:.2f},{hi:.2f}]")
