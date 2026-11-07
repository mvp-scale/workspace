"""T37 cross labeller test (L893): heads trained on HAIKU labels of items Sonnet did not label, scored against SONNET labels on items both labelled.
    /workspace/models/embed-zs/.venv/bin/python perkind_cross.py   (from projects/world-state)"""
import json, re, time, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
S, H = {}, {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = set(r["kinds"])
    if r["family"] == "haiku": H.setdefault(r["item_id"], set()).update(r["kinds"])
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
train = sorted(i for i in H if i in pool and i not in S); test = sorted(i for i in S if i in H and i in pool); print("train (Haiku only items)", len(train), "test (both)", len(test))
t0 = time.time(); Etr = np.array([emb(pool[i]) for i in train], dtype=np.float32); Ete = np.array([emb(pool[i]) for i in test], dtype=np.float32); print("embedded", round(time.time() - t0), "s")
kinds = {}
for k in sorted({k for i in test for k in S[i] | H[i]}):
    s = sum(1 for i in test if k in S[i]); h = sum(1 for i in test if k in H[i]); a = sum(1 for i in test if k in S[i] and k in H[i]); f1 = 2 * a / (s + h) if s + h else 0
    if s >= 30 and f1 >= 0.6: kinds[k] = round(f1, 3)
perm = np.random.RandomState(0).permutation(len(train)); c = int(0.8 * len(train)); fit, hold = perm[:c], perm[c:]
res = {}; passed = 0
for k, ceil in kinds.items():
    y = np.array([int(k in H[i]) for i in train]); yt = np.array([int(k in S[i]) for i in test])
    m = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(Etr[fit], y[fit]); ph = m.predict_proba(Etr[hold])[:, 1]; best, thr = 0, 0.5
    for t in np.linspace(0.1, 0.95, 35):
        p = ph >= t; f = 2 * int((p & (y[hold] == 1)).sum()) / max(int(p.sum()) + int(y[hold].sum()), 1)
        if f > best: best, thr = f, float(t)
    pt = m.predict_proba(Ete)[:, 1]; pr = pt >= thr; tp = int((pr & (yt == 1)).sum()); f1 = 2 * tp / max(int(pr.sum()) + int(yt.sum()), 1); auc = roc_auc_score(yt, pt)
    bs = np.random.RandomState(4); FB = []
    for _ in range(200):
        ix = bs.randint(0, len(yt), len(yt)); q = pr[ix]; FB.append(2 * int((q & (yt[ix] == 1)).sum()) / max(int(q.sum()) + int(yt[ix].sum()), 1))
    ok = bool(f1 >= ceil - 0.05); passed += ok
    res[k] = {"labeller_f1_ceiling": ceil, "train_pos": int(y.sum()), "test_pos": int(yt.sum()), "threshold": round(thr, 2), "f1_vs_sonnet": round(f1, 3), "f1_range": [round(float(np.percentile(FB, 2.5)), 3), round(float(np.percentile(FB, 97.5)), 3)], "auc_vs_sonnet": round(auc, 3), "precision": round(tp / max(int(pr.sum()), 1), 3), "recall": round(tp / max(int(yt.sum()), 1), 3), "pass": ok}
    print(k, res[k])
json.dump({"kinds_tested": len(kinds), "kinds_passed": passed, "per_kind": res}, open("runs/pulse/perkind_cross.json", "w"), indent=1); print("PASSED", passed, "of", len(kinds))
