"""T209 (step 17, P0a of the end-to-end plan, ledger L2429): the per-key answer-when-sure triage of t206 on the 8,545 further Clef-labelled stories in data/clef-labels (test, r3, r5, c1, r1_local, r1b; 328 keys each, no overlap with the 2,488 used before). Input text is the engine's own state text (title plus description, median 233 characters), embedded with the v6b student (one window), reduced to 256 dimensions by label-free PCA; logistic head per key with at least 10 positives in the training part, yes-line fitted at false-positive quota 0.0010 on out-of-fold training scores. Splits: TIME (oldest 70% by the stories' day field for training, newest 30% test) and FEED (whole publishers held out, smallest first, until about 30% of stories; publisher = host of the story id URL). A key passes when held-out false positives are at most 0.0025 of its negatives and, if it has held-out positives, true-positive rate is at least 0.90. Prediction in card T148-K.
Run (from projects/world-state): OUT=runs/pulse/t209 /workspace/models/embed-zs/.venv/bin/python -u t209_triage_state_text.py   (N=5 for a smoke run)"""
import json, os, pathlib, sqlite3, time, collections, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t209")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0)); T0 = time.time(); FPQ = 0.0010
rows = []; seen = set()
for f in ("test", "r3", "r5", "c1", "r1_local", "r1b"):
    for l in open("/workspace/data/clef-labels/" + f + ".jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if "P" in r and len(r["P"]) == 328 and r["id"] not in seen: seen.add(r["id"]); rows.append(r)
keys = list(rows[0]["P"]); Y = np.array([[r["P"][k] >= 0.5 for k in keys] for r in rows]).astype(int); grp = np.array([r["id"] for r in rows]); n = len(rows)
from urllib.parse import urlparse
pub = [r.get("day") or "" for r in rows]; feed = [urlparse(r["id"].split(":", 1)[1]).netloc if r["id"].startswith("cc:") else r["id"][:12] for r in rows]
emb = OUT / "t209_embeddings.npy"
if emb.exists() and not N: X = np.load(emb)
else:
    from expert1_runtime import ExpertS; e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); t1 = time.time(); X = np.array([e.student(r["state_text"]) for r in (rows[:200] if N else rows)], dtype=np.float32); print("embedded", len(X), round(time.time() - t1), "s", flush=True)
    if not N: np.save(emb, X)
if N: rows = rows[:200]; Y = Y[:200]; grp = grp[:200]; pub = pub[:200]; feed = feed[:200]; n = 200
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
X = PCA(min(256, len(X) - 1), random_state=0).fit_transform(X - X.mean(0)).astype(np.float32); X /= X.std(0) + 1e-6
def fitline(s, yy, fp=FPQ, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
order = np.argsort(pub); time_test = np.zeros(n, bool); time_test[order[int(0.7 * n):]] = True
cnt = collections.Counter(feed); held = set(); nh = 0
for f in sorted(cnt, key=lambda f: (cnt[f], f)):
    if nh >= 0.3 * n: break
    held.add(f); nh += cnt[f]
feed_test = np.array([f in held for f in feed]); res = {"stories": n, "keys_total": len(keys), "fit_fp_quota": FPQ, "splits": {}}
for name, te in (("time", time_test), ("feed", feed_test)):
    tr = ~te; use = [j for j in range(len(keys)) if Y[tr, j].sum() >= 10]; use = use[:N] if N else use; per = []; Xt, gt = X[tr], grp[tr]
    for jn, j in enumerate(use):
        y = Y[:, j]; yt = y[tr]; oof = np.zeros(len(yt))
        for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
        lo, hi = fitline(oof, yt); h = LogisticRegression(C=0.3, max_iter=300).fit(Xt, yt).predict_proba(X[te])[:, 1]; yy = y[te]
        yes = h > hi; no = h < lo; ans = yes | no; npos = int((yy == 1).sum()); nneg = int((yy == 0).sum()); fp = int(np.sum(yes & (yy == 0))); fn = int(np.sum(no & (yy == 1)))
        fpr = fp / max(nneg, 1); tpr = 1 - fn / npos if npos else None; ok = fpr <= 0.0025 and (tpr is None or tpr >= 0.90)
        per.append({"key": keys[j], "train_pos": int(yt.sum()), "test_pos": npos, "coverage": round(float(ans.mean()), 3), "fpr": round(fpr, 4), "tpr": None if tpr is None else round(tpr, 3), "fp": fp, "fn": fn, "pass": bool(ok)})
        if jn % 40 == 0: print(name, jn, len(use), round(time.time() - T0), flush=True)
    cov = np.array([p["coverage"] for p in per]); okm = np.array([p["pass"] for p in per]); tfp = sum(p["fp"] for p in per); tneg = sum(int((Y[te, keys.index(p["key"])] == 0).sum()) for p in per); tfn = sum(p["fn"] for p in per); tpos = sum(p["test_pos"] for p in per)
    res["splits"][name] = {"train_stories": int(tr.sum()), "test_stories": int(te.sum()), "keys_tested": len(per), "keys_pass": int(okm.sum()), "tolerance_saving": round(float(cov[okm].sum() / len(keys)), 3), "all_keys_coverage_share": round(float(cov.sum() / len(keys)), 3), "micro_fpr": round(tfp / max(tneg, 1), 4), "micro_tpr": round(1 - tfn / max(tpos, 1), 3), "per_key": per}
res["tolerance_saving_worst"] = min(s["tolerance_saving"] for s in res["splits"].values()); res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / ("t209_smoke.json" if N else "t209_triage_state_text.json"), "w"), indent=1); print(json.dumps({k: ({a: {b: c for b, c in v.items() if b != "per_key"} for a, v in val.items()} if k == "splits" else val) for k, val in res.items()}))
