import json, glob, re, pickle, pathlib, sys, time, os, subprocess, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
from model2vec import StaticModel
from threadpoolctl import threadpool_limits
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("build-expert2", where="[CPU]", task="T10", state="running", why="Add which-condition, direction and size to the expert and time every field", success="p50 under 6 ms; end-to-end precision 0.60+", next="Score, log, rerun gates_auto", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v1.pkl", "rb")); sm = StaticModel.from_pretrained(art["static"]); hk = {}; sn = {}; old = set()
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and hk[i]["conditions"]]
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); feat = lambda texts: sp.hstack([art["vw"].transform(texts), art["vc"].transform(texts)]).tocsr()
rows, ycond = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); ycond.append(c["condition"])
X0 = feat([clean(i) for i in rows]); keepc = np.argsort(-np.asarray((X0 > 0).sum(0)).ravel())[:40000]; Xtr = X0[:, keepc]
hb.beat("build-expert2", progress=f"fitting condition head on {len(rows)} rows")
cmod = LogisticRegression(max_iter=300, C=3).fit(Xtr, ycond); cl = cmod.classes_
dirs = np.array([next(c["direction"] for c in hk[i]["conditions"] if c["condition"] == y) for i, y in zip(rows, ycond)]); LV = ["minor", "notable", "major", "severe", "extreme"]; lvi = np.array([LV.index(next(c["level"] for c in hk[i]["conditions"] if c["condition"] == y)) for i, y in zip(rows, ycond)])
oh = lambda labels: sp.csr_matrix((np.ones(len(labels)), (range(len(labels)), [list(cl).index(x) for x in labels])), shape=(len(labels), len(cl)))
Xd = sp.hstack([Xtr, oh(ycond) * 2]).tocsr(); dmod = LogisticRegression(max_iter=300, C=1).fit(Xd, dirs); lmod = LogisticRegression(max_iter=300, C=1).fit(Xd, lvi)
# unknown rule for the condition head: items where Sonnet names a condition, cut for 80 percent running agreement (top-1 in Sonnet's set) on half A
vs = [i for i in vt if sn[i]["conditions"]]; Xv = feat([clean(i) for i in vs])[:, keepc]; P = cmod.predict_proba(Xv); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]
ok = np.array([cl[P[k].argmax()] in sset[k] for k in range(len(vs))]); conf = P.max(1); perm = np.random.RandomState(3).permutation(len(vs)); A_, B_ = perm[:len(vs) // 2], perm[len(vs) // 2:]
q = np.argsort(-conf[A_]); run = np.cumsum(ok[A_][q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; ccut = float(conf[A_][q][idx.max()]) if len(idx) else 1.01
a = conf[B_] >= ccut; cond_report = {"n_sonnet_positive_voted": len(vs), "cutoff": round(ccut, 3), "answered_share_B": round(float(a.mean()), 3), "agreement_on_answered_B": round(float(ok[B_][a].mean()), 3) if a.any() else None, "forced_B": round(float(ok[B_].mean()), 3)}
art2 = {**art, "cond": cmod, "dirm": dmod, "sizem": lmod, "keepc": keepc, "cond_cut": ccut, "LV": LV}; pkl = H0 / "runs/expert1/expert1_v2.pkl"; pickle.dump(art2, open(pkl, "wb")); size_mb = round(os.path.getsize(pkl) / 1e6, 1)
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def read(text, M=art2):
    t = re.sub(r"\s+", " ", text); h = re.split(r"(?<=[.!?])\s", t, 1)[0]; e = np.hstack([sm.encode([t]), sm.encode([h])]); xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr()
    xt = sp.hstack([M["vt"].transform([t]), sp.csr_matrix(M["ss"].transform(e) * 0.1)]).tocsr(); ps_ = M["story"].predict_proba(xwc)[0]; pt_ = M["topic"].predict_proba(xt)[0]
    pr = float((1 / (1 + np.exp(-(lg(M["ph"].predict_proba(xwc)[:, 1]) + lg(M["ps"].predict_proba(xwc)[:, 1])) / 2)))[0]); o2 = np.argsort(-pt_)[:2]; cp_ = max(pr, 1 - pr)
    out = {"story_type": {"answer": str(M["story"].classes_[ps_.argmax()]), "status": "answered" if ps_.max() >= M["cuts"]["story_type"] else "unknown"},
           "topic_top2": {"answer": [str(M["topic"].classes_[k]) for k in o2], "status": "answered" if pt_[o2].sum() >= M["cuts"]["topic_top2"] else "unknown"},
           "condition_present": {"answer": bool(pr > .5), "status": "answered" if cp_ >= M["cuts"]["condition_present"] else "unknown"}}
    if pr > .5:
        xc = xwc[:, M["keepc"]]; pc = M["cond"].predict_proba(xc)[0]; c2 = np.argsort(-pc)[:2]; top = M["cond"].classes_[c2[0]]
        xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [list(M["cond"].classes_).index(top)])), shape=(1, len(M["cond"].classes_)))]).tocsr()
        out["condition"] = {"answer": [str(M["cond"].classes_[k]) for k in c2], "status": "answered" if pc.max() >= M["cond_cut"] else "unknown", "direction": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])]}
    return out
hb.beat("build-expert2", progress="timing and end-to-end scoring")
# end to end on the voted later items: among items answered present, is the top-1 condition in Sonnet's set; of Sonnet positives, how many answered present with a top-2 hit
res_e = [(i, read(pool[i]["text"])) for i in vt]; ans = [(i, r) for i, r in res_e if r["condition_present"]["status"] == "answered" and r["condition_present"]["answer"] and "condition" in r]
prec = np.mean([r["condition"]["answer"][0] in {c["condition"] for c in sn[i]["conditions"]} for i, r in ans]) if ans else None
pos = [(i, r) for i, r in res_e if sn[i]["conditions"]]; rec = np.mean([("condition" in r and r["condition_present"]["status"] == "answered" and bool(set(r["condition"]["answer"]) & {c["condition"] for c in sn[i]["conditions"]})) for i, r in pos])
fa = np.mean([bool(not sn[i]["conditions"]) for i, r in ans]) if ans else None
with threadpool_limits(limits=1):
    sample = [pool[i]["text"] for i in test[:400]]; read(sample[0]); ts = []
    for t in sample: t0 = time.perf_counter(); read(t); ts.append((time.perf_counter() - t0) * 1000)
res = {"artefact_mb": size_mb, "condition_head_B": cond_report, "end_to_end": {"items": len(vt), "answered_present_with_condition": len(ans), "top1_in_sonnet_set_among_answered_present": round(float(prec), 3) if prec is not None else None, "sonnet_positives": len(pos), "positives_answered_present_with_top2_hit": round(float(rec), 3), "answered_present_but_sonnet_none": round(float(fa), 3) if fa is not None else None},
       "read_ms_all_fields_one_thread": {"p50": round(float(np.percentile(ts, 50)), 2), "p95": round(float(np.percentile(ts, 95)), 2), "mean": round(float(np.mean(ts)), 2), "n": len(ts)}, "example_present": next((r for i, r in res_e if "condition" in r), None)}
json.dump(res, open(H0 / "runs/expert1/expert1_v2_report.json", "w"), indent=1); print(json.dumps(res, indent=1))
subprocess.run(["node", "cp.mjs", "note", "T10", "SCORE T22 expert 1 v2 (runs/expert1/expert1_v2_report.json): " + json.dumps({k: res[k] for k in ("artefact_mb", "condition_head_B", "end_to_end", "read_ms_all_fields_one_thread")}), "--who", "S?"], cwd=H0.parents[1] / ".ledger", capture_output=True)
hb.finish("build-expert2", "done", last=f"p50 {res['read_ms_all_fields_one_thread']['p50']} ms p95 {res['read_ms_all_fields_one_thread']['p95']} ms; precision {res['end_to_end']['top1_in_sonnet_set_among_answered_present']}", progress=f"{size_mb} MB")
