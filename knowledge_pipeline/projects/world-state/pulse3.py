import json, glob, re, pickle, pathlib, sys, time, os, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
from model2vec.distill import distill
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t29-static-bge", where="[5090]", task="T10", state="running", why="Can a static distillation of bge-small keep the encoder's lift at read speed?", success="Keeps half the lift", next="Ship the static bge if yes", need="Nothing", progress="distilling", spent=0.0, cap=0.0)
t0 = time.time(); sm = distill(model_name="BAAI/bge-small-en-v1.5", pca_dims=256, device="cuda"); sm.save_pretrained(str(H0 / "runs/embeds/bge_small_static")); dt_ = round(time.time() - t0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); EB = np.load(H0 / "runs/embeds/bge_small.npy"); eid = {i: k for k, i in enumerate(json.load(open(H0 / "runs/embeds/bge_small_ids.json")))}
hk = {}; sn = {}; old = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"])
pot = StaticModel.from_pretrained(art["static"])
def stat(m, ids): T = [clean(i) for i in ids]; return np.hstack([m.encode(T), m.encode([re.split(r"(?<=[.!?])\s", t, 1)[0] for t in T])]).astype(np.float32)
feats = {"potion_static": (lambda ids: stat(pot, ids)), "bge_static_distilled": (lambda ids: stat(sm, ids)), "bge_full_frozen": (lambda ids: EB[[eid[i] for i in ids]] * 1.5)}
res = {"distill_seconds": dt_, "static_dims": int(sm.embedding.shape[1]), "n_train": len(trn)}
# topic
yt = np.array([hk[i]["topic"] for i in trn]); cl = np.array(sorted(set(yt))); yi = np.searchsorted(cl, yt); ys = np.array([sn[i]["topic"] for i in vt])
Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt]); res["topic"] = {}
for name, f in feats.items():
    Et, Ev = f(trn), f(vt)
    if name != "bge_full_frozen": sc = Et.std(0, keepdims=True) + 1e-6; Et = Et / sc * 0.1; Ev = Ev / sc * 0.1
    m = G.fit(Tt, Et, yi, len(cl), C=3.0); P = G.predict(m, Tv, Ev); t = np.argsort(-P, 1)[:, :2]; res["topic"][name] = {"top1": round(float(np.mean(cl[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(cl[t[k]]) for k in range(len(vt))])), 3)}
    hb.beat("t29-static-bge", progress=f"topic {name} done")
json.dump(res, open(H0 / "runs/snapshots/loop16_results.json", "w"), indent=1)
# which condition on Sonnet-positive items
vs = [i for i in test if i in sn and sn[i]["conditions"]]; sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
cc = np.array(sorted(set(yc))); ci = np.searchsorted(cc, yc); keep = art["keepc"]
wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, keep]; Xc, Xcv = wc(rows), wc(vs); res["condition"] = {}
for name, f in feats.items():
    Et, Ev = f(rows), f(vs)
    if name != "bge_full_frozen": sc = Et.std(0, keepdims=True) + 1e-6; Et = Et / sc * 0.1; Ev = Ev / sc * 0.1
    m = G.fit(Xc, Et, ci, len(cc), C=3.0); P = G.predict(m, Xcv, Ev); t = np.argsort(-P, 1)[:, :2]
    res["condition"][name] = {"top1": round(float(np.mean([cc[t[k, 0]] in sset[k] for k in range(len(vs))])), 3), "top2": round(float(np.mean([bool({cc[t[k, 0]], cc[t[k, 1]]} & sset[k]) for k in range(len(vs))])), 3)}
json.dump(res, open(H0 / "runs/snapshots/loop16_results.json", "w"), indent=1)
# read speed of the static encoders
import time as T_; txt = [clean(i) for i in test[:400]]
for nm, m in (("potion", pot), ("bge_static", sm)):
    t0 = T_.perf_counter(); [m.encode([t]) for t in txt]; res[f"encode_ms_per_item_{nm}"] = round((T_.perf_counter() - t0) / len(txt) * 1000, 3)
res["static_bge_dir_mb"] = round(sum(f.stat().st_size for f in (H0 / "runs/embeds/bge_small_static").glob("*")) / 1e6, 1)
json.dump(res, open(H0 / "runs/snapshots/loop16_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t29-static-bge", "done", last=f"topic top-2 potion {res['topic']['potion_static']['top2']} / static bge {res['topic']['bge_static_distilled']['top2']} / full {res['topic']['bge_full_frozen']['top2']}", progress="static distillation scored")
