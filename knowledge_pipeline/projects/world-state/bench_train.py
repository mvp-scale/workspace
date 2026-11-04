import json, glob, re, pickle, pathlib, sys, time, numpy as np, scipy.sparse as sp, warnings, torch
warnings.filterwarnings("ignore")
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.linear_model import LogisticRegression
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("bench-train", where="[5090]+[CPU]", task="T10", state="running", why="Is our training slow because of the language or the algorithm and threads?", success="GPU softmax 5x faster at the same accuracy", next="Decide whether to move heads to the GPU", need="Nothing", progress="building features", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); hk = {}; sn = {}; old = set()
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"])
Xt = art["vt"].transform([clean(i) for i in trn]).tocsr().astype(np.float32); Xv = art["vt"].transform([clean(i) for i in vt]).tocsr().astype(np.float32)
yt = np.array([hk[i]["topic"] for i in trn]); ys = np.array([sn[i]["topic"] for i in vt]); cl = np.array(sorted(set(yt))); yi = np.searchsorted(cl, yt)
def score(P): t = np.argsort(-P, 1)[:, :2]; return {"top1": round(float(np.mean(cl[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(cl[t[k]]) for k in range(len(vt))])), 3)}
res = {"n_train": len(trn), "features": Xt.shape[1], "classes": len(cl)}
# GPU softmax regression, sparse matmul, L-BFGS, objective matched to sklearn C=3: C * sum(logloss) + 0.5 * ||W||^2
dev = "cuda"; Xg = torch.sparse_csr_tensor(torch.tensor(Xt.indptr, dtype=torch.int64), torch.tensor(Xt.indices, dtype=torch.int64), torch.tensor(Xt.data), size=Xt.shape).to(dev); Y = torch.tensor(yi, device=dev)
W = torch.zeros(Xt.shape[1], len(cl), device=dev, requires_grad=True); b = torch.zeros(len(cl), device=dev, requires_grad=True); C = 3.0
opt = torch.optim.LBFGS([W, b], lr=1, max_iter=300, history_size=20, line_search_fn="strong_wolfe", tolerance_grad=1e-5, tolerance_change=1e-9)
def closure():
    opt.zero_grad(); L = C * torch.nn.functional.cross_entropy(torch.sparse.mm(Xg, W) + b, Y, reduction="sum") + 0.5 * (W ** 2).sum(); L.backward(); return L
torch.cuda.synchronize(); t0 = time.time(); opt.step(closure); torch.cuda.synchronize(); gt = time.time() - t0
Xvg = torch.sparse_csr_tensor(torch.tensor(Xv.indptr, dtype=torch.int64), torch.tensor(Xv.indices, dtype=torch.int64), torch.tensor(Xv.data), size=Xv.shape).to(dev)
Pg = torch.softmax(torch.sparse.mm(Xvg, W) + b, 1).detach().cpu().numpy(); res["gpu"] = {"seconds": round(gt, 1), **score(Pg), "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)}
json.dump(res, open(H0 / "runs/snapshots/bench_train.json", "w"), indent=1); hb.beat("bench-train", progress="GPU done; sklearn CPU baseline (single core, minutes)")
t0 = time.time(); m = LogisticRegression(max_iter=300, C=3).fit(Xt, yt); ct = time.time() - t0; res["cpu_sklearn"] = {"seconds": round(ct, 1), **score(m.predict_proba(Xv))}
res["speedup"] = round(ct / gt, 1); json.dump(res, open(H0 / "runs/snapshots/bench_train.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("bench-train", "done", last=f"GPU {gt:.0f}s vs CPU {ct:.0f}s ({ct / gt:.0f}x)", progress="49-class topic head, 36k items")
