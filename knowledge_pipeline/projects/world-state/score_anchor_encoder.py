"""T71: the T56 encoder and the live v6b-student on the same MN-DS human-labelled items (outside truth, lenient topic mapping), top-2 topic. Paired.
    /workspace/models/embed-zs/.venv/bin/python score_anchor_encoder.py   (from projects/world-state; CPU only) -> runs/pulse/anchor_encoder_vs_v6b.json"""
import os, sys, json, math, time
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
sys.path.insert(0, "."); from expert1_runtime import ExpertS
torch.set_num_threads(4); M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; A = "/workspace/data/anchors/mn_ds/"
ck = torch.load("runs/expert1/leaf_ft_cpu2_best.pt"); TOP = ck["topics"]
n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); enc.load_state_dict(ck["enc"]); enc.eval()
W = ck["heads"]["topic.weight"]; B = ck["heads"]["topic.bias"]
def enc_top2(texts):
    out = []
    with torch.no_grad():
        for k in range(0, len(texts), 64):
            x = tok(texts[k:k + 64], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); e = (h * m).sum(1) / m.sum(1)
            lo = e @ W.T + B; out += [[TOP[j] for j in r.topk(2).indices.tolist()] for r in lo]
    return out
v6 = ExpertS("runs/expert1/expert1_v6b_student.pkl")
def wil(k, n_, z=1.96):
    p = k / n_; d = 1 + z * z / n_; c = (p + z * z / (2 * n_)) / d; h = z * math.sqrt(p * (1 - p) / n_ + z * z / (4 * n_ * n_)) / d; return [round(c - h, 3), round(c + h, 3)]
res = {"judge": "MN-DS human topic labels through topic_to_iptc_v1 (lenient: the gold category is among the mapped categories of either of the top two guesses); v6b abstains count as wrong", "sets": {}}
for name, it, gd in (("fresh", "items_fresh.jsonl", "gold_fresh.json"), ("fresh2", "items_fresh2.jsonl", "gold_fresh2.json")):
    G = json.load(open(A + gd)); items = [json.loads(l) for l in open(A + it)]; items = list({x["id"]: x for x in items}.values()); items = [x for x in items if x["id"] in G]; texts = [x["text"] for x in items]
    et = enc_top2(texts); ok_e = np.array([any(G[x["id"]]["l1"] in M.get(t, []) for t in tt) for x, tt in zip(items, et)])
    ok_v = np.array([bool((r := v6.read(x["text"])["topic_top2"])["answer"] and any(G[x["id"]]["l1"] in M.get(t, []) for t in r["answer"])) for x in items])
    rg = np.random.default_rng(0); d = [ok_e[ix].mean() - ok_v[ix].mean() for ix in (rg.integers(0, len(items), len(items)) for _ in range(1000))]
    res["sets"][name] = {"n": len(items), "encoder_top2": round(float(ok_e.mean()), 4), "encoder_ci95": wil(int(ok_e.sum()), len(items)), "v6b_top2": round(float(ok_v.mean()), 4), "v6b_ci95": wil(int(ok_v.sum()), len(items)), "paired_diff": round(float(ok_e.mean() - ok_v.mean()), 4), "paired_diff_ci95": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]}
json.dump(res, open("runs/pulse/anchor_encoder_vs_v6b.json", "w"), indent=1); print(json.dumps(res["sets"]))
