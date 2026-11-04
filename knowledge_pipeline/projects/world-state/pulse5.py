import json, glob, re, pickle, pathlib, sys, time, os, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t32-sweep", where="[5090]", task="T10", state="running", why="Can a linear-first cascade keep the encoder's lift at low average cost?", success="Routed 35% or less, top-1 0.75+", next="Build expert v3 if yes", need="Nothing", progress="loading", spent=0.0, cap=0.0)
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
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); pot = StaticModel.from_pretrained(art["static"])
def stat(ids): T = [clean(i) for i in ids]; return np.hstack([pot.encode(T), pot.encode([re.split(r"(?<=[.!?])\s", t, 1)[0] for t in T])]).astype(np.float32)
bge = lambda ids: EB[[eid[i] for i in ids]] * 1.5
def scale(a, b): s = a.std(0, keepdims=True) + 1e-6; return a / s * 0.1, b / s * 0.1
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda m: float(w[m].sum()); tot = W(np.ones(len(vt), bool))
# cheap presence probability from the artefact (blend)
wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()
Xv = wc(vt); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))); pp = 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(Xv)[:, 1]) + lg(art["ps"].predict_proba(Xv)[:, 1])) / 2))
# topic: linear (potion) vs encoder (bge) heads on all voted items
yt = np.array([hk[i]["topic"] for i in trn]); cl = np.array(sorted(set(yt))); yi = np.searchsorted(cl, yt); ys = np.array([sn[i]["topic"] for i in vt])
Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt]); Ps = {}
for nm, f in (("lin", stat), ("enc", bge)):
    Et, Ev = f(trn), f(vt)
    if nm == "lin": Et, Ev = scale(Et, Ev)
    Ps[nm] = G.predict(G.fit(Tt, Et, yi, len(cl), C=3.0), Tv, Ev)
t2 = lambda P: np.argsort(-P, 1)[:, :2]; hit1 = lambda P: cl[P.argmax(1)] == ys; hit2 = lambda P: np.array([ys[k] in set(cl[t2(P)[k]]) for k in range(len(vt))])
conf_lin = np.sort(Ps["lin"], 1)[:, -2:].sum(1); route_t = conf_lin < 0.80
# conditions: heads on ALL voted items
rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
cc = np.array(sorted(set(yc))); ci = np.searchsorted(cc, yc); keep = art["keepc"]; Xc = wc(rows)[:, keep]; Xcv = Xv[:, keep]; Pc = {}
for nm, f in (("lin", stat), ("enc", bge)):
    Et, Ev = f(rows), f(vt)
    if nm == "lin": Et, Ev = scale(Et, Ev)
    Pc[nm] = G.predict(G.fit(Xc, Et, ci, len(cc), C=3.0), Xcv, Ev)
sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vt]; pos = sp_ == 1
def ctop(P, m):
    t = np.argsort(-P, 1)[:, :2]; ix = np.where(m)[0]; return round(float(np.mean([cc[t[k, 0]] in sset[k] for k in ix])), 3), round(float(np.mean([bool({cc[t[k, 0]], cc[t[k, 1]]} & sset[k]) for k in ix])), 3)
rows_ = []
for tc in (0.3, 0.4, 0.5, 0.6, 0.7):
    for tt in (0.0, 0.6, 0.7, 0.8):
        rc = pp >= tc; rt = conf_lin < tt; ru = rc | rt; cas = np.where(rc[:, None], Pc["enc"], Pc["lin"]); ct = np.where(rt[:, None], Ps["enc"], Ps["lin"])
        c1, c2 = ctop(cas, pos); rows_.append({"presence_gate": tc, "topic_gate": tt, "routed_share": round(W(ru) / tot, 3), "positives_routed": round(float(rc[pos].mean()), 3), "cond_top1": c1, "cond_top2": c2, "topic_top2": round(float(hit2(ct).mean()), 3), "latency_ms_model": round(2.7 + W(ru) / tot * 30, 1)})
res = {"sweep": rows_, "linear_only": {"cond_top1": ctop(Pc["lin"], pos)[0], "topic_top2": round(float(hit2(Ps["lin"]).mean()), 3)}, "encoder_everywhere": {"cond_top1": ctop(Pc["enc"], pos)[0], "topic_top2": round(float(hit2(Ps["enc"]).mean()), 3)}}
good = [r for r in rows_ if r["routed_share"] <= 0.30 and r["cond_top1"] >= 0.74 and r["topic_top2"] >= 0.85]; res["points_meeting_prediction"] = good
json.dump(res, open(H0 / "runs/snapshots/loop19_results.json", "w"), indent=1)
for r in rows_: print(r)
print("meeting prediction:", good); hb.finish("t32-sweep", "done", last=f"{len(good)} points meet routed<=30%, cond top-1>=0.74, topic top-2>=0.85", progress="20 settings")
