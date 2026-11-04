"""T20 traits step (ledger L454): 51 linear heads on [word+char counts, leaf vector] trained on Sonnet's grades (TRAIN, 1,500 pool items), scored on EVAL (DEVQ items). Agreement with Sonnet, never accuracy. CPU, local.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python train_traits.py"""
import json, sys, re, pickle, numpy as np, scipy.sparse as sp, warnings, collections
warnings.filterwarnings("ignore"); sys.path.insert(0, ".")
from expert1_runtime import Expert3
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from joblib import Parallel, delayed
sys.path.insert(0, '../../kit/live'); import heartbeat as hb, os
hb.beat('t20-traits-student-light', pid=os.getpid(), where='[CPU]', task='T20', state='running', progress='51 trait heads, fixed C=1, 8 parallel workers', why='Can a CPU head grade each of the 51 trait questions like Sonnet does? Bar: exact agreement 0.80 and +0.05 over always saying not at all (ledger L454). Lighter rerun after the first run hit the 1-hour cap.', success='Per question: exact agreement 0.80+ and lift 0.05+ over the majority answer', next='Name the ready questions per group; reword or relabel the rest', need='Nothing', cap=3600)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb")); reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}["v5-leaf"]; e = Expert3(reg["path"])
Q = json.load(open("specs/traits_v0.json"))["questions"]; qid = [q["id"] for q in Q]; ORD = {"not at all": 0, "slightly": 1, "clearly": 2, "strongly": 3}
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}; pool.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}); pool.update({r["id"]: r["text"] for r in J("runs/pulse/devq_items.jsonl")})
eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; LEAF = np.load("runs/embeds/leaf_64_fp32.npy")
tr = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/train/labels.jsonl")}; ev = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/eval/labels.jsonl")}
for r in J("runs/pulse/traits_pilot/sonnet_r1/labels.jsonl"): ev.setdefault(r["item_id"], r["label"])
tri = sorted(i for i in tr if i in eid); evi = sorted(i for i in ev if i in pool); print("train", len(tri), "eval", len(evi), flush=True)
clean = lambda t: re.sub(r"\s+", " ", t); XS = lambda texts: sp.hstack([art["vw"].transform([clean(t) for t in texts]), art["vc"].transform([clean(t) for t in texts])]).tocsr()
Xtr = sp.hstack([XS([pool[i] for i in tri]), sp.csr_matrix(LEAF[[eid[i] for i in tri]] * 1.5)]).tocsr(); Xev = sp.hstack([XS([pool[i] for i in evi]), sp.csr_matrix(np.array([e.embed(pool[i]) for i in evi]))]).tocsr()
res = {"n_train": len(tri), "n_eval": len(evi), "questions": {}}; heads = {}
def one(q):
    ytr = np.array([ORD.get(tr[i][q], -1) for i in tri]); yev = np.array([ORD.get(ev[i][q], -1) for i in evi]); mtr = ytr >= 0; mev = yev >= 0
    maj = collections.Counter(ytr[mtr]).most_common(1)[0][0]; base = float((yev[mev] == maj).mean()); clf = None; auc = None
    if len(set(ytr[mtr])) > 1 and mtr.sum() >= 60:
        clf = LogisticRegression(C=1.0, max_iter=200).fit(Xtr[mtr], ytr[mtr]); P = clf.predict_proba(Xev[mev]); pred = clf.classes_[P.argmax(1)]
        act = (yev[mev] > 0); a0 = list(clf.classes_).index(0) if 0 in clf.classes_ else None
        auc = round(float(roc_auc_score(act, 1 - P[:, a0])), 3) if a0 is not None and act.sum() >= 5 and (~act).sum() >= 5 else None
    else: pred = np.full(mev.sum(), maj)
    ex = float((pred == yev[mev]).mean()); w1 = float((np.abs(pred - yev[mev]) <= 1).mean()); rng = np.random.RandomState(0); h = (pred == yev[mev]); bs = [h[rng.randint(0, len(h), len(h))].mean() for _ in range(200)]
    return q, clf, {"group": next(x["group"] for x in Q if x["id"] == q), "question": next(x["question"] for x in Q if x["id"] == q), "exact": round(ex, 3), "exact_ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)], "within1": round(w1, 3), "majority_baseline": round(base, 3), "lift": round(ex - base, 3), "auc_active": auc, "active_share_eval": round(float((yev[mev] > 0).mean()), 3), "C": 1.0, "ready": bool(ex >= 0.80 and ex - base >= 0.05)}
for q, clf, r in Parallel(n_jobs=8)(delayed(one)(q) for q in qid):
    res["questions"][q] = r
    if clf is not None: heads[q] = clf
Qs = list(res["questions"].values()); G = collections.defaultdict(list)
for v in Qs: G[v["group"]].append(v)
res["groups"] = {g: {"n": len(v), "ready": sum(x["ready"] for x in v), "exact_mean": round(float(np.mean([x["exact"] for x in v])), 3), "lift_mean": round(float(np.mean([x["lift"] for x in v])), 3), "auc_mean": round(float(np.nanmean([x["auc_active"] if x["auc_active"] is not None else np.nan for x in v])), 3)} for g, v in G.items()}
res["overall"] = {"ready": sum(v["ready"] for v in Qs), "of": len(Qs), "exact_mean": round(float(np.mean([v["exact"] for v in Qs])), 3), "lift_mean": round(float(np.mean([v["lift"] for v in Qs])), 3), "baseline_mean": round(float(np.mean([v["majority_baseline"] for v in Qs])), 3), "exact_ge_080": sum(v["exact"] >= 0.80 for v in Qs), "lift_ge_005": sum(v["lift"] >= 0.05 for v in Qs)}
json.dump(res, open("runs/pulse/traits_student.json", "w"), indent=1); pickle.dump({"heads": heads, "questions": qid}, open("runs/pulse/traits_heads_v0.pkl", "wb")); print(json.dumps({"overall": res["overall"], "groups": res["groups"]}, indent=1)); hb.finish("t20-traits-student-light", "done", last=f"ready {res['overall']['ready']} of 51, mean exact {res['overall']['exact_mean']}, mean lift {res['overall']['lift_mean']}")
