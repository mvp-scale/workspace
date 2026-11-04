"""B2 (ledger T16, prediction L403): leave-one-kind-out news-vs-other router, sparse words+chars vs leaf vector, logistic regression. Local, CPU. Text stays local; only numbers are written.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python router_test.py"""
import os, re, json, glob, time, random, sqlite3, numpy as np, scipy.sparse as sp, pyarrow.parquet as pq
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
R = random.Random(7)
def paras(text):
    out = []
    for b in re.split(r"\n\s*\n", text):
        b = re.sub(r"\s+", " ", re.sub(r"[`*#|>_]+", " ", b)).strip()
        if 120 <= len(b) <= 600 and sum(c.isalpha() or c == " " for c in b) / len(b) > 0.85: out.append(b)
    return out
pool = [json.loads(l) for l in open("data/pool_train.jsonl")]; R.shuffle(pool); short = [re.sub(r"\s+", " ", r["text"]) for r in pool[:1000]]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); body = [b for (b,) in db.execute("select body from items where length(coalesce(body,'')) > 3500 limit 4000")]; R.shuffle(body)
art = [p for b in body[:600] for p in paras(b)[3:5]][:300]; news = short + art
kinds = {}
rd = []
for f in glob.glob("/workspace/models/embed-zs/.venv/lib/python3*/site-packages/*/METADATA") + glob.glob("/workspace/kev/.venv/lib/python3*/site-packages/*/METADATA"): rd += paras(open(f, encoding="utf-8", errors="ignore").read().split("\n\n", 1)[-1])
rd = list(dict.fromkeys(rd)); R.shuffle(rd); kinds["readme"] = rd[:1200]
t = pq.read_table(next(iter(glob.glob("/workspace/data/hf/hub/datasets--cais--mmlu/snapshots/*/all/test-*.parquet")))).to_pandas(); q = [re.sub(r"\s+", " ", x) for x in t["question"] if 60 <= len(x) <= 600]; R.shuffle(q); kinds["mmlu"] = q[:1000]
docs = []
for f in glob.glob("/workspace/knowledge_pipeline/playbook/*.md") + glob.glob("/workspace/*.md") + glob.glob("specs/*.md"): docs += paras(open(f, encoding="utf-8", errors="ignore").read())
led = [re.sub(r"\s+", " ", json.loads(l).get("text", ""))[:600] for l in open("../../.ledger/ledger.jsonl")]; led = [x for x in led if len(x) >= 120]
mine = list(dict.fromkeys(docs + led)); R.shuffle(mine); kinds["our_notes"] = mine[:1000]
print({"news": len(news), **{k: len(v) for k, v in kinds.items()}}, flush=True)
enc = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cpu"); enc.max_seq_length = 128
allt = news + [x for v in kinds.values() for x in v]; kind = np.array(["news"] * len(news) + [k for k, v in kinds.items() for _ in v]); y = (kind == "news").astype(int)
t0 = time.time(); E = enc.encode(allt, batch_size=64, normalize_embeddings=True, show_progress_bar=False); enc_ms = (time.time() - t0) * 1000 / len(allt); print("leaf encode ms/item", round(enc_ms, 1), flush=True)
def feats(name, tr, te):
    if name == "leaf": return E[tr], E[te], None
    vw = TfidfVectorizer(min_df=2, sublinear_tf=True, ngram_range=(1, 2), max_features=60000); vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=60000)
    A = [allt[i] for i in tr]; B = [allt[i] for i in te]; return sp.hstack([vw.fit_transform(A), vc.fit_transform(A)]).tocsr(), sp.hstack([vw.transform(B), vc.transform(B)]).tocsr(), None
idx = np.arange(len(allt)); nid = idx[y == 1]; R2 = np.random.default_rng(1); R2.shuffle(nid); held = set(nid[: len(nid) // 5].tolist()); res = {"n": {"news": len(news), **{k: len(v) for k, v in kinds.items()}}, "leaf_encode_ms_per_item": round(enc_ms, 2), "leave_one_kind_out": {}, "within_kind_auc": {}}
for name in ("sparse", "leaf"):
    res["leave_one_kind_out"][name] = {}
    for k in kinds:
        te = np.array([i for i in idx if (kind[i] == k) or (i in held)]); tr = np.array([i for i in idx if i not in set(te.tolist())])
        t1 = time.time(); Xtr, Xte, _ = feats(name, tr, te); clf = LogisticRegression(C=3, max_iter=1000, class_weight="balanced").fit(Xtr, y[tr])
        ptr = clf.predict_proba(Xtr)[:, 1]; thr = float(np.percentile(ptr[y[tr] == 1], 1)); pte = clf.predict_proba(Xte)[:, 1]; yt = y[te]
        t2 = time.time(); clf.predict_proba(Xte[:200]); ms = (time.time() - t2) * 1000 / 200
        res["leave_one_kind_out"][name][k] = {"auc": round(float(roc_auc_score(yt, pte)), 4), "news_kept": round(float((pte[yt == 1] >= thr).mean()), 3), "other_stopped": round(float((pte[yt == 0] < thr).mean()), 3), "head_ms_per_item": round(ms, 3)}
        print(name, k, res["leave_one_kind_out"][name][k], flush=True)
    sk = StratifiedKFold(5, shuffle=True, random_state=0); st = np.array([f"{kind[i]}" for i in idx]); aucs = []
    for a, b in sk.split(idx, st):
        Xa, Xb, _ = feats(name, a, b); c = LogisticRegression(C=3, max_iter=1000, class_weight="balanced").fit(Xa, y[a]); aucs.append(roc_auc_score(y[b], c.predict_proba(Xb)[:, 1]))
    res["within_kind_auc"][name] = round(float(np.mean(aucs)), 4)
os.makedirs("runs/snapshots", exist_ok=True); json.dump(res, open("runs/snapshots/router_test.json", "w"), indent=1); print(json.dumps(res["within_kind_auc"]))
