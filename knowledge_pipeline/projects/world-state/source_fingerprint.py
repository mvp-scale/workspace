"""Test S (source as a feature) and Test F (fingerprint -> if-then rules). Run: /workspace/models/embed-zs/.venv/bin/python source_fingerprint.py"""
import json, os, re, glob, pathlib, warnings, collections
from urllib.parse import urlparse
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, balanced_accuracy_score
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.tree import DecisionTreeClassifier
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
src0 = open(H0 / "triage.py").read(); import sys as _s; _s.argv = ["x"]; __file__ = str(H0 / "triage.py")
_cache = H0 / "runs/structure/feat_all.npz"
if _cache.exists():
    z = np.load(_cache, allow_pickle=True); ids = list(z["ids"]); F = z["F"]
    lab = {}
    for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
        for r in J(f): lab[r["item_id"]] = r["label"]
else:
    exec(src0[:src0.index("p = cross_val_predict")]); lab = H; np.savez(_cache, F=F, ids=np.array(ids))
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
_ss = open(H0 / "structure.py").read().splitlines(); exec("\n".join(l for l in _ss if l.startswith(("ENT =", "NAMES ="))))
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}
def source(i):
    r = pool[i]; k = i.split(":")[0]
    if k == "cc": d = urlparse(i[3:]).netloc.lower().replace("www.", ""); return "reuters.com" if d.endswith("reuters.com") else d
    if k == "nq": return r["from"].replace("newsreader-queue:", "")
    return "unknown"
src = np.array([source(i) for i in ids]); corpus = np.array([i.split(":")[0] for i in ids]); txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]
y = np.array([1 if lab[i]["conditions"] else 0 for i in ids]); st = np.array([lab[i]["story_type"] for i in ids]); cls = sorted(set(st))
out = {"items": len(ids)}
# --- rates by corpus and by source
out["condition_rate_by_corpus"] = {c: round(float(y[corpus == c].mean()), 3) for c in sorted(set(corpus))}
cnt = collections.Counter(src); big = [s for s, n in cnt.items() if n >= 100]
rt = sorted(((round(float(y[src == s].mean()), 3), s, int((src == s).sum())) for s in big), reverse=True)
out["sources_100plus"] = len(big); out["top_condition_rate_sources"] = rt[:8]; out["bottom_condition_rate_sources"] = rt[-8:]
op = sorted(((round(float((st[src == s] == "opinion").mean()), 3), s, int((src == s).sum())) for s in big), reverse=True)
out["top_opinion_share_sources"] = op[:6]; out["bottom_opinion_share_sources"] = op[-4:]
fc = sorted(((round(float((st[src == s] == "forecast").mean()), 3), s, int((src == s).sum())) for s in big), reverse=True); out["top_forecast_share_sources"] = fc[:6]
# --- Test S
keep = [s for s, n in cnt.items() if n >= 30]; S = np.array([[1.0 if x == s else 0.0 for s in keep] + [1.0 if x not in keep else 0.0] for x in src])
E = StaticModel.from_pretrained("minishlab/potion-base-8M").encode(txt)
cv = StratifiedKFold(5, shuffle=True, random_state=0)
mk = lambda C=0.1, **k: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=C, **k))
prob = lambda X: cross_val_predict(mk(), X, y, cv=cv, method="predict_proba")[:, 1]
pb, ps, po = prob(np.hstack([F, E])), prob(np.hstack([F, E, S])), prob(S)
out["S_condition_auc"] = {"source_only": round(roc_auc_score(y, po), 4), "baseline": round(roc_auc_score(y, pb), 4), "baseline_plus_source": round(roc_auc_score(y, ps), 4)}
cc = corpus == "cc"; nq = corpus == "nq"
out["S_condition_auc_within_corpus"] = {c: {"baseline": round(roc_auc_score(y[m], pb[m]), 4), "plus_source": round(roc_auc_score(y[m], ps[m]), 4), "source_only": round(roc_auc_score(y[m], po[m]), 4)} for c, m in (("cc", cc), ("nq", nq))}
cvs = StratifiedKFold(5, shuffle=True, random_state=0); mks = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=0.1, class_weight="balanced"))
b = cross_val_predict(mks(), np.hstack([F, E]), st, cv=cvs); s2 = cross_val_predict(mks(), np.hstack([F, E, S]), st, cv=cvs); so = cross_val_predict(mks(), S, st, cv=cvs)
out["S_story_type_balanced_acc"] = {"baseline": round(balanced_accuracy_score(st, b), 4), "plus_source": round(balanced_accuracy_score(st, s2), 4), "source_only": round(balanced_accuracy_score(st, so), 4), "chance": 0.25}
# --- Test F: fingerprint -> rules (80/20 split)
cvz = CountVectorizer(binary=True, ngram_range=(1, 2), min_df=60, max_features=3000, stop_words=[w for w in __import__("sklearn.feature_extraction.text", fromlist=["x"]).ENGLISH_STOP_WORDS if w not in ("not", "no", "more", "less", "nor")])
W = cvz.fit_transform(txt); words = list(cvz.get_feature_names_out())
flags = (F > 0).astype(float)
Xr = sp.hstack([W, sp.csr_matrix(flags), sp.csr_matrix(S)]).tocsr(); fn = words + [f"flag:{n}" for n in NAMES] + [f"source:{s}" for s in keep] + ["source:other"]
tr, te = train_test_split(np.arange(len(y)), test_size=0.2, random_state=1, stratify=y)
tree = DecisionTreeClassifier(max_depth=4, min_samples_leaf=40, class_weight=None, random_state=0).fit(Xr[tr], y[tr])
def leaf_rules(tree, X, yv, fn):
    t = tree.tree_; leaf = tree.apply(X); res = {}
    def path(node, conds):
        if t.children_left[node] == -1: res[node] = conds; return
        f = fn[t.feature[node]]
        path(t.children_left[node], conds + [("NOT " + f)]); path(t.children_right[node], conds + [f])
    path(0, [])
    rows = []
    for nd, conds in res.items():
        m = leaf == nd; n = int(m.sum())
        if n: rows.append((nd, conds, n, float(yv[m].mean())))
    return rows, leaf
rtr, ltr = leaf_rules(tree, Xr[tr], y[tr], fn); rte, lte = leaf_rules(tree, Xr[te], y[te], fn)
te_by = {r[0]: r for r in rte}; sel = []
for nd, conds, n, prec in rtr:
    if prec >= 0.55 and nd in te_by:
        sel.append({"if": [c for c in conds if not c.startswith("NOT ")][:4], "train_n": n, "train_precision": round(prec, 3), "test_n": te_by[nd][2], "test_precision": round(te_by[nd][3], 3)})
pos_te = y[te].sum(); cov = sum(round(s["test_n"] * s["test_precision"]) for s in sel) / pos_te
out["F_rules"] = {"leaves": len(rtr), "rules_precision_55plus": len(sel), "share_of_test_positives_covered": round(float(cov), 3),
                  "mean_train_precision": round(float(np.mean([s["train_precision"] for s in sel])) if sel else 0, 3), "mean_test_precision": round(float(np.mean([s["test_precision"] for s in sel])) if sel else 0, 3),
                  "tree_test_auc": round(roc_auc_score(y[te], tree.predict_proba(Xr[te])[:, 1]), 4), "examples": sorted(sel, key=lambda s: -s["test_precision"])[:8]}
used = collections.Counter(fn[f] for f in tree.tree_.feature if f >= 0); out["F_features_used"] = used.most_common(12)
json.dump(out, open(H0 / "runs/fingerprint/source_fingerprint.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
