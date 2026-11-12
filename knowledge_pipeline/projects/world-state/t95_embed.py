"""T95 step 1: embed every usable row of one CC-News parquet file with bge-small (headline + description, 64 word pieces, the T90 text). One card per file keeps each run under the one-hour cap (about 170 articles/s on CPU).
    FILE=<0-4> NP=<max rows, 0 = all> OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t95_embed.py -> <OUT>/emb_<FILE>.npy (float16, normalised), <OUT>/meta_<FILE>.jsonl (url, domain, date)"""
import os, sys, json, glob, time, pathlib
DEV = os.environ.get("DEVICE", "cpu")  # cpu or cuda (the local GPU, fp32, owner yes 2026-11-10 for this embedding)
if DEV == "cpu": os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch, pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "/workspace/knowledge_pipeline/kit/live"); import heartbeat as hb
F = int(os.environ["FILE"]); NP = int(os.environ.get("NP", 0)); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t95")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); torch.set_num_threads(int(os.environ.get("THREADS", 18)))
JOB = f"t95-embed-{F}" + ("-gpu" if DEV == "cuda" else "") + ("-smoke" if NP else "")
hb.beat(JOB, state="running", where="[CPU]", alive_pid=os.getpid(), every_s=180, why=f"Embed CC-News parquet file {F} for the full-pool pair search (T95)", success="emb and meta files written", progress="reading")
try:
    fs = sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")); rows = []
    for r in pq.read_table(fs[F], columns=["title", "description", "url", "domain", "date"]).to_pylist():
        d = " ".join((r["description"] or "").split()); ti = " ".join((r["title"] or "").split())
        if len(ti) >= 10 and len(d) >= 30 and r["date"]: rows.append((r["url"], ti + ". " + d, r["domain"], str(r["date"])[:10]))
        if NP and len(rows) >= NP: break
    m = SentenceTransformer("BAAI/bge-small-en-v1.5", device=DEV); m.max_seq_length = 64; E = []
    for k in range(0, len(rows), 8192):
        E.append(m.encode([r[1] for r in rows[k:k + 8192]], batch_size=(512 if DEV == "cuda" else 128), normalize_embeddings=True, convert_to_numpy=True).astype(np.float16)); hb.beat(JOB, progress=f"embedded {min(k + 8192, len(rows))} of {len(rows)}")
    np.save(OUT / f"emb_{F}.npy", np.vstack(E))
    with open(OUT / f"meta_{F}.jsonl", "w") as w:
        for r in rows: w.write(json.dumps({"url": r[0], "domain": r[2], "date": r[3]}) + "\n")
    json.dump({"file": F, "rows": len(rows), "seconds": round(time.time() - T0)}, open(OUT / f"embed_{F}.json", "w"))
    (hb.drop(JOB) if NP else hb.finish(JOB, "done", progress=f"{len(rows)} rows", last="finished")); print(json.dumps({"file": F, "rows": len(rows), "seconds": round(time.time() - T0)}))
except BaseException as e:
    hb.finish(JOB, "failed", last=f"{type(e).__name__}: {str(e)[:100]}"); raise
