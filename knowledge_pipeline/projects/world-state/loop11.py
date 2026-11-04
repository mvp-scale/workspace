import json, glob, re, pickle, pathlib, sys, collections, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t20-which-condition", where="[CPU]", task="T10", state="running", why="Which of the 38 conditions, up or down, and how big: the half of the product not yet measured", success="Top-1 condition in Sonnet's set 0.70+; direction 0.80+", next="Score and log", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v1.pkl", "rb")); hk = {}; sn = {}; old = set()
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
vt = [i for i in test if i in sn and hk[i]["conditions"] and sn[i]["conditions"]]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and hk[i]["conditions"]]
rows, ycond = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); ycond.append(c["condition"])
feat = lambda ids: sp.hstack([art["vw"].transform([re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]), art["vc"].transform([re.sub(r"\s+", " ", pool[i]["text"]) for i in ids])]).tocsr()
Xtr0 = feat(rows); keepc = np.argsort(-np.asarray((Xtr0 > 0).sum(0)).ravel())[:40000]; feat0 = feat; feat = lambda ids: feat0(ids)[:, keepc]; Xtr = Xtr0[:, keepc]; Xv = feat(vt); hb.beat("t20-which-condition", progress=f"fitting on {len(rows)} condition rows from {len(trn)} positive items; testing on {len(vt)} items where both teachers name a condition")
m = LogisticRegression(max_iter=300, C=3).fit(Xtr, ycond); P = m.predict_proba(Xv); cl = m.classes_; top = np.argsort(-P, 1)[:, :2]
sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vt]; hset = [{c["condition"] for c in hk[i]["conditions"]} for i in vt]
t1 = np.mean([cl[top[k, 0]] in sset[k] for k in range(len(vt))]); t2 = np.mean([bool({cl[top[k, 0]], cl[top[k, 1]]} & sset[k]) for k in range(len(vt))]); base = np.mean([bool(hset[k] & sset[k]) for k in range(len(vt))])
# direction and size: separate classifiers on the rows, keyed on the same features plus the condition identity
dirs = np.array([next(c["direction"] for c in hk[i]["conditions"] if c["condition"] == y) for i, y in zip(rows, ycond)]); lvs = np.array([next(c["level"] for c in hk[i]["conditions"] if c["condition"] == y) for i, y in zip(rows, ycond)])
oh = lambda labels: sp.csr_matrix((np.ones(len(labels)), (range(len(labels)), [list(cl).index(x) for x in labels])), shape=(len(labels), len(cl)))
Xd = sp.hstack([Xtr, oh(ycond) * 2]).tocsr(); md = LogisticRegression(max_iter=300, C=1).fit(Xd, dirs); LV = ["minor", "notable", "major", "severe", "extreme"]; lvi = np.array([LV.index(x) for x in lvs]); ml = LogisticRegression(max_iter=300, C=1).fit(Xd, lvi)
dm = []; ex = []; w1 = []; bd = []; bl = []; bw = []
for k, i in enumerate(vt):
    pc = cl[top[k, 0]]
    if pc not in sset[k]: continue
    x = sp.hstack([feat([i]), oh([pc]) * 2]).tocsr(); sc = next(c for c in sn[i]["conditions"] if c["condition"] == pc)
    dm.append(md.predict(x)[0] == sc["direction"]); pl = int(ml.predict(x)[0]); sl = LV.index(sc["level"]); ex.append(pl == sl); w1.append(abs(pl - sl) <= 1)
    hc = next((c for c in hk[i]["conditions"] if c["condition"] == pc), None)
    if hc: bd.append(hc["direction"] == sc["direction"]); bl.append(LV.index(hc["level"]) == sl); bw.append(abs(LV.index(hc["level"]) - sl) <= 1)
res = {"n_items_both_teachers_name_a_condition": len(vt), "train_condition_rows": len(rows), "teachers_share_a_condition": round(float(base), 3), "student_top1_in_sonnet_set": round(float(t1), 3), "student_top2_hits_sonnet_set": round(float(t2), 3),
       "n_condition_matches": len(dm), "direction_student_vs_sonnet": round(float(np.mean(dm)), 3), "size_exact_student_vs_sonnet": round(float(np.mean(ex)), 3), "size_within_one_student_vs_sonnet": round(float(np.mean(w1)), 3),
       "teacher_baseline_on_same_matches": {"n": len(bd), "direction_haiku_vs_sonnet": round(float(np.mean(bd)), 3) if bd else None, "size_exact": round(float(np.mean(bl)), 3) if bl else None, "size_within_one": round(float(np.mean(bw)), 3) if bw else None}}
json.dump(res, open(H0 / "runs/snapshots/loop11_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t20-which-condition", "done", last=f"top1 {res['student_top1_in_sonnet_set']}, direction {res['direction_student_vs_sonnet']}, size within one {res['size_within_one_student_vs_sonnet']}", progress=f"{len(vt)} items")
