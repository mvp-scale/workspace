import json, glob, re, pickle, pathlib, sys, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t26-bge-features", where="[CPU]", task="T10", state="running", why="Do frozen bge-small embeddings add what word counts miss?", success="A lift of 0.02+ somewhere", next="Fine-tune on the 5090 if yes", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); EB = np.load(H0 / "runs/embeds/bge_small.npy"); eid = {i: k for k, i in enumerate(json.load(open(H0 / "runs/embeds/bge_small_ids.json")))}
hk = {}; sn = {}; old = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); bge = lambda ids, wt=1.5: sp.csr_matrix(EB[[eid[i] for i in ids]] * wt)
wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()
res = {"n_train": len(trn), "n_voted_test": len(vt)}
# --- presence, natural weights
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); sy = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); y = np.array([1 if hk[i]["conditions"] else 0 for i in trn])
Xw = wc(trn); Xwv = wc(vt); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
ph = art["ph"].predict_proba(Xwv)[:, 1]; ps = art["ps"].predict_proba(Xwv)[:, 1]; bl = 1 / (1 + np.exp(-(lg(ph) + lg(ps)) / 2))
auc = lambda p: round(float(roc_auc_score(sy, p, sample_weight=w)), 4)
res["presence_weighted_auc"] = {"tfidf_haiku_trained(ph)": auc(ph), "shipped_blend": auc(bl)}
Xb = bge(trn); Xbv = bge(vt)
res["presence_weighted_auc"]["bge_only"] = auc(LogisticRegression(max_iter=500, C=3).fit(Xb, y).predict_proba(Xbv)[:, 1])
pst = LogisticRegression(max_iter=500, C=1).fit(sp.hstack([Xw, Xb]).tocsr(), y).predict_proba(sp.hstack([Xwv, Xbv]).tocsr())[:, 1]; res["presence_weighted_auc"]["tfidf_plus_bge"] = auc(pst)
res["presence_weighted_auc"]["blend_plus_bge_stack"] = auc(1 / (1 + np.exp(-(lg(pst) + lg(ps)) / 2)))
json.dump(res, open(H0 / "runs/snapshots/loop14_results.json", "w"), indent=1); hb.beat("t26-bge-features", progress="presence done; condition head")
# --- which condition, Sonnet-positive test items
vs = [i for i in test if i in sn and sn[i]["conditions"]]; sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
def cond(Xt, Xv_, C):
    m = LogisticRegression(max_iter=300, C=C).fit(Xt, yc); P = m.predict_proba(Xv_); cl = m.classes_; t = np.argsort(-P, 1)[:, :2]
    return {"top1": round(float(np.mean([cl[t[k, 0]] in sset[k] for k in range(len(vs))])), 3), "top2": round(float(np.mean([bool({cl[t[k, 0]], cl[t[k, 1]]} & sset[k]) for k in range(len(vs))])), 3)}
keep = art["keepc"]; Xc = wc(rows)[:, keep]; Xcv = wc(vs)[:, keep]; Bc = bge(rows); Bcv = bge(vs)
res["condition_top1_top2"] = {"baseline_tfidf_from_expert_v2": {"top1": 0.704, "top2": 0.828, "note": "L285"}, "bge_only": cond(Bc, Bcv, 10), "tfidf_plus_bge": cond(sp.hstack([Xc, Bc]).tocsr(), sp.hstack([Xcv, Bcv]).tocsr(), 3)}
json.dump(res, open(H0 / "runs/snapshots/loop14_results.json", "w"), indent=1); hb.beat("t26-bge-features", progress="condition done; topic head (slow)")
# --- topic, voted items vs Sonnet
ys = np.array([sn[i]["topic"] for i in vt]); yt = np.array([hk[i]["topic"] for i in trn])
def topic(Xt, Xv_, C, mi=300):
    m = LogisticRegression(max_iter=mi, C=C).fit(Xt, yt); P = m.predict_proba(Xv_); cl = m.classes_; t = np.argsort(-P, 1)[:, :2]
    return {"top1": round(float(np.mean(cl[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(cl[t[k]]) for k in range(len(vt))])), 3)}
res["topic_top1_top2"] = {"baseline_expert_v2_tfidf_plus_static": {"top1": 0.679, "top2": 0.831, "note": "v6"}, "bge_only": topic(Xb, Xbv, 10)}
Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt]); res["topic_top1_top2"]["tfidf_plus_bge"] = topic(sp.hstack([Tt, Xb]).tocsr(), sp.hstack([Tv, Xbv]).tocsr(), 3)
json.dump(res, open(H0 / "runs/snapshots/loop14_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t26-bge-features", "done", last=f"presence AUC {res['presence_weighted_auc']}; condition {res['condition_top1_top2']['tfidf_plus_bge']}; topic {res['topic_top1_top2']['tfidf_plus_bge']}", progress="bge-small features scored")
