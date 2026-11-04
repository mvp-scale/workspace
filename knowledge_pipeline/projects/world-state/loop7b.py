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
hb.beat("t13b-presence-vs-haiku", where="[CPU]", task="T10", state="running", why="Can the condition-present answer match Sonnet better if trained on Sonnet's view or in two stages?", success="A variant gains 0.02 AUC against Sonnet over the Haiku-trained one", next="Score, log, rerun loop", need="Nothing", progress="3 variants", spent=0.0, cap=0.0)
tr4 = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]
def vec(trn):
    v1 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True); v2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000)
    T = [txt[i] for i in trn]; Xa = sp.hstack([v1.fit_transform(T), v2.fit_transform(T)]).tocsr()
    return Xa, (lambda idx: sp.hstack([v1.transform([txt[i] for i in idx]), v2.transform([txt[i] for i in idx])]).tocsr())
def cover(conf, ok):
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); out = {"full": round(float(ok.mean()), 3)}
    for t in (0.8, 0.9): idx = np.where(run >= t)[0]; out[f"share_at_{int(t*100)}"] = round(float((idx.max() + 1) / len(o)) if len(idx) else 0.0, 3)
    return out
def rep(p):
    return {"auc_vs_sonnet": round(float(roc_auc_score(sy[vt], p)), 4), "auc_vs_haiku": round(float(roc_auc_score(y[vt], p)), 4), **cover(np.maximum(p, 1 - p), ((p > .5).astype(int) == sy[vt]))}
res = {}
Xa, tr_ = vec(tr4); Xv = tr_(vt)
pa = LogisticRegression(max_iter=1000, C=1).fit(Xa, y[tr4]).predict_proba(Xv)[:, 1]; res["a_haiku_trained"] = rep(pa)
trv = tr4[voted[tr4]]; Xs, trs = vec(trv); pb = LogisticRegression(max_iter=1000, C=1).fit(Xs, sy[trv]).predict_proba(trs(vt))[:, 1]; res["b_sonnet_trained_voted_only"] = {**rep(pb), "train_n": int(len(trv))}
trp = tr4[(y[tr4] == 1) & voted[tr4]]; Xp, trp_ = vec(trp); pc_conf = LogisticRegression(max_iter=1000, C=1).fit(Xp, sy[trp]).predict_proba(trp_(vt))[:, 1]
pc = pa * pc_conf; res["c_two_stage"] = {**rep(pc), "train_n_stage2": int(len(trp))}
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))); pm = 1 / (1 + np.exp(-(lg(pa) + lg(pb)) / 2)); res["d_blend_a_b"] = rep(pm)
json.dump(res, open(H0 / "runs/snapshots/loop7b_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t13b-presence-vs-haiku", "done", last=f"AUC vs Sonnet a {res['a_haiku_trained']['auc_vs_sonnet']} b {res['b_sonnet_trained_voted_only']['auc_vs_sonnet']} c {res['c_two_stage']['auc_vs_sonnet']}", progress="1,466 Sonnet-voted later items")
