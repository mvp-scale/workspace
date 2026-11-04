import json, glob, re, pickle, pathlib, sys, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t25-condition-curve", where="[CPU]", task="T10", state="running", why="Is which-condition data-starved? Learning curve of the condition head", success="Top-1 still rising 0.04+ from 50 to 100 percent of rows", next="Collect more items or stop", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); hk = {}; sn = {}; old = set()
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vs = [i for i in test if i in sn and sn[i]["conditions"]]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and hk[i]["conditions"]]; rng = np.random.RandomState(0); rng.shuffle(trn)
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); feat = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, art["keepc"]]
Xv = feat(vs); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; res = {"n_test_sonnet_positive": len(vs), "n_train_items": len(trn), "curve": {}}
for frac in (0.25, 0.5, 1.0):
    ids = trn[:int(len(trn) * frac)]; rows, y = [], []
    for i in ids:
        for c in hk[i]["conditions"]: rows.append(i); y.append(c["condition"])
    hb.beat("t25-condition-curve", progress=f"fitting {int(frac*100)}% ({len(rows)} rows)")
    m = LogisticRegression(max_iter=300, C=3).fit(feat(rows), y); P = m.predict_proba(Xv); cl = m.classes_; t = np.argsort(-P, 1)[:, :2]
    res["curve"][str(frac)] = {"rows": len(rows), "classes_seen": int(len(cl)), "top1": round(float(np.mean([cl[t[k, 0]] in sset[k] for k in range(len(vs))])), 3), "top2": round(float(np.mean([bool({cl[t[k, 0]], cl[t[k, 1]]} & sset[k]) for k in range(len(vs))])), 3)}
    json.dump(res, open(H0 / "runs/snapshots/loop13_results.json", "w"), indent=1)
print(json.dumps(res, indent=1)); hb.finish("t25-condition-curve", "done", last=str({k: v["top1"] for k, v in res["curve"].items()}), progress=f"{len(vs)} test items")
