"""T20 round 1b (ledger L446): retrain the which-condition head and the presence blend on different teachers; evaluate on DEVQ (1,997 natural) and the old 1,466. CPU, local, no hosted calls.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python round1b.py"""
import json, glob, re, sys, math, time, pickle, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, ".")
from expert1_runtime import Expert3
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb")); reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}["v5-leaf"]; e = Expert3(reg["path"])
eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; LEAF = np.load("runs/embeds/leaf_64_fp32.npy")
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and i in eid]; vt = [i for i in test if i in sn]; strn = [i for i in trn if i in sn]
hn_t = sum(1 for i in test if not hk[i]["conditions"]); hn_v = sum(1 for i in vt if not hk[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = len(vt) - hn_v; wold = np.array([hp_t / hp_v if hk[i]["conditions"] else hn_t / hn_v for i in vt])
qt = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}; dsn = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; dq = sorted(i for i in dsn if i in qt)
clean = lambda t: re.sub(r"\s+", " ", t); XS = lambda texts: sp.hstack([art["vw"].transform([clean(t) for t in texts]), art["vc"].transform([clean(t) for t in texts])]).tocsr()
t0 = time.time(); Xtr = XS([pool[i]["text"] for i in trn]); Etr = LEAF[[eid[i] for i in trn]] * 1.5; Xold = XS([pool[i]["text"] for i in vt]); Eold = LEAF[[eid[i] for i in vt]] * 1.5
Xdq = XS([qt[i] for i in dq]); Edq = np.array([e.embed(qt[i]) for i in dq]); print("features", round(time.time() - t0), "s; train", len(trn), "sonnet-train", len(strn), "devq", len(dq), "old", len(vt), flush=True)
pos_ix = {i: k for k, i in enumerate(trn)}; keepc = art["keepc"]; classes = list(art["enc_heads"]["cond"]["classes"]); cix = {c: k for k, c in enumerate(classes)}
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
res = {"which_condition_top1": {}, "presence": {}}
# ---- which-condition head: rows = one per labelled condition
def rows(src, ids):
    r_, y_ = [], []
    for i in ids:
        for c in src[i]["conditions"]:
            if c["condition"] in cix: r_.append(pos_ix[i]); y_.append(cix[c["condition"]])
    return np.array(r_), np.array(y_)
Xc = lambda X, E: sp.hstack([X[:, keepc], sp.csr_matrix(E)]).tocsr()
rh, yh = rows(hk, trn); rs, ys = rows(sn, strn); print("which rows Haiku", len(rh), "Sonnet", len(rs), flush=True)
dsets = {"devq": (Xc(Xdq, Edq), [dsn[i]["conditions"] for i in dq]), "old": (Xc(Xold, Eold), [sn[i]["conditions"] for i in vt])}
def evalw(clf, name):
    out = {}
    for dn, (Xe, S) in dsets.items():
        ix = [k for k, s in enumerate(S) if s]; P = clf.predict_proba(Xe[ix]); cl = clf.classes_; top1 = [cl[P[n].argmax()] for n in range(len(ix))]; hit = np.array([classes[t] in [x["condition"] for x in S[k]] for t, k in zip(top1, ix)])
        t2 = np.array([any(classes[cl[j]] in [x["condition"] for x in S[k]] for j in np.argsort(-P[n])[:2]) for n, k in enumerate(ix)]); out[dn] = {"n_positive": len(ix), "top1": round(float(hit.mean()), 3), "top1_ci95": wil(int(hit.sum()), len(hit)), "top2": round(float(t2.mean()), 3)}
    res["which_condition_top1"][name] = out; print("which", name, json.dumps(out), flush=True)
Xtrc = Xc(Xtr, Etr)
for C in (3.0,):
    evalw(LogisticRegression(C=C, max_iter=300).fit(Xtrc[rh], yh), f"haiku_rows_C{C}")
    evalw(LogisticRegression(C=C, max_iter=300).fit(Xtrc[rs], ys), f"sonnet_rows_C{C}")
    X2 = sp.vstack([Xtrc[rh], Xtrc[rs]]).tocsr(); y2 = np.r_[yh, ys]; w2 = np.r_[np.ones(len(yh)), 5 * np.ones(len(ys))]; evalw(LogisticRegression(C=C, max_iter=300).fit(X2, y2, sample_weight=w2), f"haiku+sonnetx5_C{C}")
# ---- presence blend
yH = np.array([bool(hk[i]["conditions"]) for i in trn]); yS = np.array([bool(sn[i]["conditions"]) for i in strn]); ixs = [pos_ix[i] for i in strn]
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
yq = np.array([bool(dsn[i]["conditions"]) for i in dq]); yo = np.array([bool(sn[i]["conditions"]) for i in vt])
def curve(p, y, w=None):
    w = np.ones(len(y)) if w is None else w; o = np.argsort(-p); tp = np.cumsum((y[o]) * w[o]); n = np.cumsum(w[o]); prec = tp / n; rec = tp / (y * w).sum(); m = prec >= 0.83
    return float(rec[m].max()) if m.any() else 0.0
def evalp(p_dq, p_old, name):
    res["presence"][name] = {"auc_devq": round(float(roc_auc_score(yq, p_dq)), 4), "auc_old_w": round(float(roc_auc_score(yo, p_old, sample_weight=wold)), 4), "recall_at_precision_0.83_devq": round(curve(p_dq, yq), 3), "recall_at_precision_0.83_old_w": round(curve(p_old, yo, wold), 3)}; print("presence", name, json.dumps(res["presence"][name]), flush=True)
cur = lambda X, Xs_: 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(Xs_)[:, 1]) + lg(art["ps"].predict_proba(Xs_)[:, 1])) / 2))
evalp(cur(None, Xdq), cur(None, Xold), "current_engine (sparse, Haiku head + Sonnet head, equal blend)")
Xtrp = sp.hstack([Xtr, sp.csr_matrix(Etr)]).tocsr(); Xdqp = sp.hstack([Xdq, sp.csr_matrix(Edq)]).tocsr(); Xoldp = sp.hstack([Xold, sp.csr_matrix(Eold)]).tocsr()
mh = LogisticRegression(C=1.0, max_iter=400).fit(Xtrp, yH); ms = LogisticRegression(C=1.0, max_iter=400).fit(Xtrp[ixs], yS)
for wS in (0.0, 0.5, 0.75, 1.0):
    f = lambda X: 1 / (1 + np.exp(-((1 - wS) * lg(mh.predict_proba(X)[:, 1]) + wS * lg(ms.predict_proba(X)[:, 1]))))
    evalp(f(Xdqp), f(Xoldp), f"sparse+leaf, Sonnet weight {wS}")
json.dump(res, open("runs/pulse/round1b.json", "w"), indent=1)
