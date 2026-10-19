"""Attack A5 (docs/value-indicators.md): does fine-tuning pay with all the data, and would more data help? e5-small (Scholar) fine-tuned end to end
as one multi-task network (one output per atom) on title + lead (the input Scholar uses at run time, ~48 ms on CPU), trained on 25%, 50% and 100%
of each training fold; cross-fitted with the baselines' folds (5 folds, test = average of the fold models). Labels: Clef agreed per atom.
Training runs on the GPU (offline); scoring is the same as run time. Scored by value_eval.py (R@9) and macro average precision (power_check).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/attack_a5_finetune.py"""
import sys, os, json, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.model_selection import KFold
from transformers import AutoTokenizer, AutoModel
first = {r["id"]: r for r in map(json.loads, open(f"{V.D}/queue.jsonl"))}; rows = [first[i] for i in V.ids]
text = ["query: " + r["title"] + ". " + " ".join(r["text"].split()[:80]) for r in rows]
A = V.ATOMS; Yall = np.array([V.L[n]["agreed"] for n in A]).T.astype(np.float32)
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); dev = "cuda"
tr_idx = np.where(V.TRN)[0]; te_idx = np.where(V.test)[0]; folds = list(KFold(5, shuffle=True, random_state=0).split(tr_idx))
class Net(torch.nn.Module):
    def __init__(s):
        super().__init__(); s.enc = AutoModel.from_pretrained("intfloat/e5-small-v2"); s.out = torch.nn.Linear(s.enc.config.hidden_size, len(A))
    def forward(s, **b):
        h = s.enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); return s.out((h * m).sum(1) / m.sum(1))
def train_predict(fit, outs, epochs=8, seed=0):
    torch.manual_seed(seed); net = Net().to(dev); opt = torch.optim.AdamW(net.parameters(), lr=5e-5, weight_decay=0.01)
    pw = torch.tensor(np.clip((1 - Yall[fit].mean(0)) / np.maximum(Yall[fit].mean(0), 1e-3), 1, 30), device=dev); lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
    for ep in range(epochs):
        net.train(); perm = np.random.RandomState(seed + ep).permutation(fit)
        for i in range(0, len(perm), 16):
            bi = perm[i:i + 16]; b = tok([text[k] for k in bi], truncation=True, max_length=160, padding=True, return_tensors="pt").to(dev)
            opt.zero_grad(); lossf(net(**b), torch.tensor(Yall[bi], device=dev)).backward(); opt.step()
    net.eval(); res = []
    with torch.no_grad():
        for r in outs:
            p = []
            for i in range(0, len(r), 64): b = tok([text[k] for k in r[i:i + 64]], truncation=True, max_length=160, padding=True, return_tensors="pt").to(dev); p.append(torch.sigmoid(net(**b)).cpu().numpy())
            res.append(np.concatenate(p))
    return res
out = {}
for share in (0.25, 0.5, 1.0):
    S = np.zeros((len(V.ids), len(A)), np.float32)
    for f, (a, b) in enumerate(folds):
        fit = tr_idx[a]; fit = np.random.RandomState(f).permutation(fit)[: int(len(fit) * share)]
        pb, pt = train_predict(fit, [tr_idx[b], te_idx]); S[tr_idx[b]] = pb; S[te_idx] += pt / 5
        print(f"share {share}: fold {f + 1} done", flush=True)
    np.save(f"{V.D}/proof/a5-scores-{int(share * 100)}.npy", S); out[f"A5 fine-tuned Scholar lead, {int(share * 100)}% of training"] = {n: S[:, k] for k, n in enumerate(A)}
V.evaluate(out, out_file=f"{V.D}/proof/a5-results.json")
