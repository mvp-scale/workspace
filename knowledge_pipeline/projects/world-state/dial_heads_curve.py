"""T35 learning curve (pre-registered after L923): same all-dial heads as dial_heads_cv.py, trained on 25, 50, 100 percent of each training fold (V1 embedding: title+text, 64 tokens), plus V2 (title + first 3 chunks of 62 tokens, embeddings averaged) at 100 percent. Same 5 folds, scored on the same held-out folds against Clef readings.
    /workspace/models/embed-zs/.venv/bin/python dial_heads_curve.py   (from projects/world-state)"""
import json, re, time, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
run = lambda ids: sess.run(None, {"input_ids": np.array([ids], dtype=np.int64), "attention_mask": np.ones((1, len(ids)), dtype=np.int64)})[0][0]
def emb1(t):
    tk.enable_truncation(max_length=64); return run(tk.encode(re.sub(r"\s+", " ", t)[:1200]).ids)
def emb2(title, body):
    tk.no_truncation(); ids = tk.encode(re.sub(r"\s+", " ", title + ". " + body)[:6000]).ids; a, z, mid = ids[0], ids[-1], ids[1:-1]
    ch = [mid[i:i + 62] for i in range(0, min(len(mid), 62 * 3), 62)] or [[]]
    return np.mean([run([a] + c + [z]) for c in ch], axis=0)
A = J("/workspace/data/newsreader/labels/clef-q4km.jsonl")
K = lambda r: {(x["dial"], x["direction"]) for x in r["readings"] if x["direction"] != "conflict"}
t0 = time.time(); E1 = np.array([emb1(r["title"] + ". " + r["text"][:1100]) for r in A], dtype=np.float32); E2 = np.array([emb2(r["title"], r["text"]) for r in A], dtype=np.float32); print("embedded", round(time.time() - t0), "s", flush=True)
keys = sorted({k for r in A for k in K(r)}); hk = [k for k in keys if sum(1 for r in A if k in K(r)) >= 8]
Y = np.array([[int(k in K(r)) for k in hk] for r in A]); N = len(A); allk = sum(len(K(r)) for r in A); negs = N * len(keys) - allk; Kset = [K(r) for r in A]
def score(S):
    o = np.sort(S[Y == 0])[::-1]; th = o[max(int(0.002 * negs) - 1, 0)]; P = S > th; tp = int((P & (Y == 1)).sum())
    js = []
    for i in range(N):
        p = {hk[j] for j in np.where(P[i])[0]}; u = p | Kset[i]; js.append(len(p & Kset[i]) / len(u) if u else 1.0)
    return {"tpr_at_fpr_0.002": round(tp / allk, 3), "jaccard": round(float(np.mean(js)), 3)}
out = {}
for name, E, frac in (("V1_25", E1, .25), ("V1_50", E1, .5), ("V1_100", E1, 1.0), ("V2_100", E2, 1.0)):
    S = np.zeros(Y.shape); rs = np.random.RandomState(7)
    for a, b in KFold(5, shuffle=True, random_state=0).split(E):
        a = rs.permutation(a)[: int(len(a) * frac)]
        for j in range(len(hk)):
            if Y[a, j].sum() < 2: continue
            S[b, j] = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(E[a], Y[a, j]).predict_proba(E[b])[:, 1]
    out[name] = score(S); print(name, out[name], flush=True)
json.dump(out, open("runs/pulse/dial_heads_curve.json", "w"), indent=1)
