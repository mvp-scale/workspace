"""T37 per kind cross validation (pre-registered next after L888): 5 fold CV over all labelled items (pool_train plus devq) for the 16 kinds, threshold chosen inside each training part; pooled out of fold AUC and F1 with item bootstrap ranges.
    /workspace/models/embed-zs/.venv/bin/python perkind_condition_cv.py   (from projects/world-state)"""
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
from sklearn.model_selection import StratifiedKFold
allid = tr + dq; E = np.vstack([Etr, Edq]); res = {}; passed = 0
for k, ceil in kinds.items():
    y = np.array([int(k in S[i]) for i in allid]); oof = np.zeros(len(y)); pred = np.zeros(len(y), bool)
    for a, b in StratifiedKFold(5, shuffle=True, random_state=1).split(E, y):
        r = np.random.RandomState(0).permutation(len(a)); c = int(0.8 * len(a)); fa, ha = a[r[:c]], a[r[c:]]
        m = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(E[fa], y[fa]); ph = m.predict_proba(E[ha])[:, 1]; best, thr = 0, 0.5
        for t in np.linspace(0.1, 0.95, 35):
            p = ph >= t; f = 2 * int((p & (y[ha] == 1)).sum()) / max(int(p.sum()) + int(y[ha].sum()), 1)
            if f > best: best, thr = f, float(t)
        oof[b] = m.predict_proba(E[b])[:, 1]; pred[b] = oof[b] >= thr
    def stats(ix):
        yy, pp, oo = y[ix], pred[ix], oof[ix]; tp = int((pp & (yy == 1)).sum()); return roc_auc_score(yy, oo), 2 * tp / max(int(pp.sum()) + int(yy.sum()), 1)
    auc, f1 = stats(np.arange(len(y))); bs = np.random.RandomState(2); A, F = [], []
    for _ in range(200):
        ix = bs.randint(0, len(y), len(y)); a_, f_ = stats(ix); A.append(a_); F.append(f_)
    ok = bool(np.percentile(A, 2.5) >= 0.90 and np.percentile(F, 2.5) >= 0.50); passed += ok
    res[k] = {"labeller_f1_ceiling": ceil, "positives": int(y.sum()), "auc": round(auc, 3), "auc_range": [round(float(np.percentile(A, 2.5)), 3), round(float(np.percentile(A, 97.5)), 3)], "f1": round(f1, 3), "f1_range": [round(float(np.percentile(F, 2.5)), 3), round(float(np.percentile(F, 97.5)), 3)], "pass_lower_ends": ok}
    print(k, res[k])
json.dump({"kinds_tested": len(kinds), "kinds_passed": passed, "per_kind": res}, open("runs/pulse/perkind_condition_cv.json", "w"), indent=1); print("PASSED", passed, "of", len(kinds))
