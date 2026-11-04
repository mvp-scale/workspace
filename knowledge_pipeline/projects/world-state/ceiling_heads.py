"""T20 overnight Phase A, step 2: the same dense softmax head (GPU LBFGS, L2 chosen on a 10% holdout of the training rows) for every frozen encoder, field and training target; scored on DEVQ (1,997 natural) and the old 1,466. Agreement with Sonnet, never accuracy. Registers heartbeat t20-ceiling-heads.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python ceiling_heads.py [--tranche]       --tranche adds the 10,000 extra Sonnet labels once they exist"""
import os, sys, json, glob, math, time, numpy as np, torch, torch.nn.functional as Fn
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
TR = "--tranche" in sys.argv; tag = "t16k" if TR else "t6k"
hb.beat("t20-ceiling-heads", pid=os.getpid(), where="[5090] local GPU", task="T20", state="running", progress="loading labels", why="Overnight Phase A: same dense head on 9 frozen encoders, 4 fields, Haiku vs Sonnet targets (ledger overnight program).", success="Table complete for all encoders; paired differences vs leaf with intervals", next="Read the table: distillation path or labels path (rule in the program note)", need="Nothing", cap=3600)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; D = "runs/pulse/ceiling/"; M = json.load(open(D + "main_ids.json")); ids = M["ids"]; nt, nq, no = M["n_train"], M["n_devq"], M["n_old"]
hk = {}; sn = {}; dsn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl") + (glob.glob("runs/pulse/tranche/c*/labels.jsonl") if TR else []):
    for r in J(f): sn[r["item_id"]] = r["label"]
for r in J("runs/pulse/devq/labels.jsonl"): dsn[r["item_id"]] = r["label"]
train_ids, devq_ids, old_ids = ids[:nt], ids[nt:nt + nq], ids[nt + nq:]; S_tr = [k for k, i in enumerate(train_ids) if i in sn]; print("train", nt, "Sonnet-labelled in train", len(S_tr), "devq", nq, "old", no, flush=True)
dev = "cuda"; story_cl = sorted({hk[i]["story_type"] for i in train_ids} | {sn[i]["story_type"] for i in sn}); topic_cl = sorted({hk[i]["topic"] for i in train_ids} | {sn[i]["topic"] for i in sn} | {l["topic"] for l in dsn.values()}); cond_cl = sorted({c["condition"] for i in train_ids for c in hk[i]["conditions"]} | {c["condition"] for i in sn for c in sn[i]["conditions"]})
def fit(X, y, K, lam, iters=120):
    W = torch.zeros(X.shape[1], K, device=dev, requires_grad=True); b = torch.zeros(K, device=dev, requires_grad=True); opt = torch.optim.LBFGS([W, b], lr=1, max_iter=iters, history_size=20, line_search_fn="strong_wolfe")
    def cl(): opt.zero_grad(); loss = Fn.cross_entropy(X @ W + b, y) + lam * (W ** 2).sum(); loss.backward(); return loss
    opt.step(cl); return W.detach(), b.detach()
def best_fit(X, y, K):
    g = torch.Generator().manual_seed(0); perm = torch.randperm(len(y), generator=g).to(dev); nv = max(50, len(y) // 10); v, t = perm[:nv], perm[nv:]; best = (1e9, 1e-4)
    for lam in (1e-5, 1e-4, 1e-3):
        W, b = fit(X[t], y[t], K, lam); l = Fn.cross_entropy(X[v] @ W + b, y[v]).item()
        if l < best[0]: best = (l, lam)
    return fit(X, y, K, best[1]), best[1]
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
def recall_at(p, y, prec=0.83):
    o = np.argsort(-p); tp = np.cumsum(y[o]); n = np.arange(1, len(o) + 1); ok = tp / n >= prec; return float((tp / y.sum())[ok].max()) if ok.any() else 0.0
yq_story = np.array([story_cl.index(dsn[i]["story_type"]) for i in devq_ids]); yq_topic = np.array([topic_cl.index(dsn[i]["topic"]) for i in devq_ids]); yq_pos = np.array([bool(dsn[i]["conditions"]) for i in devq_ids])
sno = {}
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sno[r["item_id"]] = r["label"]
old_pos = [k for k, i in enumerate(old_ids) if sno[i]["conditions"]]; dq_pos = [k for k, i in enumerate(devq_ids) if dsn[i]["conditions"]]
res = {}; corr = {}
encs = [f.split("/")[-1][:-9] for f in sorted(glob.glob(D + "*_main.npy"))]; encs = [e for e in ["leaf", "bge-small", "gte-small", "arctic-s", "bge-base", "gte-modernbert", "bge-large", "qwen3-0.6b", "qwen3-4b", "ens"] if e in encs]
if os.environ.get("ENCS"): encs = os.environ["ENCS"].split(",")
tag = tag + os.environ.get("CH_TAG", "")
for en in encs:
    t0 = time.time(); E = torch.tensor(np.load(D + f"{en}_main.npy").astype(np.float32), device=dev); Xtr, Xq, Xo = E[:nt], E[nt:nt + nq], E[nt + nq:]
    for target in ("haiku", "sonnet", "mixed"):
        if target == "haiku": rows = np.arange(nt); labs = [hk[train_ids[i]] for i in rows]
        elif target == "sonnet": rows = np.array(S_tr); labs = [sn[train_ids[i]] for i in rows]
        else: rows = np.r_[np.arange(nt), np.tile(np.array(S_tr), 5)]; labs = [hk[train_ids[i]] for i in range(nt)] + [sn[train_ids[i]] for i in np.tile(np.array(S_tr), 5)]
        # story, topic
        for field, cl, yq in (("story_type", story_cl, yq_story), ("topic", topic_cl, yq_topic)):
            y = torch.tensor([cl.index(l["story_type" if field == "story_type" else "topic"]) for l in labs], device=dev); (W, b), lam = best_fit(Xtr[rows], y, len(cl)); P = (Xq @ W + b).softmax(1).cpu().numpy(); t1 = P.argmax(1) == yq
            r = {"top1": round(float(t1.mean()), 3), "top1_ci95": wil(int(t1.sum()), len(t1)), "lam": lam}; corr[(en, field + "_top1", target)] = t1
            if field == "topic": t2 = np.array([yq[k] in np.argsort(-P[k])[:2] for k in range(len(yq))]); r["top2"] = round(float(t2.mean()), 3); corr[(en, "topic_top2", target)] = t2
            res[f"{en}|{field}|{target}"] = r
        # presence
        y = torch.tensor([int(bool(l["conditions"])) for l in labs], device=dev); (W, b), lam = best_fit(Xtr[rows], y, 2); p = (Xq @ W + b).softmax(1)[:, 1].cpu().numpy()
        from sklearn.metrics import roc_auc_score
        res[f"{en}|presence|{target}"] = {"auc_devq": round(float(roc_auc_score(yq_pos, p)), 4), "recall_at_precision_0.83": round(recall_at(p, yq_pos), 3), "lam": lam}; corr[(en, "presence_p", target)] = p
        # which-condition among positives
        rr, yy = [], []
        for i, l in zip(rows, labs):
            for c in l["conditions"]: rr.append(i); yy.append(cond_cl.index(c["condition"]))
        (W, b), lam = best_fit(Xtr[torch.tensor(rr, device=dev)], torch.tensor(yy, device=dev), len(cond_cl)); hit = []
        for X_, ks, lblset, idl in ((Xq, dq_pos, dsn, devq_ids), (Xo, old_pos, sno, old_ids)):
            P = (X_[ks] @ W + b).argmax(1).cpu().numpy(); hit += [cond_cl[P[n]] in [c["condition"] for c in lblset[idl[k]]["conditions"]] for n, k in enumerate(ks)]
        hit = np.array(hit); res[f"{en}|which|{target}"] = {"top1": round(float(hit.mean()), 3), "top1_ci95": wil(int(hit.sum()), len(hit)), "n": len(hit), "lam": lam}; corr[(en, "which_top1", target)] = hit
    print(en, f"{time.time() - t0:.0f}s", {k.split('|', 1)[1]: v.get("top1", v.get("recall_at_precision_0.83")) for k, v in res.items() if k.startswith(en + "|")}, flush=True)
    hb.beat("t20-ceiling-heads", progress=f"done {en}; {len(res)} cells", last=f"{en} {time.time() - t0:.0f}s"); del E, Xtr, Xq, Xo; torch.cuda.empty_cache()
# paired differences vs leaf (bootstrap 200)
rng = np.random.RandomState(0); diffs = {}
for (en, m, target), v in corr.items():
    if en == "leaf" or ("leaf", m, target) not in corr: continue
    a = v.astype(float); b_ = corr[("leaf", m, target)].astype(float)
    if m == "presence_p":
        y = yq_pos; d = [recall_at(a[ix], y[ix]) - recall_at(b_[ix], y[ix]) for ix in (rng.randint(0, len(y), len(y)) for _ in range(200))]; mean = recall_at(a, y) - recall_at(b_, y)
    else: d = [a[ix].mean() - b_[ix].mean() for ix in (rng.randint(0, len(a), len(a)) for _ in range(200))]; mean = a.mean() - b_.mean()
    diffs[f"{en}|{m}|{target}"] = [round(float(mean), 3), round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]
np.savez(f"runs/pulse/ceiling_corr_{tag}.npz", **{f"{en}|{m}|{t}": np.asarray(v) for (en, m, t), v in corr.items()})
out = {"version": tag, "sonnet_train_rows": len(S_tr), "cells": res, "diff_vs_leaf": diffs}; json.dump(out, open(f"runs/pulse/ceiling_heads_{tag}.json", "w"), indent=1); hb.finish("t20-ceiling-heads", "done", last=f"{len(res)} cells; table in runs/pulse/ceiling_heads_{tag}.json")
