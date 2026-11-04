import json, glob, re, pathlib, sys, os, numpy as np, torch, torch.nn as nn
os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
src = open("train_ft2.py").read(); head = src[:src.index("dev = \"cuda\"; net = Net()")]
exec(head)
cpu = Net(); cpu.load_state_dict(torch.load(H0 / "runs/expert1/ft_bge_small_v2.pt", map_location="cpu")); cpu.eval(); q = torch.quantization.quantize_dynamic(cpu, {nn.Linear}, dtype=torch.qint8); torch.set_num_threads(4)
@torch.no_grad()
def pred(model, ids, bs=64):
    R = []
    for s in range(0, len(ids), bs): R.append(model(enc(ids[s:s + bs]))["topic"].float().numpy())
    return np.concatenate(R)
ys = np.array([sn[i]["topic"] for i in vt]); T_ = np.array(TOP); out = {}
for nm, m in (("fp32", cpu), ("int8", q)):
    P = pred(m, vt); t = np.argsort(-P, 1)[:, :2]; out[nm] = {"top1": round(float(np.mean(T_[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(T_[t[k]]) for k in range(len(vt))])), 3)}
out["drop_top2"] = round(out["fp32"]["top2"] - out["int8"]["top2"], 3); out["gate_Q22_limit"] = 0.01; json.dump(out, open("runs/snapshots/int8_check.json", "w"), indent=1); print(out)
