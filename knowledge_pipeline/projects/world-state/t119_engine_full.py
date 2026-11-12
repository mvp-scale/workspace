"""T119: heads trained on the engine's own Clef readings only, full-text view (title plus first 1200 words), grouped 5-fold over the 1736 engine stories. Two rows on the same folds: word and character counts, and the same plus a bge-small embedding of the first 64 word pieces of headline plus teaser and of the mean of 250-word chunks.
    FOLDS=5 OUT=<folder> /workspace/models/embed-zs/.venv/bin/python t119_engine_full.py -> <OUT>/t119_engine_full.json"""
import os, json, re, collections, pathlib, time, zlib
import numpy as np, torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack, csr_matrix
from sentence_transformers import SentenceTransformer
torch.set_num_threads(int(os.environ.get("THREADS", 12)))
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t119")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); K = int(os.environ.get("FOLDS", 5)); LIM = int(os.environ.get("LIMIT", 0))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
E = list(eng.values())[: LIM or None]
def body(r):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); return re.sub(r"^Published\s*", "", b)
full = [(r["title"].strip() + " " + " ".join(body(r).split()[:1200])).strip() for r in E]
sh = [(r["title"].strip() + ". " + " ".join(re.split(r"(?<=[.!?])\s+", body(r))[:2])).strip() for r in E]
ch = [[" ".join(w[a:a + 250]) for a in range(0, max(len(w), 1), 250)][:5] for w in (body(r).split() for r in E)]
ep = np.array([1 if r.get("readings") else 0 for r in E]); ed = {}
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): ed[k] = 1 if w["up"] > w["down"] else 0
M = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); M.max_seq_length = 64
Es = M.encode(sh, batch_size=64, normalize_embeddings=True); Ec = np.vstack([M.encode(c, batch_size=64, normalize_embeddings=True).mean(0, keepdims=True) for c in ch]); EMB = np.hstack([Es, Ec])
fold = np.array([zlib.crc32(nk(r["title"]).encode()) % K for r in E])
out = {m: {"p": np.zeros(len(E)), "d": np.full(len(E), np.nan)} for m in ("counts", "counts_plus_embedding")}
for f in range(K):
    tr = [i for i in range(len(E)) if fold[i] != f]; te = [i for i in range(len(E)) if fold[i] == f]; trd = [i for i in tr if i in ed]; pos = {i: j for j, i in enumerate(tr)}
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000)
    Xa = hstack([w.fit_transform([full[i] for i in tr]), c.fit_transform([full[i] for i in tr])]).tocsr(); Xe = hstack([w.transform([full[i] for i in te]), c.transform([full[i] for i in te])]).tocsr()
    for m in out:
        A, B = (Xa, Xe) if m == "counts" else (hstack([Xa, csr_matrix(EMB[tr])]).tocsr(), hstack([Xe, csr_matrix(EMB[te])]).tocsr())
        out[m]["p"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(A, ep[tr]).predict_proba(B)[:, 1]
        out[m]["d"][te] = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(A[[pos[i] for i in trd]], [ed[i] for i in trd]).predict_proba(B)[:, 1]
    print("fold", f, round(time.time() - T0), flush=True)
ke = sorted(ed); yd = np.array([ed[k] for k in ke]); res = {"engine_stories": len(E), "folds": K, "direction_stories": len(ke), "direction_majority": round(float(max(yd.mean(), 1 - yd.mean())), 4)}
for m in out: res[m] = {"presence_auroc": round(float(roc_auc_score(ep, out[m]["p"])), 4), "direction_auroc": round(float(roc_auc_score(yd, out[m]["d"][ke])), 4), "direction_accuracy": round(float(((out[m]["d"][ke] >= 0.5) == yd).mean()), 4)}
res["note"] = "Grouped cross-validation over the engine stories; reference is Clef's stored reading (agreement, not accuracy). Compare T105 full view: presence AUROC 0.856, direction accuracy 0.740; bars 0.87 and 0.76."
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t119_engine_full.json", "w"), indent=1); print(json.dumps(res, indent=1))
