"""Whole-article test of the context window (L373 prediction): can a passage from the early / middle / late part of a long article find its source article, by frozen-embedding cosine?
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python long_context_test.py      local GPU a few minutes, no hosted calls; reads the local news queue (publisher text: stays local, never printed or published)
Strategies: bge-small truncated 512; bge-small chunked (300-word windows, stride 225) mean and best-chunk; Granite small R2 truncated 512; Granite small R2 whole article (up to 8k)."""
import os, re, json, sqlite3, random, time, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = db.execute("select id, title, body from items where length(coalesce(body,'')) > 3500 and length(body) < 14000").fetchall(); random.Random(0).shuffle(rows)
seen = set(); arts = []
for i, t, b in rows:
    k = re.sub(r"\W+", " ", (t or "").lower())[:60]
    if k in seen: continue
    seen.add(k); b = re.sub(r"\s+", " ", b).strip(); sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", b)
    if len(sents) < 12: continue
    arts.append({"id": i, "title": t or "", "body": b, "sents": sents})
    if len(arts) == 1500: break
print("articles", len(arts), flush=True)
def passage(a, lo, hi, rnd):
    s = a["sents"]; n = len(s); k = int(rnd.uniform(lo, hi) * (n - 2)); k = max(0, min(k, n - 2)); return (s[k] + " " + s[k + 1]).strip()
rnd = random.Random(1); Q = {"early": [], "middle": [], "late": []}
for a in arts:
    for nm, (lo, hi) in (("early", (0.0, 0.15)), ("middle", (0.45, 0.55)), ("late", (0.80, 0.95))): Q[nm].append(passage(a, lo, hi, rnd))
full = [(a["title"] + ". " + a["body"]) for a in arts]
def windows(t, w=300, st=225):
    ws = t.split(); out = []; i = 0
    while True:
        out.append(" ".join(ws[i:i + w]))
        if i + w >= len(ws): break
        i += st
    return out
def recall(S, true=None):
    r1 = float(np.mean(S.argmax(1) == np.arange(S.shape[0]))); top5 = np.argsort(-S, 1)[:, :5]; r5 = float(np.mean([k in top5[k] for k in range(S.shape[0])])); return {"r@1": round(r1, 3), "r@5": round(r5, 3)}
res = {}; dev = "cuda"
def enc(st, texts, bs): return st.encode(texts, batch_size=bs, normalize_embeddings=True, show_progress_bar=False, convert_to_tensor=True, device=dev)
for name, rid in [(n, r) for n, r in (("bge-small", "BAAI/bge-small-en-v1.5"), ("granite-small-r2", "ibm-granite/granite-embedding-small-english-r2"), ("mdbr-leaf-mt", "MongoDB/mdbr-leaf-mt")) if not os.environ.get("ONLY") or n in os.environ["ONLY"].split(",")]:
    st = SentenceTransformer(rid, device=dev, model_kwargs={"dtype": torch.float32}); t0 = time.time(); qe = {}
    st.max_seq_length = 512; qe = {nm: enc(st, qs, 128) for nm, qs in Q.items()}
    strat = {}
    st.max_seq_length = 512; strat[f"{name} truncated 512"] = enc(st, full, 32)
    if name in ("bge-small", "mdbr-leaf-mt"):
        W = [windows(t) for t in full]; flat = [w for ws in W for w in ws]; E = enc(st, flat, 128); idx = np.cumsum([0] + [len(ws) for ws in W]); print("bge windows", len(flat), flush=True)
        mean = torch.stack([torch.nn.functional.normalize(E[idx[k]:idx[k + 1]].mean(0), dim=0) for k in range(len(W))]); strat["bge-small chunked, mean vector"] = mean
        strat["bge-small chunked, best chunk"] = (E, idx)
    else:
        st.max_seq_length = 8192; strat["granite-small-r2 whole article (8k)"] = enc(st, full, 4)
    for sn, V in strat.items():
        res[sn] = {}
        for nm in Q:
            if isinstance(V, tuple):
                E, idx = V; sims = qe[nm] @ E.T; S = torch.stack([sims[:, idx[k]:idx[k + 1]].max(1).values for k in range(len(idx) - 1)], 1)
            else: S = qe[nm] @ V.T
            res[sn][nm] = recall(S.cpu().numpy())
        print(sn, res[sn], flush=True)
    print(name, f"{time.time() - t0:.0f}s", flush=True); del st; torch.cuda.empty_cache()
import statistics; toks = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu").tokenizer; L = [len(toks(t, truncation=False)["input_ids"]) for t in full[:300]]
res["_meta"] = {"n_articles": len(arts), "tokens_median": int(statistics.median(L)), "tokens_p90": int(np.percentile(L, 90)), "share_over_512_tokens": round(float(np.mean([x > 512 for x in L])), 3)}; print(res["_meta"])
json.dump(res, open(os.environ.get("OUT", "runs/snapshots/long_context_test.json"), "w"), indent=1)
