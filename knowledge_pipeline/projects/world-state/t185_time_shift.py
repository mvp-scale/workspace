"""T185 (C1): time-shifted test of the answer-when-sure rule for the Function student. Train on the oldest 70% of queue stories (+ CheckThat rows), thresholds from out-of-fold training scores, evaluate on the newest 30% of stories. Prediction in ledger L2266.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t185_time_shift.py"""
import json, sqlite3, numpy as np
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E6 = load("runs/pulse/t172/t173_embeddings.npz"); EB = load("runs/pulse/t172/t176_emb_bge_small.npz"); EE = load("runs/pulse/t172/t176_emb_e5_small.npz")
p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int); nq = len(q)
sid = [r["id"].split(":")[1] for r in q]; db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
pub = {}
for i in set(sid):
    r = db.execute("select published from items where id=?", (i,)).fetchone(); pub[i] = r[0] if r and r[0] else None
ok = [i for i in pub if pub[i]]; ok.sort(key=lambda i: pub[i]); cut = ok[int(0.7 * len(ok))]; newest = set(i for i in ok if pub[i] > pub[cut])
is_test = np.array([s in newest for s in sid] + [False] * len(ct)); has_date = np.array([pub.get(s) is not None for s in sid] + [True] * len(ct)); tr = (~is_test) & has_date; te = is_test
print("train rows", int(tr.sum()), "test rows", int(te.sum()), "cut date", pub[cut], "test from", min(pub[i] for i in newest), "to", max(pub[i] for i in newest), flush=True)
grp = np.array(sid + [r["id"] for r in ct])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
res = {"train_rows": int(tr.sum()), "test_rows": int(te.sum()), "train_up_to": pub[cut], "variants": {}}
for name, X in (("v6b", E6), ("v6b+bge+e5", np.hstack([E6, EB, EE]))):
    Xt, yt, gt = X[tr], y[tr], grp[tr]; oof = np.zeros(len(yt))
    for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=1.0, max_iter=2000).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
    lo, hi = fit(oof, yt); h = LogisticRegression(C=1.0, max_iter=2000).fit(Xt, yt).predict_proba(X[te])[:, 1]; yy = y[te]
    yes = h > hi; no = h < lo; ans = yes | no
    res["variants"][name] = {"coverage": round(float(ans.mean()), 3), "eff_tpr": round(1 - float(np.sum(no & (yy == 1))) / max(int((yy == 1).sum()), 1), 3), "eff_fpr": round(float(np.sum(yes & (yy == 0))) / max(int((yy == 0).sum()), 1), 4), "fp": int(np.sum(yes & (yy == 0))), "fn": int(np.sum(no & (yy == 1))), "test_pos": int((yy == 1).sum()), "test_neg": int((yy == 0).sum())}
    print(name, res["variants"][name], flush=True)
json.dump(res, open("runs/pulse/t179/t185_time_shift.json", "w"), indent=1)
