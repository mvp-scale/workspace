"""T37 narrow definition test (L886): one vs rest heads per condition kind on the v6b-student embedding, trained on Sonnet labelled pool_train items, scored once on devq.
    /workspace/models/embed-zs/.venv/bin/python perkind_condition_probe.py   (from projects/world-state)"""
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
dq = [r["id"] for r in J("runs/pulse/devq_items.jsonl") if r["id"] in S]; dqs = set(dq)
tr = sorted(i for i in S if i in pool and i not in dqs); print("train", len(tr), "devq", len(dq))
t0 = time.time(); Etr = np.array([emb(pool[i]) for i in tr], dtype=np.float32); Edq = np.array([emb(pool[i]) for i in dq], dtype=np.float32); print("embedded", round(time.time() - t0), "s")
both = [i for i in S if i in H]; kinds = {}
for k in sorted({k for i in both for k in S[i] | H[i]}):
    s = sum(1 for i in both if k in S[i]); h = sum(1 for i in both if k in H[i]); a = sum(1 for i in both if k in S[i] and k in H[i])
    f1 = 2 * a / (s + h) if s + h else 0
    if s >= 30 and f1 >= 0.6: kinds[k] = round(f1, 3)
print("kinds", len(kinds))
rng = np.random.RandomState(0); perm = rng.permutation(len(tr)); cut = int(0.8 * len(tr)); fit, hold = perm[:cut], perm[cut:]
res = {}; passed = 0
for k, ceil in kinds.items():
    y = np.array([int(k in S[i]) for i in tr]); yd = np.array([int(k in S[i]) for i in dq])
    m = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(Etr[fit], y[fit]); ph = m.predict_proba(Etr[hold])[:, 1]
    best, thr = 0, 0.5
    for t in np.linspace(0.1, 0.95, 35):
        p = ph >= t; tp = int((p & (y[hold] == 1)).sum()); f = 2 * tp / max(int(p.sum()) + int(y[hold].sum()), 1)
        if f > best: best, thr = f, float(t)
    pd = m.predict_proba(Edq)[:, 1]; p = pd >= thr; tp = int((p & (yd == 1)).sum()); P = int(p.sum()); N = int(yd.sum())
    f1 = 2 * tp / max(P + N, 1); auc = roc_auc_score(yd, pd) if 0 < N < len(yd) else None
    ok = bool(auc is not None and auc >= 0.90 and f1 >= 0.50); passed += ok
    res[k] = {"labeller_f1_ceiling": ceil, "train_pos": int(y.sum()), "devq_pos": N, "threshold": round(thr, 2), "devq_auc": round(auc, 3) if auc else None, "devq_f1": round(f1, 3), "precision": round(tp / max(P, 1), 3), "recall": round(tp / max(N, 1), 3), "pass": ok}
    print(k, res[k])
json.dump({"kinds_tested": len(kinds), "kinds_passed": passed, "per_kind": res}, open("runs/pulse/perkind_condition_probe.json", "w"), indent=1); print("PASSED", passed, "of", len(kinds))
