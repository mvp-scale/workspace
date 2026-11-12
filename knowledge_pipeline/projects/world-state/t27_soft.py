"""T27 steps 3 and 4: presence soft labels from the three-family panel, and a head-to-head of soft vs hard targets on the same frozen T56 encoder vectors.
Pre-registered at ledger L1466. Threshold chosen on dev (recall 0.80 against Sonnet); sealed (Sonnet gold only) read once. CPU only.
    /workspace/models/embed-zs/.venv/bin/python t27_soft.py -> runs/pulse/t27_soft.json, runs/pulse/presence_soft_labels.jsonl"""
import os, json, random, hashlib, collections
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
torch.set_num_threads(4); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; CK = "runs/expert1/leaf_ft_cpu2_best.pt"
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
SL = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(SL); best = {}; RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; panel = collections.defaultdict(dict)
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r.get("n_conditions") is not None and r["family"] in ("sonnet", "haiku", "gemma"): panel[i].setdefault(r["family"], int(r["n_conditions"] > 0))
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); random.Random(20261110).shuffle(ids); nd = int(0.15 * len(ids)); dev, fit = ids[:nd], ids[nd:]
E = np.load(f"runs/emb_cache/{os.path.basename(CK)}_{hashlib.md5(str(len(ids)).encode()).hexdigest()[:6]}.npy"); pos = {i: k for k, i in enumerate(ids)}
P3 = lambda i: len(panel.get(i, {})) == 3
fitp = [i for i in fit if P3(i)]; devp = [i for i in dev if P3(i)]
share = lambda i: sum(panel[i].values()) / 3
agree = lambda i: share(i) in (0.0, 1.0)
with open("runs/pulse/presence_soft_labels.jsonl", "w") as f:
    for i in fitp + devp: f.write(json.dumps({"item_id": i, "share_present": round(share(i), 4), "agreed": agree(i), "weight": 1.0 if agree(i) else 0.5, "sonnet": panel[i]["sonnet"]}) + "\n")
res = {"panel": "sonnet, haiku, gemma (presence = n_conditions > 0)", "fit_panel_items": len(fitp), "dev_panel_items": len(devp), "split_share_fit": round(1 - np.mean([agree(i) for i in fitp]), 4), "split_share_dev": round(1 - np.mean([agree(i) for i in devp]), 4),
       "present_share_fit_sonnet": round(float(np.mean([panel[i]["sonnet"] for i in fitp])), 4), "present_share_fit_panel_mean": round(float(np.mean([share(i) for i in fitp])), 4)}
Xf = torch.tensor(E[[pos[i] for i in fitp]]); Xd = torch.tensor(E[[pos[i] for i in devp]])
yh = torch.tensor([float(panel[i]["sonnet"]) for i in fitp]); ys_ = torch.tensor([share(i) for i in fitp]); w = torch.tensor([1.0 if agree(i) else 0.5 for i in fitp])
def train(target, weights, seed):
    torch.manual_seed(seed); lin = torch.nn.Linear(E.shape[1], 1); opt = torch.optim.AdamW(lin.parameters(), lr=3e-3, weight_decay=0.01)
    for ep in range(60):
        perm = torch.randperm(len(Xf))
        for k in range(0, len(Xf), 256):
            b = perm[k:k + 256]; l = (torch.nn.functional.binary_cross_entropy_with_logits(lin(Xf[b]).squeeze(1), target[b], reduction="none") * weights[b]).mean(); l.backward(); opt.step(); opt.zero_grad()
    return lin
def prob(lin, X): 
    with torch.no_grad(): return torch.sigmoid(lin(X).squeeze(1)).numpy()
def at_recall(score, yy, target=0.80):
    for t in sorted(set(score), reverse=True):
        pred = score >= t
        if (pred & (yy == 1)).sum() / max(yy.sum(), 1) >= target: return float(t)
    return float(min(score))
tok = AutoTokenizer.from_pretrained("MongoDB/mdbr-leaf-mt"); enc = AutoModel.from_pretrained("MongoDB/mdbr-leaf-mt"); ck = torch.load(CK); enc.load_state_dict(ck["enc"]); enc.eval()
sid = sorted(i for i in SL if i in txt); out = []
with torch.no_grad():
    for k in range(0, len(sid), 128):
        x = tok([txt[i] for i in sid[k:k + 128]], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); out.append(((h * m).sum(1) / m.sum(1)).numpy())
Xs = torch.tensor(np.concatenate(out)); yS = np.array([int(bool(SL[i]["conditions"])) for i in sid])
dsh = np.array([share(i) for i in devp]); dson = np.array([panel[i]["sonnet"] for i in devp]); dmaj = (dsh >= 0.5).astype(int); dag = np.array([agree(i) for i in devp])
res["arms"] = {}
for name, tgt, wt in (("hard_sonnet", yh, torch.ones(len(fitp))), ("soft_panel", ys_, w)):
    runs = []
    for seed in (7, 11, 13):
        lin = train(tgt, wt, seed); pd_ = prob(lin, Xd); t = at_recall(pd_, dson); pred = pd_ >= t
        r = {"seed": seed, "threshold": round(t, 4), "dev_precision_vs_sonnet": round(float((pred & (dson == 1)).sum() / max(pred.sum(), 1)), 4), "dev_recall_vs_sonnet": round(float((pred & (dson == 1)).sum() / dson.sum()), 4),
             "dev_agree_with_panel_majority_on_agreed": round(float((pred[dag] == dmaj[dag]).mean()), 4), "dev_agree_with_panel_majority_on_split": round(float((pred[~dag] == dmaj[~dag]).mean()), 4), "dev_brier_vs_panel_share": round(float(((pd_ - dsh) ** 2).mean()), 4)}
        ps = prob(lin, Xs); predS = ps >= t; tp = int((predS & (yS == 1)).sum()); r.update({"sealed_precision": round(tp / max(int(predS.sum()), 1), 4), "sealed_recall": round(tp / int(yS.sum()), 4), "sealed_agreement": round(float((predS == (yS == 1)).mean()), 4)}); runs.append(r)
    res["arms"][name] = runs
res["sealed_n"] = len(sid); res["sealed_always_no_agreement"] = round(float(1 - yS.mean()), 4)
json.dump(res, open("runs/pulse/t27_soft.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in res if k != "arms"}))
for a, rs in res["arms"].items():
    print(a); [print(" ", {k: v for k, v in r.items() if k != "threshold"}) for r in rs]
