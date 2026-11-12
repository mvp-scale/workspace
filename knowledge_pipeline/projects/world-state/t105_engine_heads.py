"""T105: CPU heads on the engine's own reference. The engine stores, for 1736 news stories, what Clef read: dials with a direction and a strength (data/newsreader/labels/clef-q4km*.jsonl). The goal of the engine work is a CPU reader that stays within the engine's tolerance of that reading, so agreement with it is the target here (reference is Clef: agreement, not accuracy). Three heads with 5-fold cross-validation, sparse word and character features and a logistic model, each read two ways: the headline plus first two sentences (what the Pulse reader sees) and the first 1200 words (what Clef read).
 1. presence: the story has at least one dial reading. 2. direction: up against down for stories whose strength-weighted majority is one of them (conflict and ties dropped). 3. dials: one head per dial with 50 or more stories.
Out-of-fold predictions only; no tuning on the folds beyond a fixed regularisation.
    OUT=<folder> /workspace/kev/.venv/bin/python -u t105_engine_heads.py -> <OUT>/t105_engine_heads.json"""
import os, json, re, collections, pathlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, f1_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t105")); OUT.mkdir(parents=True, exist_ok=True)
rows = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); rows.setdefault(r["id"], r)
R = list(rows.values())
if os.environ.get("NP"): R = R[:int(os.environ["NP"])]
def short(r):
    body = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); body = re.sub(r"^Published\s*", "", body); s = re.split(r"(?<=[.!?])\s+", body)
    return (r["title"].strip() + ". " + " ".join(s[:2])).strip()
def full(r): return " ".join(r["text"].split()[:1200])
VIEWS = {"headline_teaser": [short(r) for r in R], "first_1200_words": [full(r) for r in R]}
def feats(tr, te):
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
    return hstack([w.fit_transform(tr), c.fit_transform(tr)]).tocsr(), hstack([w.transform(te), c.transform(te)]).tocsr()
def oof(texts, y, idx):
    p = np.zeros(len(idx)); t = [texts[i] for i in idx]; yy = np.array([y[i] for i in idx])
    for a, b in StratifiedKFold(5, shuffle=True, random_state=7).split(t, yy):
        Xa, Xb = feats([t[i] for i in a], [t[i] for i in b]); m = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, yy[a]); p[b] = m.predict_proba(Xb)[:, 1]
    return p, yy
def binm(p, y):
    prev = float(y.mean()); f1 = f1_score(y, p >= 0.5); return {"items": int(len(y)), "positive_share": round(prev, 4), "auroc": round(float(roc_auc_score(y, p)), 4), "f1_at_half": round(float(f1), 4), "always_yes_f1": round(2 * prev / (1 + prev), 4), "accuracy": round(float(((p >= 0.5) == y).mean()), 4), "majority_accuracy": round(max(prev, 1 - prev), 4)}
has = [1 if r.get("readings") else 0 for r in R]; ya = {}
for k, r in enumerate(R):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ya[k] = 1 if w["up"] > w["down"] else 0
dcount = collections.Counter(x["dial"] for r in R for x in (r.get("readings") or [])); dials = [d for d, n in dcount.items() if n >= int(os.environ.get("MINDIAL", 50))]
res = {"stories": len(R), "with_reading": int(sum(has)), "direction_stories": len(ya), "dials_head_count": len(dials)}
for vn, texts in VIEWS.items():
    if os.environ.get("VIEWS") and vn not in os.environ["VIEWS"].split(","): continue
    v = {}; p, y = oof(texts, has, list(range(len(R)))); v["presence"] = binm(p, y)
    di = sorted(ya); p, y = oof(texts, ya, di); v["direction"] = binm(p, y)
    dr = {}
    for d in dials:
        yd = [1 if any(x["dial"] == d for x in (r.get("readings") or [])) else 0 for r in R]; p, y = oof(texts, yd, list(range(len(R)))); dr[d] = binm(p, y)
    v["dials"] = dr; v["dials_macro_auroc"] = round(float(np.mean([m["auroc"] for m in dr.values()])), 4); v["dials_macro_f1"] = round(float(np.mean([m["f1_at_half"] for m in dr.values()])), 4); v["dials_macro_always_yes_f1"] = round(float(np.mean([m["always_yes_f1"] for m in dr.values()])), 4)
    res[vn] = v; json.dump(res, open(OUT / "t105_engine_heads.json", "w"), indent=1); print(vn, json.dumps({k: v[k] for k in ("presence", "direction", "dials_macro_auroc", "dials_macro_f1", "dials_macro_always_yes_f1")}), flush=True)
res["note"] = "Reference is Clef's stored reading, so these are agreement figures for the engine goal, not accuracy. Out-of-fold, 5 folds, fixed settings. Direction = up against down by strength-weighted majority."
json.dump(res, open(OUT / "t105_engine_heads.json", "w"), indent=1)
