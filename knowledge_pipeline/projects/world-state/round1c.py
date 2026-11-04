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
# ---- round 1c: 38 one-vs-rest detectors
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
Xc = lambda X, E: sp.hstack([X[:, keepc], sp.csr_matrix(E)]).tocsr()
Xtrc = Xc(Xtr, Etr); Xdqc = Xc(Xdq, Edq); Xoldc = Xc(Xold, Eold)
ixs = [pos_ix[i] for i in strn]
def Y(src, ids): return np.array([[any(c["condition"] == cl for c in src[i]["conditions"]) for cl in classes] for i in ids])
YH = Y(hk, trn); YS = Y(sn, strn); print("positives per condition (Haiku) min/median/max", YH.sum(0).min(), int(np.median(YH.sum(0))), YH.sum(0).max(), "Sonnet", YS.sum(0).min(), int(np.median(YS.sum(0))), YS.sum(0).max(), flush=True)
def heads(X, Yb, C):
    out = []
    for k in range(len(classes)):
        out.append(LogisticRegression(C=C, max_iter=200).fit(X, Yb[:, k]) if Yb[:, k].sum() >= 5 else None)
    return out
def probs(hs, X): return np.column_stack([h.predict_proba(X)[:, 1] if h is not None else np.zeros(X.shape[0]) for h in hs])
yq = np.array([bool(dsn[i]["conditions"]) for i in dq]); yo = np.array([bool(sn[i]["conditions"]) for i in vt]); Sq = [dsn[i]["conditions"] for i in dq]; So = [sn[i]["conditions"] for i in vt]
def curve(p, y, w=None):
    w = np.ones(len(y)) if w is None else w; o = np.argsort(-p); tp = np.cumsum((y[o]) * w[o]); n = np.cumsum(w[o]); prec = tp / n; rec = tp / (y * w).sum(); m = prec >= 0.83
    return float(rec[m].max()) if m.any() else 0.0
cur_dq = 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(Xdq)[:, 1]) + lg(art["ps"].predict_proba(Xdq)[:, 1])) / 2)); cur_old = 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(Xold)[:, 1]) + lg(art["ps"].predict_proba(Xold)[:, 1])) / 2))
res = {}
def report(name, pq, po, Pq=None, Po=None):
    r = {"auc_devq": round(float(roc_auc_score(yq, pq)), 4), "auc_old_w": round(float(roc_auc_score(yo, po, sample_weight=wold)), 4), "recall_at_precision_0.83_devq": round(curve(pq, yq), 3), "recall_at_precision_0.83_old_w": round(curve(po, yo, wold), 3)}
    rng = np.random.RandomState(0); d = []
    for _ in range(200):
        b = rng.randint(0, len(yq), len(yq)); d.append(curve(pq[b], yq[b]) - curve(cur_dq[b], yq[b]))
    r["devq_recall_gain_vs_current_boot"] = [round(float(np.mean(d)), 3), round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]
    if Pq is not None:
        ix = [k for k, s in enumerate(Sq) if s]; r["argmax_head_top1_devq"] = round(float(np.mean([classes[Pq[k].argmax()] in [x["condition"] for x in Sq[k]] for k in ix])), 3); ix = [k for k, s in enumerate(So) if s]; r["argmax_head_top1_old"] = round(float(np.mean([classes[Po[k].argmax()] in [x["condition"] for x in So[k]] for k in ix])), 3)
    res[name] = r; print(name, json.dumps(r), flush=True)
for tn, (Xt, Yb, label) in {"haiku": (Xtrc, YH, "Haiku labels"), "sonnet": (Xtrc[ixs], YS, "Sonnet labels")}.items():
    hs = heads(Xt, Yb, 1.0); Pq = probs(hs, Xdqc); Po = probs(hs, Xoldc)
    nor = lambda P: 1 - np.prod(1 - P, axis=1); mx = lambda P: P.max(1)
    report(f"{tn}: noisy-OR", nor(Pq), nor(Po), Pq, Po); report(f"{tn}: max", mx(Pq), mx(Po), Pq, Po)
    bl = lambda cur, P: 1 / (1 + np.exp(-(lg(cur) + lg(np.clip(mx(P), 1e-6, 1 - 1e-6))) / 2)); report(f"{tn}: blend(current, max)", bl(cur_dq, Pq), bl(cur_old, Po), Pq, Po)
json.dump(res, open("runs/pulse/round1c.json", "w"), indent=1)
