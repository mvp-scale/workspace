"""T7: improvement loop with snapshots. Batches by date; train on <=k, score unseen k+1. Run with /workspace/models/embed-zs/.venv/bin/python loop.py"""
import json, glob, re, pathlib, warnings, urllib.parse
warnings.filterwarnings("ignore")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, brier_score_loss
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk, sn = {}, {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
F = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True)["F"]
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]
head = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in txt]                       # headline = first sentence, any sentence end (fixes the emoji split flaw)
def src(i):
    if i.startswith("cc:"): return urllib.parse.urlparse(i[3:]).netloc.replace("www.", "")
    if i.startswith("nq:"): return (pool[i].get("from") or "").split(":", 1)[-1]
    return "nr"
S = np.array([src(i) for i in ids]); dt = np.array([pool[i]["date"] or "" for i in ids]); keep = dt != ""
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); E = m.encode(txt); EH = m.encode(head)
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids]); sy = np.array([1 if (i in sn and sn[i]["conditions"]) else 0 for i in ids]); voted = np.array([i in sn for i in ids])
order = np.argsort(dt, kind="stable"); order = order[keep[order]]; B = np.array_split(order, 5)
def src_rate(tr, idx, mm=20):                                                    # smoothed per-outlet positive rate learned on train only
    g = y[tr].mean(); d = {}
    for s in np.unique(S[tr]): k = tr[S[tr] == s]; d[s] = (y[k].sum() + mm * g) / (len(k) + mm)
    r = np.array([d.get(s, g) for s in S[idx]]); return np.log(r / (1 - r))[:, None]
def fit(tr, te, kind):
    parts = {"base": lambda idx, tr_: np.hstack([F[idx], E[idx]]), "head": lambda idx, tr_: np.hstack([F[idx], EH[idx]]), "srcprior": lambda idx, tr_: np.hstack([F[idx], E[idx], src_rate(tr_, idx)]), "both": lambda idx, tr_: np.hstack([F[idx], E[idx], EH[idx]])}
    mdl = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1)).fit(parts[kind](tr, tr), y[tr]); p = mdl.predict_proba(parts[kind](te, tr))[:, 1]; return p
def sel_agree(te, p):                                                            # student vs Sonnet on the voted slice, all vs the more confident half
    v = te[voted[te]]
    if len(v) < 50: return None
    pv = p[np.isin(te, v)]; c = np.maximum(pv, 1 - pv); o = np.argsort(-c); a = ((pv > .5).astype(int) == sy[v])[o]
    return {"all": round(float(a.mean()), 3), "top_half": round(float(a[:len(a) // 2].mean()), 3), "n": int(len(v))}

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedKFold, cross_val_predict
tr = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]
Xb = lambda idx: np.hstack([F[idx], E[idx]])
def base_fit(idx, w=None, yy=None):
    mdl = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1))
    yy = y[idx] if yy is None else yy
    if w is None: return mdl.fit(Xb(idx), yy)
    X2 = np.vstack([Xb(idx), Xb(idx)]); y2 = np.r_[np.ones(len(idx)), np.zeros(len(idx))]; w2 = np.r_[w, 1 - w]
    return mdl.fit(X2, y2, logisticregression__sample_weight=w2)
def score(p_all):                                                                # p_all: probabilities for te
    pv = p_all[np.isin(te, vt)]
    return {"auc_vs_haiku_all": round(float(roc_auc_score(y[te], p_all)), 4), "auc_vs_sonnet_voted": round(float(roc_auc_score(sy[vt], pv)), 4)}
res = {"n_test": int(len(te)), "n_voted_test": int(len(vt))}
pb = base_fit(tr).predict_proba(Xb(te))[:, 1]; res["base"] = score(pb)
tv = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); Xt = tv.fit_transform([txt[i] for i in tr]); lr = LogisticRegression(max_iter=1000, C=3).fit(Xt, y[tr])
pt = lr.predict_proba(tv.transform([txt[i] for i in te]))[:, 1]; res["tfidf_alone"] = score(pt)
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))); blend = 1 / (1 + np.exp(-(lg(pb) + lg(pt)) / 2)); res["L1_blend"] = score(blend)
oof = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1)), Xb(tr), y[tr], cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
self_conf = np.where(y[tr] == 1, oof, 1 - oof)
for frac in (0.10, 0.15, 0.25):
    keepm = self_conf >= np.quantile(self_conf, frac); res[f"L2_prune_{int(frac*100)}"] = score(base_fit(tr[keepm]).predict_proba(Xb(te))[:, 1])
soft = np.where(voted[tr], (y[tr] + sy[tr]) / 2, y[tr].astype(float)); res["L3_soft"] = score(base_fit(tr, w=soft).predict_proba(Xb(te))[:, 1])
res["L3_n_soft_items"] = int(voted[tr].sum())
json.dump(res, open(H0 / "runs/snapshots/loop2_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
