"""Build BitMob Expert 1 on a different frozen trunk (generalised from the Granite build; ledger L366, L378).
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python build_expert_trunk.py <tag> <hf id> <out pkl>      local GPU for seconds (gpu_lr heads), no hosted calls
Base = v3.2 (linear heads as tuned, routing gates unchanged). Only the encoder heads change: topic head C chosen on a validation slice (earliest 90 / latest 10 percent of the training period, Haiku labels,
tie within 0.002 takes the smaller C), which-condition head C=3 as in v3.1. Output: runs/expert1/expert1_v4_granite.pkl (names its own ONNX and tokenizer files). Score it with score_version.py."""
import json, glob, re, pickle, pathlib, sys, os, numpy as np, scipy.sparse as sp, warnings
TAG, RID, OUTPKL = sys.argv[1], sys.argv[2], sys.argv[3]
warnings.filterwarnings("ignore"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import gpu_lr as G
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v32.pkl", "rb"))
EB = np.load(f"runs/embeds/{TAG}_64_fp32.npy"); eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}
hk = {}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; trn.sort(key=lambda i: pool[i]["date"]); n = len(trn); cut_at = int(n * 0.9)
clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"]); emb = lambda ids: EB[[eid[i] for i in ids]] * 1.5; npy = lambda m: {"W": m[0].cpu().numpy(), "V": m[1].cpu().numpy(), "b": m[2].cpu().numpy()}
yt = np.array([hk[i]["topic"] for i in trn]); tcl = np.array(sorted(set(yt))); y = np.searchsorted(tcl, yt); Tt = art["vt"].transform([clean(i) for i in trn]); B = emb(trn)
fi, vi = np.arange(cut_at), np.arange(cut_at, n); grid = {}
for C in (0.3, 1, 3, 10):
    m = G.fit(Tt[fi], B[fi], y[fi], len(tcl), C=C); P = G.predict(m, Tt[vi], B[vi]); grid[C] = float(np.mean([y[vi][k] in np.argsort(-P[k])[:2] for k in range(len(vi))])); print("topic encoder head C", C, "val top-2", round(grid[C], 4), flush=True)
top = max(grid.values()); Ct = min(c for c, v in grid.items() if v >= top - 0.002); print("chosen topic C", Ct, flush=True)
mt = G.fit(Tt, B, y, len(tcl), C=Ct); Ht = {**npy(mt), "classes": tcl}
rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
ccl = np.array(sorted(set(yc))); wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, art["keepc"]]
mc = G.fit(wc(rows), emb(rows), np.searchsorted(ccl, yc), len(ccl), C=3.0); Hc = {**npy(mc), "classes": ccl}; assert list(ccl) == list(art["cond"].classes_), "condition class order differs"
vs = [i for i in vt if sn[i]["conditions"]]; Pc = G.predict(mc, wc(vs), emb(vs)); sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; ok = np.array([ccl[Pc[k].argmax()] in sset[k] for k in range(len(vs))]); conf = Pc.max(1)
perm = np.random.RandomState(3).permutation(len(vs)); A_ = perm[:len(vs) // 2]; q = np.argsort(-conf[A_]); run = np.cumsum(ok[A_][q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; ccut = float(conf[A_][q][idx.max()]) if len(idx) else 1.01
new = {**art, "enc_heads": {"topic": Ht, "cond": Hc}, "enc_max_tokens": 64, "cond_cut_enc": ccut, "onnx_path": f"runs/embeds/{TAG}.onnx", "tok_path": f"runs/embeds/{TAG}_tokenizer.json", "trunk": RID}
pickle.dump(new, open(OUTPKL, "wb")); json.dump({"topic_C_grid_val_top2": {str(k): round(v, 4) for k, v in grid.items()}, "chosen_topic_C": Ct, "cond_C": 3.0, "cond_cut_enc": ccut}, open(f"runs/snapshots/build_{TAG}.json", "w"), indent=1)
from expert1_runtime import Expert3
e = Expert3(OUTPKL); cs = [float((e.embed(pool[i]["text"]) / 1.5) @ EB[eid[i]]) for i in test[:50] if i in eid]; print("saved; encoder-file embedding vs saved GPU embedding, min cosine", round(min(cs), 5), flush=True)
