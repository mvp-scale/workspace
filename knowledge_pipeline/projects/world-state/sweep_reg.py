"""Overfitting sweep (L362): regularisation C of the story head, the linear topic head and the encoder topic head of BitMob Expert 1 v3.1.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python sweep_reg.py        local GPU for seconds (gpu_lr softmax heads, same objective as sklearn), no hosted calls
RULE (written before any score, ledger L362): fit on the earliest 90% of the training period, validate on the latest 10% (Haiku labels, the training teacher), grid C in {0.1, 0.3, 1, 3, 10};
pick per head the best validation agreement (story agreement; topic top-2); a tie within 0.002 takes the smaller C; refit on the full training period; save expert1_v32.pkl (v3.1 with only these heads replaced).
The test items (later period, Sonnet labels) are never used here. Score v3.2 afterwards with score_version.py."""
import json, glob, re, pickle, pathlib, sys, os, time, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import gpu_lr as G
from sklearn.linear_model import LogisticRegression
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
art = pickle.load(open("runs/expert1/expert1_v31.pkl", "rb")); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; trn.sort(key=lambda i: pool[i]["date"]); n = len(trn); cut_at = int(n * 0.9); print("train", n, "fit", cut_at, "val", n - cut_at, flush=True)
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); T = [clean(i) for i in trn]; head = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in T]
sm = StaticModel.from_pretrained(art["static"]); E = np.hstack([sm.encode(T), sm.encode(head)])
Xwc = sp.hstack([art["vw"].transform(T), art["vc"].transform(T)]).tocsr(); Xt = sp.hstack([art["vt"].transform(T), sp.csr_matrix(art["ss"].transform(E) * 0.1)]).tocsr(); Tt = art["vt"].transform(T).tocsr()
EB = np.load("runs/embeds/bge_small_64.npy"); eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; B = EB[[eid[i] for i in trn]] * 1.5
scl = np.array(art["story"].classes_); tcl = np.array(sorted(set(hk[i]["topic"] for i in trn))); assert list(tcl) == list(art["topic"].classes_) or True
ys = np.searchsorted(scl, [hk[i]["story_type"] for i in trn]); yt = np.searchsorted(tcl, [hk[i]["topic"] for i in trn])
fit_ix = np.arange(cut_at); val_ix = np.arange(cut_at, n); GRID = [0.1, 0.3, 1, 3, 10]; res = {"n_train": n, "n_fit": cut_at, "n_val": n - cut_at, "grid": {}}
def top2(P, y): return float(np.mean([y[k] in np.argsort(-P[k])[:2] for k in range(len(y))]))
for name, X, Xd, y, kind in (("story", Xwc, None, ys, "acc"), ("topic_linear", Xt, None, yt, "top2"), ("topic_encoder", Tt, B, yt, "top2")):
    res["grid"][name] = {}
    for C in GRID:
        t0 = time.time(); m = G.fit(X[fit_ix], None if Xd is None else Xd[fit_ix], y[fit_ix], int(y.max()) + 1, C=C); P = G.predict(m, X[val_ix], None if Xd is None else Xd[val_ix])
        a = float(np.mean(P.argmax(1) == y[val_ix])); b = top2(P, y[val_ix]) if kind == "top2" else a; res["grid"][name][str(C)] = {"val_top1": round(a, 4), "val_metric": round(b, 4)}; print(name, "C", C, "val top1", round(a, 4), "metric", round(b, 4), f"{time.time() - t0:.0f}s", flush=True)
best = {}
for name in res["grid"]:
    g = res["grid"][name]; top = max(v["val_metric"] for v in g.values()); best[name] = min(float(c) for c, v in g.items() if v["val_metric"] >= top - 0.002)   # tie within 0.002 takes the smaller C
res["chosen_C"] = best; print("chosen", best, flush=True)
def lr_from(m, classes, nfeat):
    lr = LogisticRegression(); lr.classes_ = np.array(classes); lr.coef_ = m[0].cpu().numpy().T.astype(np.float64); lr.intercept_ = m[2].cpu().numpy().astype(np.float64); lr.n_features_in_ = nfeat; return lr
npy = lambda m: {"W": m[0].cpu().numpy(), "V": m[1].cpu().numpy(), "b": m[2].cpu().numpy()}
ms = G.fit(Xwc, None, ys, len(scl), C=best["story"]); mt = G.fit(Xt, None, yt, len(tcl), C=best["topic_linear"]); me = G.fit(Tt, B, yt, len(tcl), C=best["topic_encoder"])
new = {**art}; new["story"] = lr_from(ms, scl, Xwc.shape[1]); new["topic"] = lr_from(mt, tcl, Xt.shape[1]); new["enc_heads"] = {**art["enc_heads"], "topic": {**npy(me), "classes": tcl}}
# the answered/unknown cut-offs depend on confidence scale: recompute them with the original rule (80 percent running agreement) on the validation slice only
def cutoff(conf, ok):
    q = np.argsort(-conf); run = np.cumsum(ok[q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; return float(conf[q][idx.max()]) if len(idx) else 1.01
Ps = new["story"].predict_proba(Xwc[val_ix]); Pt = new["topic"].predict_proba(Xt[val_ix]); cuts = dict(art["cuts"])
cuts["story_type"] = cutoff(Ps.max(1), Ps.argmax(1) == ys[val_ix]); o2 = np.argsort(-Pt, 1)[:, :2]; cuts["topic_top2"] = cutoff(np.take_along_axis(Pt, o2, 1).sum(1), np.array([yt[val_ix][k] in o2[k] for k in range(len(val_ix))]))
new["cuts"] = cuts; res["cuts_old"] = art["cuts"]; res["cuts_new"] = cuts
chk = G.predict(ms, Xwc[val_ix[:200]], None); assert np.allclose(chk, new["story"].predict_proba(Xwc[val_ix[:200]]), atol=1e-4), "sklearn wrapper does not match the GPU head"
pickle.dump(new, open("runs/expert1/expert1_v32.pkl", "wb")); json.dump(res, open("runs/snapshots/sweep_reg.json", "w"), indent=1); print("saved expert1_v32.pkl", os.path.getsize("runs/expert1/expert1_v32.pkl") // 1000000, "MB", flush=True)
