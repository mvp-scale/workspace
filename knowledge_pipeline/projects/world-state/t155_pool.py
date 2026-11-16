"""T155 pooling (ledger T-0032, A08): pools the test predictions of the fine-tuned bge-small and the sparse heads over the folds present in runs/pulse/t155/fold*/predictions.npz; paired bootstrap over stories of fine-tuned minus sparse (presence AUROC, direction AUROC, direction accuracy).
    /workspace/models/embed-zs/.venv/bin/python t155_pool.py -> runs/pulse/t155/t155_pooled.json"""
import glob, json, numpy as np
from sklearn.metrics import roc_auc_score
F = sorted(glob.glob("runs/pulse/t155/fold*/predictions.npz")); Z = [np.load(f) for f in F]
fine = np.vstack([z["fine"] for z in Z]); sp = np.vstack([z["sparse"] for z in Z]); pg = np.concatenate([z["presence_gold"] for z in Z]); dm = np.concatenate([z["dir_mask"] for z in Z]).astype(bool); dg = np.concatenate([z["dir_gold"] for z in Z])
D = np.where(dm)[0]; yd = dg[D]
def stats(i, j):
    return (roc_auc_score(pg[i], fine[i, 0]) - roc_auc_score(pg[i], sp[i, 0]), roc_auc_score(dg[j], fine[j, 1]) - roc_auc_score(dg[j], sp[j, 1]), (((fine[j, 1] >= 0.5) == dg[j]).mean()) - (((sp[j, 1] >= 0.5) == dg[j]).mean()))
rng = np.random.default_rng(155); pt = stats(np.arange(len(pg)), D); B = []
for _ in range(500):
    i = rng.integers(0, len(pg), len(pg)); j = rng.choice(D, len(D))
    if len(set(pg[i])) < 2 or len(set(dg[j])) < 2: continue
    B.append(stats(i, j))
B = np.array(B); ci = lambda k: [round(float(np.percentile(B[:, k], 2.5)), 4), round(float(np.percentile(B[:, k], 97.5)), 4)]
res = {"folds_pooled": len(F), "stories": int(len(pg)), "direction_stories": int(len(D)), "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4),
       "fine_tuned": {"presence_auroc": round(float(roc_auc_score(pg, fine[:, 0])), 4), "direction_auroc": round(float(roc_auc_score(yd, fine[D, 1])), 4), "direction_accuracy": round(float(((fine[D, 1] >= 0.5) == yd).mean()), 4)},
       "sparse": {"presence_auroc": round(float(roc_auc_score(pg, sp[:, 0])), 4), "direction_auroc": round(float(roc_auc_score(yd, sp[D, 1])), 4), "direction_accuracy": round(float(((sp[D, 1] >= 0.5) == yd).mean()), 4)},
       "fine_minus_sparse": {"presence_auroc": round(pt[0], 4), "presence_ci95": ci(0), "direction_auroc": round(pt[1], 4), "direction_auroc_ci95": ci(1), "direction_accuracy": round(pt[2], 4), "direction_accuracy_ci95": ci(2)},
       "note": "Each fold's fine-tuned epoch picked on its own dev split; test folds grouped by headline hash; reference is the engine's stored reading (agreement, not accuracy); bootstrap over stories pooled across folds."}
json.dump(res, open("runs/pulse/t155/t155_pooled.json", "w"), indent=1); print(json.dumps(res, indent=1))
