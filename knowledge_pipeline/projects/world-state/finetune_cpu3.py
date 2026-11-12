"""T60 (from finetune_cpu2.py, T56): env knobs TAG, SEED, LABELS=hard|soft. soft = mean of the one-hot votes of every teacher family (sonnet, haiku, gemma) that labelled the item, for topic, story type and presence; dev and sealed gold stay Sonnet. T56: monitored, resumable CPU fine-tune of mdbr-leaf-mt with three heads (topic, story type, presence) on the Sonnet labels. Same data, split and model as finetune_cpu.py (T55). New: dev scored every half epoch; best-dev checkpoint kept; early stop after PATIENCE evaluations without a composite gain of MIN_GAIN; resume from runs/expert1/leaf_ft_state.pt so the planned epochs run in chunks under the one hour cap; the dev curve and the stop reason are written to the result file. Sealed set read once, at the end, with the BEST checkpoint. Judge: agreement with Sonnet, not outside truth.
    nohup timeout 3300 /workspace/models/embed-zs/.venv/bin/python -u finetune_cpu2.py PLANNED_EPOCHS CHUNK_SECONDS [EVAL_EVERY_STEPS]  -> runs/pulse/finetune_cpu2.json"""
import json, os, sys, time, random
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["OMP_NUM_THREADS"] = "18"
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
T0 = time.time(); EP = int(sys.argv[1]) if len(sys.argv) > 1 else 8; CHUNK = float(sys.argv[2]) if len(sys.argv) > 2 else 3000; torch.set_num_threads(18); SEED = int(os.environ.get("SEED", 7)); TAG = os.environ.get("TAG", "r0"); SOFT = os.environ.get("LABELS", "hard") == "soft"; torch.manual_seed(SEED)
PATIENCE = 3; MIN_GAIN = 0.002; STATE = f"runs/expert1/leaf_ft3_{TAG}_state.pt"; BESTP = f"runs/expert1/leaf_ft3_{TAG}_best.pt"
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
FAM = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] in ("sonnet", "haiku", "gemma") and r["item_id"] in best: FAM.setdefault(r["item_id"], {}).setdefault(r["family"], r)
def soft(i):
    t = np.zeros(len(TOP)); s_ = np.zeros(len(ST)); p = np.zeros(2); k = 0
    for fam, r in FAM.get(i, {}).items():
        if r.get("topic") in ti and r.get("story_type") in si: t[ti[r["topic"]]] += 1; s_[si[r["story_type"]]] += 1; p[int((r.get("n_conditions") or 0) > 0)] += 1; k += 1
    return (t / k, s_ / k, p / k) if k else None
n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); H = enc.config.hidden_size
heads = torch.nn.ModuleDict({"topic": torch.nn.Linear(H, len(TOP)), "story": torch.nn.Linear(H, len(ST)), "pres": torch.nn.Linear(H, 2)})
def embed(batch):
    x = tok([txt[i] for i in batch], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); return (h * m).sum(1) / m.sum(1)
steps_per = len(fit) // 32; total = EP * steps_per; EVERY = int(sys.argv[3]) if len(sys.argv) > 3 else steps_per // 2
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
comp = lambda d: (d["topic"] + d["story_type"] + d["presence_f1"]) / 3
step = 0; curve = []; bestc = -1.0; bad = 0; stop = None
if os.path.exists(STATE):
    st = torch.load(STATE); enc.load_state_dict(st["enc"]); heads.load_state_dict(st["heads"]); opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"]); step, curve, bestc, bad, stop = st["step"], st["curve"], st["bestc"], st["bad"], st["stop"]
    print(f"resumed at step {step}/{total}, best composite {bestc:.4f}, bad {bad}, stop {stop}", flush=True)
print(f"ready {time.time() - T0:.0f}s fit {len(fit)} dev {len(dev)} planned steps {total} eval every {EVERY}", flush=True); enc.train()
def save_state(): torch.save({"enc": enc.state_dict(), "heads": heads.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(), "step": step, "curve": curve, "bestc": bestc, "bad": bad, "stop": stop}, STATE)
while stop is None and step < total:
    if time.time() - T0 > CHUNK: stop = None; print("chunk time reached, state saved", flush=True); save_state(); sys.exit(0)
    ep, k = divmod(step, steps_per); order = list(fit); random.Random(100 + ep + 1000 * SEED).shuffle(order); b = order[k * 32:(k + 1) * 32]
    e = embed(b); y = torch.from_numpy(np.array([lab(i) for i in b]))
    if SOFT:
        sv = [soft(i) or None for i in b]; ok_ = [k for k, v in enumerate(sv) if v is not None]; lt = -(torch.tensor(np.array([sv[k][0] for k in ok_]), dtype=torch.float32) * heads["topic"](e[ok_]).log_softmax(1)).sum(1).mean(); ls = -(torch.tensor(np.array([sv[k][1] for k in ok_]), dtype=torch.float32) * heads["story"](e[ok_]).log_softmax(1)).sum(1).mean()
        pp = torch.tensor(np.array([sv[k][2] for k in ok_]), dtype=torch.float32); lp = (-(pp * heads["pres"](e[ok_]).log_softmax(1)) * cw).sum(1).mean(); loss = lt + ls + lp
    else: loss = ce(heads["topic"](e), y[:, 0]) + ce(heads["story"](e), y[:, 1]) + ce(heads["pres"](e), y[:, 2], weight=cw)
    loss.backward(); torch.nn.utils.clip_grad_norm_(list(enc.parameters()) + list(heads.parameters()), 1.0); opt.step(); sched.step(); opt.zero_grad(); step += 1
    if step % 50 == 0: print(f"step {step}/{total} loss {loss.item():.3f} {time.time() - T0:.0f}s", flush=True)
    if step % EVERY == 0 or step == total:
        d, _ = score(dev, [lab(i) for i in dev]); c = comp(d); curve.append({"step": step, "epoch": round(step / steps_per, 2), "dev": d, "composite": round(c, 4), "train_loss": round(loss.item(), 3)})
        if c > bestc + MIN_GAIN: bestc = c; bad = 0; torch.save({"enc": enc.state_dict(), "heads": heads.state_dict(), "topics": TOP, "story_types": ST, "step": step}, BESTP)
        else:
            bad += 1
            if c > bestc: bestc = c; torch.save({"enc": enc.state_dict(), "heads": heads.state_dict(), "topics": TOP, "story_types": ST, "step": step}, BESTP)
        print("DEV", json.dumps(curve[-1]), "bad", bad, flush=True)
        if bad >= PATIENCE: stop = f"early stop: {PATIENCE} evaluations without a composite gain of {MIN_GAIN}"
        save_state()
if stop is None: stop = "planned epochs finished"
bst = torch.load(BESTP); enc.load_state_dict(bst["enc"]); heads.load_state_dict(bst["heads"])
gl = [(ti[S[i]["topic"]] if S[i]["topic"] in ti else -1, si[S[i]["story_type"]] if S[i]["story_type"] in si else -1, int(bool(S[i]["conditions"]))) for i in sid]; sc, (t, s, p) = score(sid, gl)
g = np.array(gl); rg = np.random.default_rng(7); base = {"topic": 0.7532, "story_type": 0.8893, "presence_f1": 0.6429}
def f1(q, y): tp = (q & y).sum(); fp = (q & ~y).sum(); fn = (~q & y).sum(); a = tp / max(tp + fp, 1); b = tp / max(tp + fn, 1); return 2 * a * b / max(a + b, 1e-9)
n_ = len(sid); ixs = [rg.integers(0, n_, n_) for _ in range(500)]; y = g[:, 2].astype(bool); q = p.astype(bool)
out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "planned_epochs": EP, "steps_done": step, "best_checkpoint_step": bst["step"], "stop_reason": stop, "dev_curve": curve, "sealed": sc, "sparse_default_sealed": base, "t2_short_run_sealed": {"topic": 0.8185, "story_type": 0.9139, "presence_f1": 0.6592},
       "interval_vs_recorded_sparse": {"topic": [round(float(np.percentile([(t[i] == g[i, 0]).mean() for i in ixs], q_)) - base["topic"], 4) for q_ in (2.5, 97.5)], "story_type": [round(float(np.percentile([(s[i] == g[i, 1]).mean() for i in ixs], q_)) - base["story_type"], 4) for q_ in (2.5, 97.5)], "presence_f1": [round(float(np.percentile([f1(q[i], y[i]) for i in ixs], q_)) - base["presence_f1"], 4) for q_ in (2.5, 97.5)], "note": "bootstrap of the encoder score minus the recorded sparse score; not paired"}}
json.dump(out, open(f"runs/pulse/finetune3_{TAG}.json", "w"), indent=1); print("DONE", json.dumps(out)[:900], flush=True)
