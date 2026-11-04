"""T20 overnight Phase A: embed all development and training items with 9 frozen encoders on the local GPU (fp16, 128 tokens, no remote code). Resumable (skips encoders already saved). Registers heartbeat t20-ceiling-embed with pid.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python ceiling_embed.py [extra]     'extra' embeds devq2 + hf334 once their labels exist"""
import os, sys, json, glob, time, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live")
import heartbeat as hb
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; OUT = "runs/pulse/ceiling/"; EXTRA = "extra" in sys.argv
ENC = {"leaf": "MongoDB/mdbr-leaf-mt", "bge-small": "BAAI/bge-small-en-v1.5", "bge-base": "BAAI/bge-base-en-v1.5", "bge-large": "BAAI/bge-large-en-v1.5", "gte-small": "thenlper/gte-small", "arctic-s": "Snowflake/snowflake-arctic-embed-s", "gte-modernbert": "Alibaba-NLP/gte-modernbert-base", "qwen3-0.6b": "Qwen/Qwen3-Embedding-0.6B", "qwen3-4b": "Qwen/Qwen3-Embedding-4B"}
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
for p in ("runs/pulse/more/devq2_items.jsonl", "runs/pulse/more/hf334_items.jsonl"):
    if os.path.exists(p):
        for r in J(p): pool[r["id"]] = r["text"]
if not EXTRA:
    hk = {}; old = {}
    for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
        for r in J(f): hk[r["item_id"]] = 1; old[r["item_id"]] = 1
    for f in glob.glob("runs/p7/more*/labels.jsonl"):
        for r in J(f): hk[r["item_id"]] = 1
    oi = sorted(old); dt = np.array([pool[i] and (next(x for x in [0]) or "") for i in oi]) if False else None
    P = {r["id"]: r for r in J("data/pool_train.jsonl")}; dt = np.array([P[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(P[i]["date"] for i in test)
    trn = sorted(i for i in hk if i not in tset and P[i]["date"] and P[i]["date"] < start); devq = [r["item_id"] for r in J("runs/pulse/devq/labels.jsonl")]
    sn = set()
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): sn.add(r["item_id"])
    oldv = [i for i in test if i in sn]; ids = trn + sorted(devq) + oldv; json.dump({"ids": ids, "n_train": len(trn), "n_devq": len(devq), "n_old": len(oldv)}, open(OUT + "main_ids.json", "w")); name = "main"
else:
    ids = [json.loads(l)["id"] for p in ("runs/pulse/more/devq2_items.jsonl", "runs/pulse/more/hf334_items.jsonl") for l in open(p)]; json.dump({"ids": ids}, open(OUT + "extra_ids.json", "w")); name = "extra"
texts = [pool[i] for i in ids]; print(name, len(texts), flush=True)
for k, (tag, rid) in enumerate(ENC.items()):
    f = OUT + f"{tag}_{name}.npy"
    if os.path.exists(f): continue
    hb.beat("t20-ceiling-embed", pid=os.getpid(), where="[5090] local GPU", task="T20", state="running", progress=f"encoder {k + 1} of {len(ENC)}: {tag} ({name})", why="Overnight Phase A: is the limit the reader's size or the labels? Embed every item with 9 frozen encoders (ledger overnight program).", success="All 9 encoders embedded, no crash, GPU memory under 12 GB", next="Train the same dense head on every encoder (ceiling_heads.py) and read the table", need="Nothing", cap=3600)
    t0 = time.time(); m = SentenceTransformer(rid, device="cuda", model_kwargs={"torch_dtype": torch.float16}); m.max_seq_length = 128
    E = m.encode(texts, batch_size=64 if "4b" in tag else 128, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float16); np.save(f, E)
    print(tag, E.shape, f"{time.time() - t0:.0f}s", f"peak {torch.cuda.max_memory_allocated() / 1e9:.1f} GB", flush=True); del m; torch.cuda.empty_cache()
hb.finish("t20-ceiling-embed", "done", last=f"{name}: {len(ENC)} encoders embedded")
