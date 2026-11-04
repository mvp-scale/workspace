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


import scipy.sparse as sp, sys, time
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits
hb.beat("t14-bundle-loop", where="[CPU]", task="T10", state="running", why="Does the whole three-output student keep improving as data accumulates, and how fast does it read?", success="2 of 3 outputs gain 0.02+ from v1 to v4; bundle under 5 ms per item", next="Score, log, write unknown rules", need="Nothing", progress="starting", spent=0.0, cap=0.0)
def fit_bundle(trn):
    M = {}
    T = [txt[i] for i in trn]
    M["vw"] = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True).fit(T); M["vc"] = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000).fit(T)
    M["vt"] = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=100000).fit(T)
    Xwc = sp.hstack([M["vw"].transform(T), M["vc"].transform(T)]).tocsr()
    M["story"] = LogisticRegression(max_iter=300, C=3).fit(Xwc, [hk[ids[i]]["story_type"] for i in trn])
    M["pres_h"] = LogisticRegression(max_iter=1000, C=1).fit(Xwc, y[trn])
    vv = np.array([voted[i] for i in trn]); M["pres_s"] = LogisticRegression(max_iter=1000, C=1).fit(Xwc[vv], sy[trn][vv])
    emb = np.hstack([E[trn], EH[trn]]); M["ss"] = StandardScaler().fit(emb)
    Xt = sp.hstack([M["vt"].transform(T), sp.csr_matrix(M["ss"].transform(emb) * 0.1)]).tocsr()
    M["topic"] = LogisticRegression(max_iter=300, C=3).fit(Xt, [hk[ids[i]]["topic"] for i in trn]); return M
def predict(M, idx):
    T = [txt[i] for i in idx]; Xwc = sp.hstack([M["vw"].transform(T), M["vc"].transform(T)]).tocsr()
    emb = np.hstack([E[idx], EH[idx]]); Xt = sp.hstack([M["vt"].transform(T), sp.csr_matrix(M["ss"].transform(emb) * 0.1)]).tocsr()
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    ph = M["pres_h"].predict_proba(Xwc)[:, 1]; ps = M["pres_s"].predict_proba(Xwc)[:, 1]
    return {"story": M["story"].predict_proba(Xwc), "topic": M["topic"].predict_proba(Xt), "pres": 1 / (1 + np.exp(-(lg(ph) + lg(ps)) / 2))}
def cover(conf, ok):
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); out = {"agree": round(float(ok.mean()), 3)}
    idx = np.where(run >= 0.8)[0]; out["share_at_80"] = round(float((idx.max() + 1) / len(o)) if len(idx) else 0.0, 3); return out
res = {"snapshots": {}, "flags": []}
for k in range(1, 5):
    trn = np.concatenate(B[:k]); te = B[k]; vt = te[voted[te]]; t0 = time.time(); M = fit_bundle(trn); P = predict(M, vt)
    ys_story = np.array([sn[ids[i]]["story_type"] for i in vt]); ys_topic = np.array([sn[ids[i]]["topic"] for i in vt])
    st = M["story"].classes_[P["story"].argmax(1)]; tc = M["topic"].classes_; t2 = np.argsort(-P["topic"], 1)[:, :2]
    snap = {"train_n": int(len(trn)), "test_voted_n": int(len(vt)), "fit_s": round(time.time() - t0),
        "story": cover(P["story"].max(1), st == ys_story), "topic_top1": cover(P["topic"].max(1), tc[P["topic"].argmax(1)] == ys_topic),
        "topic_top2": cover(np.sort(P["topic"], 1)[:, -2:].sum(1), np.array([ys_topic[i] in set(tc[t2[i]]) for i in range(len(vt))])),
        "presence": cover(np.maximum(P["pres"], 1 - P["pres"]), ((P["pres"] > .5).astype(int) == sy[vt]))}
    res["snapshots"][f"v{k}"] = snap; json.dump(snap, open(H0 / f"runs/snapshots/v{k}_bundle.json", "w"), indent=1)
    hb.beat("t14-bundle-loop", progress=f"snapshot v{k} done: story {snap['story']['agree']}, topic top2 {snap['topic_top2']['agree']}, presence {snap['presence']['agree']}", last=f"v{k} saved")
    if k > 1:
        prev = res["snapshots"][f"v{k-1}"]
        for key in ("story", "topic_top2", "presence"):
            if snap[key]["agree"] < prev[key]["agree"]: res["flags"].append(f"v{k} {key} fell {prev[key]['agree']} -> {snap[key]['agree']} (rollback flag)")
with threadpool_limits(limits=1):
    idx = B[4][:500]; t0 = time.perf_counter()
    for i in idx: predict(M, np.array([i]))
    res["latency_ms_per_item_bundle_one_thread"] = round((time.perf_counter() - t0) / len(idx) * 1000, 2)
json.dump(res, open(H0 / "runs/snapshots/loop8_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t14-bundle-loop", "done", last=f"v4 story {res['snapshots']['v4']['story']['agree']}, topic top2 {res['snapshots']['v4']['topic_top2']['agree']}, presence {res['snapshots']['v4']['presence']['agree']}; {res['latency_ms_per_item_bundle_one_thread']} ms", progress="4 snapshots, bundle read time measured")
