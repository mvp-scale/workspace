import json, glob, re, pickle, pathlib, sys, time, os, subprocess, numpy as np, scipy.sparse as sp, warnings, torch
warnings.filterwarnings("ignore"); os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
from threadpoolctl import threadpool_limits
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("build-expert3", where="[5090]+[CPU]", task="T10", state="running", why="Cascade expert: linear always, ONNX encoder only for routed items", success="Mean read 13 ms or less; topic top-2 0.855+", next="Score, log, run gates", need="Nothing", progress="training encoder heads on the GPU", spent=0.0, cap=0.0)
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
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); bge = lambda ids: EB[[eid[i] for i in ids]] * 1.5
npy = lambda m: {"W": m[0].cpu().numpy(), "V": m[1].cpu().numpy(), "b": m[2].cpu().numpy()}
yt = np.array([hk[i]["topic"] for i in trn]); tcl = np.array(sorted(set(yt))); Tt = art["vt"].transform([clean(i) for i in trn]); mt = G.fit(Tt, bge(trn), np.searchsorted(tcl, yt), len(tcl), C=3.0); Ht = {**npy(mt), "classes": tcl}
rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
ccl = np.array(sorted(set(yc))); wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, art["keepc"]]
mc = G.fit(wc(rows), bge(rows), np.searchsorted(ccl, yc), len(ccl), C=3.0); Hc = {**npy(mc), "classes": ccl}
assert list(ccl) == list(art["cond"].classes_), "condition class order differs from the v2 head"
# unknown cut-off for the encoder condition head: 80% running agreement on half A of Sonnet-positive voted items
vs = [i for i in vt if sn[i]["conditions"]]; Pc = G.predict(mc, wc(vs), bge(vs)); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; ok = np.array([ccl[Pc[k].argmax()] in sset[k] for k in range(len(vs))]); conf = Pc.max(1)
perm = np.random.RandomState(3).permutation(len(vs)); A_ = perm[:len(vs) // 2]; q = np.argsort(-conf[A_]); run = np.cumsum(ok[A_][q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; ccut = float(conf[A_][q][idx.max()]) if len(idx) else 1.01
art3 = {**art, "enc_heads": {"topic": Ht, "cond": Hc}, "gate_present": 0.5, "gate_topic": 0.7, "cond_cut_enc": ccut}; pkl = H0 / "runs/expert1/expert1_v3.pkl"; pickle.dump(art3, open(pkl, "wb")); size_mb = round(os.path.getsize(pkl) / 1e6, 1)
hb.beat("build-expert3", progress="scoring and timing on one CPU thread"); from expert1_runtime import Expert3
with threadpool_limits(limits=1):
    e = Expert3(str(pkl)); cs = [float((e.embed(pool[i]["text"]) / 1.5) @ (EB[eid[i]])) for i in test[:50] if i in eid]
    R = {i: e.read(pool[i]["text"]) for i in vt}
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda m: float(w[m].sum()); tot = W(np.ones(len(vt), bool)); routed = np.array([R[i]["path"] == "encoder" for i in vt])
ys = np.array([sn[i]["topic"] for i in vt]); top2 = np.array([ys[k] in set(R[vt[k]]["topic_top2"]["answer"] or []) for k in range(len(vt))]); ans_t = np.array([R[i]["topic_top2"]["status"] == "answered" for i in vt])
pos = [k for k, i in enumerate(vt) if sn[i]["conditions"]]; got = [k for k in pos if "condition" in R[vt[k]]]; cond_ans = [k for k in got if R[vt[k]]["condition"]["status"] == "answered"]
hit1 = lambda k: R[vt[k]]["condition"]["answer"][0] in {c["condition"] for c in sn[vt[k]]["conditions"]}
res = {"artefact_mb": size_mb, "onnx_embedding_cosine_vs_saved_min": round(min(cs), 5), "routed_share_weighted": round(W(routed) / tot, 3), "topic": {"top2_all_voted": round(float(top2.mean()), 3), "answered_share": round(float(ans_t.mean()), 3), "top2_on_answered": round(float(top2[ans_t].mean()), 3)},
       "condition_given_present_answered": {"sonnet_positives": len(pos), "with_condition_output": len(got), "top1_among_those": round(float(np.mean([hit1(k) for k in got])), 3) if got else None, "answered_with_cut": len(cond_ans), "top1_among_answered": round(float(np.mean([hit1(k) for k in cond_ans])), 3) if cond_ans else None}}
with threadpool_limits(limits=1):
    sample = [pool[i]["text"] for i in test[:400]]; e.read(sample[0]); ts = []; paths = []
    for t in sample: t0 = time.perf_counter(); r = e.read(t); ts.append((time.perf_counter() - t0) * 1000); paths.append(r["path"])
ts = np.array(ts); pe = np.array(paths) == "encoder"; res["latency_ms_one_thread_400_natural_items"] = {"mean": round(float(ts.mean()), 1), "p50": round(float(np.percentile(ts, 50)), 1), "p95": round(float(np.percentile(ts, 95)), 1), "max": round(float(ts.max()), 1), "routed_share_in_sample": round(float(pe.mean()), 3), "linear_only_p50": round(float(np.percentile(ts[~pe], 50)), 1), "encoder_path_p50": round(float(np.percentile(ts[pe], 50)), 1), "encoder_path_p95": round(float(np.percentile(ts[pe], 95)), 1)}
json.dump(res, open(H0 / "runs/expert1/expert1_v3_report.json", "w"), indent=1); print(json.dumps(res, indent=1))
subprocess.run(["node", "cp.mjs", "note", "T10", "SCORE T34 expert 1 v3 cascade (runs/expert1/expert1_v3_report.json): " + json.dumps(res), "--who", "S?"], cwd=H0.parents[1] / ".ledger", capture_output=True)
hb.finish("build-expert3", "done", last=f"mean {res['latency_ms_one_thread_400_natural_items']['mean']} ms, topic top-2 {res['topic']['top2_all_voted']}, routed {res['routed_share_weighted']}", progress=f"{size_mb} MB")
