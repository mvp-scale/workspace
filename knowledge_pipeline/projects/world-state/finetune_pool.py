"""T21 main loop round 1: fine-tune the leaf student on the 46k Gemma-4 v3b pool labels, story type and topic only (no presence, no conditions). dev2 ids are left out of training; devq is disjoint from the pool. Scored on devq (Sonnet truth), top-1 like finetune_distill.py. Registers heartbeat t21-round1-pool-ft.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python finetune_pool.py"""
import os, sys, json, glob, math, time, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live")
import heartbeat as hb
from sentence_transformers import SentenceTransformer
dev = "cuda"; EPOCHS = int(os.environ.get("FT_EPOCHS", 3)); LRE = float(os.environ.get("FT_LR", 2e-5)); BS = int(os.environ.get("FT_BS", 64)); TAG = os.environ.get("FT_TAG", "_pool3"); T0 = time.time()
hb.beat("t21-round1-pool-ft", pid=os.getpid(), where="[5090] local GPU, 450 W", task="T21", state="running", progress="loading", why="Main loop round 1: does training the reader on 46k Gemma-4 pool labels beat the 6k Sonnet + Haiku student on story type and topic?", success="story or topic top-1 up 0.02 on devq with the other within 0.01", next="Score on ledger, mine mistakes, change one thing", need="Nothing", cap=3600)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {}
for r in J("data/pool.jsonl"): pool.setdefault(r["id"], r["text"])
g = {r["item_id"]: r["label"] for r in J("runs/pulse/pool_gemma4_off/labels.jsonl")}; skip = set(open("runs/pulse/dev2_ids.txt").read().split())
qt = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}; dsn = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; dq = sorted(i for i in dsn if i in qt)
MIX = int(os.environ.get("FT_SONNET_W", 0)); sn = {}
if MIX:
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): sn[r["item_id"]] = r["label"]
    if os.environ.get("FT_NEW6K"):
        for f in glob.glob("runs/pulse/sonnet_pool6k/part*/labels.jsonl"):
            for r in J(f): sn[r["item_id"]] = r["label"]
    if os.environ.get("FT_BASE") == "haiku":
        g = {}
        for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
            for r in J(f): g[r["item_id"]] = r["label"]
    g.update({i: l for i, l in sn.items() if i in pool}); print("sonnet labels", len([i for i in sn if i in pool and i not in skip]), "weight", MIX, flush=True)
if os.environ.get("FT_AGREE"):
    hk = {}
    for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
        for r in J(f): hk[r["item_id"]] = r["label"]
    keep = {i for i in g if i in sn or (i in hk and hk[i]["topic"] == g[i]["topic"] and hk[i]["story_type"] == g[i]["story_type"])}; g = {i: l for i, l in g.items() if i in keep}; print("agree filter kept", len(g), flush=True)
tr = [i for i in g if i in pool and i not in skip]; tr += [i for i in sn if i in pool and i not in skip] * (MIX - 1 if MIX else 0); story_cl = sorted({g[i]["story_type"] for i in tr} | {dsn[i]["story_type"] for i in dq}); topic_cl = sorted({g[i]["topic"] for i in tr} | {dsn[i]["topic"] for i in dq}); nt = len(tr)
ys = torch.tensor([story_cl.index(g[i]["story_type"]) for i in tr], device=dev); yt = torch.tensor([topic_cl.index(g[i]["topic"]) for i in tr], device=dev)
yq_s = np.array([story_cl.index(dsn[i]["story_type"]) for i in dq]); yq_t = np.array([topic_cl.index(dsn[i]["topic"]) for i in dq])
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
torch.manual_seed(0); np.random.seed(0); m = SentenceTransformer(os.environ.get("FT_ENC", "MongoDB/mdbr-leaf-mt"), device=dev); m.max_seq_length = 64; d = m.get_sentence_embedding_dimension()
H = nn.ModuleDict({"s": nn.Linear(d, len(story_cl)), "t": nn.Linear(d, len(topic_cl))}).to(dev)
opt = torch.optim.AdamW([{"params": m.parameters(), "lr": LRE}, {"params": H.parameters(), "lr": 1e-3}], weight_decay=0.01); steps = EPOCHS * math.ceil(nt / BS); sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[LRE, 1e-3], total_steps=steps, pct_start=0.1); texts = [pool[i] for i in tr]
print("train", nt, "devq", len(dq), "classes", len(story_cl), len(topic_cl), flush=True)
for ep in range(EPOCHS):
    m.train(); perm = np.random.permutation(nt); tl = 0
    for k in range(0, nt, BS):
        ix = perm[k:k + BS]; ixt = torch.tensor(ix, device=dev); f = {a: b.to(dev) for a, b in m.tokenize([texts[j] for j in ix]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"]
        e = e.float(); loss = Fn.cross_entropy(H["s"](e), ys[ixt]) + Fn.cross_entropy(H["t"](e), yt[ixt])
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(list(m.parameters()) + list(H.parameters()), 1.0); opt.step(); sched.step(); tl += loss.item()
    print("epoch", ep + 1, "loss", round(tl / math.ceil(nt / BS), 3), f"{time.time() - T0:.0f}s", flush=True); hb.beat("t21-round1-pool-ft", progress=f"epoch {ep + 1} of {EPOCHS}", last=f"loss {tl / math.ceil(nt / BS):.3f}")
m.eval(); out = []
with torch.no_grad():
    for k in range(0, len(dq), 256):
        f = {a: b.to(dev) for a, b in m.tokenize([qt[i] for i in dq[k:k + 256]]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): out.append(m(f)["sentence_embedding"].float())
    Eq = torch.cat(out); Ps = H["s"](Eq).softmax(1).cpu().numpy(); Pt = H["t"](Eq).softmax(1).cpu().numpy()
t1 = Ps.argmax(1) == yq_s; a1 = Pt.argmax(1) == yq_t; a2 = np.array([yq_t[k] in np.argsort(-Pt[k])[:2] for k in range(len(yq_t))])
r = {"story_top1": round(float(t1.mean()), 3), "story_ci95": wil(int(t1.sum()), len(t1)), "topic_top1": round(float(a1.mean()), 3), "topic_ci95": wil(int(a1.sum()), len(a1)), "topic_top2": round(float(a2.mean()), 3), "train_n": nt, "epochs": EPOCHS, "minutes": round((time.time() - T0) / 60, 1)}
print(json.dumps(r), flush=True); json.dump(r, open(f"runs/pulse/finetune_pool{TAG}.json", "w"), indent=1); np.savez(f"runs/pulse/ceiling/ft_pool{TAG}_corr.npz", s=t1, t=a1, Pt=Pt, Ps=Ps, ids=np.array(dq), topic_cl=np.array(topic_cl), story_cl=np.array(story_cl))
hb.finish("t21-round1-pool-ft", "done", last=f"story {r['story_top1']}, topic {r['topic_top1']}")
