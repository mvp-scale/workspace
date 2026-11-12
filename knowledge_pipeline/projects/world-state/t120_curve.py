"""T120: learning curve of the engine-readings heads. Training on 300, 600, 1000 and all Clef readings of the engine stories (full-text view, word and character counts), scored on grouped 5-fold held-out stories. Shows whether more Clef readings would lift presence and direction.
    FOLDS=5 SIZES=300,600,1000,0 OUT=<folder> /workspace/kev/.venv/bin/python t120_curve.py -> <OUT>/t120_curve.json"""
import os, json, re, collections, pathlib, time, zlib, random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t120")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = int(os.environ.get("FOLDS", 5)); SZ = [int(x) for x in os.environ.get("SIZES", "300,600,1000,0").split(",")]; LIM = int(os.environ.get("LIMIT", 0))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
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
out = {s: {"p": np.zeros(len(E)), "d": np.full(len(E), np.nan)} for s in SZ}
for f in range(K):
    tr = [i for i in range(len(E)) if fold[i] != f]; te = [i for i in range(len(E)) if fold[i] == f]; random.Random(f).shuffle(tr)
    for s in SZ:
        sub = tr if s == 0 or s >= len(tr) else tr[:s]; trd = [i for i in sub if i in ed]
        w = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=60000)
        Xa = hstack([w.fit_transform([full[i] for i in sub]), c.fit_transform([full[i] for i in sub])]).tocsr(); Xe = hstack([w.transform([full[i] for i in te]), c.transform([full[i] for i in te])]).tocsr(); pos = {i: j for j, i in enumerate(sub)}
        out[s]["p"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, ep[sub]).predict_proba(Xe)[:, 1]
        out[s]["d"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[[pos[i] for i in trd]], [ed[i] for i in trd]).predict_proba(Xe)[:, 1]
    print("fold", f, round(time.time() - T0), flush=True)
res = {"engine_stories": len(E), "folds": K, "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4), "curve": {}}
for s in SZ:
    n = len(E) * (K - 1) // K if s == 0 else s; res["curve"][str(s)] = {"train_readings": n, "presence_auroc": round(float(roc_auc_score(ep, out[s]["p"])), 4), "direction_auroc": round(float(roc_auc_score(yd, out[s]["d"][ke])), 4), "direction_accuracy": round(float(((out[s]["d"][ke] >= 0.5) == yd).mean()), 4)}
res["note"] = "Grouped cross-validation over the engine stories, full-text view, reference is Clef's stored reading (agreement, not accuracy). Size 0 means every training story of the fold."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t120_curve.json", "w"), indent=1); print(json.dumps(res["curve"], indent=1))
