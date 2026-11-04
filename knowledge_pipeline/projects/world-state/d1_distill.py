"""T45: train the student heads on SOFT targets = 0.5 x Haiku one-hot + 0.5 x d1 probabilities. Same split, same test items. Run with the main venv."""
import json, glob, re, pickle, pathlib, sys, os, subprocess, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t45-distill", where="[5090]", task="T10", state="running", why="Does learning from d1's soft labels lift the CPU student?", success="Linear topic top-2 +0.02, condition top-1 +0.03", next="Decide whether to ship the soft-label student", need="Nothing", progress="loading", spent=0.0, cap=0.0)
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; TOP = sch["topic"]["enum"]; CON = sch["conditions"]["items"]["properties"]["condition"]["enum"]; ST = ["fact", "forecast", "opinion", "unclear"]
art = pickle.load(open("runs/expert1/expert1_v2.pkl", "rb")); EB = np.load("runs/embeds/bge_small.npy"); eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; pot = StaticModel.from_pretrained(art["static"])
hk = {}; sn = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
D1 = {}
for f in sorted(glob.glob("runs/d1_train_probs/chunk*.npz")):
    z = np.load(f, allow_pickle=True)
    for k, i in enumerate(z["ids"]): D1[str(i)] = (z["topic"][k].astype(np.float32), z["story"][k].astype(np.float32), z["cond"][k].astype(np.float32))
trn = sorted(i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and i in D1); res = {"n_train_with_d1": len(trn), "n_test": len(vt)}
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); bge = lambda ids: EB[[eid[i] for i in ids]] * 1.5
def stat(ids): T = [clean(i) for i in ids]; return np.hstack([pot.encode(T), pot.encode([re.split(r"(?<=[.!?])\s", t, 1)[0] for t in T])]).astype(np.float32)
def mix(onehot, d1p, a=0.5): y = (1 - a) * onehot + a * d1p; return y / y.sum(1, keepdims=True)
# ---- topic
tcl = sorted(set(hk[i]["topic"] for i in trn)); ti = {t: k for k, t in enumerate(tcl)}; oh = np.zeros((len(trn), len(tcl)), np.float32)
for r, i in enumerate(trn): oh[r, ti[hk[i]["topic"]]] = 1
d1t = np.stack([D1[i][0][[TOP.index(t) for t in tcl]] for i in trn]); d1t = d1t / np.clip(d1t.sum(1, keepdims=True), 1e-9, None)
Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt]); ys = np.array([sn[i]["topic"] for i in vt]); T_ = np.array(tcl)
Et_l, Ev_l = stat(trn), stat(vt); sc = Et_l.std(0, keepdims=True) + 1e-6; Et_l, Ev_l = Et_l / sc * 0.1, Ev_l / sc * 0.1; Et_e, Ev_e = bge(trn), bge(vt)
def tscore(P): t = np.argsort(-P, 1)[:, :2]; return {"top1": round(float(np.mean(T_[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(T_[t[k]]) for k in range(len(vt))])), 3)}
res["topic"] = {}
for nm, (Et, Ev) in (("linear_cpu_student", (Et_l, Ev_l)), ("encoder_student", (Et_e, Ev_e))):
    for tg, Y in (("haiku_hard", oh), ("soft_mix_half_d1", mix(oh, d1t))):
        res["topic"][f"{nm}/{tg}"] = tscore(G.predict(G.fit_soft(Tt, Et, Y, C=3.0), Tv, Ev)); hb.beat("t45-distill", progress=f"topic {nm}/{tg}")
# ---- story type (word+char sparse only)
wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr(); Xw, Xwv = wc(trn), wc(vt); ys_s = np.array([sn[i]["story_type"] for i in vt]); sti = {s: k for k, s in enumerate(ST)}
ohs = np.zeros((len(trn), 4), np.float32)
for r, i in enumerate(trn): ohs[r, sti[hk[i]["story_type"]]] = 1
d1s = np.stack([D1[i][1] for i in trn]); d1s = d1s / np.clip(d1s.sum(1, keepdims=True), 1e-9, None); res["story_type"] = {}
for tg, Y in (("haiku_hard", ohs), ("soft_mix_half_d1", mix(ohs, d1s))): P = G.predict(G.fit_soft(Xw, None, Y, C=3.0), Xwv, None); res["story_type"][tg] = round(float(np.mean(np.array(ST)[P.argmax(1)] == ys_s)), 3)
# ---- which condition: rows = (item, Haiku condition); targets mix the one-hot with d1's condition probabilities normalised over the 38
rows, ycl = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); ycl.append(c["condition"])
cci = {c: k for k, c in enumerate(CON)}; ohc = np.zeros((len(rows), len(CON)), np.float32)
for r, c in enumerate(ycl): ohc[r, cci[c]] = 1
d1c = np.stack([D1[i][2] for i in rows]); d1c = d1c / np.clip(d1c.sum(1, keepdims=True), 1e-9, None); keep = art["keepc"]; wck = lambda ids: wc(ids)[:, keep]; Xc = wck(rows)
vs = [i for i in test if i in sn and sn[i]["conditions"]]; Xcv = wck(vs); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; C_ = np.array(CON); res["condition_on_sonnet_positives"] = {"n": len(vs), "n_train_rows": len(rows)}
Ec_l, Ecv_l = stat(rows), stat(vs); sc = Ec_l.std(0, keepdims=True) + 1e-6; Ec_l, Ecv_l = Ec_l / sc * 0.1, Ecv_l / sc * 0.1
def cscore(P): t = np.argsort(-P, 1)[:, :2]; return {"top1": round(float(np.mean([C_[t[k, 0]] in sset[k] for k in range(len(vs))])), 3), "top2": round(float(np.mean([bool({C_[t[k, 0]], C_[t[k, 1]]} & sset[k]) for k in range(len(vs))])), 3)}
for nm, (Et, Ev) in (("linear_cpu_student", (Ec_l, Ecv_l)), ("encoder_student", (bge(rows), bge(vs)))):
    for tg, Y in (("haiku_hard", ohc), ("soft_mix_half_d1", mix(ohc, d1c))): res["condition_on_sonnet_positives"][f"{nm}/{tg}"] = cscore(G.predict(G.fit_soft(Xc, Et, Y, C=3.0), Xcv, Ev)); hb.beat("t45-distill", progress=f"condition {nm}/{tg}")
json.dump(res, open("runs/snapshots/d1_distill.json", "w"), indent=1); print(json.dumps(res, indent=1)); hb.finish("t45-distill", "done", last="see runs/snapshots/d1_distill.json", progress="soft-label heads scored")
