"""T121: self-training. Heads trained on the engine's Clef readings (headline plus two sentences) label unlabelled queue stories; only confident labels are kept and added to training; scored on grouped 5-fold held-out engine stories. Same folds as T116 (engine_only row is the comparison).
    FOLDS=5 NQ=<queue stories> CONF=0.75 OUT=<folder> /workspace/kev/.venv/bin/python t121_selftrain.py -> <OUT>/t121_selftrain.json"""
import os, json, re, collections, pathlib, time, zlib, random, sqlite3
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t121")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = int(os.environ.get("FOLDS", 5)); NQ = int(os.environ.get("NQ", 20000)); CONF = float(os.environ.get("CONF", 0.75)); LIM = int(os.environ.get("LIMIT", 0))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
short = lambda t, b: (t.strip() + ". " + " ".join(re.split(r"(?<=[.!?])\s+", b.strip())[:2])).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
E = list(eng.values())[: LIM or None]; et = {nk(r["title"]) for r in eng.values()}
def etext(r):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); return short(r["title"], re.sub(r"^Published\s*", "", b))
tx = [etext(r) for r in E]
cn = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
Q = [(i, t.strip(), tz) for i, t, tz in cn.execute("select id,title,teaser from items where length(teaser)>=40 and length(title)>=10 order by id") if i not in eng and nk(t) not in et]
random.Random(121).shuffle(Q); Q = Q[:NQ]; qt = [short(t, z) for _, t, z in Q]
ep = np.array([1 if r.get("readings") else 0 for r in E]); ed = {}
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ed[k] = 1 if w["up"] > w["down"] else 0
fold = np.array([zlib.crc32(nk(r["title"]).encode()) % K for r in E])
def feats(train, tests):
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
    A = hstack([w.fit_transform(train), c.fit_transform(train)]).tocsr(); return [A] + [hstack([w.transform(t), c.transform(t)]).tocsr() for t in tests]
LR = lambda: LogisticRegression(C=4.0, max_iter=400, class_weight="balanced")
out = {m: {"p": np.zeros(len(E)), "d": np.full(len(E), np.nan)} for m in ("engine_only", "self_trained")}; kept = []
for f in range(K):
    tr = [i for i in range(len(E)) if fold[i] != f]; te = [i for i in range(len(E)) if fold[i] == f]; trd = [i for i in tr if i in ed]; pos = {i: j for j, i in enumerate(tr)}
    Xa, Xe, Xq = feats([tx[i] for i in tr], [[tx[i] for i in te], qt])
    mp = LR().fit(Xa, ep[tr]); md = LR().fit(Xa[[pos[i] for i in trd]], [ed[i] for i in trd])
    out["engine_only"]["p"][te] = mp.predict_proba(Xe)[:, 1]; out["engine_only"]["d"][te] = md.predict_proba(Xe)[:, 1]
    qp = mp.predict_proba(Xq)[:, 1]; qd = md.predict_proba(Xq)[:, 1]
    sp = [j for j in range(len(Q)) if qp[j] >= CONF or qp[j] <= 1 - CONF]; sd = [j for j in range(len(Q)) if qp[j] >= CONF and (qd[j] >= CONF or qd[j] <= 1 - CONF)]; kept.append((len(sp), len(sd)))
    Xb = hstack  # placeholder to keep names short
    from scipy.sparse import vstack
    Xp = vstack([Xa, Xq[sp]]).tocsr(); yp = np.concatenate([ep[tr], (qp[sp] >= 0.5).astype(int)])
    Xdd = vstack([Xa[[pos[i] for i in trd]], Xq[sd]]).tocsr(); ydd = np.concatenate([[ed[i] for i in trd], (qd[sd] >= 0.5).astype(int)])
    out["self_trained"]["p"][te] = LR().fit(Xp, yp).predict_proba(Xe)[:, 1]; out["self_trained"]["d"][te] = LR().fit(Xdd, ydd).predict_proba(Xe)[:, 1]
    print("fold", f, round(time.time() - T0), kept[-1], flush=True)
ke = sorted(ed); yd = np.array([ed[k] for k in ke]); res = {"engine_stories": len(E), "queue_stories_scored": len(Q), "confidence": CONF, "pseudo_labels_kept_per_fold_presence_direction": kept, "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4)}
for m in out: res[m] = {"presence_auroc": round(float(roc_auc_score(ep, out[m]["p"])), 4), "direction_auroc": round(float(roc_auc_score(yd, out[m]["d"][ke])), 4), "direction_accuracy": round(float(((out[m]["d"][ke] >= 0.5) == yd).mean()), 4)}
res["note"] = "Grouped cross-validation over the engine stories, headline plus two sentences; reference is Clef's stored reading (agreement, not accuracy); engine_only here uses the same folds as T116."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t121_selftrain.json", "w"), indent=1); print(json.dumps(res, indent=1))
