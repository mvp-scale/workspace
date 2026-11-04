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


import scipy.sparse as sp, sys, urllib.parse
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
hb.beat("t15-source-for-topic", where="[CPU]", task="T10", state="running", why="Is the outlet and section new information for topic and story type?", success="Topic top-1 gains 0.03+ against Sonnet", next="Score and log", need="Nothing", progress="fitting", spent=0.0, cap=0.0)
def srcsec(i):
    if i.startswith("cc:"):
        u = urllib.parse.urlparse(i[3:]); seg = [x for x in u.path.split("/") if x]; dom = u.netloc.replace("www.", ""); return dom, dom + "/" + (seg[0] if seg else "")
    if i.startswith("nq:"): f = (pool[i].get("from") or "").split(":", 1)[-1]; return f, f
    return "nr", "nr"
SS = [srcsec(i) for i in ids]; Sa = np.array([[a, b] for a, b in SS])
tr4 = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]
ys_topic = np.array([sn[ids[i]]["topic"] for i in vt]); ys_story = np.array([sn[ids[i]]["story_type"] for i in vt]); yt = np.array([hk[ids[i]]["topic"] for i in tr4]); yst = np.array([hk[ids[i]]["story_type"] for i in tr4])
T = [txt[i] for i in tr4]; Tv = [txt[i] for i in vt]
vt_ = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=100000).fit(T)
ss = StandardScaler().fit(np.hstack([E[tr4], EH[tr4]])); oh = OneHotEncoder(handle_unknown="ignore", min_frequency=5).fit(Sa[tr4])
def X(idx, T_, src):
    parts = [vt_.transform(T_), sp.csr_matrix(ss.transform(np.hstack([E[idx], EH[idx]])) * 0.1)]
    if src: parts.append(oh.transform(Sa[idx]) * 0.5)
    return sp.hstack(parts).tocsr()
res = {"n_voted_test": int(len(vt)), "known_source_share_in_test": round(float(np.mean([a in set(Sa[tr4][:, 0]) for a in Sa[vt][:, 0]])), 3)}
for src in (False, True):
    m_ = LogisticRegression(max_iter=300, C=3).fit(X(tr4, T, src), yt); P = m_.predict_proba(X(vt, Tv, src)); cl = m_.classes_; t2 = np.argsort(-P, 1)[:, :2]
    res["topic_" + ("with_source" if src else "no_source")] = {"top1": round(float((cl[P.argmax(1)] == ys_topic).mean()), 3), "top2": round(float(np.mean([ys_topic[i] in set(cl[t2[i]]) for i in range(len(vt))])), 3)}
    hb.beat("t15-source-for-topic", progress=f"topic {'with' if src else 'without'} source done")
    Xs = sp.hstack([TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True).fit(T).transform(T)] + ([oh.transform(Sa[tr4]) * 0.5] if src else [])).tocsr()
    vw = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True).fit(T); Xs = sp.hstack([vw.transform(T)] + ([oh.transform(Sa[tr4]) * 0.5] if src else [])).tocsr(); Xv = sp.hstack([vw.transform(Tv)] + ([oh.transform(Sa[vt]) * 0.5] if src else [])).tocsr()
    sm = LogisticRegression(max_iter=300, C=3).fit(Xs, yst); res["story_" + ("with_source" if src else "no_source")] = round(float((sm.classes_[sm.predict_proba(Xv).argmax(1)] == ys_story).mean()), 3)
json.dump(res, open(H0 / "runs/snapshots/loop9_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t15-source-for-topic", "done", last=f"topic top-1 {res['topic_no_source']['top1']} -> {res['topic_with_source']['top1']}; top-2 {res['topic_no_source']['top2']} -> {res['topic_with_source']['top2']}", progress="1,466 Sonnet-voted later items")
