"""T37 biodiversity_loss direction head (pre-registered after L896). 5 fold CV on v6b-student embeddings, Sonnet labels, scored also against Haiku direction.
    /workspace/models/embed-zs/.venv/bin/python biodiv_direction.py   (from projects/world-state)"""
import json, re, glob, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
K = "biodiversity_loss"; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
S, H = {}, {}
for f in glob.glob("runs/**/labels.jsonl", recursive=True):
    if "label_store" in f: continue
    for r in J(f):
        pv = r.get("provenance") or {}; m = pv.get("model", ""); v = pv.get("prompt_version", "")
        c = {x["condition"]: x["direction"] for x in (r.get("label") or {}).get("conditions", [])}
        if K not in c: continue
        if "sonnet" in m and v == "ws-v2-frozen": S[r["item_id"]] = c[K]
        if "haiku" in m: H[r["item_id"]] = c[K]
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); y = np.array([int(S[i] == "down") for i in ids]); E = np.array([emb(pool[i]) for i in ids], dtype=np.float32)
print("items", len(ids), "down", int(y.sum()), "up", int((1 - y).sum()))
oof = np.zeros(len(y))
for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(E, y):
    oof[b] = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(E[a], y[a]).predict(E[b])
acc = float(((oof == y)).mean()); maj = max(y.mean(), 1 - y.mean()); rs = np.random.RandomState(5)
bs = [float((oof[ix] == y[ix]).mean()) for ix in (rs.randint(0, len(y), len(y)) for _ in range(500))]
hid = [k for k, i in enumerate(ids) if i in H]; yh = np.array([int(H[ids[k]] == "down") for k in hid]); acch = float((oof[hid] == yh).mean())
res = {"items": len(ids), "majority_share": round(float(maj), 3), "cv_accuracy_vs_sonnet": round(acc, 3), "range": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)], "items_haiku_also": len(hid), "cv_accuracy_vs_haiku": round(acch, 3), "haiku_majority_share": round(float(max(yh.mean(), 1 - yh.mean())), 3)}
json.dump(res, open("runs/pulse/biodiv_direction.json", "w"), indent=1); print(res)
