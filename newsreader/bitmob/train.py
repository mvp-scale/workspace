"""Train and test a CPU reader (BitMob method) on Clef's answers. Method and pass bar fixed before looking at results.
Encoder: e5-small int8 (BitMob's runtime, CPU). Story vector: the title plus the article in chunks of ~300 words (up to 4), each encoded, then averaged.
Heads: one logistic regression per question (328), trained on Clef's yes/no (p >= 0.5); no class weighting, so probabilities stay usable by the engine's
own thresholds. Questions with fewer than 3 yes in training get a constant (their training rate).
Test: 20% of stories held out by id (never seen in training). The engine's own read() turns probabilities into readings (condition, direction).
PASS: on held-out stories where Clef moved at least one condition, the CPU reader's readings match Clef's with recall >= 0.85 and precision >= 0.85.
Also reported: per-question agreement, the gate (fact / opinion / recent) agreement, CPU time per story.
Run: WE_RULES=rules_v2 /workspace/models/embed-zs/.venv/bin/python -I train.py   (from /workspace/probes/world-engine)"""
import sys, os, json, time, hashlib, numpy as np
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
import onnxruntime as ort
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
from sklearn.linear_model import LogisticRegression

LAB = "/workspace/data/newsreader/labels/clef-q4km.jsonl"; OUTD = "/workspace/data/newsreader/bitmob"; os.makedirs(OUTD, exist_ok=True)
rows = [json.loads(l) for l in open(LAB)]; QN = sorted(C.QS); print(len(rows), "labelled stories", flush=True)
tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); tok.enable_truncation(512)
o = ort.SessionOptions(); o.intra_op_num_threads = 8; o.inter_op_num_threads = 1
sess = ort.InferenceSession("/workspace/data/embed-zs/engine/e5.int8.onnx", o, providers=["CPUExecutionProvider"])

def enc(texts):
    out = []
    for i in range(0, len(texts), 32):
        e = tok.encode_batch(["query: " + t for t in texts[i:i + 32]]); L = max(len(x.ids) for x in e)
        ids = np.array([x.ids + [0] * (L - len(x.ids)) for x in e], np.int64); m = np.array([x.attention_mask + [0] * (L - len(x.ids)) for x in e], np.int64)
        h = sess.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0]
        v = (h * m[..., None]).sum(1) / m.sum(1, keepdims=True); out.append(v / np.linalg.norm(v, axis=1, keepdims=True))
    return np.concatenate(out)

def story_vec(r, chunks=4, words=300):
    w = r["text"].split(); parts = [r["title"] + ". " + " ".join(w[i:i + words]) for i in range(0, max(1, len(w)), words)][:chunks]
    return parts

def vectors(rs, chunks):
    parts, owner = [], []
    for k, r in enumerate(rs):
        p = story_vec(r, chunks); parts += p; owner += [k] * len(p)
    t = time.perf_counter(); V = enc(parts); ms = (time.perf_counter() - t) * 1000 / len(rs)
    owner = np.array(owner); X = np.stack([V[owner == k].mean(0) for k in range(len(rs))]); return X / np.linalg.norm(X, axis=1, keepdims=True), ms

test = [r for r in rows if int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 5 == 0]; train = [r for r in rows if r not in test]
key = lambda rd: {(x["dial"], x["direction"]) for x in rd if x["direction"] != "conflict"}
results = {}
CONFIGS = [(1, 1.0), (4, 0.5), (4, 1.0)]          # (chunks, share of the training stories): the 0.5 vs 1.0 pair is the learning curve
for chunks, frac in CONFIGS:
    tr_ = train[:max(10, int(len(train) * frac))]
    Xtr, _ = vectors(tr_, chunks); Xte, ms = vectors(test, chunks)
    Ytr = np.array([[r["P"][q] >= 0.5 for q in QN] for r in tr_]); Yte = np.array([[r["P"][q] >= 0.5 for q in QN] for r in test])
    Phat = np.zeros((len(test), len(QN))); heads = {}
    for j, q in enumerate(QN):
        if Ytr[:, j].sum() < 3 or Ytr[:, j].sum() > len(tr_) - 3: Phat[:, j] = Ytr[:, j].mean(); heads[q] = float(Ytr[:, j].mean()); continue
        m = LogisticRegression(C=2.0, max_iter=3000).fit(Xtr, Ytr[:, j]); Phat[:, j] = m.predict_proba(Xte)[:, 1]; heads[q] = (m.coef_[0], float(m.intercept_[0]))
    agree = ((Phat >= 0.5) == Yte).mean(0)
    rec, pre, gate_ok, n = [], [], 0, 0
    for k, r in enumerate(test):
        mine = C.read({q: float(Phat[k, j]) for j, q in enumerate(QN)}); a, b = key(mine["readings"]), key(r["readings"]); gate_ok += mine["gate_ok"] == r["gate_ok"]
        if b: n += 1; rec.append(len(a & b) / len(b)); pre.append(len(a & b) / len(a) if a else 0.0)
    R, Pp = float(np.mean(rec)), float(np.mean(pre))
    results[f"chunks{chunks}_train{len(tr_)}"] = {"train": len(tr_), "test": len(test), "stories_scored": n, "recall": round(R, 3), "precision": round(Pp, 3), "gate_agree": round(gate_ok / len(test), 3),
                       "question_agree_mean": round(float(agree.mean()), 3), "questions_ge_97": int((agree >= .97).sum()), "questions_ge_90": int((agree >= .90).sum()), "cpu_ms_per_story": round(ms, 1),
                       "PASS": R >= .85 and Pp >= .85}
    print(f"chunks={chunks} train={len(tr_)}: {results[f'chunks{chunks}_train{len(tr_)}']}", flush=True)
    if chunks == 4 and frac == 1.0: np.save(f"{OUTD}/agree_per_question.npy", agree); json.dump({q: round(float(a), 3) for q, a in zip(QN, agree)}, open(f"{OUTD}/agree_per_question.json", "w"), indent=0)
json.dump(results, open(f"{OUTD}/results.json", "w"), indent=1)
