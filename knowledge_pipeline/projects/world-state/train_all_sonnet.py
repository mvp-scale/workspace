"""T21 round 13: one reader on EVERY Sonnet label we hold (label store: v3b > v2-frozen > wave versions, one label per item), leaf fine-tuned with three heads: story type, topic, presence. Excludes devq, the 601, dev2 and sealed ids. Scores: devq story/topic top-1 (vs Sonnet v2), presence on the 601 vs Sonnet v3b (alpha, AUC, recall at precision 0.80) and on devq vs v2. HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -I train_all_sonnet.py"""
import os, sys, json, glob, math, time, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sentence_transformers import SentenceTransformer
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p)]; dev = "cuda"; EP = int(os.environ.get("TA_EPOCHS", 10)); LR = float(os.environ.get("TA_LR", 5e-5)); TAG = os.environ.get("TA_TAG", "_all"); T0 = time.time()
hb.beat("t21-train-all-sonnet", pid=os.getpid(), where="[5090] local GPU, 450 W", task="T21", state="running", progress="loading", why="Does pooling every Sonnet label we hold (one label per item, newest version first) beat the subsets used so far?", success="presence recall at precision 0.80 up on the 601 and topic at or above 0.786", next="Decide the one codebook and relabel only what is missing", need="Nothing", cap=3600)
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] != "sonnet" or r["item_id"] not in txt: continue
    k = RANK.get(r["version"], 2)
    if r["item_id"] not in best or k < best[r["item_id"]][0]: best[r["item_id"]] = (k, r)
if os.environ.get("TA_HAIKU"):
    for r in J("runs/label_store/labels.jsonl"):
        if r["family"] == "haiku" and r["version"] == "ws-v2-frozen" and r["item_id"] in txt and r["item_id"] not in best: best[r["item_id"]] = (3, r)
ex = set(open("runs/pulse/dev2_ids.txt").read().split()) | set(open("runs/pulse/sealed_ids.txt").read().split()) | set(open("runs/pulse/sealed_q_ids.txt").read().split())
dq = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; ex |= set(dq)
it = {r["id"]: r["text"] for r in J("runs/pulse/ceiling_sonnet/items601.jsonl")}; ex |= set(it)
A = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/a601/labels.jsonl")}; B = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/b601/labels.jsonl")}
tr = sorted(i for i in best if i not in ex); lab = {i: best[i][1] for i in tr}; print("train", len(tr), "by version rank", {k: sum(best[i][0] == k for i in tr) for k in (0, 1, 2)}, "presence pos", sum(lab[i]["n_conditions"] > 0 for i in tr), flush=True)
story_cl = sorted({lab[i]["story_type"] for i in tr}); topic_cl = sorted({lab[i]["topic"] for i in tr}); dqi = sorted(i for i in dq if i in txt)
ys = torch.tensor([story_cl.index(lab[i]["story_type"]) for i in tr], device=dev); yt = torch.tensor([topic_cl.index(lab[i]["topic"]) for i in tr], device=dev); yp = torch.tensor([float(lab[i]["n_conditions"] > 0) for i in tr], device=dev); pm = torch.tensor([1.0 if best[i][0] <= int(os.environ.get("TA_PRES_MAX", 9)) else 0.0 for i in tr], device=dev)
torch.manual_seed(0); np.random.seed(0); m = SentenceTransformer("MongoDB/mdbr-leaf-mt", device=dev); m.max_seq_length = 64; d = m.get_sentence_embedding_dimension()
H = nn.ModuleDict({"s": nn.Linear(d, len(story_cl)), "t": nn.Linear(d, len(topic_cl)), "p": nn.Linear(d, 1), "l": nn.Linear(d, 6)}).to(dev); yl = torch.tensor([lab[i].get("max_level", -1) + 1 for i in tr], device=dev); LW = float(os.environ.get("TA_LEVEL_W", 0)); BS = 64; nt = len(tr)
opt = torch.optim.AdamW([{"params": m.parameters(), "lr": LR}, {"params": H.parameters(), "lr": 1e-3}], weight_decay=0.01); sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[LR, 1e-3], total_steps=EP * math.ceil(nt / BS), pct_start=0.1); pw = torch.tensor(3.0, device=dev)
for ep in range(EP):
    m.train(); perm = np.random.permutation(nt); tl = 0
    for k in range(0, nt, BS):
        ix = perm[k:k + BS]; ixt = torch.tensor(ix, device=dev); f = {a: b.to(dev) for a, b in m.tokenize([txt[tr[j]] for j in ix]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"]
        e = e.float(); loss = Fn.cross_entropy(H["s"](e), ys[ixt]) + Fn.cross_entropy(H["t"](e), yt[ixt]) + (Fn.binary_cross_entropy_with_logits(H["p"](e).squeeze(1), yp[ixt], pos_weight=pw, reduction="none") * pm[ixt]).sum() / pm[ixt].sum().clamp(min=1) + LW * (Fn.cross_entropy(H["l"](e), yl[ixt], reduction="none") * pm[ixt]).sum() / pm[ixt].sum().clamp(min=1)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(list(m.parameters()) + list(H.parameters()), 1.0); opt.step(); sch.step(); tl += loss.item()
    print("epoch", ep + 1, "loss", round(tl / math.ceil(nt / BS), 3), f"{time.time() - T0:.0f}s", flush=True); hb.beat("t21-train-all-sonnet", progress=f"epoch {ep + 1} of {EP}")
def emb(texts):
    m.eval(); o = []
    with torch.no_grad():
        for k in range(0, len(texts), 256):
            f = {a: b.to(dev) for a, b in m.tokenize(texts[k:k + 256]).items() if torch.is_tensor(b)}
            with torch.autocast("cuda", dtype=torch.bfloat16): o.append(m(f)["sentence_embedding"].float())
    return torch.cat(o)
def alpha(a, b):
    a = np.array(a, int); b = np.array(b, int); n = len(a); do = (a != b).mean(); N = 2 * n; c1 = a.sum() + b.sum(); c0 = N - c1; de = (N * N - c1 * c1 - c0 * c0) / (N * (N - 1)); return 1 - do / de
def r80(p, y):
    o = np.argsort(-p); tp = np.cumsum(y[o]); n = np.arange(1, len(o) + 1); ok = np.where(tp / n >= 0.8)[0]; return float(tp[ok.max()] / y.sum()) if len(ok) else 0.0
torch.set_grad_enabled(False)
Eq = emb([txt[i] for i in dqi]); Ps = H["s"](Eq).softmax(1).cpu().numpy(); Pt = H["t"](Eq).softmax(1).cpu().numpy(); pd = torch.sigmoid(H["p"](Eq).squeeze(1)).cpu().numpy()
sa = np.mean([story_cl[Ps[k].argmax()] == dq[i]["story_type"] for k, i in enumerate(dqi)]); ta = np.mean([topic_cl[Pt[k].argmax()] == dq[i]["topic"] for k, i in enumerate(dqi)])
yd = np.array([bool(dq[i]["conditions"]) for i in dqi]); ev = sorted(i for i in it if i in A and i in B); pe = torch.sigmoid(H["p"](emb([it[i] for i in ev])).squeeze(1)).cpu().numpy(); ya = np.array([A[i] for i in ev]); yb = np.array([B[i] for i in ev])
bt = max((alpha(pe >= t, ya), t) for t in np.arange(0.05, 1, 0.025))[1]
r = {"train_n": nt, "story_top1": round(float(sa), 3), "topic_top1": round(float(ta), 3), "devq_presence_auc": round(float(roc_auc_score(yd, pd)), 3), "devq_presence_r80": round(r80(pd, yd.astype(int)), 3), "p601_auc_A": round(float(roc_auc_score(ya, pe)), 3), "p601_auc_B": round(float(roc_auc_score(yb, pe)), 3), "p601_r80_A": round(r80(pe, ya.astype(int)), 3), "p601_r80_B": round(r80(pe, yb.astype(int)), 3), "p601_alpha_A_at_best_thr": round(alpha(pe >= bt, ya), 3), "p601_alpha_B_at_best_thr": round(alpha(pe >= bt, yb), 3), "minutes": round((time.time() - T0) / 60, 1)}
print(json.dumps(r), flush=True); json.dump(r, open(f"runs/pulse/train_all_sonnet{TAG}.json", "w"), indent=1); hb.finish("t21-train-all-sonnet", "done", last=json.dumps(r))
