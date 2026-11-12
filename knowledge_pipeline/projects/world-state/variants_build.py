"""Build compact views for 800 MN-DS full articles (50 per category of the L995 sample). Appends to runs/harvest/mnds_variants.jsonl (resumable).
    nohup /workspace/models/embed-zs/.venv/bin/python variants_build.py &"""
import json, os, sys, random, collections, time, warnings; warnings.filterwarnings("ignore")
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
from sentence_transformers import SentenceTransformer
import article_views as V
gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}
R = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; R = [r for r in R if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
rng = random.Random(20261105); by = collections.defaultdict(list)
for r in R: by[r["category_level_1"]].append(r)
S = []
for c in sorted(by): S += rng.sample(by[c], 100)[:50]
OUT = "runs/harvest/mnds_variants.jsonl"; done = {json.loads(l)["i"] for l in open(OUT)} if os.path.exists(OUT) else set()
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
embed = lambda xs: m.encode(xs, batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
t0 = time.time(); n = 0
with open(OUT, "a") as f:
    for i, r in enumerate(S):
        if i in done: continue
        v = V.views(r["content"], nlp, embed)
        if v is None: continue
        f.write(json.dumps({"i": i, "title": r["title"], "category": r["category_level_1"], "content": r["content"], "views": v}) + "\n"); f.flush(); n += 1
        if n % 20 == 0: print(f"{n} built, {(time.time()-t0)/n:.1f}s each, elapsed {time.time()-t0:.0f}s", flush=True)
print("done", n, "built;", len(S), "selected", flush=True)
