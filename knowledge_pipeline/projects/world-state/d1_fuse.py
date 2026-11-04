import json, glob, re, pickle, pathlib, sys, os, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; TOP = sch["topic"]["enum"]; CON = sch["conditions"]["items"]["properties"]["condition"]["enum"]; ST = ["fact", "forecast", "opinion", "unclear"]
D = np.load("runs/d1_label_probs.npz", allow_pickle=True); vt = list(D["ids"]); dt_, ds_, dc_ = D["topic"], D["story"], D["cond"]
art = pickle.load(open("runs/expert1/expert1_v2.pkl", "rb")); EB = np.load("runs/embeds/bge_small.npy"); eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}
hk = {}; sn = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); bge = lambda ids: EB[[eid[i] for i in ids]] * 1.5
res = {}
def fuse(Ps, Pd, classes_s, classes_d): # align student columns to d1 column order, equal weight on log probabilities
    idx = [list(classes_s).index(c) for c in classes_d]; a = np.log(np.clip(Ps[:, idx], 1e-9, 1)); b = np.log(np.clip(Pd, 1e-9, 1)); z = (a + b) / 2; z = np.exp(z - z.max(1, keepdims=True)); return z / z.sum(1, keepdims=True)
# topic
yt = np.array([hk[i]["topic"] for i in trn]); tcl = np.array(sorted(set(yt))); Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt])
Pt = G.predict(G.fit(Tt, bge(trn), np.searchsorted(tcl, yt), len(tcl), C=3.0), Tv, bge(vt)); ys = np.array([sn[i]["topic"] for i in vt]); Tn = np.array(TOP)
def tscore(P, cls): t = np.argsort(-P, 1)[:, :2]; c = np.array(cls); return {"top1": round(float(np.mean(c[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(c[t[k]]) for k in range(len(vt))])), 3)}
Pf = fuse(Pt, dt_, tcl, TOP); res["topic"] = {"student_encoder": tscore(Pt, tcl), "d1": tscore(dt_, TOP), "fused": tscore(Pf, TOP)}
# story type (student = tfidf word+char linear on 4 classes via GPU softmax)
ys_s = np.array([sn[i]["story_type"] for i in vt]); st_tr = np.array([hk[i]["story_type"] for i in trn]); scl = np.array(sorted(set(st_tr)))
wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()
Ps = G.predict(G.fit(wc(trn), None, np.searchsorted(scl, st_tr), len(scl), C=3.0), wc(vt), None); Pfs = fuse(Ps, ds_, scl, ST)
res["story_type"] = {"student": round(float(np.mean(scl[Ps.argmax(1)] == ys_s)), 3), "d1": round(float(np.mean(np.array(ST)[ds_.argmax(1)] == ys_s)), 3), "fused": round(float(np.mean(np.array(ST)[Pfs.argmax(1)] == ys_s)), 3)}
# which condition on Sonnet positives: student encoder heads vs d1 multiple-choice probabilities (normalised over the 38)
rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
ccl = np.array(sorted(set(yc))); keep = art["keepc"]; Xc = wc(rows)[:, keep]; Xv = wc(vt)[:, keep]
Pc = G.predict(G.fit(Xc, bge(rows), np.searchsorted(ccl, yc), len(ccl), C=3.0), Xv, bge(vt)); dn = dc_ / dc_.sum(1, keepdims=True); Pcf = fuse(Pc, dn, ccl, CON)
pos = [k for k, i in enumerate(vt) if sn[i]["conditions"]]; sset = {k: {c["condition"] for c in sn[vt[k]]["conditions"]} for k in pos}
def cscore(P, cls): t = np.argsort(-P, 1)[:, :2]; c = np.array(cls); return {"top1": round(float(np.mean([c[t[k, 0]] in sset[k] for k in pos])), 3), "top2": round(float(np.mean([bool({c[t[k, 0]], c[t[k, 1]]} & sset[k]) for k in pos])), 3)}
res["condition_on_sonnet_positives"] = {"student_encoder": cscore(Pc, ccl), "d1": cscore(dn, CON), "fused": cscore(Pcf, CON)}
json.dump(res, open("runs/snapshots/d1_fuse.json", "w"), indent=1); print(json.dumps(res, indent=1))
