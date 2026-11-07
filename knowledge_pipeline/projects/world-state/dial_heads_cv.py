"""T35 engine-level test (plan of 2026-11-05): one head per Clef (dial, direction) key on v6b-student embeddings, trained and scored against CLEF's own readings (the engine's real input) on 1736 Clef-read stories, 5 fold CV by story. Metrics on the engine's terms: pooled key TPR and FPR (F-0020 tolerance: TPR .9 at FPR .001, or .95 at .0025) and mean keys_jaccard per story (shadow_run). Keys with fewer than MINPOS positives get no head (counted as misses).
    /workspace/models/embed-zs/.venv/bin/python dial_heads_cv.py   (from projects/world-state)"""
import json, re, time, sys, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
MINPOS = 8
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
A = J("/workspace/data/newsreader/labels/clef-q4km.jsonl")
K = lambda r: {(x["dial"], x["direction"]) for x in r["readings"] if x["direction"] != "conflict"}
t0 = time.time(); E = np.array([emb(r["title"] + ". " + r["text"][:1100]) for r in A], dtype=np.float32); print("embedded", len(A), round(time.time() - t0), "s", flush=True)
keys = sorted({k for r in A for k in K(r)}); pos = {k: sum(1 for r in A if k in K(r)) for k in keys}; head_keys = [k for k in keys if pos[k] >= MINPOS]
Y = np.array([[int(k in K(r)) for k in head_keys] for r in A]); print("keys", len(keys), "with head", len(head_keys), flush=True)
S = np.zeros(Y.shape)
for a, b in KFold(5, shuffle=True, random_state=0).split(E):
    for j in range(len(head_keys)):
        S[b, j] = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(E[a], Y[a, j]).predict_proba(E[b])[:, 1]
N = len(A); allkeys = sum(len(K(r)) for r in A); true_in_heads = int(Y.sum()); universe = N * len(keys); negs = universe - allkeys
def at(th):
    P = S >= th; tp = int((P & (Y == 1)).sum()); fp = int((P & (Y == 0)).sum())
    js = [(len({head_keys[j] for j in np.where(P[i])[0]} & K(A[i])) / len({head_keys[j] for j in np.where(P[i])[0]} | K(A[i]))) if (P[i].any() or K(A[i])) else 1.0 for i in range(N)]
    return {"th": round(float(th), 3), "tpr": round(tp / allkeys, 3), "fpr": round(fp / negs, 5), "jaccard": round(float(np.mean(js)), 3), "tp": tp, "fp": fp}
curve = [at(t) for t in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98)]
best = max(curve, key=lambda c: c["jaccard"])
per = {}
for j, k in enumerate(head_keys):
    p = S[:, j] >= best["th"]; tp = int((p & (Y[:, j] == 1)).sum()); per["|".join(k)] = {"pos": int(Y[:, j].sum()), "f1": round(2 * tp / max(int(p.sum()) + int(Y[:, j].sum()), 1), 3)}
res = {"stories": N, "clef_keys": allkeys, "keys_total": len(keys), "keys_with_head": len(head_keys), "ceiling_tpr_from_heads": round(true_in_heads / allkeys, 3), "empty_reader_jaccard": round(float(np.mean([1.0 if not K(r) else 0.0 for r in A])), 3),
       "curve": curve, "best_by_jaccard": best, "f0020_tolerance": {"tpr_0.90_at_fpr_0.001": True, "tpr_0.95_at_fpr_0.0025": True}, "per_key": per}
np.savez("runs/pulse/dial_heads_cv_scores.npz", S=S, Y=Y, ids=np.array([r["id"] for r in A]), keys=np.array(["|".join(k) for k in head_keys]))
json.dump(res, open("runs/pulse/dial_heads_cv.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "per_key"}, indent=1))
