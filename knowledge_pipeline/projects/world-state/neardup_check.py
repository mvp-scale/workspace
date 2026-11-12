"""T58: sealed items with a near-duplicate among the training texts (same Sonnet-labelled set the heads train on). TF-IDF word 1-2 cosine, sparse product in chunks.
    /workspace/models/embed-zs/.venv/bin/python neardup_check.py  -> runs/pulse/neardup.json"""
import json, re, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
sealed = [r["item_id"] for r in J("runs/pulse/sealed/labels.jsonl")]; sset = set(sealed); sid = [i for i in sealed if i in txt]
tr = sorted({r["item_id"] for r in J("runs/label_store/labels.jsonl") if r["family"] == "sonnet" and r["item_id"] in txt and r["item_id"] not in sset})
v = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True); A = v.fit_transform([txt[i] for i in tr]); B = v.transform([txt[i] for i in sid])
norm = lambda t: re.sub(r"\W+", " ", t.lower()).strip(); trn = {norm(txt[i]) for i in tr}; exact = [i for i in sid if norm(txt[i]) in trn]
mx = np.zeros(len(sid)); arg = np.zeros(len(sid), dtype=int)
for k in range(0, len(sid), 200):
    M = (B[k:k + 200] @ A.T).toarray(); mx[k:k + 200] = M.max(1); arg[k:k + 200] = M.argmax(1)
res = {"sealed_items": len(sid), "train_texts": len(tr), "exact_normalised_matches": len(exact), "cos_ge_0p95": int((mx >= 0.95).sum()), "cos_ge_0p9": int((mx >= 0.9).sum()), "cos_ge_0p8": int((mx >= 0.8).sum()), "max_cosine_median": round(float(np.median(mx)), 3),
       "examples_ge_0p9": [{"sealed": sid[k], "train": tr[arg[k]], "cos": round(float(mx[k]), 3), "sealed_text": txt[sid[k]][:140], "train_text": txt[tr[arg[k]]][:140]} for k in np.argsort(-mx)[:5] if mx[k] >= 0.9], "dup_ids_ge_0p9": [sid[k] for k in range(len(sid)) if mx[k] >= 0.9]}
json.dump(res, open("runs/pulse/neardup.json", "w"), indent=1); print({k: v for k, v in res.items() if k not in ("examples_ge_0p9", "dup_ids_ge_0p9")})
