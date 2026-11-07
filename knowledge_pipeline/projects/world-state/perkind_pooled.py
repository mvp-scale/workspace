"""T37 pooled labeller heads (pre-registered at the ledger line after L903): train on both labellers, test on a held-out part of the items both labelled, score against Sonnet and Haiku separately.
    /workspace/models/embed-zs/.venv/bin/python perkind_pooled.py   (from projects/world-state)"""
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
ids = sorted(i for i in set(S) | set(H) if i in pool); both = [i for i in ids if i in S and i in H]
rng = np.random.RandomState(0); bperm = rng.permutation(len(both)); test = [both[k] for k in bperm[: int(0.3 * len(both))]]; tset = set(test)
train = [i for i in ids if i not in tset]; print("train items", len(train), "test items", len(test))
t0 = time.time(); E = {i: emb(pool[i]) for i in train + test}; print("embedded", round(time.time() - t0), "s")
Etr = np.array([E[i] for i in train], dtype=np.float32); Ete = np.array([E[i] for i in test], dtype=np.float32)
w = np.array([0.5 if (i in S and i in H) else 1.0 for i in train])
kinds = {}
for k in sorted({k for i in both for k in S[i] | H[i]}):
    s = sum(1 for i in both if k in S[i]); h = sum(1 for i in both if k in H[i]); a = sum(1 for i in both if k in S[i] and k in H[i]); f1 = 2 * a / (s + h) if s + h else 0
    if s >= 30 and f1 >= 0.6: kinds[k] = round(f1, 3)
perm = np.random.RandomState(1).permutation(len(train)); c = int(0.8 * len(train)); fit, hold = perm[:c], perm[c:]
f1f = lambda pr, y: 2 * int((pr & (y == 1)).sum()) / max(int(pr.sum()) + int(y.sum()), 1)
res = {}; passed = 0
for k, ceil in kinds.items():
    # one row per labeller: for both-labelled items average the two labels as a soft target by duplicating rows
    X2, y2, w2 = [], [], []
    for n, i in enumerate(train):
        if i in S and i in H:
            for lab in (S[i], H[i]): X2.append(n); y2.append(int(k in lab)); w2.append(0.5)
        else: X2.append(n); y2.append(int(k in (S[i] if i in S else H[i]))); w2.append(1.0)
    X2 = np.array(X2); y2 = np.array(y2); w2 = np.array(w2); inh = np.isin(X2, hold); fi = ~inh
    m = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(Etr[X2[fi]], y2[fi], sample_weight=w2[fi])
    ph = m.predict_proba(Etr[X2[inh]])[:, 1]; best, thr = 0, 0.5
    for t in np.linspace(0.1, 0.95, 35):
        f = f1f(ph >= t, y2[inh])
        if f > best: best, thr = f, float(t)
    pt = m.predict_proba(Ete)[:, 1]; pr = pt >= thr; ys = np.array([int(k in S[i]) for i in test]); yh = np.array([int(k in H[i]) for i in test])
    fs, fh = f1f(pr, ys), f1f(pr, yh); ok = bool(fs >= ceil - 0.05 and fh >= ceil - 0.05); passed += ok
    res[k] = {"labeller_f1_ceiling": ceil, "test_pos_sonnet": int(ys.sum()), "test_pos_haiku": int(yh.sum()), "threshold": round(thr, 2), "f1_vs_sonnet": round(fs, 3), "f1_vs_haiku": round(fh, 3), "auc_vs_sonnet": round(roc_auc_score(ys, pt), 3), "auc_vs_haiku": round(roc_auc_score(yh, pt), 3), "pass_both": ok}
    print(k, res[k])
json.dump({"kinds_tested": len(kinds), "kinds_passed": passed, "per_kind": res}, open("runs/pulse/perkind_pooled.json", "w"), indent=1); print("PASSED", passed, "of", len(kinds))
