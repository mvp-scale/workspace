"""T127: learning curve of the engine-readings heads. Training on 300, 600, 1000 and all Clef readings of the engine stories (full-text view, word and character counts), scored on grouped 5-fold held-out stories. Shows whether more Clef readings would lift presence and direction.
    FOLDS=5 SIZES=300,600,1000,0 OUT=<folder> /workspace/kev/.venv/bin/python t127_curve.py -> <OUT>/t127_curve.json"""
import os, json, re, collections, pathlib, time, zlib, random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t127")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = int(os.environ.get("FOLDS", 5)); SZ = [int(x) for x in os.environ.get("SIZES", "300,600,1000,0").split(",")]; LIM = int(os.environ.get("LIMIT", 0)); REPS = int(os.environ.get("REPS", 3))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl", "clef-q4km-ext.jsonl"):  # T127: the 1736 stories plus the extension readings from T126
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
E = list(eng.values())[: LIM or None]
def body(r):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); return re.sub(r"^Published\s*", "", b)
full = [(r["title"].strip() + " " + " ".join(body(r).split()[:1200])).strip() for r in E]
ep = np.array([1 if r.get("readings") else 0 for r in E]); ed = {}
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ed[k] = 1 if w["up"] > w["down"] else 0
fold = np.array([zlib.crc32(nk(r["title"]).encode()) % K for r in E]); ke = sorted(ed); yd = np.array([ed[k] for k in ke])
out = {(s, r): {"p": np.zeros(len(E)), "d": np.full(len(E), np.nan)} for s in SZ for r in range(REPS if s else 1)}
for f in range(K):
    tr = [i for i in range(len(E)) if fold[i] != f]; te = [i for i in range(len(E)) if fold[i] == f]; base = list(tr)
    for s in SZ:
      for rp in range(REPS if s else 1):
        tr = list(base); random.Random(f * 10 + rp).shuffle(tr); sub = tr if s == 0 or s >= len(tr) else tr[:s]; trd = [i for i in sub if i in ed]
        w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
        Xa = hstack([w.fit_transform([full[i] for i in sub]), c.fit_transform([full[i] for i in sub])]).tocsr(); Xe = hstack([w.transform([full[i] for i in te]), c.transform([full[i] for i in te])]).tocsr(); pos = {i: j for j, i in enumerate(sub)}
        out[(s, rp)]["p"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, ep[sub]).predict_proba(Xe)[:, 1]
        out[(s, rp)]["d"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[[pos[i] for i in trd]], [ed[i] for i in trd]).predict_proba(Xe)[:, 1]
    print("fold", f, round(time.time() - T0), flush=True)
def sc(o):
    return roc_auc_score(ep, o["p"]), roc_auc_score(yd, o["d"][ke]), float(((o["d"][ke] >= 0.5) == yd).mean())
res = {"engine_stories": len(E), "folds": K, "reps_per_size": REPS, "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4), "curve": {}}
for s in SZ:
    v = np.array([sc(out[(s, r)]) for r in range(REPS if s else 1)]); n = len(E) * (K - 1) // K if s == 0 else s
    res["curve"][str(s)] = {"train_readings": n, "presence_auroc": round(float(v[:, 0].mean()), 4), "direction_auroc": round(float(v[:, 1].mean()), 4), "direction_accuracy": round(float(v[:, 2].mean()), 4), "presence_auroc_range": [round(float(v[:, 0].min()), 4), round(float(v[:, 0].max()), 4)]}
rg = np.random.default_rng(7); o = out[(0, 0)]; bs = []
for _ in range(1000):
    i = rg.integers(0, len(E), len(E)); j = rg.integers(0, len(ke), len(ke))
    bs.append((roc_auc_score(ep[i], o["p"][i]), float(((o["d"][ke][j] >= 0.5) == yd[j]).mean())))
bs = np.array(bs); res["all_readings_95_interval"] = {"presence_auroc": [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)], "direction_accuracy": [round(float(np.percentile(bs[:, 1], 2.5)), 4), round(float(np.percentile(bs[:, 1], 97.5)), 4)]}
res["note"] = "Grouped cross-validation over the engine stories, full-text view, reference is Clef's stored reading (agreement, not accuracy). Size 0 means every training story of the fold."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t127_curve.json", "w"), indent=1); print(json.dumps(res["curve"], indent=1))
