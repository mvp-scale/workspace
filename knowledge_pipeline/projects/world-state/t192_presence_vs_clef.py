"""T192 (A1''): Condition presence against Clef: answer-when-sure coverage with the L2254 rule, random half-splits and a time-shifted split. Prediction in the ledger on T148 (L2368).
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t192_presence_vs_clef.py"""
import json, sqlite3, numpy as np
rows = []
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): rows.append(json.loads(l))
seen = set(); rows = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
X = np.load("runs/pulse/t182/t182_embeddings.npy"); assert len(X) == len(rows), (len(X), len(rows))
Y1 = np.array([bool(r.get("readings")) for r in rows]).astype(int); Y2 = np.array([any(v >= 0.5 for v in r["P"].values()) for r in rows]).astype(int)
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); pub = []
for r in rows:
    q = db.execute("select published from items where id=?", (r["id"],)).fetchone(); pub.append(q[0] if q and q[0] else None)
print("stories", len(rows), "with date", sum(p is not None for p in pub), "presence rate (readings)", round(Y1.mean(), 3), "(any P>=0.5)", round(Y2.mean(), 3), flush=True)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
def ev(s, yy, lo, hi):
    yes = s > hi; no = s < lo; return float((yes | no).mean()), 1 - float(np.sum(no & (yy == 1))) / max(int((yy == 1).sum()), 1), float(np.sum(yes & (yy == 0))) / max(int((yy == 0).sum()), 1)
grp = np.array([r["id"] for r in rows]); res = {"stories": len(rows)}
for name, Y in (("readings", Y1), ("any_P_0_5", Y2)):
    oof = np.zeros(len(Y))
    for a, b in GroupKFold(5).split(X, Y, grp): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], Y[a]).predict_proba(X[b])[:, 1]
    rng = np.random.RandomState(1); R = []
    for k in range(10):
        ug = np.unique(grp); rng.shuffle(ug); ha = set(ug[: len(ug) // 2]); m = np.array([g in ha for g in grp])
        for tr, te in ((m, ~m), (~m, m)): lo, hi = fit(oof[tr], Y[tr]); R.append(ev(oof[te], Y[te], lo, hi))
    R = np.array(R); out = {"positive_share": round(float(Y.mean()), 3), "random_split": {"coverage_mean": round(float(R[:, 0].mean()), 3), "coverage_min": round(float(R[:, 0].min()), 3), "eff_tpr_mean": round(float(R[:, 1].mean()), 3), "eff_fpr_mean": round(float(R[:, 2].mean()), 4), "eff_fpr_max": round(float(R[:, 2].max()), 4)}}
    dated = [i for i, p in enumerate(pub) if p]; order = sorted(dated, key=lambda i: pub[i]); cut = int(0.7 * len(order)); trn = np.array(order[:cut]); tst = np.array(order[cut:])
    oof2 = np.zeros(len(trn))
    for a, b in GroupKFold(5).split(X[trn], Y[trn], grp[trn]): oof2[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[trn][a], Y[trn][a]).predict_proba(X[trn][b])[:, 1]
    lo, hi = fit(oof2, Y[trn]); h = LogisticRegression(C=1.0, max_iter=3000).fit(X[trn], Y[trn]).predict_proba(X[tst])[:, 1]; c, t, f = ev(h, Y[tst], lo, hi)
    out["time_shifted"] = {"train": int(len(trn)), "test": int(len(tst)), "train_up_to": pub[order[cut - 1]], "coverage": round(c, 3), "eff_tpr": round(t, 3), "eff_fpr": round(f, 4), "test_negatives": int((Y[tst] == 0).sum())}
    res[name] = out; print(name, out, flush=True)
json.dump(res, open("runs/pulse/t179/t192_presence_vs_clef.json", "w"), indent=1)
