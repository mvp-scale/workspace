import json, glob, re, pathlib, sys, time, numpy as np, os
os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sentence_transformers import SentenceTransformer
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("embed-bge-small", where="[5090]", task="T10", state="running", why="Frozen bge-small embeddings for all labelled items: do they add meaning that word counts miss?", success="Embeddings saved for every labelled item", next="Pulse 1 scoring", need="Nothing", progress="loading", spent=0.0, cap=0.0)
ids = sorted({r["item_id"] for f in glob.glob(str(H0 / "runs/p7/*/labels.jsonl")) for r in J(f)}); pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}
txt = [re.sub(r"\s+", " ", pool[i]["text"])[:1200] for i in ids]; m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda"); m.max_seq_length = 256; t0 = time.time()
E = m.encode(txt, batch_size=256, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
np.save(H0 / "runs/embeds/bge_small.npy", E); json.dump(ids, open(H0 / "runs/embeds/bge_small_ids.json", "w")); print(E.shape, round(time.time() - t0), "s")
hb.finish("embed-bge-small", "done", last=f"{E.shape[0]} items in {time.time() - t0:.0f}s on the 5090", progress=str(E.shape))
