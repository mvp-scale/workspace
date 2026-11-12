"""T95 step 2: same-event pairs over the whole embedded pool, by date window instead of all against all. Same rule as T90: cosine >= 0.85, different domain, dates within 2 days. Articles are grouped by day; each day is compared with itself and the next two days.
    OUT=<folder with emb_*.npy, meta_*.jsonl> /workspace/models/embed-zs/.venv/bin/python -u t95_pairs.py -> <OUT>/t95_pairs.json (counts), <OUT>/pairs_idx.npy (int32 pairs of row numbers in the order of the meta files), <OUT>/pool_meta.jsonl"""
import os, sys, json, glob, time, pathlib, datetime, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
sys.path.insert(0, "/workspace/knowledge_pipeline/kit/live"); import heartbeat as hb
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t95")); T0 = time.time(); torch.set_num_threads(18); JOB = "t95-pairs" + ("-smoke" if os.environ.get("SMOKE") else "")
hb.beat(JOB, state="running", where="[CPU]", alive_pid=os.getpid(), every_s=180, why="Find same-event pairs over the whole embedded CC-News pool by date window (T95)", success="t95_pairs.json and pairs_idx.npy written", progress="loading")
try:
    ids = sorted(int(p.name[4:-4]) for p in OUT.glob("emb_*.npy")); E = np.vstack([np.load(OUT / f"emb_{i}.npy") for i in ids]); meta = []
    for i in ids: meta += [json.loads(l) for l in open(OUT / f"meta_{i}.jsonl")]
    assert len(meta) == len(E); day = np.array([datetime.date.fromisoformat(m["date"]).toordinal() for m in meta]); dom = np.array([m["domain"] for m in meta])
    by = collections.defaultdict(list)
    for k, d in enumerate(day): by[int(d)].append(k)
    Et = torch.from_numpy(E.astype(np.float32)); pairs = []; days = sorted(by); n = 0
    for d in days:
        A = np.array(by[d]); B = np.array(by[d] + by.get(d + 1, []) + by.get(d + 2, [])); EB = Et[B]
        for s in range(0, len(A), 2000):
            ia = A[s:s + 2000]; sim = (Et[ia] @ EB.T).numpy(); r, c = np.where(sim >= 0.85)
            a = ia[r]; b = B[c]; keep = (a != b) & (dom[a] != dom[b]); pairs.append(np.sort(np.stack([a[keep], b[keep]], 1), axis=1).astype(np.int32))  # rows are not date-ordered: a pair is found from its earlier day only, so no a < b test; sorted and made unique below
        n += 1
        if n % 20 == 0: hb.beat(JOB, progress=f"day {n} of {len(days)}")
    P = np.vstack(pairs) if pairs else np.zeros((0, 2), np.int32); P = np.unique(P, axis=0); np.save(OUT / "pairs_idx.npy", P)
    nb = np.bincount(P.ravel(), minlength=len(meta))
    with open(OUT / "pool_meta.jsonl", "w") as w:
        for m in meta: w.write(json.dumps(m) + "\n")
    res = {"articles": len(meta), "days": len(days), "pairs": int(len(P)), "articles_with_1plus_partner": int((nb >= 1).sum()), "core_ge2": int((nb >= 2).sum()), "core_ge6": int((nb >= 6).sum()), "seconds": round(time.time() - T0), "rule": "bge-small-en-v1.5 headline+description, cosine >= 0.85, different domain, dates within 2 days (day window), as T90"}
    json.dump(res, open(OUT / "t95_pairs.json", "w"), indent=1); (hb.drop(JOB) if os.environ.get("SMOKE") else hb.finish(JOB, "done", progress=f"{res['core_ge2']} core articles", last="finished")); print(json.dumps(res))
except BaseException as e:
    hb.finish(JOB, "failed", last=f"{type(e).__name__}: {str(e)[:100]}"); raise
