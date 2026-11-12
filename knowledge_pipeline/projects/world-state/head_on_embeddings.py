"""Train a small head on CACHED vectors from a fine-tuned encoder checkpoint (no encoder training). Heads: kinds (multi-label, kinds with at least MINK unique items) and size (levels 0 to 3). Same train/dev split as finetune_cpu*.py. Dev is scored every 5 epochs, best checkpoint kept, early stop after 3 evaluations without a gain of 0.002. DEV ONLY: the sealed set has no kinds or size gold, and the size and kinds contracts are unconfirmed, so these are research numbers. Judge: agreement with Sonnet.
    python3 head_on_embeddings.py CKPT kinds|size [THREADS]  -> runs/pulse/heademb_<head>.json"""
import json, os, sys, time, random, hashlib
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf")
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
CK, HEAD = sys.argv[1], sys.argv[2]; torch.set_num_threads(int(sys.argv[3]) if len(sys.argv) > 3 else 4); SEED = int(os.environ.get('SEED', 7)); torch.manual_seed(SEED); MINK = 100; T0 = time.time()
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
sealed = {r["item_id"] for r in J("runs/pulse/sealed/labels.jsonl")}; RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); random.Random(20261110).shuffle(ids)
if os.environ.get("SMOKE"): ids = ids[:3000]
nd = int(0.15 * len(ids)); dev, fit = ids[:nd], ids[nd:]
n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); ck = torch.load(CK); enc.load_state_dict(ck["enc"]); enc.eval()
cache = f"runs/emb_cache/{os.path.basename(CK)}_{hashlib.md5(str(len(ids)).encode()).hexdigest()[:6]}.npy"; os.makedirs("runs/emb_cache", exist_ok=True)
if os.path.exists(cache): E = np.load(cache)
else:
    out = []
    with torch.no_grad():
        for k in range(0, len(ids), 128):
            x = tok([txt[i] for i in ids[k:k + 128]], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); out.append(((h * m).sum(1) / m.sum(1)).numpy())
            if (k // 128) % 40 == 0: print("embed", k, f"{time.time() - T0:.0f}s", flush=True)
    E = np.concatenate(out); np.save(cache, E)
pos = {i: k for k, i in enumerate(ids)}; print("embeddings", E.shape, f"{time.time() - T0:.0f}s", flush=True)
rows = lambda r: (r.get("kinds") or [])
if HEAD == "kinds":
    cnt = {}
    for i in ids:
        for kd in rows(best[i][1]): cnt[kd] = cnt.get(kd, 0) + 1
    K = sorted(k for k, v in cnt.items() if v >= MINK); ki = {k: j for j, k in enumerate(K)}; use = [i for i in ids if rows(best[i][1])]
    Y = {i: np.eye(len(K))[[ki[x] for x in rows(best[i][1]) if x in ki]].sum(0).clip(0, 1) if any(x in ki for x in rows(best[i][1])) else np.zeros(len(K)) for i in use}; nout = len(K); loss_fn = torch.nn.BCEWithLogitsLoss()
else:
    use = [i for i in ids if best[i][1].get("max_level") in (0, 1, 2, 3)]; Y = {i: best[i][1]["max_level"] for i in use}; nout = 4; K = ["0", "1", "2", "3"]; loss_fn = torch.nn.CrossEntropyLoss()
assert nout > 0 and len([i for i in fit if i in Y]) > 0, f"no classes or no fit items for {HEAD} (kinds need MINK={MINK} unique items each; the SMOKE subset is too small for kinds)"
fu = [i for i in fit if i in Y]; du = [i for i in dev if i in Y]; print(HEAD, "fit", len(fu), "dev", len(du), "classes", nout, flush=True)
Xf, Xd = torch.tensor(E[[pos[i] for i in fu]]), torch.tensor(E[[pos[i] for i in du]]); yt = (lambda a: torch.tensor(np.array(a), dtype=torch.float32 if HEAD == "kinds" else torch.long))
Yf, Yd = yt([Y[i] for i in fu]), yt([Y[i] for i in du]); lin = torch.nn.Linear(E.shape[1], nout); opt = torch.optim.AdamW(lin.parameters(), lr=3e-3, weight_decay=0.01)
def metric(X, Yt):
    with torch.no_grad(): lo = lin(X)
    if HEAD == "size": return float((lo.argmax(1) == Yt).float().mean())
    p = (lo > 0).float(); tp = (p * Yt).sum(); fp = (p * (1 - Yt)).sum(); fn = ((1 - p) * Yt).sum(); return float(2 * tp / max(2 * tp + fp + fn, 1))
base = float(np.bincount(Yd.numpy()).max() / len(Yd)) if HEAD == "size" else None
curve = []; bestm = -1; bad = 0; bst = None; stop = "max epochs"
for ep in range(1, 301):
    perm = torch.randperm(len(Xf))
    for k in range(0, len(Xf), 256): b = perm[k:k + 256]; l = loss_fn(lin(Xf[b]), Yf[b]); l.backward(); opt.step(); opt.zero_grad()
    if ep % 5 == 0:
        m = metric(Xd, Yd); curve.append({"epoch": ep, "dev": round(m, 4), "train_loss": round(float(l.detach()), 4)})
        if m > bestm + 0.002: bestm = m; bad = 0; bst = {k_: v.clone() for k_, v in lin.state_dict().items()}
        else:
            bad += 1
            if m > bestm: bestm = m; bst = {k_: v.clone() for k_, v in lin.state_dict().items()}
        if bad >= 3: stop = f"early stop at epoch {ep}"; break
lin.load_state_dict(bst); out = {"head": HEAD, "classes": K, "fit_items": len(fu), "dev_items": len(du), "metric": "accuracy" if HEAD == "size" else "micro-F1 at 0.5", "best_dev": round(bestm, 4), "majority_baseline_dev": base, "stop": stop, "curve": curve, "encoder_ckpt": CK, "judge": "agreement with Sonnet, dev split only, research (contract unconfirmed)", "wall_s": round(time.time() - T0, 1)}
if HEAD == "kinds":  # T69: baselines on dev, then the sealed set read once, over sealed items that have a condition (the head is trained and scored on those only)
    def f1(p, Yt): tp = float((p * Yt).sum()); fp = float((p * (1 - Yt)).sum()); fn = float(((1 - p) * Yt).sum()); return 2 * tp / max(2 * tp + fp + fn, 1)
    freq = Yf.sum(0); order_ = torch.argsort(freq, descending=True)
    def topk(k, n_): z = torch.zeros(n_, len(K)); z[:, order_[:k]] = 1; return z
    out["dev_baseline_most_common_kind"] = round(f1(topk(1, len(Yd)), Yd), 4); out["dev_baseline_top3_kinds"] = round(f1(topk(3, len(Yd)), Yd), 4)
    SL = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sk = [i for i in sorted(SL) if i in txt and any(c.get("condition") in ki for c in (SL[i].get("conditions") or []))]
    Ys = torch.tensor(np.array([np.eye(len(K))[[ki[c["condition"]] for c in SL[i]["conditions"] if c.get("condition") in ki]].sum(0).clip(0, 1) for i in sk]), dtype=torch.float32); outv = []
    with torch.no_grad():
        for k in range(0, len(sk), 128):
            x = tok([txt[i] for i in sk[k:k + 128]], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); outv.append(((h * m).sum(1) / m.sum(1)).numpy())
    Xs = torch.tensor(np.concatenate(outv)); ps = (lin(Xs) > 0).float(); rg = np.random.default_rng(0); bs = []
    for _ in range(500): ix = torch.tensor(rg.integers(0, len(sk), len(sk))); bs.append(f1(ps[ix], Ys[ix]))
    out["sealed"] = {"n": len(sk), "micro_f1": round(f1(ps, Ys), 4), "ci95": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)], "baseline_most_common_kind": round(f1(topk(1, len(sk)), Ys), 4), "baseline_top3_kinds": round(f1(topk(3, len(sk)), Ys), 4), "note": "sealed items that have at least one kept kind; agreement with Sonnet, not outside truth; read once"}
    out["seed"] = SEED
json.dump(out, open(f"runs/pulse/heademb_{HEAD}{os.environ.get('OUTSUF', '')}.json", "w"), indent=1); print("DONE", json.dumps(out)[:700], flush=True)
