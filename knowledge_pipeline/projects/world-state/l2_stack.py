"""T20 lever L2 (ledger): stacked presence model, cross-validated on DEVQ + old. CPU, local, no hosted calls. Registers its own heartbeat (job t20-l2-stack) with its pid.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python l2_stack.py"""
import json, glob, re, sys, os, math, pickle, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, "."); sys.path.insert(0, "../../kit/live")
import heartbeat as hb
hb.beat("t20-l2-stack", pid=os.getpid(), where="[CPU]", task="T20", state="running", progress="building features", why="Does a stacked model that adds topic and story context find more real conditions at 83% right than the current presence gate? (ledger L2 note)", success="Recall at presence precision 0.83 on DEVQ up 0.08, bootstrap lower bound above 0", next="Record WIN or NO GAIN, refresh the scoreboard; then second-stage reader (L3) or more Sonnet labels (L4)", need="Nothing", cap=3600)
from model2vec import StaticModel
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb")); sm = StaticModel.from_pretrained(art["static"])
raw = json.load(open("runs/pulse/raw_v5-leaf.json")); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r
eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; LEAF = np.load("runs/embeds/leaf_64_fp32.npy")
hk = {}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and i in eid]; strn = [i for i in trn if i in sn]; pos = {i: k for k, i in enumerate(trn)}
clean = lambda t: re.sub(r"\s+", " ", t); XS = lambda texts: sp.hstack([art["vw"].transform([clean(t) for t in texts]), art["vc"].transform([clean(t) for t in texts])]).tocsr()
Xtr = sp.hstack([XS([pool[i]["text"] for i in trn]), sp.csr_matrix(LEAF[[eid[i] for i in trn]] * 1.5)]).tocsr()
mh = LogisticRegression(C=1.0, max_iter=300).fit(Xtr, np.array([bool(hk[i]["conditions"]) for i in trn])); ixs = [pos[i] for i in strn]; ms = LogisticRegression(C=1.0, max_iter=300).fit(Xtr[ixs], np.array([bool(sn[i]["conditions"]) for i in strn])); print("leaf presence heads trained", flush=True)
items = [dict(r, set="devq") for r in raw["devq"]] + [dict(r, set="old") for r in raw["old"]]; M = art; feats = []
for r in items:
    t = clean(pool[r["id"]]["text"]); h = re.split(r"(?<=[.!?])\s", t, 1)[0]; e = np.hstack([sm.encode([t]), sm.encode([h])]); xt = sp.hstack([M["vt"].transform([t]), sp.csr_matrix(M["ss"].transform(e) * 0.1)]).tocsr(); xwc = XS([t])
    pt = M["topic"].predict_proba(xt)[0]; ps_ = M["story"].predict_proba(xwc)[0]; v = np.array(LEAF[eid[r["id"]]] * 1.5) if r["id"] in eid else None
    if v is None:  # queue items: no cached vector; the leaf vector was computed by the raw step through the same encoder, recompute cheaply
        from expert1_runtime import Expert3
        if "_e" not in globals(): globals()["_e"] = Expert3({r_["version"]: r_ for r_ in json.load(open("engine_versions.json"))}["v5-leaf"]["path"])
        v = _e.embed(pool[r["id"]]["text"])
    xe = sp.hstack([xwc, sp.csr_matrix(v[None, :])]).tocsr()
    feats.append(np.r_[lg(r["ph"]), lg(r["ps"]), lg(mh.predict_proba(xe)[0, 1]), lg(ms.predict_proba(xe)[0, 1]), pt, ps_, r["cconf"], len(t) / 300.0])
F = np.array(feats); y = np.array([bool(r["S"]["conditions"]) for r in items]); isq = np.array([r["set"] == "devq" for r in items]); w = np.array([r.get("w", 1.0) if r["set"] == "old" else 1.0 for r in items]); print("features", F.shape, "positives", int(y.sum()), flush=True)
cur = 1 / (1 + np.exp(-(F[:, 0] + F[:, 1]) / 2))
def curve(p, yy, ww=None):
    ww = np.ones(len(yy)) if ww is None else ww; o = np.argsort(-p); tp = np.cumsum(yy[o] * ww[o]); n = np.cumsum(ww[o]); prec = tp / n; rec = tp / (yy * ww).sum(); m = prec >= 0.83
    return float(rec[m].max()) if m.any() else 0.0
res = {"n_devq": int(isq.sum()), "positives_devq": int(y[isq].sum()), "current_gate_recall_at_0.83_devq": round(curve(cur[isq], y[isq]), 3)}; out = {}
for name in ("logistic", "gbm"):
    P = np.zeros(len(y))
    for seed in range(3):
        for a, b in StratifiedKFold(5, shuffle=True, random_state=seed).split(F, y):
            clf = LogisticRegression(C=1.0, max_iter=500) if name == "logistic" else HistGradientBoostingClassifier(max_iter=150, learning_rate=0.06, max_leaf_nodes=8, l2_regularization=1.0, random_state=seed)
            if name == "logistic": mu, sd = F[a].mean(0), F[a].std(0) + 1e-6; clf.fit((F[a] - mu) / sd, y[a], sample_weight=w[a]); P[b] += clf.predict_proba((F[b] - mu) / sd)[:, 1] / 3
            else: clf.fit(F[a], y[a], sample_weight=w[a]); P[b] += clf.predict_proba(F[b])[:, 1] / 3
    out[name] = P; rq = curve(P[isq], y[isq]); rng = np.random.RandomState(0); d = []
    ix = np.where(isq)[0]
    for _ in range(200): bb = ix[rng.randint(0, len(ix), len(ix))]; d.append(curve(P[bb], y[bb]) - curve(cur[bb], y[bb]))
    from sklearn.metrics import roc_auc_score
    res[name] = {"recall_at_0.83_devq": round(rq, 3), "gain_vs_current_boot": [round(float(np.mean(d)), 3), round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)], "auc_devq": round(float(roc_auc_score(y[isq], P[isq])), 4), "auc_current_devq": round(float(roc_auc_score(y[isq], cur[isq])), 4)}; print(name, json.dumps(res[name]), flush=True)
json.dump(res, open("runs/pulse/l2_stack.json", "w"), indent=1); hb.finish("t20-l2-stack", "done", last=f"current {res['current_gate_recall_at_0.83_devq']}, logistic {res['logistic']['recall_at_0.83_devq']}, gbm {res['gbm']['recall_at_0.83_devq']} (recall at 83% precision, DEVQ)")
