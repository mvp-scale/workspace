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


import time, scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
tr4 = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]; tr3 = np.concatenate(B[:3]); va = B[3]
def sc(p_all):
    pv = p_all[np.isin(te, vt)]; return {"vs_haiku": round(float(roc_auc_score(y[te], p_all)), 4), "vs_sonnet": round(float(roc_auc_score(sy[vt], pv)), 4)}
def tf(trn, tst, C, char=False, flags=False, w=None):
    v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); Xa = v1.fit_transform([txt[i] for i in trn]); Xb_ = v1.transform([txt[i] for i in tst])
    if char:
        v2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000); Xa = sp.hstack([Xa, v2.fit_transform([txt[i] for i in trn])]).tocsr(); Xb_ = sp.hstack([Xb_, v2.transform([txt[i] for i in tst])]).tocsr()
    if flags:
        sc_ = StandardScaler().fit(F[trn]); Xa = sp.hstack([Xa, sp.csr_matrix(sc_.transform(F[trn]) * 0.1)]).tocsr(); Xb_ = sp.hstack([Xb_, sp.csr_matrix(sc_.transform(F[tst]) * 0.1)]).tocsr()
    if w is None: m_ = LogisticRegression(max_iter=1000, C=C).fit(Xa, y[trn])
    else: m_ = LogisticRegression(max_iter=1000, C=C).fit(sp.vstack([Xa, Xa]), np.r_[np.ones(len(trn)), np.zeros(len(trn))], sample_weight=np.r_[w, 1 - w])
    return m_.predict_proba(Xb_)[:, 1]
res = {}
res["C_selection_on_batch4"] = {str(C): round(float(roc_auc_score(y[va], tf(tr3, va, C))), 4) for C in (1, 3, 10)}
C = max((1, 3, 10), key=lambda c: res["C_selection_on_batch4"][str(c)]); res["C_chosen"] = C
res["tfidf"] = sc(tf(tr4, te, C)); res["A_plus_flags"] = sc(tf(tr4, te, C, flags=True)); res["B_plus_char"] = sc(tf(tr4, te, C, char=True))
soft = np.where(voted[tr4], (y[tr4] + sy[tr4]) / 2, y[tr4].astype(float)); res["C_soft"] = sc(tf(tr4, te, C, w=soft))
# D passing-mention model: among Haiku-positive with a Sonnet vote, predict Sonnet confirms
trp = tr4[(y[tr4] == 1) & voted[tr4]]; tep = te[(y[te] == 1) & voted[te]]
v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); Xp = v1.fit_transform([txt[i] for i in trp]); lm = LogisticRegression(max_iter=1000, C=1).fit(Xp, sy[trp])
res["D_passing_mention"] = {"train_n": int(len(trp)), "test_n": int(len(tep)), "auc_tfidf": round(float(roc_auc_score(sy[tep], lm.predict_proba(v1.transform([txt[i] for i in tep]))[:, 1])), 4), "confirm_rate_test": round(float(sy[tep].mean()), 3)}
mb = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1)).fit(np.hstack([F[trp], E[trp]]), sy[trp]); res["D_passing_mention"]["auc_flags_embedding"] = round(float(roc_auc_score(sy[tep], mb.predict_proba(np.hstack([F[tep], E[tep]]))[:, 1])), 4)
# E latency, one thread: tfidf transform + predict for 2000 items
v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); Xa = v1.fit_transform([txt[i] for i in tr4]); lm = LogisticRegression(max_iter=1000, C=C).fit(Xa, y[tr4])
sample = [txt[i] for i in te[:2000]]; t0 = time.perf_counter()
for t in sample: lm.predict_proba(v1.transform([t]))
res["E_latency_ms_per_item_single"] = round((time.perf_counter() - t0) / len(sample) * 1000, 3)
json.dump(res, open(H0 / "runs/snapshots/loop3_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
