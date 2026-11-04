"""T20: traits as present/absent flags on frozen embeddings (GPU heads). Registers heartbeat t20-traits-binary.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python traits_binary.py"""
import os, sys, json, math, numpy as np, torch, torch.nn.functional as Fn
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
hb.beat("t20-traits-binary", pid=os.getpid(), where="[5090] local GPU", task="T20", state="running", progress="51 questions x 3 readers", why="Traits as present/absent flags: does a stronger reader help, and which questions are ready? (ledger L488)", success="Per question AUC and recall at precision 0.80; group verdicts", next="Put ready traits on the Engine card; distil the traits student if the strong reader gains 0.03 AUC", need="Nothing", cap=3600)
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; D = "runs/pulse/ceiling/"; M = json.load(open(D + "main_ids.json")); ids = M["ids"]; pos = {i: k for k, i in enumerate(ids)}
Q = json.load(open("specs/traits_v0.json"))["questions"]; qid = [q["id"] for q in Q]; grp = {q["id"]: q["group"] for q in Q}
tr = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/train/labels.jsonl")}; ev = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/eval/labels.jsonl")}
for r in J("runs/pulse/traits_pilot/sonnet_r1/labels.jsonl"): ev.setdefault(r["item_id"], r["label"])
tri = [i for i in tr if i in pos]; evi = [i for i in ev if i in pos]; print("train", len(tri), "eval", len(evi), flush=True); dev = "cuda"
def fit(X, y, lam, iters=100):
    W = torch.zeros(X.shape[1], 2, device=dev, requires_grad=True); b = torch.zeros(2, device=dev, requires_grad=True); opt = torch.optim.LBFGS([W, b], lr=1, max_iter=iters, history_size=20, line_search_fn="strong_wolfe")
    def cl(): opt.zero_grad(); loss = Fn.cross_entropy(X @ W + b, y) + lam * (W ** 2).sum(); loss.backward(); return loss
    opt.step(cl); return W.detach(), b.detach()
def recall_at(p, y, prec=0.80):
    o = np.argsort(-p); tp = np.cumsum(y[o]); n = np.arange(1, len(o) + 1); ok = np.where(tp / n >= prec)[0]; return float(tp[ok.max()] / y.sum()) if len(ok) else 0.0
res = {}
for en in ("leaf", "qwen3-4b", "ens"):
    E = torch.tensor(np.load(D + f"{en}_main.npy").astype(np.float32), device=dev); Xt = E[[pos[i] for i in tri]]; Xe = E[[pos[i] for i in evi]]; rows = {}
    for q in qid:
        yt = np.array([-1 if tr[i][q] == "cannot tell" else int(tr[i][q] != "not at all") for i in tri]); ye = np.array([-1 if ev[i][q] == "cannot tell" else int(ev[i][q] != "not at all") for i in evi]); mt, me = yt >= 0, ye >= 0
        if yt[mt].sum() < 8 or ye[me].sum() < 5: rows[q] = {"group": grp[q], "present_eval": int(ye[me].sum()), "auc": None, "recall_at_p80": None, "ready": False}; continue
        X1, y1 = Xt[torch.tensor(mt, device=dev)], torch.tensor(yt[mt], device=dev); g = torch.Generator().manual_seed(0); perm = torch.randperm(len(y1), generator=g).to(dev); nv = max(30, len(y1) // 8); v, t = perm[:nv], perm[nv:]; best = (1e9, 1e-3)
        for lam in (1e-4, 1e-3, 1e-2):
            W, b = fit(X1[t], y1[t], lam); l = Fn.cross_entropy(X1[v] @ W + b, y1[v]).item()
            if l < best[0]: best = (l, lam)
        W, b = fit(X1, y1, best[1]); p = (Xe[torch.tensor(me, device=dev)] @ W + b).softmax(1)[:, 1].cpu().numpy(); y = ye[me]
        r80 = recall_at(p, y); rows[q] = {"group": grp[q], "present_eval": int(y.sum()), "present_share": round(float(y.mean()), 3), "auc": round(float(roc_auc_score(y, p)), 3), "recall_at_p80": round(r80, 3), "ready": bool(y.sum() >= 20 and r80 >= 0.5)}
    res[en] = rows; a = [r["auc"] for r in rows.values() if r["auc"] is not None]; print(en, "mean AUC", round(float(np.mean(a)), 3), "ready", sum(r["ready"] for r in rows.values()), "of", len(rows), flush=True); hb.beat("t20-traits-binary", progress=f"{en} done"); del E
G = {}
for en, rows in res.items():
    for q, r in rows.items(): G.setdefault((en, r["group"]), []).append(r)
out = {"n_train": len(tri), "n_eval": len(evi), "per_question": res, "groups": {f"{en}|{g}": {"n": len(v), "ready": sum(x["ready"] for x in v), "auc_mean": round(float(np.mean([x["auc"] for x in v if x["auc"] is not None])), 3)} for (en, g), v in G.items()}}
json.dump(out, open("runs/pulse/traits_binary.json", "w"), indent=1); hb.finish("t20-traits-binary", "done", last="; ".join(f"{en}: AUC {np.mean([r['auc'] for r in rows.values() if r['auc'] is not None]):.3f}, ready {sum(r['ready'] for r in rows.values())}" for en, rows in res.items()))
for k, v in out["groups"].items(): print(k, v)
