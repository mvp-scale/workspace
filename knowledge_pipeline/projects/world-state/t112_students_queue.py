"""T112: CPU students trained on the hosted-Jev labels of the pool (T111, queue stories) and scored on the engine's stored Clef reading of its 1736 stories (never trained on; reference is Clef's full reading, so agreement, not accuracy). Heads: presence (a dial named), direction (up or down), dial (39 classes). Sparse word and character features, logistic models, fixed settings. Views: headline plus first two sentences, and the first 1200 words. Learning curve at SIZES fitted articles. Compared in the output with the T105 cross-validated heads trained on the engine's own 1736 labels.
    SIZES=1000,3000,0 OUT=<folder> LABELS=<labels.jsonl> /workspace/kev/.venv/bin/python -u t112_students.py -> <OUT>/t112_students.json"""
import os, json, re, collections, pathlib, time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, f1_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t112")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); SIZES = [int(x) for x in os.environ.get("SIZES", "1000,3000,0").split(",")]
L = [json.loads(l) for l in open(os.environ.get("LABELS", "runs/pulse/t111/labels.jsonl"))]; L = [r for r in L if r["dial"] != "error"]
_seen = set(); _L = []
for r in L:
    k = re.sub(r"\W+", " ", r["title"].lower()).strip()
    if k not in _seen: _seen.add(k); _L.append(r)
L = _L
def short(title, body):
    s = re.split(r"(?<=[.!?])\s+", body.strip()); return (title.strip() + ". " + " ".join(s[:2])).strip()
def full(title, body): return (title.strip() + " " + " ".join(body.split()[:1200])).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
E = list(eng.values())
def etext(r, view):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); b = re.sub(r"^Published\s*", "", b); return short(r["title"], b) if view == "headline_teaser" else full(r["title"], b)
yp_e = np.array([1 if r.get("readings") else 0 for r in E]); ydir_e = {}
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ydir_e[k] = 1 if w["up"] > w["down"] else 0
edials = [set(x["dial"] for x in (r.get("readings") or [])) for r in E]
res = {"labelled": len(L), "with_dial": sum(1 for r in L if r["dial"] != "none"), "engine_stories": len(E), "engine_with_reading": int(yp_e.sum()), "engine_direction_stories": len(ydir_e), "sizes": {}}
for view in ("headline_teaser",):  # the queue holds headline plus teaser only
    txt = [short(r["title"], r["body"]) if view == "headline_teaser" else full(r["title"], r["body"]) for r in L]; et = [etext(r, view) for r in E]
    for sz in SIZES:
        n = len(L) if sz == 0 or sz > len(L) else sz; idx = list(range(n)); t = [txt[i] for i in idx]
        w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
        Xa = hstack([w.fit_transform(t), c.fit_transform(t)]).tocsr(); Xe = hstack([w.transform(et), c.transform(et)]).tocsr()
        yp = np.array([1 if L[i]["dial"] != "none" else 0 for i in idx]); pres = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, yp); pe = pres.predict_proba(Xe)[:, 1]
        di = [i for i in idx if L[i]["dial"] != "none" and L[i]["direction"] in ("up", "down")]; dm = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[di], np.array([1 if L[i]["direction"] == "up" else 0 for i in di])); de = dm.predict_proba(Xe)[:, 1]
        ke = sorted(ydir_e); yd = np.array([ydir_e[k] for k in ke]); acc = float(((de[ke] >= 0.5) == yd).mean()); maj = max(yd.mean(), 1 - yd.mean())
        dl = [i for i in idx if L[i]["dial"] != "none"]; cls = sorted({L[i]["dial"] for i in dl}); dd = LogisticRegression(C=4.0, max_iter=300).fit(Xa[dl], np.array([cls.index(L[i]["dial"]) for i in dl])); pd = dd.predict_proba(Xe); top = [cls[int(j)] for j in pd.argmax(1)]
        has = [k for k in range(len(E)) if edials[k]]; hit = float(np.mean([top[k] in edials[k] for k in has]))
        r = {"fit_articles": n, "presence_auroc": round(float(roc_auc_score(yp_e, pe)), 4), "presence_f1_at_half": round(float(f1_score(yp_e, pe >= 0.5)), 4), "direction_accuracy": round(acc, 4), "direction_majority": round(float(maj), 4), "direction_auroc": round(float(roc_auc_score(yd, de[ke])), 4), "dial_hit_of_engine_readings": round(hit, 4), "seconds": round(time.time() - T0)}
        res["sizes"][f"{view}:{sz}"] = r; print(view, sz, json.dumps(r), flush=True)
        json.dump(res, open(OUT / "t112_students.json", "w"), indent=1)
res["headline_view_largest"] = res["sizes"][f"headline_teaser:{SIZES[-1]}"]
res["note"] = "Scored on all 1736 engine stories, none in training. Reference: Clef's stored full reading (agreement, not accuracy). Compare T105: heads cross-validated on the engine's own labels, full view presence AUROC 0.856, direction 0.740; headline view 0.794 and 0.692."
json.dump(res, open(OUT / "t112_students.json", "w"), indent=1)
