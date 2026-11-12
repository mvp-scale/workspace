"""T90: same-event pair pool at a larger sample of CC-News. Same rule as triple_pairs.py (bge-small headline+description, cosine >= 0.85, different domain, dates within 2 days). Counts the articles that have 2 or more partners (the core that triple support needs, T76) and 6 or more.
    PER=<articles per file> OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t90_pairs.py -> <OUT>/t90_pairs.json, <OUT>/pairs_ids.json (pairs as url ids, not indexes)"""
import os, sys, json, glob, time, datetime, collections, pathlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch, pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "/workspace/knowledge_pipeline/kit/live"); import heartbeat as hb
PER = int(os.environ.get("PER", 20000)); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t90")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); torch.set_num_threads(18)
JOB = "t90-pairs" if PER >= 5000 else "t90-pairs-smoke"
hb.beat(JOB, state="running", where="[CPU]", alive_pid=os.getpid(), every_s=180, why="Count same-event pairs and articles with 2+ partners at a larger CC-News sample (T90)", success="result file t90_pairs.json written with core counts", progress="sampling")
try:
    rng = np.random.default_rng(90); rows = []
    for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
        t = pq.read_table(f, columns=["title", "description", "url", "domain", "date"]).to_pylist(); got = 0
        for k in rng.permutation(len(t)):
            r = t[k]; d = " ".join((r["description"] or "").split()); ti = " ".join((r["title"] or "").split())
            if len(ti) < 10 or len(d) < 30: continue
            rows.append((r["url"], ti + ". " + d, r["domain"], str(r["date"])[:10])); got += 1
            if got >= PER: break
    hb.beat(JOB, progress=f"embedding {len(rows)} articles")
    m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 64
    E = m.encode([r[1] for r in rows], batch_size=128, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
    def _d(s):
        try: return datetime.date.fromisoformat(s[:10]).toordinal()
        except Exception: return -99999
    day = np.array([_d(r[3]) for r in rows]); dom = np.array([r[2] for r in rows]); pairs = []; hb.beat(JOB, progress="searching pairs")
    for s in range(0, len(rows), 1000):
        sim = E[s:s + 1000] @ E.T
        for i in range(sim.shape[0]):
            a = s + i
            for b in np.where(sim[i] >= 0.85)[0]:
                if a < b and dom[a] != dom[b] and abs(day[a] - day[b]) <= 2: pairs.append((a, int(b)))
    nb = collections.Counter()
    for a, b in pairs: nb[a] += 1; nb[b] += 1
    res = {"articles_sampled": len(rows), "per_file": PER, "pairs": len(pairs), "articles_with_1plus_partner": len(nb), "core_ge2": sum(v >= 2 for v in nb.values()), "core_ge6": sum(v >= 6 for v in nb.values()), "seconds": round(time.time() - T0), "rule": "bge-small-en-v1.5 headline+description, cosine >= 0.85, different domain, dates within 2 days, same as triple_pairs.py", "sample": "random rows per parquet file, seed 90, not excluding labelled items"}
    json.dump(res, open(OUT / "t90_pairs.json", "w"), indent=1); json.dump([[rows[a][0], rows[b][0]] for a, b in pairs], open(OUT / "pairs_ids.json", "w"))
    (hb.drop(JOB) if JOB.endswith("smoke") else hb.finish(JOB, "done", progress=f"{res['core_ge2']} core articles", last="finished")); print(json.dumps(res))
except BaseException as e:
    hb.finish(JOB, "failed", last=f"{type(e).__name__}: {str(e)[:100]}"); raise
