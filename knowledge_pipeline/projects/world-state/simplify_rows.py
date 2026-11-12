"""Adds the cosine of each simplified variant to its original, per sentence, to runs/harvest/relations/simplify.json (so the page can show it row by row)."""
import os, json, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
P = "runs/harvest/relations/simplify.json"; D = json.load(open(P)); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
names = ["no_noise_words", "no_noise_words_keep_negation", "content_words", "core_triples"]
for a in D["per_article"]:
    O = enc([r["original"] for r in a["rows"]])
    for k in names:
        idx = [i for i, r in enumerate(a["rows"]) if r[k].strip()]; V = enc([a["rows"][i][k] for i in idx]); c = {i: round(float(V[j] @ O[i]), 3) for j, i in enumerate(idx)}
        for i, r in enumerate(a["rows"]): r["cos_" + k] = c.get(i)
json.dump(D, open(P, "w"), indent=1); print("rows updated:", sum(len(a["rows"]) for a in D["per_article"]))
