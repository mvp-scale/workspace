"""T85: novelty score check on MN-DS human level-2 labels. 'Novel' = the item's human level-2 term is not one of the IPTC depth-1 terms the Area head knows (inv False). Scores: head (1 - top softmax) and embedding (1 - max cosine to any term). AUROC per file, paired bootstrap of the difference. Reads runs/pulse/t85/t84_scores.npz (rerun of the T84 head, same seed). Prediction at ledger L1609.
    python3 -I t85_novelty.py"""
import json, numpy as np
Z = np.load("runs/pulse/t85/t84_scores.npz"); HS, inv, tag = Z["HS"], Z["inv"], Z["tag"]; sim = Z["sim_max"]
P = np.exp(HS - HS.max(1, keepdims=True)); P /= P.sum(1, keepdims=True); sH = 1 - P.max(1); sE = 1 - sim
def auc(s, y):
    r = np.argsort(np.argsort(s)) + 1.0; pos = y == 1; n1, n0 = pos.sum(), (~pos).sum(); return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
out = {}; rs = np.random.RandomState(0)
for t in ("fresh", "fresh2"):
    ix = np.where(tag == t)[0]; y = (~inv[ix]).astype(int); a, b = sH[ix], sE[ix]; d = []
    for _ in range(1000):
        j = rs.randint(0, len(ix), len(ix))
        if y[j].min() == y[j].max(): continue
        d.append(auc(a[j], y[j]) - auc(b[j], y[j]))
    d.sort(); out[t] = {"items": int(len(ix)), "novel": int(y.sum()), "auroc_head": round(auc(a, y), 4), "auroc_embedding": round(auc(b, y), 4), "paired_head_minus_embedding": round(auc(a, y) - auc(b, y), 4), "ci95": [round(d[int(.025 * len(d))], 4), round(d[int(.975 * len(d))], 4)]}
json.dump(out, open("runs/pulse/t85/t85_novelty.json", "w"), indent=1); print(json.dumps(out, indent=1))
