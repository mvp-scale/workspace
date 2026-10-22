"""Ensemble of the two condition readers (T-0021): frozen e5+tfidf logistic regression and the fine-tuned e5 (finetune_conditions.py), probabilities averaged 50/50 (fixed in advance, no tuning on the test).

Same train and frozen test as finetune_conditions.py. Writes <outdir>/status-testA.json in round_select's format (so the scorecard picks it up) plus ensemble.json.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/ensemble_conditions.py data/finetune1 <outdir>
"""
import sys, json, numpy as np, torch
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel

FT, OUT = sys.argv[1], sys.argv[2]; torch.set_num_threads(16)
L = lambda f: [json.loads(l) for l in open(f)]
night = L("/workspace/data/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + L("/workspace/data/trainset/round1.jsonl") + L("/workspace/data/trainset/round2.jsonl")
test = [night[i] for i in te_i] + L("/workspace/data/trainset/testA.jsonl")
ck = torch.load(f"{FT}/finetune.pt"); keys = ck["keys"]
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); enc = AutoModel.from_pretrained("intfloat/e5-small-v2"); enc.load_state_dict(ck["enc"]); enc.eval()
head = torch.nn.Linear(enc.config.hidden_size, len(keys)); head.load_state_dict(ck["head"])
def ft_probs(texts):
    out = []
    with torch.no_grad():
        for j in range(0, len(texts), 128):
            b = tok(["query: " + t for t in texts[j:j + 128]], padding=True, truncation=True, max_length=96, return_tensors="pt")
            h = enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float(); out.append(torch.sigmoid(head((h * m).sum(1) / m.sum(1))))
    return torch.cat(out).numpy()
Pft = ft_probs([r["input"] for r in test])
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); encf = lambda xs: e5.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit([r["input"] for r in train])
M = lambda rows: hstack([csr_matrix(encf([r["input"] for r in rows])), tf.transform([r["input"] for r in rows])]).tocsr()
Xtr, Xte = M(train), M(test); status, res = {}, {}; PE, YE, KE = [], [], []
for i, k in enumerate(keys):
    ytr = np.array([k in r["target_keys"] for r in train]); yte = np.array([k in r["target_keys"] for r in test])
    if yte.sum() < 3: continue
    pf = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    a = {n: float(average_precision_score(yte, p)) for n, p in (("frozen", pf), ("finetuned", Pft[:, i]), ("ensemble", (pf + Pft[:, i]) / 2))}
    res[k] = {n: round(v, 3) for n, v in a.items()} | {"test_pos": int(yte.sum())}; PE.append((pf + Pft[:, i]) / 2); YE.append(yte); KE.append(k)
    status[k] = {"status": "working" if a["ensemble"] >= 0.70 else "weak", "train_pos": int(ytr.sum()), "test_pos": int(yte.sum()), "AP": round(a["ensemble"], 3), "noise_sd": round(0.44 / yte.sum() ** 0.5, 3)}
summ = {n: round(float(np.mean([v[n] for v in res.values()])), 3) for n in ("frozen", "finetuned", "ensemble")} | {"keys": len(res), "ensemble_keys_ge_0.70": sum(v["ensemble"] >= 0.70 for v in res.values())}
json.dump({"summary": summ, "per_key": res}, open(f"{OUT}/ensemble.json", "w"), indent=1)
json.dump({"summary": {"reader": "ensemble frozen e5+tfidf + fine-tuned e5, 50/50"}, "keys": status}, open(f"{OUT}/status-testA.json", "w"), indent=1)
np.savez_compressed(f"{OUT}/test-probs.npz", P=np.array(PE).T, Y=np.array(YE).T, keys=np.array(KE), ids=np.array([r["id"] for r in test]), n_night=len(te_i))      # for thresholds, false alarms, calibration
print(json.dumps(summ))

import subprocess  # end every run with the acceptance scorecard (scorecard.py)
subprocess.run(["python3", "/workspace/newsreader/bitmob/scorecard.py", "ensemble_conditions " + " ".join(sys.argv[1:])])
