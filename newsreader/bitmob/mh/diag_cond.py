"""P-0017 diagnosis (round 4): the best TPR the condition head can reach at FPR .001 / .0025 on the frozen test with ANY single global or per-key score cut (the ceiling of ranking quality, not a deployable cut).
  CUDA_VISIBLE_DEVICES= python diag_cond.py MODEL_DIR LABELS.jsonl OUT.json"""
import os, sys, json
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, torch
from mh_common import load, predict
torch.set_num_threads(8); R = [json.loads(l) for l in open(sys.argv[2])]; model, tok, K = load(sys.argv[1]); model.cond_cuts = None
H = predict(model, tok, [r["state_text"] for r in R])["cond"]; COND = K["cond"]; grp = {}
for j, k in enumerate(COND): d, dr, i = k.split("|"); grp.setdefault((d, dr), []).append(j)
G = sorted(grp); S = np.stack([H[:, grp[g]].max(1) for g in G], 1); Y = np.zeros_like(S, bool)
for n, r in enumerate(R):
    for x in r["read"]["readings"]:
        if x["direction"] != "conflict": Y[n, G.index((x["dial"], x["direction"]))] = True
def tpr_at(s, y, fpr):
    neg = np.sort(s[~y])[::-1]; k = int(fpr * len(neg)); thr = neg[k] if k < len(neg) else -1; return float(((s > thr) & y).sum() / max(y.sum(), 1))
res = {"n": len(R), "positives": int(Y.sum()), "pooled_global_cut": {f"TPR@FPR{f}": round(tpr_at(S.ravel(), Y.ravel(), f), 4) for f in (.001, .0025, .01)}}
# per-key cut: fit the cut on half the stories, score on the other half
idx = np.arange(len(R)); a, b = idx[0::2], idx[1::2]; out = []
for tr, te in ((a, b), (b, a)):
    tp = fn = fp = tn = 0
    for j in range(S.shape[1]):
        neg = np.sort(S[tr][~Y[tr][:, j], j])[::-1]; k = int(.001 * len(neg)); thr = neg[k] if k < len(neg) else 1.1
        f = S[te][:, j] > thr; y = Y[te][:, j]; tp += (f & y).sum(); fn += (~f & y).sum(); fp += (f & ~y).sum(); tn += (~f & ~y).sum()
    out.append((tp / max(tp + fn, 1), fp / max(fp + tn, 1)))
res["per_key_cut_fitted_on_half_test_(diagnostic_only)"] = {"TPR": round(float(np.mean([o[0] for o in out])), 4), "FPR": round(float(np.mean([o[1] for o in out])), 5)}
pk = {f"{g[0]}|{g[1]}": int(Y[:, i].sum()) for i, g in enumerate(G)}; res["positives_per_key_median"] = int(np.median(list(pk.values()))); res["keys_with_>=20_pos"] = sum(v >= 20 for v in pk.values()); res["keys_with_0_pos"] = sum(v == 0 for v in pk.values())
json.dump(res, open(sys.argv[3], "w"), indent=1); print(json.dumps(res, indent=1))
