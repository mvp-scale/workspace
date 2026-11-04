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


import scipy.sparse as sp, sys
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.feature_extraction.text import TfidfVectorizer
hb.beat("t16-clef-third-vote", where="[CPU]", task="T10", state="running", why="Does a Clef vote lift the presence student beyond the two-teacher soft label?", success="Mean AUC over three teachers gains 0.01+", next="Score and log", need="Nothing", progress="fitting 3 variants", spent=0.0, cap=0.0)
cv = {}
for l in open(H0 / "runs/clef_vote.jsonl"):
    r = json.loads(l); cv[r["id"]] = r["raw"]["noul"]
tr = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]; vt = np.array([i for i in vt if ids[i] in cv]); trv = np.array([i for i in tr if voted[i] and ids[i] in cv])
cp = lambda idx: np.array([cv[ids[i]] for i in idx]); cb = lambda idx: (cp(idx) > 0.5).astype(float)
v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); v2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000)
T = [txt[i] for i in trv]; Xa = sp.hstack([v1.fit_transform(T), v2.fit_transform(T)]).tocsr(); Tv = [txt[i] for i in vt]; Xv = sp.hstack([v1.transform(Tv), v2.transform(Tv)]).tocsr()
def fit_soft(target):
    X2 = sp.vstack([Xa, Xa]); y2 = np.r_[np.ones(len(trv)), np.zeros(len(trv))]; w2 = np.r_[target, 1 - target]
    return LogisticRegression(max_iter=1000, C=1).fit(X2, y2, sample_weight=w2).predict_proba(Xv)[:, 1]
H_, S_ = y[trv].astype(float), sy[trv].astype(float)
res = {"n_train_voted": int(len(trv)), "n_test_voted": int(len(vt)), "clef_yes_rate_test": round(float(cb(vt).mean()), 3)}
V = {"two_vote_mean(H,S)": (H_ + S_) / 2, "three_vote_mean(H,S,Clef_yes)": (H_ + S_ + cb(trv)) / 3, "three_vote_mean(H,S,Clef_prob)": (H_ + S_ + cp(trv)) / 3, "clef_only_label": cb(trv)}
for name, tgt in V.items():
    p = fit_soft(tgt); a = {"vs_haiku": roc_auc_score(y[vt], p), "vs_sonnet": roc_auc_score(sy[vt], p), "vs_clef": roc_auc_score(cb(vt), p)}
    res[name] = {k: round(float(v), 4) for k, v in a.items()}; res[name]["mean_of_three"] = round(float(np.mean(list(a.values()))), 4)
json.dump(res, open(H0 / "runs/snapshots/loop10_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t16-clef-third-vote", "done", last="; ".join(f"{k} {v['mean_of_three']}" for k, v in res.items() if isinstance(v, dict)), progress="1,4xx later voted items")
