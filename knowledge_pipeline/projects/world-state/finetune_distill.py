"""T20 overnight Phase C: fine-tune leaf with multi-task heads on the local GPU; variant A hard labels, variant B plus soft targets from Qwen3-Embedding-4B heads (cross-fitted). Scored like the ceiling matrix on DEVQ. Registers heartbeat t20-finetune with pid. Each variant must end within 60 min.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python finetune_distill.py A B"""
import os, sys, json, glob, math, time, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live")
import heartbeat as hb
from sentence_transformers import SentenceTransformer
from sklearn.metrics import roc_auc_score
VAR = [a for a in sys.argv[1:] if a in ("A", "B")] or ["A", "B"]; TR = "--tranche" in sys.argv; dev = "cuda"; EPOCHS = int(os.environ.get("FT_EPOCHS", 3)); LRE = float(os.environ.get("FT_LR", 2e-5)); ALPHA = float(os.environ.get("FT_ALPHA", 1.0)); TAG = os.environ.get("FT_TAG", ""); MODEL = os.environ.get("FT_MODEL", "MongoDB/mdbr-leaf-mt"); BS = int(os.environ.get("FT_BS", 64)); SAVE = os.environ.get("FT_SAVE", "1") == "1"; T0 = time.time()
hb.beat("t20-finetune" + TAG, pid=os.getpid(), where="[5090] local GPU", task="T20", state="running", progress=f"variants {VAR}", why="Overnight Phase C: can fine-tuning (with or without distillation from the 4B reader) lift the CPU-size encoder on topic, presence and which-condition?", success="A student beats frozen leaf by the field bars with a bootstrap lower bound above 0", next="ONNX export + CPU speed + full-feature test for candidates; otherwise close fine-tuning for this size", need="Nothing", cap=3600)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; D = "runs/pulse/ceiling/"; M = json.load(open(D + "main_ids.json")); ids = M["ids"]; nt, nq, no = M["n_train"], M["n_devq"], M["n_old"]
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
hk = {}; sn = {}; dsn = {}; sno = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]; sno[r["item_id"]] = r["label"]
if TR:
    for f in glob.glob("runs/pulse/tranche/c*/labels.jsonl"):
        for r in J(f): sn[r["item_id"]] = r["label"]
for r in J("runs/pulse/devq/labels.jsonl"): dsn[r["item_id"]] = r["label"]
train_ids, devq_ids, old_ids = ids[:nt], ids[nt:nt + nq], ids[nt + nq:]
lab = [sn.get(i, hk[i]) for i in train_ids]; wt = np.array([3.0 if i in sn else 1.0 for i in train_ids], dtype=np.float32)
story_cl = sorted({l["story_type"] for l in lab} | {l["story_type"] for l in dsn.values()}); topic_cl = sorted({l["topic"] for l in lab} | {l["topic"] for l in dsn.values()}); cond_cl = sorted({c["condition"] for l in lab for c in l["conditions"]})
ys = torch.tensor([story_cl.index(l["story_type"]) for l in lab], device=dev); yt = torch.tensor([topic_cl.index(l["topic"]) for l in lab], device=dev); yp = torch.tensor([int(bool(l["conditions"])) for l in lab], device=dev)
Yc = torch.zeros(nt, len(cond_cl), device=dev)
for k, l in enumerate(lab):
    for c in l["conditions"]: Yc[k, cond_cl.index(c["condition"])] = 1.0
posm = Yc.sum(1) > 0
# ---- soft targets from the Qwen3-4B reader, cross-fitted
def fit(X, y, K, lam=1e-4, iters=100):
    W = torch.zeros(X.shape[1], K, device=dev, requires_grad=True); b = torch.zeros(K, device=dev, requires_grad=True); opt = torch.optim.LBFGS([W, b], lr=1, max_iter=iters, history_size=20, line_search_fn="strong_wolfe")
    def cl(): opt.zero_grad(); loss = Fn.cross_entropy(X @ W + b, y) + lam * (W ** 2).sum(); loss.backward(); return loss
    opt.step(cl); return W.detach(), b.detach()
soft = None
if "B" in VAR:
    E4 = torch.tensor(np.load(D + "qwen3-4b_main.npy")[:nt].astype(np.float32), device=dev); fold = torch.arange(nt, device=dev) % 5; soft = {"s": torch.zeros(nt, len(story_cl), device=dev), "t": torch.zeros(nt, len(topic_cl), device=dev), "p": torch.zeros(nt, 2, device=dev), "c": torch.zeros(nt, len(cond_cl), device=dev)}
    for f in range(5):
        tr, te = fold != f, fold == f
        for key, y, K in (("s", ys, len(story_cl)), ("t", yt, len(topic_cl)), ("p", yp, 2)): W, b = fit(E4[tr], y[tr], K); soft[key][te] = (E4[te] @ W + b).softmax(1)
        m = tr & posm; W, b = fit(E4[m], Yc[m].argmax(1), len(cond_cl)); soft["c"][te] = (E4[te] @ W + b).softmax(1)
    del E4; print("soft targets cross-fitted", flush=True)
# ---- eval data
def toks(model, texts): return model.tokenize(texts)
yq_s = np.array([story_cl.index(dsn[i]["story_type"]) for i in devq_ids]); yq_t = np.array([topic_cl.index(dsn[i]["topic"]) for i in devq_ids]); yq_p = np.array([bool(dsn[i]["conditions"]) for i in devq_ids])
pos_eval = [(("q", k), dsn[i]["conditions"]) for k, i in enumerate(devq_ids) if dsn[i]["conditions"]] + [(("o", k), sno[i]["conditions"]) for k, i in enumerate(old_ids) if sno[i]["conditions"]]
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
def recall_at(p, y, prec=0.83):
    o = np.argsort(-p); tp = np.cumsum(y[o]); n = np.arange(1, len(o) + 1); ok = tp / n >= prec; return float((tp / y.sum())[ok].max()) if ok.any() else 0.0
def run(variant):
    torch.manual_seed(0); np.random.seed(0); alpha = ALPHA if variant == "B" else 0.0; m = SentenceTransformer(MODEL, device=dev); m.max_seq_length = 64; d = m.get_sentence_embedding_dimension()
    H = nn.ModuleDict({"s": nn.Linear(d, len(story_cl)), "t": nn.Linear(d, len(topic_cl)), "p": nn.Linear(d, 2), "c": nn.Linear(d, len(cond_cl))}).to(dev)
    opt = torch.optim.AdamW([{"params": m.parameters(), "lr": LRE}, {"params": H.parameters(), "lr": 1e-3}], weight_decay=0.01); steps = EPOCHS * math.ceil(nt / BS); sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[LRE, 1e-3], total_steps=steps, pct_start=0.1)
    texts = [pool[i] for i in train_ids]; w_all = torch.tensor(wt, device=dev); step = 0
    for ep in range(EPOCHS):
        m.train(); perm = np.random.permutation(nt); tl = 0
        for k in range(0, nt, BS):
            ix = perm[k:k + BS]; ixt = torch.tensor(ix, device=dev); f = {a: b.to(dev) for a, b in m.tokenize([texts[j] for j in ix]).items() if torch.is_tensor(b)}
            with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"]
            e = e.float(); w = w_all[ixt]; pm = posm[ixt]
            ls = (Fn.cross_entropy(H["s"](e), ys[ixt], reduction="none") * w).mean(); lt = (Fn.cross_entropy(H["t"](e), yt[ixt], reduction="none") * w).mean(); lp = (Fn.cross_entropy(H["p"](e), yp[ixt], reduction="none") * w).mean()
            lc = (Fn.cross_entropy(H["c"](e[pm]), Yc[ixt][pm].argmax(1), reduction="none") * w[pm]).mean() if pm.any() else e.sum() * 0
            loss = ls + lt + lp + lc
            if alpha:
                T = 2.0; kl = lambda lo, sp: Fn.kl_div((lo / T).log_softmax(1), (sp ** (1 / T)) / (sp ** (1 / T)).sum(1, keepdim=True), reduction="batchmean") * T * T
                loss = loss + alpha * (kl(H["s"](e), soft["s"][ixt]) + kl(H["t"](e), soft["t"][ixt]) + kl(H["p"](e), soft["p"][ixt]) + (kl(H["c"](e[pm]), soft["c"][ixt][pm]) if pm.any() else 0))
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(list(m.parameters()) + list(H.parameters()), 1.0); opt.step(); sched.step(); tl += loss.item(); step += 1
        print(variant, "epoch", ep + 1, "loss", round(tl / math.ceil(nt / BS), 3), f"{time.time() - T0:.0f}s", flush=True); hb.beat("t20-finetune" + TAG, progress=f"variant {variant} epoch {ep + 1} of {EPOCHS}", last=f"loss {tl / math.ceil(nt / BS):.3f}")
    m.eval()
    def emb(idl):
        out = []
        with torch.no_grad():
            for k in range(0, len(idl), 256):
                f = {a: b.to(dev) for a, b in m.tokenize([pool[i] for i in idl[k:k + 256]]).items() if torch.is_tensor(b)}
                with torch.autocast("cuda", dtype=torch.bfloat16): out.append(m(f)["sentence_embedding"].float())
        return torch.cat(out)
    Eq = emb(devq_ids); Eo = emb(old_ids); r = {}
    with torch.no_grad():
        Ps = H["s"](Eq).softmax(1).cpu().numpy(); Pt = H["t"](Eq).softmax(1).cpu().numpy(); Pp = H["p"](Eq).softmax(1)[:, 1].cpu().numpy()
        t1 = Ps.argmax(1) == yq_s; r["story_top1"] = round(float(t1.mean()), 3); r["story_ci95"] = wil(int(t1.sum()), len(t1)); a1 = Pt.argmax(1) == yq_t; r["topic_top1"] = round(float(a1.mean()), 3); r["topic_ci95"] = wil(int(a1.sum()), len(a1)); a2 = np.array([yq_t[k] in np.argsort(-Pt[k])[:2] for k in range(len(yq_t))]); r["topic_top2"] = round(float(a2.mean()), 3)
        r["presence_recall_at_0.83"] = round(recall_at(Pp, yq_p), 3); r["presence_auc"] = round(float(roc_auc_score(yq_p, Pp)), 4); hit = []
        for (src, k), cs in pos_eval:
            e = (Eq if src == "q" else Eo)[k:k + 1]; hit.append(cond_cl[int(H["c"](e).argmax())] in [c["condition"] for c in cs])
        hit = np.array(hit); r["which_top1"] = round(float(hit.mean()), 3); r["which_ci95"] = wil(int(hit.sum()), len(hit)); r["which_n"] = len(hit)
    r["minutes"] = round((time.time() - T0) / 60, 1); print(variant, json.dumps(r), flush=True)
    corr = {"s": t1, "t": a1, "p": Pp, "w": hit}
    if SAVE: torch.save({"model": m[0].auto_model.state_dict(), "st_full": {k: v.cpu() for k, v in m.state_dict().items()}, "heads": H.state_dict()}, f"runs/pulse/ceiling/ft_{variant}{TAG}.pt")
    np.savez(f"runs/pulse/ceiling/ft_{variant}{TAG}_corr.npz", **corr); return r
out = {}
for v in VAR:
    out[v] = run(v); json.dump(out, open(f"runs/pulse/finetune_distill{TAG}.json" if not TR else f"runs/pulse/finetune_distill_t16k{TAG}.json", "w"), indent=1); torch.cuda.empty_cache()
hb.finish("t20-finetune" + TAG, "done", last="; ".join(f"{v}: topic {r['topic_top1']}, presence {r['presence_recall_at_0.83']}, which {r['which_top1']}" for v, r in out.items()))
