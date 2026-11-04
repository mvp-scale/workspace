"""T21 round T-1: leaf encoder fine-tuned end to end with 51 present/absent heads on the Sonnet trait labels (1,500 train items), Ready rule per question as in traits_ready.py (threshold from a 12.5% train split to reach recall 0.80; eval = devq items). HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -I traits_ft.py"""
import os, json, math, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p)]; dev = "cuda"; EP = int(os.environ.get("TF_EPOCHS", 8)); LR = float(os.environ.get("TF_LR", 3e-5)); ENC = os.environ.get("TF_ENC", "MongoDB/mdbr-leaf-mt")
Q = json.load(open("specs/traits_v0.json"))["questions"]; qid = [q["id"] for q in Q]; grp = {q["id"]: q["group"] for q in Q}
txt = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}); txt.update({r["id"]: r["text"] for r in J("runs/pulse/devq_items.jsonl")})
tr = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/train/labels.jsonl")}; ev = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/eval/labels.jsonl")}
for r in J("runs/pulse/traits_pilot/sonnet_r1/labels.jsonl"): ev.setdefault(r["item_id"], r["label"])
tri = sorted(i for i in tr if i in txt); evi = sorted(i for i in ev if i in txt); rng = np.random.RandomState(0); idx = np.arange(len(tri)); rng.shuffle(idx); nv = len(tri) // 8; vix, tix = idx[:nv], idx[nv:]
Y = lambda D, ids: np.array([[-1 if D[i][q] == "cannot tell" else int(D[i][q] != "not at all") for q in qid] for i in ids]); Yt, Ye = Y(tr, tri), Y(ev, evi)
torch.manual_seed(0); m = SentenceTransformer(ENC, device=dev); m.max_seq_length = 96; d = m.get_sentence_embedding_dimension(); H = nn.Linear(d, len(qid)).to(dev)
opt = torch.optim.AdamW([{"params": m.parameters(), "lr": LR}, {"params": H.parameters(), "lr": 1e-3}], weight_decay=0.01); BS = 32; steps = EP * math.ceil(len(tix) / BS); sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[LR, 1e-3], total_steps=steps, pct_start=0.1)
Yt_t = torch.tensor(Yt, device=dev).float(); pw = torch.tensor([(max(1, (Yt[tix, k] == 0).sum())) / max(1, (Yt[tix, k] == 1).sum()) for k in range(len(qid))], device=dev).clamp(max=8)
def score(texts):
    m.eval(); o = []
    with torch.no_grad():
        for k in range(0, len(texts), 128):
            f = {a: b.to(dev) for a, b in m.tokenize(texts[k:k + 128]).items() if torch.is_tensor(b)}
            with torch.autocast("cuda", dtype=torch.bfloat16): o.append(torch.sigmoid(H(m(f)["sentence_embedding"].float())).float().cpu())
    return torch.cat(o).numpy()
for ep in range(EP):
    m.train(); perm = np.random.permutation(len(tix)); tl = 0
    for k in range(0, len(tix), BS):
        ix = tix[perm[k:k + BS]]; f = {a: b.to(dev) for a, b in m.tokenize([txt[tri[j]] for j in ix]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"]
        y = Yt_t[torch.tensor(ix, device=dev)]; mask = (y >= 0).float(); lo = Fn.binary_cross_entropy_with_logits(H(e.float()), y.clamp(min=0), pos_weight=pw, reduction="none"); loss = (lo * mask).sum() / mask.sum()
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(list(m.parameters()) + list(H.parameters()), 1.0); opt.step(); sch.step(); tl += loss.item()
    print("epoch", ep + 1, "loss", round(tl / math.ceil(len(tix) / BS), 3), flush=True)
Pv = score([txt[tri[j]] for j in vix]); Pe = score([txt[i] for i in evi])
def wil(k, mm, z=1.96):
    p = k / mm; dd = 1 + z * z / mm; c = (p + z * z / (2 * mm)) / dd; s = z * math.sqrt(p * (1 - p) / mm + z * z / (4 * mm * mm)) / dd; return c - s
rows = {}
for k, q in enumerate(qid):
    me = Ye[:, k] >= 0; y = Ye[me, k]; share = float(y.mean()); guess = max(share, 1 - share); mv = Yt[vix, k] >= 0; yv = Yt[vix, k][mv]; pv = Pv[mv, k]
    if (Yt[tix, k] == 1).sum() < 8 or y.sum() < 5: rows[q] = {"ready": False}; continue
    thr = float(np.sort(pv[yv == 1])[max(0, int(0.2 * yv.sum()))]) - 1e-9 if yv.sum() >= 3 else 0.5
    pr = Pe[me, k] >= thr; kk = int((pr == (y == 1)).sum()); rec = float(pr[y == 1].mean()); low = wil(kk, len(y)); ok = low >= 0.80 and low > guess and (share >= 0.5 or rec >= 0.80)
    rows[q] = {"group": grp[q], "agree": round(kk / len(y), 3), "low": round(low, 3), "guess": round(guess, 3), "recall": round(rec, 3), "ready": bool(ok)}
rd = [q for q in qid if rows[q]["ready"]]; print("READY", len(rd), "of 51 |", ENC, "| mean agree", round(float(np.mean([r["agree"] for r in rows.values() if "agree" in r])), 3)); print("ready:", rd)
json.dump(rows, open(f"runs/pulse/traits_ft_{ENC.split('/')[-1]}.json", "w"), indent=1)
