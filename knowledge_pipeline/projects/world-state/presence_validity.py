"""T21: is presence a valid field? Applies the verdict rule pre-registered in ledger L668/L669 to the 600 devq items rated by Sonnet A and B (v3b), Gemma 4 26B, Qwen3.6-27B and hosted Jev (primary reading: P(yes) >= 0.5). Krippendorff alpha (nominal), 1,000-resample bootstrap over items. python3 presence_validity.py"""
import json, numpy as np
J = lambda p: [json.loads(l) for l in open(p)]; rng = np.random.RandomState(0)
S = lambda d: {r["item_id"]: bool(r["label"]["conditions"]) for r in J(f"runs/pulse/{d}/labels.jsonl")}
A, B = S("ceiling_sonnet/a601"), S("ceiling_sonnet/b601"); G = S("screen_devq_base"); Q = S("devq601_qwen36_27b_off")
jv = {r["id"]: r["answers"]["presence"]["noul"] for r in J("runs/pulse/jev_presence601/raw.jsonl") if "answers" in r}
ids = sorted(i for i in A if i in B and i in G and i in Q and i in jv); print("items rated by all five:", len(ids), "| Sonnet A positive share", round(np.mean([A[i] for i in ids]), 3))
R = {"Sonnet A": np.array([A[i] for i in ids]), "Sonnet B": np.array([B[i] for i in ids]), "Gemma 4 26B": np.array([G[i] for i in ids]), "Qwen3.6-27B": np.array([Q[i] for i in ids]), "Jev (P>=0.5)": np.array([jv[i] >= 0.5 for i in ids])}
def alpha(M):
    M = np.asarray(M, int); n_items, m = M.shape; y = M.sum(1); nn = m - y; o01 = (y * nn / (m - 1)).sum(); N = n_items * m; Y = y.sum(); Nn = N - Y
    if Y == 0 or Nn == 0: return float("nan")
    return 1 - (2 * o01 / N) / (2 * Y * Nn / (N * (N - 1)))
def boot(M, k=1000):
    M = np.asarray(M); n = len(M); v = [alpha(M[rng.randint(0, n, n)]) for _ in range(k)]; return [round(float(np.nanpercentile(v, 2.5)), 3), round(float(np.nanpercentile(v, 97.5)), 3)]
ref = R["Sonnet A"]; out = {}; ok = 0
for k in ("Sonnet B", "Gemma 4 26B", "Qwen3.6-27B", "Jev (P>=0.5)"):
    M = np.stack([ref, R[k]], 1); a = alpha(M); ci = boot(M); dis = float((ref != R[k]).mean()); out[k] = {"alpha": round(a, 3), "ci95": ci, "disagree": round(dis, 3), "yes_rate": round(float(R[k].mean()), 3)}
    if k != "Sonnet B" and a >= 0.667: ok += 1
    print(f"{k:14s} vs Sonnet A: alpha {a:.3f} {ci} | disagree {dis:.1%} | yes rate {R[k].mean():.3f}")
panel = np.stack([R["Sonnet A"], R["Jev (P>=0.5)"], R["Qwen3.6-27B"], R["Gemma 4 26B"]], 1); pa = alpha(panel); print("panel alpha (Sonnet A, Jev, Qwen, Gemma):", round(pa, 3), boot(panel))
# secondary, marked optimistic: Jev AUC and best-threshold alpha
from sklearn.metrics import roc_auc_score
p = np.array([jv[i] for i in ids]); auc = roc_auc_score(ref, p); bt = max(((alpha(np.stack([ref, p >= t], 1)), t) for t in np.arange(0.05, 0.96, 0.025)), key=lambda x: x[0]); print(f"Jev secondary (optimistic): AUC {auc:.3f}; best-threshold alpha {bt[0]:.3f} at {bt[1]:.3f}")
v = "VALID AS DEFINED" if ok >= 2 else "TENTATIVE" if ok == 1 else "NOT VALID AS DEFINED"; print(f"families at alpha >= 0.667: {ok} of 3  ->  VERDICT (pre-registered rule): {v}")
# other families pairwise among themselves
for a, b in (("Gemma 4 26B", "Qwen3.6-27B"), ("Gemma 4 26B", "Jev (P>=0.5)"), ("Qwen3.6-27B", "Jev (P>=0.5)")): print(f"  {a} vs {b}: alpha {alpha(np.stack([R[a], R[b]], 1)):.3f}")
json.dump({"n": len(ids), "pairs": out, "panel_alpha": round(pa, 3), "families_at_0667": ok, "verdict": v, "jev_auc": round(float(auc), 3)}, open("runs/pulse/presence_validity.json", "w"), indent=1)
