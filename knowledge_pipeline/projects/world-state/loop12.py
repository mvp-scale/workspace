import json, glob, re, pickle, pathlib, sys, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t24-joint-model", where="[CPU]", task="T10", state="running", why="Does a joint 38-conditions-plus-none model recall more conditions at the same precision?", success="Weighted recall 14%+ at precision 0.80", next="Score, log", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); hk = {}; sn = {}; old = set()
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); feat = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, art["keepc"]]
rows, y = [], []
for i in trn:
    cs = [c["condition"] for c in hk[i]["conditions"]] or ["none"]
    for c in cs: rows.append(i); y.append(c)
hb.beat("t24-joint-model", progress=f"fitting 39 classes on {len(rows)} rows")
X = feat(rows); m = LogisticRegression(max_iter=200, C=3).fit(X, y); cl = list(m.classes_); ni = cl.index("none")
P = m.predict_proba(feat(vt)); pres = 1 - P[:, ni]
sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); hneg_t = sum(1 for i in test if not old_l if False) if False else None
oldl = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): oldl[r["item_id"]] = r["label"]
hp_t = sum(1 for i in test if oldl[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if oldl[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if oldl[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda mk: float(w[mk].sum())
res = {"train_rows": len(rows), "weighted_auc_vs_sonnet_presence": round(float(roc_auc_score(sp_, pres, sample_weight=w)), 4)}
# the shipped blend's weighted AUC on the same items for comparison
from expert1_runtime import Expert
e = Expert(str(H0 / "runs/expert1/expert1_v2.pkl")); bl = np.array([e.read(pool[i]["text"])["condition_present"]["confidence"] * (1 if e.read(pool[i]["text"])["condition_present"]["answer"] else -1) for i in vt]); bls = 1 / (1 + np.exp(-3 * bl)) if False else (bl + 1) / 2
res["blend_weighted_auc_vs_sonnet_presence_approx"] = round(float(roc_auc_score(sp_, bls, sample_weight=w)), 4)
scan = []
for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    mk = pres >= t; scan.append({"min_p_present": t, "n": int(mk.sum()), "weighted_precision": round(W(mk & (sp_ == 1)) / W(mk), 3) if mk.any() else None, "weighted_recall": round(W(mk & (sp_ == 1)) / W(sp_ == 1), 3)})
res["scan"] = scan; best = [s for s in scan if s["weighted_precision"] and s["weighted_precision"] >= 0.8]; res["recall_at_precision_0.8"] = max((s["weighted_recall"] for s in best), default=None)
json.dump(res, open(H0 / "runs/snapshots/loop12_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t24-joint-model", "done", last=f"recall at precision 0.8: {res['recall_at_precision_0.8']}; AUC {res['weighted_auc_vs_sonnet_presence']}", progress="1,466 voted items, natural weights")
