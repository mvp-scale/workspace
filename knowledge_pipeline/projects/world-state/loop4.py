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


import scipy.sparse as sp, time
from sklearn.feature_extraction.text import TfidfVectorizer
def vec(trn):
    v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); v2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000)
    T = [txt[i] for i in trn]; Xa = sp.hstack([v1.fit_transform(T), v2.fit_transform(T)]).tocsr()
    return Xa, (lambda idx: sp.hstack([v1.transform([txt[i] for i in idx]), v2.transform([txt[i] for i in idx])]).tocsr())
res = {"curve": {}}
for k in range(1, 5):
    trk = np.concatenate(B[:k]); tek = B[k]; Xa, tr_ = vec(trk); p = LogisticRegression(max_iter=1000, C=1).fit(Xa, y[trk]).predict_proba(tr_(tek))[:, 1]
    res["curve"][f"v{k}"] = {"train_n": int(len(trk)), "auc_vs_haiku": round(float(roc_auc_score(y[tek], p)), 4)}
    vk = tek[voted[tek]]; pv = p[np.isin(tek, vk)]; c = np.maximum(pv, 1 - pv); o = np.argsort(-c); a = ((pv > .5).astype(int) == sy[vk])[o]
    res["curve"][f"v{k}"]["vs_sonnet_all"] = round(float(a.mean()), 3); res["curve"][f"v{k}"]["vs_sonnet_top_half"] = round(float(a[:len(a) // 2].mean()), 3)
    json.dump(res["curve"][f"v{k}"], open(H0 / f"runs/snapshots/v{k}_tfidf.json", "w"), indent=1)
tr4 = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]; Xa, tr_ = vec(tr4); Xt = tr_(te); Xv = tr_(vt)
def cover(conf, ok):                                                              # largest answered share whose running agreement stays >= target
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); out = {}
    for t in (0.8, 0.9): idx = np.where(run >= t)[0]; out[f"share_at_{int(t*100)}"] = round(float((idx.max() + 1) / len(o)) if len(idx) else 0.0, 3)
    out["full_agreement"] = round(float(ok.mean()), 3); return out
res["outputs"] = {}
pp = LogisticRegression(max_iter=1000, C=1).fit(Xa, y[tr4]).predict_proba(Xv)[:, 1]
res["outputs"]["presence"] = {**cover(np.maximum(pp, 1 - pp), ((pp > .5).astype(int) == sy[vt])), "teachers_agree": round(float((y[vt] == sy[vt]).mean()), 3)}
for name in ("story_type", "topic"):
    yt = np.array([hk[ids[i]][name] for i in tr4]); ys = np.array([sn[ids[i]][name] for i in vt]); yh = np.array([hk[ids[i]][name] for i in vt])
    if name == "topic":
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=100000); A = v.fit_transform([txt[i] for i in tr4]); Z = v.transform([txt[i] for i in vt])
    else: A, Z = Xa, Xv
    t0 = time.time(); m_ = LogisticRegression(max_iter=300, C=3).fit(A, yt); P = m_.predict_proba(Z); pred = m_.classes_[P.argmax(1)]
    res["outputs"][name] = {**cover(P.max(1), pred == ys), "teachers_agree": round(float((yh == ys).mean()), 3), "n_classes": int(len(m_.classes_)), "fit_s": round(time.time() - t0)}
res["outputs"]["n_voted_test"] = int(len(vt))
json.dump(res, open(H0 / "runs/snapshots/loop4_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
