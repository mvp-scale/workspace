"""T55: fine-tune MongoDB/mdbr-leaf-mt (22.7M) on CPU with three linear heads (topic, story type, presence) on the Sonnet labels (same train/dev split as learn_loop.py; sealed set read once at the end). 64 tokens, mean pooling, batch 32, AdamW, linear decay. Judge: agreement with Sonnet, not outside truth.
    nohup timeout 3300 /workspace/models/embed-zs/.venv/bin/python -u finetune_cpu.py EPOCHS [MAX_STEPS]  -> runs/expert1/leaf_ft_cpu.pt, runs/pulse/finetune_cpu.json"""
import json, os, sys, time, random
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["OMP_NUM_THREADS"] = "18"
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
T0 = time.time(); EP = int(sys.argv[1]) if len(sys.argv) > 1 else 2; MAXSTEP = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9; torch.set_num_threads(18); torch.manual_seed(7)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); random.Random(20261110).shuffle(ids); nd = int(0.15 * len(ids)); dev, fit = ids[:nd], ids[nd:]
TOP = sorted({best[i][1]["topic"] for i in ids}); ST = sorted({best[i][1]["story_type"] for i in ids}); ti = {t: k for k, t in enumerate(TOP)}; si = {t: k for k, t in enumerate(ST)}
lab = lambda i: (ti[best[i][1]["topic"]], si[best[i][1]["story_type"]], int((best[i][1].get("n_conditions") or 0) > 0))
n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); H = enc.config.hidden_size
heads = torch.nn.ModuleDict({"topic": torch.nn.Linear(H, len(TOP)), "story": torch.nn.Linear(H, len(ST)), "pres": torch.nn.Linear(H, 2)})
def embed(batch):
    x = tok([txt[i] for i in batch], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); return (h * m).sum(1) / m.sum(1)
steps_per = len(fit) // 32; total = min(EP * steps_per, MAXSTEP)
opt = torch.optim.AdamW([{"params": enc.parameters(), "lr": 5e-5}, {"params": heads.parameters(), "lr": 1e-3}], weight_decay=0.01); sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: max(0.0, 1 - s / total))
cw = torch.tensor([1.0, 3.0]); ce = torch.nn.functional.cross_entropy
def predict(idlist):
    enc.eval(); P = []
    with torch.no_grad():
        for k in range(0, len(idlist), 128):
            e = embed(idlist[k:k + 128]); P.append((heads["topic"](e).argmax(1).numpy(), heads["story"](e).argmax(1).numpy(), heads["pres"](e).argmax(1).numpy()))
    enc.train(); return [np.concatenate([p[j] for p in P]) for j in range(3)]
def score(ids_, truth):
    t, s, p = predict(ids_); g = np.array(truth); a = float((t == g[:, 0]).mean()); b = float((s == g[:, 1]).mean()); y = g[:, 2].astype(bool); q = p.astype(bool); tp = (q & y).sum(); fp = (q & ~y).sum(); fn = (~q & y).sum(); pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return {"topic": round(a, 4), "story_type": round(b, 4), "presence_f1": round(float(2 * pr * rc / max(pr + rc, 1e-9)), 4)}, (t, s, p)
print(f"ready {time.time() - T0:.0f}s fit {len(fit)} dev {len(dev)} steps {total}", flush=True); enc.train(); step = 0; rng = random.Random(7); log = []
for ep in range(EP):
    rng.shuffle(fit)
    for k in range(steps_per):
        if step >= total: break
        b = fit[k * 32:(k + 1) * 32]; e = embed(b); L = np.array([lab(i) for i in b]); y = torch.from_numpy(L)
        loss = ce(heads["topic"](e), y[:, 0]) + ce(heads["story"](e), y[:, 1]) + ce(heads["pres"](e), y[:, 2], weight=cw); loss.backward(); torch.nn.utils.clip_grad_norm_(list(enc.parameters()) + list(heads.parameters()), 1.0); opt.step(); sched.step(); opt.zero_grad(); step += 1
        if step % 50 == 0: print(f"ep {ep} step {step}/{total} loss {loss.item():.3f} {time.time() - T0:.0f}s", flush=True)
    d, _ = score(dev, [lab(i) for i in dev]); log.append({"epoch": ep + 1, "dev": d, "t": round(time.time() - T0)}); print("DEV", json.dumps(log[-1]), flush=True)
torch.save({"enc": enc.state_dict(), "heads": heads.state_dict(), "topics": TOP, "story_types": ST}, "runs/expert1/leaf_ft_cpu.pt")
gl = [(ti[S[i]["topic"]] if S[i]["topic"] in ti else -1, si[S[i]["story_type"]] if S[i]["story_type"] in si else -1, int(bool(S[i]["conditions"]))) for i in sid]; sc, (t, s, p) = score(sid, gl)
g = np.array(gl); rg = np.random.default_rng(7); base = {"topic": 0.7532, "story_type": 0.8893, "presence_f1": 0.6429}
def f1(q, y): tp = (q & y).sum(); fp = (q & ~y).sum(); fn = (~q & y).sum(); a = tp / max(tp + fp, 1); b = tp / max(tp + fn, 1); return 2 * a * b / max(a + b, 1e-9)
out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "epochs": EP, "steps": step, "fit_items": len(fit), "dev_log": log, "sealed": sc, "sparse_default_sealed": base, "wall_s": round(time.time() - T0, 1)}
n_ = len(sid); ixs = [rg.integers(0, n_, n_) for _ in range(500)]; y = g[:, 2].astype(bool); q = p.astype(bool)
# paired against the sparse default needs its predictions; interval is against the recorded sparse score (unpaired) and is marked as such
out["interval_vs_recorded_sparse"] = {"topic": [round(float(np.percentile([(t[i] == g[i, 0]).mean() for i in ixs], q_)) - base["topic"], 4) for q_ in (2.5, 97.5)], "story_type": [round(float(np.percentile([(s[i] == g[i, 1]).mean() for i in ixs], q_)) - base["story_type"], 4) for q_ in (2.5, 97.5)], "presence_f1": [round(float(np.percentile([f1(q[i], y[i]) for i in ixs], q_)) - base["presence_f1"], 4) for q_ in (2.5, 97.5)], "note": "bootstrap of the encoder score minus the recorded sparse score; not paired"}
json.dump(out, open("runs/pulse/finetune_cpu.json", "w"), indent=1); print("DONE", json.dumps(out), flush=True)
