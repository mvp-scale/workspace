"""T132: does training on Jev's engine readings work as well as training on Clef's? Both label sets cover the same 1736 engine stories (Jev: T130 rows, Clef: the stored readings). Heads on word and character counts, full-text view, grouped 5-fold (crc32 of the headline mod 5), every model scored against CLEF's stored reading on the held-out fold. Paired bootstrap interval for Jev-trained minus Clef-trained.
    OUT=<folder> /workspace/kev/.venv/bin/python t132_jev_label_train.py -> <OUT>/t132_jev_label_train.json"""
import os, json, re, collections, pathlib, time, zlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t132")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = 5
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
R = [json.loads(l) for l in open("/workspace/data/newsreader/labels/jev-engine-stored.jsonl")]
def lab(rd):
    p = 1 if rd else 0; w = collections.Counter()
    for x in rd or []: w[x["direction"]] += x.get("strength", 1.0)
    d = (1 if w["up"] > w["down"] else 0) if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down") else None
    return p, d
C = [lab(r["clef_readings"]) for r in R]; J = [lab(r["jev_readings"]) for r in R]
tx = [(r["title"].strip() + " " + " ".join(r["text"].split()[:1200])).strip() for r in R]; fold = np.array([zlib.crc32(nk(r["title"]).encode()) % K for r in R])
out = {m: {"p": np.zeros(len(R)), "d": np.full(len(R), np.nan)} for m in ("clef_trained", "jev_trained")}
for f in range(K):
    tr = [i for i in range(len(R)) if fold[i] != f]; te = [i for i in range(len(R)) if fold[i] == f]
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
    Xa = hstack([w.fit_transform([tx[i] for i in tr]), c.fit_transform([tx[i] for i in tr])]).tocsr(); Xe = hstack([w.transform([tx[i] for i in te]), c.transform([tx[i] for i in te])]).tocsr()
    for m, L in (("clef_trained", C), ("jev_trained", J)):
        yp = np.array([L[i][0] for i in tr]); di = [j for j, i in enumerate(tr) if L[i][1] is not None]
        out[m]["p"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, yp).predict_proba(Xe)[:, 1]
        out[m]["d"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[di], [L[tr[j]][1] for j in di]).predict_proba(Xe)[:, 1]
    print("fold", f, round(time.time() - T0), flush=True)
ep = np.array([c[0] for c in C]); ke = [i for i in range(len(R)) if C[i][1] is not None]; yd = np.array([C[i][1] for i in ke])
res = {"stories": len(R), "folds": K, "direction_stories_by_clef": len(ke), "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4), "jev_vs_clef_presence_label_agreement": round(float(np.mean([J[i][0] == C[i][0] for i in range(len(R))])), 4)}
for m in out: res[m] = {"presence_auroc": round(float(roc_auc_score(ep, out[m]["p"])), 4), "direction_auroc": round(float(roc_auc_score(yd, out[m]["d"][ke])), 4), "direction_accuracy": round(float(((out[m]["d"][ke] >= 0.5) == yd).mean()), 4)}
rg = np.random.default_rng(5); B = []
for _ in range(1000):
    i = rg.integers(0, len(R), len(R)); j = rg.integers(0, len(ke), len(ke)); k = [ke[x] for x in j]
    B.append((roc_auc_score(ep[i], out["jev_trained"]["p"][i]) - roc_auc_score(ep[i], out["clef_trained"]["p"][i]), roc_auc_score(yd[j], out["jev_trained"]["d"][k]) - roc_auc_score(yd[j], out["clef_trained"]["d"][k]), float(((out["jev_trained"]["d"][k] >= 0.5) == yd[j]).mean() - ((out["clef_trained"]["d"][k] >= 0.5) == yd[j]).mean())))
B = np.array(B); ci = lambda c_: [round(float(np.percentile(B[:, c_], 2.5)), 4), round(float(np.percentile(B[:, c_], 97.5)), 4)]
res["paired_95_interval_jev_minus_clef_trained"] = {"presence_auroc": ci(0), "direction_auroc": ci(1), "direction_accuracy": ci(2)}
res["note"] = "Both heads scored against Clef's stored reading on held-out folds; train labels differ only in who read the story. Agreement, not accuracy."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t132_jev_label_train.json", "w"), indent=1); print(json.dumps(res, indent=1))
