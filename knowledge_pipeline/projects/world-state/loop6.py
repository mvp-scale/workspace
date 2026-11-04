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



import scipy.sparse as sp, time, sys
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.feature_extraction.text import TfidfVectorizer
hb.beat("t12-topic-abstain", where="[CPU]", task="T10", state="running", why="Can topic say unknown or give two choices and reach 80 percent agreement on most items?", success="Top-2 agrees with Sonnet 0.85+; 65%+ answerable at 80% agreement", next="Score, log, rerun loop with the combined student", need="Nothing", progress="fitting 49-class student", spent=0.0, cap=0.0)
tr4 = np.concatenate(B[:4]); te = B[4]; vt = te[voted[te]]; vm = np.isin(te, vt)
yt = np.array([hk[ids[i]]["topic"] for i in tr4]); ys = np.array([sn[ids[i]]["topic"] for i in vt]); yhh = np.array([hk[ids[i]]["topic"] for i in te])
v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=100000); A = v.fit_transform([txt[i] for i in tr4]); Z = v.transform([txt[i] for i in te])
ss = StandardScaler().fit(np.hstack([E[tr4], EH[tr4]])); A2 = sp.hstack([A, sp.csr_matrix(ss.transform(np.hstack([E[tr4], EH[tr4]])) * 0.1)]).tocsr(); Z2 = sp.hstack([Z, sp.csr_matrix(ss.transform(np.hstack([E[te], EH[te]])) * 0.1)]).tocsr()
m_ = LogisticRegression(max_iter=300, C=3).fit(A2, yt); P = m_.predict_proba(Z2); cl = m_.classes_; np.save(H0 / "runs/snapshots/topic_probs_v4.npy", P)
Pv = P[vm]; top1 = cl[Pv.argmax(1)]; top2 = np.argsort(-Pv, 1)[:, :2]; hit2 = np.array([ys[i] in set(cl[top2[i]]) for i in range(len(ys))])
def cover(conf, ok):
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); out = {"full": round(float(ok.mean()), 3)}
    for t in (0.8, 0.9): idx = np.where(run >= t)[0]; out[f"share_at_{int(t*100)}"] = round(float((idx.max() + 1) / len(o)) if len(idx) else 0.0, 3)
    return out
res = {"n_voted": int(vm.sum()), "top1": cover(Pv.max(1), top1 == ys), "top2": cover(np.sort(Pv, 1)[:, -2:].sum(1), hit2)}
G = {"crime_policing": "law", "courts_rulings": "law", "governance_corruption": "politics", "elections_politics": "politics", "business_corporate": "money", "markets_investment": "money"}
g = lambda a: np.array([G.get(x, x) for x in a]); gp = g(top1); res["merged_pairs_top1"] = {"agree_vs_sonnet": round(float((gp == g(ys)).mean()), 3), "teachers_merged": round(float((g(np.array([hk[ids[i]]["topic"] for i in vt])) == g(ys)).mean()), 3), "unmerged_top1": round(float((top1 == ys).mean()), 3)}
json.dump(res, open(H0 / "runs/snapshots/loop6_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t12-topic-abstain", "done", last=f"top1 {res['top1']['full']}, top2 {res['top2']['full']}, merged pairs {res['merged_pairs_top1']['agree_vs_sonnet']}", progress="1,466 Sonnet-voted test items")
