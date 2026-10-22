"""Fine-tune e5-small-v2 on CPU as one multi-label reader for all condition keys (T-0020), vs the frozen e5+tfidf reader (F-0056).

Train: night1 train split (seed 0) + round1 + round2. Test: night1 held-out + testA (frozen). Keys: those with >= 30 training positives.
Mean pooling ("query: " prefix per the e5 model card), linear head, BCE with per-key positive weight (capped at 20), AdamW, 2 epochs, max 96 tokens.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/finetune_conditions.py <outdir>
"""
import sys, json, time, numpy as np, torch
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from transformers import AutoTokenizer, AutoModel

OUT = sys.argv[1]; torch.manual_seed(0); torch.set_num_threads(16)
L = lambda f: [json.loads(l) for l in open(f)]
night = L("/workspace/data/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + L("/workspace/data/trainset/round1.jsonl") + L("/workspace/data/trainset/round2.jsonl")
test = [night[i] for i in te_i] + L("/workspace/data/trainset/testA.jsonl")
cnt = {}
for r in train:
    for k in r["target_keys"]: cnt[k] = cnt.get(k, 0) + 1
keys = sorted(k for k, n in cnt.items() if n >= 30); K = {k: i for i, k in enumerate(keys)}
Y = lambda rows: torch.tensor([[k in r["target_keys"] for k in keys] for r in rows], dtype=torch.float32)
Ytr, Yte = Y(train), Y(test)
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); enc = AutoModel.from_pretrained("intfloat/e5-small-v2")
head = torch.nn.Linear(enc.config.hidden_size, len(keys))
def embed(texts):
    b = tok(["query: " + t for t in texts], padding=True, truncation=True, max_length=96, return_tensors="pt")
    h = enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float(); return (h * m).sum(1) / m.sum(1)
pos = Ytr.sum(0); pw = ((len(train) - pos) / pos.clamp(min=1)).clamp(max=20)
loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
opt = torch.optim.AdamW([{"params": enc.parameters(), "lr": 3e-5}, {"params": head.parameters(), "lr": 1e-3}], weight_decay=0.01)
X = [r["input"] for r in train]; t0 = time.time(); BS, EP = 32, 2
for ep in range(EP):
    enc.train(); perm = torch.randperm(len(X)).tolist()
    for j in range(0, len(X), BS):
        idx = perm[j:j + BS]; opt.zero_grad(); l = loss_fn(head(embed([X[i] for i in idx])), Ytr[idx]); l.backward(); opt.step()
        if j % (BS * 100) == 0: print(f"epoch {ep} step {j // BS} loss {l.item():.3f} {time.time() - t0:.0f}s", flush=True)
t_train = time.time() - t0
enc.eval(); P = []
with torch.no_grad():
    t1 = time.time()
    for j in range(0, len(test), 128): P.append(torch.sigmoid(head(embed([r["input"] for r in test[j:j + 128]]))))
    t_inf = (time.time() - t1) / len(test)
P = torch.cat(P).numpy(); Yn = Yte.numpy()
ap = {k: round(float(average_precision_score(Yn[:, i], P[:, i])), 3) for k, i in K.items() if Yn[:, i].sum() >= 3}
res = {"train": len(train), "test": len(test), "keys": len(ap), "train_min": round(t_train / 60, 1), "ms_per_story_infer_batch128": round(1000 * t_inf, 2),
       "mean_AP": round(float(np.mean(list(ap.values()))), 3), "keys_AP_ge_0.70": sum(v >= 0.70 for v in ap.values()), "AP": ap}
json.dump(res, open(f"{OUT}/finetune.json", "w"), indent=1); torch.save({"enc": enc.state_dict(), "head": head.state_dict(), "keys": keys}, f"{OUT}/finetune.pt")
print(json.dumps({k: v for k, v in res.items() if k != "AP"}))

import subprocess  # end every run with the acceptance scorecard (scorecard.py)
subprocess.run(["python3", "/workspace/newsreader/bitmob/scorecard.py", "finetune_conditions " + " ".join(sys.argv[1:])])
