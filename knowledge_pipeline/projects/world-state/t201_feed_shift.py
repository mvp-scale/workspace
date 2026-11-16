"""T201 (step 9): feed-ordered test of the answer-when-sure rule for the Function student. Whole feeds are held out: smallest-first feeds go to test until about 30% of queue stories are held out; train on the other feeds (+ CheckThat rows), thresholds from out-of-fold training scores grouped by story. Prediction in card T148-D.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t201_feed_shift.py -> runs/pulse/t201/t201_feed_shift.json"""
import json, sqlite3, numpy as np
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E6 = load("runs/pulse/t172/t173_embeddings.npz"); EB = load("runs/pulse/t172/t176_emb_bge_small.npz"); EE = load("runs/pulse/t172/t176_emb_e5_small.npz")
p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int); nq = len(q)
sid = [r["id"].split(":")[1] for r in q]; db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
feed = {}
for i in set(sid):
    r = db.execute("select feed from items where id=?", (i,)).fetchone(); feed[i] = r[0] if r and r[0] else None
import collections; cnt = collections.Counter(f for f in feed.values() if f); order = sorted(cnt, key=lambda f: (cnt[f], f)); tot = sum(cnt.values()); held = set(); n_held = 0
for f in order:
    if n_held >= 0.3 * tot: break
    held.add(f); n_held += cnt[f]
is_test = np.array([feed.get(s) in held for s in sid] + [False] * len(ct)); has_date = np.array([feed.get(s) is not None for s in sid] + [True] * len(ct)); tr = (~is_test) & has_date; te = is_test
print("train rows", int(tr.sum()), "test rows", int(te.sum()), "held-out feeds", len(held), "of", len(cnt), flush=True)
grp = np.array(sid + [r["id"] for r in ct])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
res = {"train_rows": int(tr.sum()), "test_rows": int(te.sum()), "held_out_feeds": len(held), "feeds_total": len(cnt), "variants": {}}
for name, X in (("v6b", E6), ("v6b+bge+e5", np.hstack([E6, EB, EE]))):
    Xt, yt, gt = X[tr], y[tr], grp[tr]; oof = np.zeros(len(yt))
    for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=1.0, max_iter=2000).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
    lo, hi = fit(oof, yt); h = LogisticRegression(C=1.0, max_iter=2000).fit(Xt, yt).predict_proba(X[te])[:, 1]; yy = y[te]
    yes = h > hi; no = h < lo; ans = yes | no
    res["variants"][name] = {"coverage": round(float(ans.mean()), 3), "eff_tpr": round(1 - float(np.sum(no & (yy == 1))) / max(int((yy == 1).sum()), 1), 3), "eff_fpr": round(float(np.sum(yes & (yy == 0))) / max(int((yy == 0).sum()), 1), 4), "fp": int(np.sum(yes & (yy == 0))), "fn": int(np.sum(no & (yy == 1))), "test_pos": int((yy == 1).sum()), "test_neg": int((yy == 0).sum())}
    print(name, res["variants"][name], flush=True)
import pathlib; pathlib.Path("runs/pulse/t201").mkdir(parents=True, exist_ok=True); json.dump(res, open("runs/pulse/t201/t201_feed_shift.json", "w"), indent=1)
