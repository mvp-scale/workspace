"""T116: students on the queue Jev labels plus the engine's own Clef readings, scored by grouped 5-fold cross-validation over the engine stories (a scored story is never in training; headlines shared with an engine story are dropped from the Jev labels). The same folds give the engine-labels-only heads for comparison. Headline plus two sentences, word and character counts.
    FOLDS=5 LIMIT=<jev labels, 0 = all> OUT=<folder> LABELS=<labels.jsonl> python3 t116_mix.py -> <OUT>/t116_mix.json"""
import os, json, re, collections, pathlib, time, zlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t116")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = int(os.environ.get("FOLDS", 5)); LIM = int(os.environ.get("LIMIT", 0))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
def short(title, body):
    s = re.split(r"(?<=[.!?])\s+", body.strip()); return (title.strip() + ". " + " ".join(s[:2])).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
E = list(eng.values()); et = {nk(r["title"]) for r in E}
def etext(r):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); b = re.sub(r"^Published\s*", "", b); return short(r["title"], b)
L = [json.loads(l) for l in open(os.environ.get("LABELS", "runs/pulse/t114/labels_all.jsonl"))]; seen = set(); J = []
for r in L:
    k = nk(r["title"])
    if r["dial"] != "error" and k not in seen and k not in et: seen.add(k); J.append(r)
if LIM: J = J[:LIM]
jt = [short(r["title"], r["body"]) for r in J]; jp = np.array([r["dial"] != "none" for r in J], int)
jd = [i for i, r in enumerate(J) if r["dial"] != "none" and r["direction"] in ("up", "down")]; jdy = np.array([J[i]["direction"] == "up" for i in jd], int)
ep = np.array([1 if r.get("readings") else 0 for r in E]); ed = {}
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ed[k] = 1 if w["up"] > w["down"] else 0
tx = [etext(r) for r in E]; fold = np.array([zlib.crc32(nk(r["title"]).encode()) % K for r in E])
def feats(train, test):
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
    return hstack([w.fit_transform(train), c.fit_transform(train)]).tocsr(), hstack([w.transform(test), c.transform(test)]).tocsr()
out = {m: {"p": np.zeros(len(E)), "d": np.full(len(E), np.nan)} for m in ("mix", "engine_only")}
for f in range(K):
    tr = [i for i in range(len(E)) if fold[i] != f]; te = [i for i in range(len(E)) if fold[i] == f]; trd = [i for i in tr if i in ed]
    for m in ("mix", "engine_only"):
        T = ([tx[i] for i in tr] + (jt if m == "mix" else [])); Xa, Xe = feats(T, [tx[i] for i in te]); ne = len(tr)
        yp = np.concatenate([ep[tr]] + ([jp] if m == "mix" else [])); out[m]["p"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, yp).predict_proba(Xe)[:, 1]
        rows = [tr.index(i) for i in trd] + ([ne + i for i in jd] if m == "mix" else []); yd = np.concatenate([[ed[i] for i in trd]] + ([jdy] if m == "mix" else []))
        out[m]["d"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[rows], yd).predict_proba(Xe)[:, 1]
    print("fold", f, round(time.time() - T0), flush=True)
ke = sorted(ed); yd = np.array([ed[k] for k in ke]); res = {"jev_labels_used": len(J), "engine_stories": len(E), "folds": K, "direction_stories": len(ke), "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4)}
for m in out:
    res[m] = {"presence_auroc": round(float(roc_auc_score(ep, out[m]["p"])), 4), "direction_auroc": round(float(roc_auc_score(yd, out[m]["d"][ke])), 4), "direction_accuracy": round(float(((out[m]["d"][ke] >= 0.5) == yd).mean()), 4)}
res["note"] = "Grouped cross-validation over the engine's 1736 stories; reference is Clef's stored reading (agreement, not accuracy). Compare T105 heads: presence AUROC 0.7936, direction AUROC 0.7221, direction accuracy 0.6921."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t116_mix.json", "w"), indent=1); print(json.dumps(res, indent=1))
