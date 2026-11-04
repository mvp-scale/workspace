"""T21 round 7: can a head on frozen embeddings, trained on the 5,985 new Sonnet v3b pool labels, predict condition presence like Sonnet? Scored on the 601 devq items against Sonnet v3b (a601, b601). Alpha bar 0.754 (0.80 x 0.943, ledger L627). HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -I presence_probe.py"""
import os, json, glob, numpy as np
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
J = lambda p: [json.loads(l) for l in open(p)]
pool = {}
for r in J("data/pool.jsonl"): pool.setdefault(r["id"], r["text"])
tr = {r["item_id"]: bool(r["label"]["conditions"]) for f in glob.glob("runs/pulse/sonnet_pool6k/part*/labels.jsonl") for r in J(f)}
it = {r["id"]: r["text"] for r in J("runs/pulse/ceiling_sonnet/items601.jsonl")}
A = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/a601/labels.jsonl")}; B = {r["item_id"]: bool(r["label"]["conditions"]) for r in J("runs/pulse/ceiling_sonnet/b601/labels.jsonl")}
ev = sorted(i for i in it if i in A and i in B); tri = sorted(i for i in tr if i in pool and i not in it)
def alpha(a, b):
    a = np.array(a, int); b = np.array(b, int); n = len(a); do = (a != b).mean(); N = 2 * n; c1 = a.sum() + b.sum(); c0 = N - c1; de = (N * N - c1 * c1 - c0 * c0) / (N * (N - 1)); return 1 - do / de
print("train", len(tri), "pos", sum(tr[i] for i in tri), "eval", len(ev), "pos", sum(A[i] for i in ev), flush=True)
ya = [A[i] for i in ev]; yb = [B[i] for i in ev]; print("sonnet a vs b alpha", round(alpha(ya, yb), 3))
for name in os.environ.get("PP_MODELS", "MongoDB/mdbr-leaf-mt,BAAI/bge-base-en-v1.5").split(","):
    m = SentenceTransformer(name, device="cuda", model_kwargs={"torch_dtype": "bfloat16"}); m.max_seq_length = 128
    X = m.encode([pool[i] for i in tri], batch_size=32, normalize_embeddings=True); Xe = m.encode([it[i] for i in ev], batch_size=128, normalize_embeddings=True); y = np.array([tr[i] for i in tri], int)
    for C in (1, 10):
        clf = LogisticRegression(C=C, max_iter=500, class_weight="balanced").fit(X, y); p = clf.predict_proba(Xe)[:, 1]
        for t in (0.5, 0.7):
            pr = p >= t; print(name.split("/")[1], "C", C, "thr", t, "alpha vs A", round(alpha(pr, ya), 3), "vs B", round(alpha(pr, yb), 3), "disagree A", round(float((pr != np.array(ya)).mean()), 3), "pred yes", int(pr.sum()), flush=True)
