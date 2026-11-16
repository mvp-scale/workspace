"""T207 (next_steps 14): learning curve of the per-key triage on the TIME split of t206: train on a random 25, 50, 75 and 100 percent of the older 70% of stories, same newest-30% test, same keys (those with at least 10 positives in the full training part), same rule. Would more labelled stories lift the tolerance-meeting share? (T206 text follows.) Same data, features and rule as t204 (v6b story embedding reduced to 256 dimensions, logistic head per key with at least 10 positives in the training part, yes-line fitted at false-positive quota 0.0010 on out-of-fold training scores). Two splits: TIME (train on the oldest 70% of stories by publish date, test on the newest 30%) and FEED (hold out whole feeds, smallest first, until about 30% of stories). A key passes when held-out false positives are at most 0.0025 of its negatives and, if it has held-out positives, true-positive rate is at least 0.90. Prediction in card T148-I.
Run (from projects/world-state): OUT=runs/pulse/t207 /workspace/models/embed-zs/.venv/bin/python -u t207_learning_curve.py   (N=5 for a smoke run)"""
import json, os, pathlib, sqlite3, time, collections, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t207")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0)); T0 = time.time(); FPQ = 0.0010
rows = []
for f in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + f): rows.append(json.loads(l))
seen = set(); rows = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
keys = list(rows[0]["P"]); Y = np.array([[r["P"][k] >= 0.5 for k in keys] for r in rows]).astype(int); grp = np.array([r["id"] for r in rows])
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); pub = []; feed = []
for r in rows: q = db.execute("select published, feed from items where id=?", (r["id"],)).fetchone(); pub.append(q[0]); feed.append(q[1])
X = np.load("runs/pulse/t182/t182_embeddings.npy"); assert len(X) == len(rows)
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
X = PCA(256, random_state=0).fit_transform(X - X.mean(0)).astype(np.float32); X /= X.std(0) + 1e-6
def fitline(s, yy, fp=FPQ, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
order = np.argsort(pub); n = len(rows); time_test = np.zeros(n, bool); time_test[order[int(0.7 * n):]] = True
cnt = collections.Counter(feed); held = set(); nh = 0
for f in sorted(cnt, key=lambda f: (cnt[f], f)):
    if nh >= 0.3 * n: break
    held.add(f); nh += cnt[f]
feed_test = np.array([f in held for f in feed]); res = {"stories": n, "keys_total": len(keys), "fit_fp_quota": FPQ, "splits": {}}
te = time_test; tr_full = ~te; use = [j for j in range(len(keys)) if Y[tr_full, j].sum() >= 10]; use = use[:N] if N else use; res["curve"] = {}
for frac in (0.25, 0.5, 0.75, 1.0):
    rng = np.random.RandomState(3); idx = np.where(tr_full)[0]; sub = np.sort(rng.choice(idx, int(frac * len(idx)), replace=False)) if frac < 1 else idx; Xt, gt = X[sub], grp[sub]; per = []
    for jn, j in enumerate(use):
        y = Y[:, j]; yt = y[sub]
        if yt.sum() < 3 or yt.sum() == len(yt): per.append({"key": keys[j], "pass": False, "coverage": 0.0, "fp": 0, "fn": 0, "test_pos": int((y[te] == 1).sum())}); continue
        oof = np.zeros(len(yt))
        for a, b in GroupKFold(5).split(Xt, yt, gt):
            if yt[a].sum() == 0: oof[b] = 0.0; continue
            oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
        lo, hi = fitline(oof, yt); h = LogisticRegression(C=0.3, max_iter=300).fit(Xt, yt).predict_proba(X[te])[:, 1]; yy = y[te]
        yes = h > hi; no = h < lo; ans = yes | no; npos = int((yy == 1).sum()); nneg = int((yy == 0).sum()); fp = int(np.sum(yes & (yy == 0))); fn = int(np.sum(no & (yy == 1)))
        fpr = fp / max(nneg, 1); tpr = 1 - fn / npos if npos else None; ok = fpr <= 0.0025 and (tpr is None or tpr >= 0.90)
        per.append({"key": keys[j], "test_pos": npos, "coverage": round(float(ans.mean()), 3), "fp": fp, "fn": fn, "pass": bool(ok)})
    cov = np.array([p["coverage"] for p in per]); okm = np.array([p["pass"] for p in per])
    res["curve"][str(frac)] = {"train_stories": len(sub), "keys_tested": len(per), "keys_pass": int(okm.sum()), "tolerance_saving": round(float(cov[okm].sum() / len(keys)), 3), "all_keys_coverage_share": round(float(cov.sum() / len(keys)), 3)}
    print(frac, res["curve"][str(frac)], round(time.time() - T0), flush=True)
c = res["curve"]; res["gain_50_to_100"] = round(c["1.0"]["tolerance_saving"] - c["0.5"]["tolerance_saving"], 3); res["gain_25_to_50"] = round(c["0.5"]["tolerance_saving"] - c["0.25"]["tolerance_saving"], 3)
res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / ("t207_smoke.json" if N else "t207_learning_curve.json"), "w"), indent=1); print(json.dumps(res["curve"]), res["gain_25_to_50"], res["gain_50_to_100"])
