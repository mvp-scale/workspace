"""T21 round 8: fine-tune the encoder end to end on condition presence (Sonnet v3b pool labels), threshold chosen on a 10% train split, scored on the 601 devq items vs Sonnet v3b A/B (alpha; bar 0.754, ledger L627). Env PF_ENC, PF_EPOCHS, PF_LR. HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -I presence_ft.py"""
import os, json, glob, math, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p)]; dev = "cuda"; ENC = os.environ.get("PF_ENC", "MongoDB/mdbr-leaf-mt"); EP = int(os.environ.get("PF_EPOCHS", 8)); LR = float(os.environ.get("PF_LR", 3e-5))
pool = {}
for r in J("data/pool.jsonl"): pool.setdefault(r["id"], r["text"])
tr = {r["item_id"]: bool(r["label"]["conditions"]) for f in glob.glob("runs/pulse/sonnet_pool6k/part*/labels.jsonl") + (glob.glob("runs/pulse/sonnet_pool_pos/part*/labels.jsonl") if os.environ.get("PF_POS") else []) for r in J(f)}
if os.environ.get("PF_V2"):
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): tr.setdefault(r["item_id"], bool(r["label"]["conditions"]))
it = {r["id"]: r["text"] for r in J("runs/pulse/ceiling_sonnet/items601.jsonl")}
A = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/a601/labels.jsonl")}; B = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/b601/labels.jsonl")}
ev = sorted(i for i in it if i in A and i in B); ids = sorted(i for i in tr if i in pool and i not in it); rng = np.random.RandomState(0); rng.shuffle(ids); ids = ids[:int(len(ids) * float(os.environ.get("PF_FRAC", 1)))]; nv = len(ids) // 10; vi, ti = ids[:nv], ids[nv:]
def alpha(a, b):
    a = np.array(a, int); b = np.array(b, int); n = len(a); do = (a != b).mean(); N = 2 * n; c1 = a.sum() + b.sum(); c0 = N - c1; de = (N * N - c1 * c1 - c0 * c0) / (N * (N - 1)); return 1 - do / de
torch.manual_seed(0); m = SentenceTransformer(ENC, device=dev); m.max_seq_length = 96; d = m.get_sentence_embedding_dimension(); H = nn.Linear(d, 1).to(dev)
opt = torch.optim.AdamW([{"params": m.parameters(), "lr": LR}, {"params": H.parameters(), "lr": 1e-3}], weight_decay=0.01); BS = 32; steps = EP * math.ceil(len(ti) / BS); sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[LR, 1e-3], total_steps=steps, pct_start=0.1)
y = {i: float(tr[i]) for i in ids}; pw = torch.tensor((1 - np.mean([y[i] for i in ti])) / np.mean([y[i] for i in ti]) ** 1.0, device=dev).clamp(max=6)
def score(texts):
    m.eval(); o = []
    with torch.no_grad():
        for k in range(0, len(texts), 128):
            f = {a: b.to(dev) for a, b in m.tokenize(texts[k:k + 128]).items() if torch.is_tensor(b)}
            with torch.autocast("cuda", dtype=torch.bfloat16): o.append(torch.sigmoid(H(m(f)["sentence_embedding"].float())).squeeze(1).float().cpu())
    return torch.cat(o).numpy()
for ep in range(EP):
    m.train(); perm = np.random.permutation(len(ti)); tl = 0
    for k in range(0, len(ti), BS):
        ix = perm[k:k + BS]; f = {a: b.to(dev) for a, b in m.tokenize([pool[ti[j]] for j in ix]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"]
        loss = Fn.binary_cross_entropy_with_logits(H(e.float()).squeeze(1), torch.tensor([y[ti[j]] for j in ix], device=dev), pos_weight=pw)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(list(m.parameters()) + list(H.parameters()), 1.0); opt.step(); sch.step(); tl += loss.item()
    pv = score([pool[i] for i in vi]); yv = [tr[i] for i in vi]; best = max(((alpha(pv >= t, yv), t) for t in np.arange(0.1, 0.95, 0.05)))
    print("epoch", ep + 1, "loss", round(tl / math.ceil(len(ti) / BS), 3), "val alpha", round(best[0], 3), "thr", round(best[1], 2), flush=True)
pe = score([it[i] for i in ev]); t = best[1]; pr = pe >= t; ya = [A[i] for i in ev]; yb = [B[i] for i in ev]
print("RESULT", ENC, "thr", round(t, 2), "alpha vs A", round(alpha(pr, ya), 3), "vs B", round(alpha(pr, yb), 3), "disagree A", round(float((pr != np.array(ya)).mean()), 3), "pred yes", int(pr.sum()), "of", len(ev), flush=True)
DQ = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/devq/labels.jsonl")}; QT = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}; di = sorted(i for i in DQ if i in QT); pd = score([QT[i] for i in di]); yd = [DQ[i] for i in di]
print("DEVQ v2 truth n", len(di), "pos", sum(yd), "alpha", round(alpha(pd >= t, yd), 3), "disagree", round(float(((pd >= t) != np.array(yd)).mean()), 3), flush=True)
v2c = [i for i in ev if i in DQ]; print("601 items: v3b A vs v2 truth alpha", round(alpha([A[i] for i in v2c], [DQ[i] for i in v2c]), 3), "| reader vs v2 on same", round(alpha([bool(pe[k] >= t) for k, i in enumerate(ev) if i in DQ], [DQ[i] for i in v2c]), 3), flush=True)
np.savez(os.environ.get("PF_OUT", "runs/pulse/presence_scores.npz"), ev=np.array(ev), pe=pe, A=np.array(ya), B=np.array(yb), di=np.array(di), pd=pd, yd=np.array(yd))
if os.environ.get("PF_POS_SKIP"): raise SystemExit
ex = set(open("runs/pulse/dev2_ids.txt").read().split()) | set(open("runs/pulse/sealed_ids.txt").read().split()) | set(open("runs/pulse/sealed_q_ids.txt").read().split()) | set(tr) | set(it) | {r["item_id"] for r in J("runs/pulse/devq/labels.jsonl")}
for f in glob.glob("runs/p7b/*/labels.jsonl"): ex |= {r["item_id"] for r in J(f)}
cand = sorted(i for i in pool if i not in ex); ps = score([pool[i] for i in cand]); o = np.argsort(-ps)
print("candidates", len(cand), "score>=thr", int((ps >= t).sum()), "score>=0.5", int((ps >= 0.5).sum()), flush=True)
os.makedirs("runs/pulse/sonnet_pool_pos", exist_ok=True)
with open("runs/pulse/sonnet_pool_pos/items.jsonl", "w") as f:
    for k in o[:3000]: f.write(json.dumps({"id": cand[k], "text": pool[cand[k]][:700]}) + "\n")
print("wrote top 3000, score range", float(ps[o[0]]), float(ps[o[2999]]))
