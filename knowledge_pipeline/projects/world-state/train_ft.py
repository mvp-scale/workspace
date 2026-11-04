"""Pulse 2: multi-task fine-tune of bge-small on the 5090. Fixed settings (L291). Run: /workspace/models/embed-zs/.venv/bin/python train_ft.py"""
import json, glob, re, pathlib, sys, time, os, numpy as np, torch, torch.nn as nn, torch.nn.functional as F
os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
torch.manual_seed(0); np.random.seed(0)
hb.beat("t28-finetune", where="[5090]", task="T10", state="running", why="Does fine-tuning the encoder beat frozen features on every field?", success="Beats tfidf+frozen bge by 0.01+ somewhere", next="Score, quantise, time on CPU", need="Nothing", progress="loading data", spent=0.0, cap=0.0)
hk = {}; sn = {}; old = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"])[:1200]
TOP = sorted({hk[i]["topic"] for i in trn}); ST = sorted({hk[i]["story_type"] for i in trn}); CO = sorted({c["condition"] for i in trn for c in hk[i]["conditions"]}); LV = ["minor", "notable", "major", "severe"]; DR = ["down", "up"]
def targets(i):
    h = hk[i]; cs = h["conditions"]; pres = float(bool(cs))
    if i in sn: pres = (pres + float(bool(sn[i]["conditions"]))) / 2
    mh = np.zeros(len(CO), np.float32)
    for c in cs: mh[CO.index(c["condition"])] = 1
    d = DR.index(cs[0]["direction"]) if cs else -1; s = min(LV.index(cs[0]["level"]) if cs[0]["level"] in LV else 3, 3) if cs else -1
    return TOP.index(h["topic"]), ST.index(h["story_type"]), pres, mh, d, s
tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5"); enc = lambda ids: tok([clean(i) for i in ids], padding=True, truncation=True, max_length=128, return_tensors="pt")
class Net(nn.Module):
    def __init__(s):
        super().__init__(); s.enc = AutoModel.from_pretrained("BAAI/bge-small-en-v1.5"); h = s.enc.config.hidden_size; s.drop = nn.Dropout(0.1)
        s.topic = nn.Linear(h, len(TOP)); s.story = nn.Linear(h, len(ST)); s.pres = nn.Linear(h, 1); s.cond = nn.Linear(h, len(CO)); s.dire = nn.Linear(h, 2); s.size = nn.Linear(h, 4)
    def forward(s, b):
        x = s.enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float(); e = s.drop((x * m).sum(1) / m.sum(1))
        return {"topic": s.topic(e), "story": s.story(e), "pres": s.pres(e).squeeze(-1), "cond": s.cond(e), "dir": s.dire(e), "size": s.size(e)}
dev = "cuda"; net = Net().to(dev); T = [targets(i) for i in trn]; opt = torch.optim.AdamW(net.parameters(), lr=4e-5, weight_decay=0.01); EP, BS = 3, 64; steps = EP * ((len(trn) + BS - 1) // BS)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=4e-5, total_steps=steps, pct_start=0.1, anneal_strategy="linear"); t0 = time.time(); k = 0
for ep in range(EP):
    perm = np.random.permutation(len(trn)); net.train()
    for s in range(0, len(trn), BS):
        ix = perm[s:s + BS]; b = {a: v.to(dev) for a, v in enc([trn[j] for j in ix]).items()}; tg = [T[j] for j in ix]
        yt = torch.tensor([t[0] for t in tg], device=dev); ys = torch.tensor([t[1] for t in tg], device=dev); yp = torch.tensor([t[2] for t in tg], device=dev, dtype=torch.float32); yc = torch.tensor(np.stack([t[3] for t in tg]), device=dev)
        yd = torch.tensor([t[4] for t in tg], device=dev); yz = torch.tensor([t[5] for t in tg], device=dev)
        with torch.autocast("cuda", dtype=torch.bfloat16): out = net(b)
        o_ = {a: v.float() for a, v in out.items()}; L = F.cross_entropy(o_["topic"], yt) + F.cross_entropy(o_["story"], ys) + F.binary_cross_entropy_with_logits(o_["pres"], yp) + F.binary_cross_entropy_with_logits(o_["cond"], yc)
        mk = yd >= 0
        if mk.any(): L = L + F.cross_entropy(o_["dir"][mk], yd[mk]) + F.cross_entropy(o_["size"][mk], yz[mk])
        opt.zero_grad(); L.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step(); sched.step(); k += 1
        if k % 100 == 0: hb.beat("t28-finetune", progress=f"epoch {ep + 1}/{EP} step {k}/{steps} loss {L.item():.3f}")
train_s = time.time() - t0; torch.save(net.state_dict(), H0 / "runs/expert1/ft_bge_small.pt")
@torch.no_grad()
def predict(model, ids, device, bs=128):
    model.eval(); R = {k: [] for k in ("topic", "story", "pres", "cond", "dir", "size")}
    for s in range(0, len(ids), bs):
        b = {a: v.to(device) for a, v in enc(ids[s:s + bs]).items()}; out = model(b)
        for k_ in R: R[k_].append(out[k_].float().cpu())
    return {k_: torch.cat(v).numpy() for k_, v in R.items()}
sig = lambda x: 1 / (1 + np.exp(-x)); P = predict(net, vt, dev)
hp_t = sum(1 for i in test if old[i]["conditions"]); hn_t = len(test) - hp_t; hp_v = sum(1 for i in vt if old[i]["conditions"]); hn_v = len(vt) - hp_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); sy = np.array([1 if sn[i]["conditions"] else 0 for i in vt])
ys_t = np.array([sn[i]["topic"] for i in vt]); ys_s = np.array([sn[i]["story_type"] for i in vt]); T_ = np.array(TOP); t2 = np.argsort(-P["topic"], 1)[:, :2]
res = {"train_items": len(trn), "train_seconds": round(train_s), "topic": {"top1": round(float(np.mean(T_[t2[:, 0]] == ys_t)), 3), "top2": round(float(np.mean([ys_t[k] in set(T_[t2[k]]) for k in range(len(vt))])), 3)}, "story_agree": round(float(np.mean(np.array(ST)[P["story"].argmax(1)] == ys_s)), 3), "presence_weighted_auc": round(float(roc_auc_score(sy, sig(P["pres"]), sample_weight=w)), 4)}
vs = [k for k, i in enumerate(vt) if sn[vt[k]]["conditions"]]; C_ = np.array(CO); ct = np.argsort(-P["cond"], 1)[:, :2]; sset = {k: {c["condition"] for c in sn[vt[k]]["conditions"]} for k in vs}
res["condition_top1_top2_on_sonnet_positive"] = {"n": len(vs), "top1": round(float(np.mean([C_[ct[k, 0]] in sset[k] for k in vs])), 3), "top2": round(float(np.mean([bool({C_[ct[k, 0]], C_[ct[k, 1]]} & sset[k]) for k in vs])), 3)}
dm, wm = [], []
for k in vs:
    pc = C_[ct[k, 0]]
    if pc in sset[k]:
        sc = next(c for c in sn[vt[k]]["conditions"] if c["condition"] == pc); dm.append(DR[P["dir"][k].argmax()] == sc["direction"]); wm.append(abs(int(P["size"][k].argmax()) - min(LV.index(sc["level"]) if sc["level"] in LV else 3, 3)) <= 1)
res["direction_vs_sonnet"] = round(float(np.mean(dm)), 3); res["size_within_one_vs_sonnet"] = round(float(np.mean(wm)), 3); res["n_direction_size_matches"] = len(dm)
json.dump(res, open(H0 / "runs/snapshots/loop15_results.json", "w"), indent=1); hb.beat("t28-finetune", progress="scored; CPU speed and int8")
# CPU serving: single thread fp32 and dynamic int8, p50/p95 and topic top-2 after int8
cpu = Net(); cpu.load_state_dict(torch.load(H0 / "runs/expert1/ft_bge_small.pt", map_location="cpu")); cpu.eval(); q = torch.quantization.quantize_dynamic(cpu, {nn.Linear}, dtype=torch.qint8); torch.set_num_threads(1)
def timed(model, ids):
    ts = []
    with torch.no_grad():
        for i in ids: b = enc([i]); t_ = time.perf_counter(); model(b); ts.append((time.perf_counter() - t_) * 1000)
    return {"p50": round(float(np.percentile(ts, 50)), 1), "p95": round(float(np.percentile(ts, 95)), 1)}
sample = test[:150]; res["cpu_one_thread_ms_fp32"] = timed(cpu, sample); res["cpu_one_thread_ms_int8"] = timed(q, sample)
Pq = predict(q, vt[:600], "cpu", 64); tq = np.argsort(-Pq["topic"], 1)[:, :2]; yq = ys_t[:600]
res["int8_topic_top2_first600"] = round(float(np.mean([yq[k] in set(T_[tq[k]]) for k in range(600)])), 3); res["fp32_topic_top2_first600"] = round(float(np.mean([yq[k] in set(T_[t2[k]]) for k in range(600)])), 3)
json.dump(res, open(H0 / "runs/snapshots/loop15_results.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("t28-finetune", "done", last=f"topic top-2 {res['topic']['top2']}, cond top-1 {res['condition_top1_top2_on_sonnet_positive']['top1']}, int8 p50 {res['cpu_one_thread_ms_int8']['p50']} ms", progress=f"trained in {train_s:.0f}s")
