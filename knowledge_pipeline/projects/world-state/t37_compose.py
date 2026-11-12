"""T37 step 4, pieces 3 and 4. Presence = presence head (T56 encoder) AND a filtered event trigger present, with the head threshold lowered until dev recall reaches 0.80.
Everything is fitted on fit items or chosen on dev; the sealed set is read once at the end. Pre-registered at ledger L1460. CPU only.
    /workspace/models/embed-zs/.venv/bin/python t37_compose.py -> runs/pulse/t37_compose.json"""
import os, sys, json, random, hashlib, collections
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
torch.set_num_threads(4); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; CK = "runs/expert1/leaf_ft_cpu2_best.pt"
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
SL = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(SL); best = {}; RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); random.Random(20261110).shuffle(ids); nd = int(0.15 * len(ids)); dev, fit = ids[:nd], ids[nd:]
E = np.load(f"runs/emb_cache/{os.path.basename(CK)}_{hashlib.md5(str(len(ids)).encode()).hexdigest()[:6]}.npy"); pos = {i: k for k, i in enumerate(ids)}; assert E.shape[0] == len(ids)
ck = torch.load(CK); W = ck["heads"]["pres.weight"].numpy(); B = ck["heads"]["pres.bias"].numpy()
def pres_p(e): z = e @ W.T + B; z = z - z.max(1, keepdims=True); p = np.exp(z); return (p / p.sum(1, keepdims=True))[:, 1]
y = lambda i: int((best[i][1].get("n_conditions") or 0) > 0)
TR = json.load(open("runs/pulse/event_triggers_by_item.json"))
# filter: trigger words over fit items only
base = np.mean([y(i) for i in fit]); cnt = collections.Counter(); pos_cnt = collections.Counter()
for i in fit:
    for w in set(TR.get(i, [])): cnt[w] += 1; pos_cnt[w] += y(i)
def keep(L, minn=30): return {w for w, n in cnt.items() if n >= minn and (pos_cnt[w] / n) / base >= L}
def ftrig(i, K): return sum(1 for w in set(TR.get(i, [])) if w in K)
pd_ = pres_p(E[[pos[i] for i in dev]]); yd = np.array([y(i) for i in dev])
def at_recall(score, yy, target=0.80):  # largest threshold whose recall reaches the target
    for t in sorted(set(score), reverse=True):
        pred = score >= t; rc = (pred & (yy == 1)).sum() / max(yy.sum(), 1)
        if rc >= target: pr = (pred & (yy == 1)).sum() / max(pred.sum(), 1); return float(t), float(pr), float(rc)
    return None
head_d = at_recall(pd_, yd); res = {"judge": "agreement with Sonnet presence labels (n_conditions > 0), not outside truth", "dev_items": len(dev), "dev_base_rate": round(float(yd.mean()), 4), "fit_base_rate": round(float(base), 4), "head_alone_dev": head_d, "filters": {}}
for L in (1.25, 1.5, 2.0, 3.0):
    K = keep(L); f = np.array([ftrig(i, K) > 0 for i in dev]); sc = np.where(f, pd_, -1.0); r_ = at_recall(sc, yd)
    res["filters"][str(L)] = {"words_kept": len(K), "dev_has_filtered_trigger_share": round(float(f.mean()), 3), "composed_dev": r_}
okL = [L for L in res["filters"] if res["filters"][L]["composed_dev"]]
bestL = float(max(okL, key=lambda L: res["filters"][L]["composed_dev"][1])) if okL else None; res["chosen_lift_cutoff"] = bestL
# sealed: read once
tok = AutoTokenizer.from_pretrained("MongoDB/mdbr-leaf-mt"); enc = AutoModel.from_pretrained("MongoDB/mdbr-leaf-mt"); enc.load_state_dict(ck["enc"]); enc.eval()
sid = sorted(i for i in SL if i in txt); out = []
with torch.no_grad():
    for k in range(0, len(sid), 128):
        x = tok([txt[i] for i in sid[k:k + 128]], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); out.append(((h * m).sum(1) / m.sum(1)).numpy())
ps = pres_p(np.concatenate(out)); ys = np.array([int(bool(SL[i]["conditions"])) for i in sid]); rg = np.random.default_rng(0)
def report(pred, name):
    tp = int((pred & (ys == 1)).sum()); pr = tp / max(int(pred.sum()), 1); rc = tp / max(int(ys.sum()), 1); acc = float((pred == (ys == 1)).mean())
    bs = []
    for _ in range(500): ix = rg.integers(0, len(ys), len(ys)); p_ = pred[ix]; t_ = ys[ix] == 1; bs.append((p_ & t_).sum() / max(p_.sum(), 1))
    res[name] = {"precision": round(pr, 4), "precision_ci95": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)], "recall": round(rc, 4), "agreement_all": round(acc, 4), "predicted_yes": int(pred.sum())}
res["sealed_n"] = len(sid); res["sealed_base_rate"] = round(float(ys.mean()), 4); res["always_no_agreement"] = round(float(1 - ys.mean()), 4)
if head_d: report(ps >= head_d[0], "sealed_head_alone")
if bestL:
    K = keep(bestL); fs = np.array([ftrig(i, K) > 0 for i in sid]); t = res["filters"][str(bestL)]["composed_dev"][0]; report(fs & (ps >= t), "sealed_composed")
json.dump(res, open("runs/pulse/t37_compose.json", "w"), indent=1); print(json.dumps({k: res[k] for k in res if k != "filters"}, indent=1)); print(json.dumps(res["filters"]))
