"""T20 step 1 pilot 2: does giving the encoder vector (leaf, cached) to the condition-PRESENCE head lift its AUC against Sonnet? Today presence uses only word and character counts. Old dev 1,466, re-weighted to the natural stream. CPU, local. A pilot (look before the sweep), not a verdict."""
import json, glob, re, sys, pickle, numpy as np, scipy.sparse as sp, warnings, time
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb"))
ids_all = json.load(open("runs/embeds/bge_small_ids.json")); eid = {i: k for k, i in enumerate(ids_all)}; LEAF = np.load("runs/embeds/leaf_64_fp32.npy")
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and i in eid]; vt = [i for i in test if i in sn]
strn = [i for i in trn if i in sn]; print("train Haiku", len(trn), "train Sonnet", len(strn), "dev", len(vt), flush=True)
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); X = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()
Ex = lambda ids: LEAF[[eid[i] for i in ids]] * 1.5
t0 = time.time(); Xt, Xs, Xv = X(trn), X(strn), X(vt); Et, Es, Ev = Ex(trn), Ex(strn), Ex(vt); print("features", round(time.time() - t0), "s", flush=True)
yh = np.array([bool(hk[i]["conditions"]) for i in trn]); ys = np.array([bool(sn[i]["conditions"]) for i in strn]); yv = np.array([bool(sn[i]["conditions"]) for i in vt])
hn_t = sum(1 for i in test if not hk[i]["conditions"]); hn_v = sum(1 for i in vt if not hk[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = len(vt) - hn_v; w = np.array([hp_t / hp_v if hk[i]["conditions"] else hn_t / hn_v for i in vt])
auc = lambda p: round(float(roc_auc_score(yv, p, sample_weight=w)), 4); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
res = {}
def fit(Xa, y, C): return LogisticRegression(C=C, max_iter=400).fit(Xa, y)
for C in (1.0, 3.0):
    a = fit(Xt, yh, C); b = fit(Xs, ys, C); pa, pb = a.predict_proba(Xv)[:, 1], b.predict_proba(Xv)[:, 1]; res[f"sparse_C{C}"] = {"haiku": auc(pa), "sonnet": auc(pb), "blend_logit_mean": auc((lg(pa) + lg(pb)) / 2)}; print(f"sparse C={C}", res[f"sparse_C{C}"], flush=True)
for C in (0.3, 1.0):
    a = fit(sp.hstack([Xt, sp.csr_matrix(Et)]).tocsr(), yh, C); b = fit(sp.hstack([Xs, sp.csr_matrix(Es)]).tocsr(), ys, C); XvE = sp.hstack([Xv, sp.csr_matrix(Ev)]).tocsr(); pa, pb = a.predict_proba(XvE)[:, 1], b.predict_proba(XvE)[:, 1]
    res[f"sparse+leaf_C{C}"] = {"haiku": auc(pa), "sonnet": auc(pb), "blend_logit_mean": auc((lg(pa) + lg(pb)) / 2)}; print(f"sparse+leaf C={C}", res[f"sparse+leaf_C{C}"], flush=True)
for C in (1.0, 10.0):
    a = fit(Et, yh, C); b = fit(Es, ys, C); pa, pb = a.predict_proba(Ev)[:, 1], b.predict_proba(Ev)[:, 1]; res[f"leaf_only_C{C}"] = {"haiku": auc(pa), "sonnet": auc(pb), "blend_logit_mean": auc((lg(pa) + lg(pb)) / 2)}; print(f"leaf only C={C}", res[f"leaf_only_C{C}"], flush=True)
json.dump(res, open("runs/pulse/presence_pilot.json", "w"), indent=1)
