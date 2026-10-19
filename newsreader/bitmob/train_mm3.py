"""Train CPU taggers on the MM3 training queue (data/mm3-train/queue.jsonl) and score them on held-out stories.
Round 2: each model's yes cut-off per condition is chosen on training stories only (5-fold for frozen models, a 20% validation
slice for the fine-tune, 15 epochs). Labels (fixed before looking): a condition is "yes" when Clef says yes (p >= 0.5) to both its `states` and `concrete` questions;
topic / scope / kind = Clef's top option. Test = stories whose id hash % 5 == 0 (never trained on).
Models compared, same split:
  A  frozen static embeddings (potion-base-32M) + logistic per label        (today's kind of model)
  B  frozen e5-small + logistic per label                                   (BitMob's encoder, frozen)
  C  e5-small fine-tuned end to end on Clef's soft answers (all questions)  (the proposal), then run on CPU
Reports per condition yes-F1, topic top-1 / top-3, scope and kind accuracy, and CPU ms per story (one thread).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/train_mm3.py"""
import json, hashlib, time, os, sys, numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold

Q = "/workspace/data/mm3-train/queue.jsonl"; OUT = "/workspace/data/mm3-train/results-r2.json"
rows = list({r["id"]: r for r in map(json.loads, open(Q))}.values())
test = np.array([int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 5 == 0 for r in rows]); tr = ~test
CONDS = sorted({k.rsplit("|", 1)[0] for k in rows[0]["answers"] if k.count("|") == 2})
YESNO = sorted(k for k in rows[0]["answers"] if k.count("|") == 2)
CH = {c: list(rows[0]["answers"][c]) for c in ("topic", "scope", "kind")}
text = [r["title"] + ". " + r["text"] for r in rows]
Y = np.array([[r["answers"][f"{c}|states"] >= .5 and r["answers"][f"{c}|concrete"] >= .5 for c in CONDS] for r in rows])
CHY = {c: np.array([max(r["answers"][c], key=r["answers"][c].get) for r in rows]) for c in CH}
print(f"{len(rows)} stories ({tr.sum()} train, {test.sum()} test); yes per condition (train): " + ", ".join(f"{c.split('|')[0]} {Y[tr, j].sum()}" for j, c in enumerate(CONDS)), flush=True)


def score(name, P, CHP, ms, cut=None):
    """P: test x conditions probabilities; CHP: {choice: test x options probabilities}."""
    res = {"cpu_ms_story": round(ms, 2), "conditions": {}}
    for j, c in enumerate(CONDS):
        yt = Y[test, j]
        if yt.sum() < 3: res["conditions"][c] = None; continue
        res["conditions"][c] = round(f1_score(yt, P[:, j] >= (cut[j] if cut is not None else .5)), 3)
    v = [x for x in res["conditions"].values() if x is not None]; res["condition_f1_median"] = round(float(np.median(v)), 3); res["condition_f1_mean"] = round(float(np.mean(v)), 3)
    for c, opts in CH.items():
        order = np.argsort(-CHP[c], 1); truth = np.array([opts.index(t) for t in CHY[c][test]])
        res[f"{c}_top1"] = round(float((order[:, 0] == truth).mean()), 3)
        if c == "topic": res["topic_top3"] = round(float((order[:, :3] == truth[:, None]).any(1).mean()), 3)
    print(f"{name}: " + json.dumps(res), flush=True); return res


def best_cut(y, p):
    if y.sum() < 2: return 0.5
    return max(np.linspace(0.05, 0.95, 37), key=lambda t: f1_score(y, p >= t))


def frozen(X, name, ms):
    P = np.zeros((test.sum(), len(CONDS))); cut = np.full(len(CONDS), 0.5)
    for j in range(len(CONDS)):
        if Y[tr, j].sum() < 2: continue
        mk = lambda: LogisticRegression(C=4, class_weight="balanced", max_iter=3000)
        P[:, j] = mk().fit(X[tr], Y[tr, j]).predict_proba(X[test])[:, 1]
        oof = cross_val_predict(mk(), X[tr], Y[tr, j], cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]; cut[j] = best_cut(Y[tr, j], oof)
    CHP = {}
    for c, opts in CH.items():
        m = LogisticRegression(C=4, max_iter=3000).fit(X[tr], CHY[c][tr]); p = m.predict_proba(X[test])
        CHP[c] = np.zeros((test.sum(), len(opts)))
        for k, o in enumerate(m.classes_): CHP[c][:, opts.index(o)] = p[:, k]
    return score(name, P, CHP, ms, cut)


results = {"stories": len(rows), "train": int(tr.sum()), "test": int(test.sum()), "label_rule": "condition yes = states >= 0.5 and concrete >= 0.5",
           "yes_train": {c: int(Y[tr, j].sum()) for j, c in enumerate(CONDS)}, "yes_test": {c: int(Y[test, j].sum()) for j, c in enumerate(CONDS)}}
torch.set_num_threads(1)
# A: potion static
from model2vec import StaticModel
pm = StaticModel.from_pretrained("minishlab/potion-base-32M"); t = time.perf_counter(); XA = pm.encode(text); msA = (time.perf_counter() - t) * 1000 / len(text)
results["A_potion_frozen"] = frozen(XA, "A potion frozen", msA)
# B: e5 frozen (same tokenizer and model as C before fine-tuning)
from transformers import AutoTokenizer, AutoModel
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2")
def e5_vectors(model, texts, bs=32, device="cpu"):
    model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(texts), bs):
            b = tok(["query: " + x for x in texts[i:i + bs]], truncation=True, max_length=512, padding=True, return_tensors="pt").to(device)
            h = model(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); out.append(((h * m).sum(1) / m.sum(1)).cpu().numpy())
    return np.concatenate(out)
dev = "cuda" if torch.cuda.is_available() else "cpu"
base = AutoModel.from_pretrained("intfloat/e5-small-v2").to(dev); XB = e5_vectors(base, text, device=dev)
one = AutoModel.from_pretrained("intfloat/e5-small-v2"); t = time.perf_counter(); e5_vectors(one, text[:40], bs=1); msB = (time.perf_counter() - t) * 1000 / 40
results["B_e5_frozen"] = frozen(XB, "B e5 frozen", msB)
# C: fine-tune e5-small on all of Clef's soft answers (yes/no + choices), multi-task, on the GPU for a few minutes
heads_yes = YESNO; SOFT = np.array([[r["answers"][k] for k in heads_yes] for r in rows], np.float32)
CHS = {c: np.array([[r["answers"][c][o] for o in CH[c]] for r in rows], np.float32) for c in CH}
class Tagger(torch.nn.Module):
    def __init__(s):
        super().__init__(); s.enc = AutoModel.from_pretrained("intfloat/e5-small-v2"); d = s.enc.config.hidden_size
        s.yes = torch.nn.Linear(d, len(heads_yes)); s.ch = torch.nn.ModuleDict({c: torch.nn.Linear(d, len(o)) for c, o in CH.items()})
    def forward(s, **b):
        h = s.enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); v = (h * m).sum(1) / m.sum(1)
        return s.yes(v), {c: l(v) for c, l in s.ch.items()}
torch.manual_seed(0); M = Tagger().to(dev); opt = torch.optim.AdamW(M.parameters(), lr=5e-5, weight_decay=0.01)
val = tr & np.array([int(hashlib.sha256(r['id'].encode()).hexdigest(), 16) % 5 == 1 for r in rows]); fit = tr & ~val
idx = np.where(fit)[0]; EPOCHS, BS = 15, 16; MAXLEN = 384; t0 = time.perf_counter()
pos_w = torch.tensor(np.clip((1 - SOFT[fit].mean(0)) / np.maximum(SOFT[fit].mean(0), 1e-3), 1, 5), device=dev)  # rare yes answers count more
for ep in range(EPOCHS):
    M.train(); np.random.RandomState(ep).shuffle(idx); tot = 0
    for i in range(0, len(idx), BS):
        bi = idx[i:i + BS]; b = tok(["query: " + text[k] for k in bi], truncation=True, max_length=MAXLEN, padding=True, return_tensors="pt").to(dev)
        ly, lc = M(**b)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(ly, torch.tensor(SOFT[bi], device=dev), pos_weight=pos_w)
        for c in CH: loss = loss + 0.3 * -(torch.tensor(CHS[c][bi], device=dev) * torch.log_softmax(lc[c], -1)).sum(-1).mean()
        opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(bi)
    print(f"  C epoch {ep + 1}: loss {tot / len(idx):.4f} ({time.perf_counter() - t0:.0f}s)", flush=True)
results["C_train_gpu_s"] = round(time.perf_counter() - t0, 1)
M.eval()
def run_on(ks, dev_):
    PY, PC = [], {c: [] for c in CH}
    with torch.no_grad():
        for k in ks:
            b = tok(["query: " + text[k]], truncation=True, max_length=MAXLEN, return_tensors="pt").to(dev_); ly, lc = M(**b)
            PY.append(torch.sigmoid(ly)[0].cpu().numpy()); [PC[c].append(torch.softmax(lc[c], -1)[0].cpu().numpy()) for c in CH]
    PY = np.array(PY); cond = np.array([[min(PY[i, heads_yes.index(f"{c}|states")], PY[i, heads_yes.index(f"{c}|concrete")]) for c in CONDS] for i in range(len(ks))])
    return cond, {c: np.array(v) for c, v in PC.items()}
vk = np.where(val)[0]; Pv, _ = run_on(vk, dev); cutC = np.array([best_cut(Y[vk, j], Pv[:, j]) for j in range(len(CONDS))])
M = M.cpu(); te = np.where(test)[0]; t = time.perf_counter(); P, PCt = run_on(te, "cpu"); msC = (time.perf_counter() - t) * 1000 / len(te)
results["C_e5_finetuned"] = score("C e5 fine-tuned (CPU fp32)", P, PCt, msC, cutC)
os.makedirs("/workspace/data/mm3-train/model", exist_ok=True); torch.save(M.state_dict(), "/workspace/data/mm3-train/model/tagger.pt")
json.dump({"heads_yes": heads_yes, "choices": CH, "conds": CONDS, "maxlen": MAXLEN}, open("/workspace/data/mm3-train/model/heads.json", "w"))
json.dump(results, open(OUT, "w"), indent=1); print("saved", OUT)
