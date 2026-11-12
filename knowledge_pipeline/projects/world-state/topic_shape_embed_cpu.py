"""CPU-only embeddings of the topic-shape views with a given model (default bge-small), saved as runs/embeds/<prefix>_<view>.npy. whole_article is left out (up to 8 chunks per article; cost not timed).
    SHAPE_MODEL=BAAI/bge-small-en-v1.5 SHAPE_PREFIX=shape_small /workspace/models/embed-zs/.venv/bin/python topic_shape_embed_cpu.py"""
import os, re, json, time, numpy as np
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
from sentence_transformers import SentenceTransformer
MODEL = os.environ.get("SHAPE_MODEL", "BAAI/bge-small-en-v1.5"); PFX = os.environ.get("SHAPE_PREFIX", "shape_small"); N = 5000
R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]; X = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/extract.jsonl"))]
T = []; B = []
for r, x in zip(R, X):
    ti = re.sub(r"\s+", " ", r["title"] or "").strip(); T.append(ti); B.append(x["text"][len(ti) + 2:] if x["text"].startswith(ti) else x["text"])
def first_sentence(b): m = re.search(r"(?<=[a-z0-9\"”’)])[.!?](?=\s+[A-Z“\"])", b[:600]); return b[:m.end()] if m else b[:300]
words = lambda b, k: " ".join(b.split()[:k])
texts = {"title": [t or b[:100] for t, b in zip(T, B)], "first_sentence": [first_sentence(b) or t for b, t in zip(B, T)], "first_250_words": [words(t + ". " + b, 250) for t, b in zip(T, B)]}
m = SentenceTransformer(MODEL, device="cpu"); m.max_seq_length = 384; tot = {}
for v, xs in texts.items():
    t0 = time.time(); E = m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32); np.save(f"runs/embeds/{PFX}_{v}.npy", E); tot[v] = round(time.time() - t0); print(v, E.shape, tot[v], "s", flush=True)
json.dump({"model": MODEL, "device": "cpu", "seconds": tot}, open(f"runs/embeds/{PFX}_timing.json", "w"))
