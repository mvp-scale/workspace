"""T59 follow-up: single-thread, batch-of-one latency of the T56 best encoder with its three heads. -> runs/pulse/latency_encoder.json"""
import json, os, time
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
torch.set_num_threads(1); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}); sid = [r["item_id"] for r in J("runs/pulse/sealed/labels.jsonl") if r["item_id"] in txt][:320]
ck = torch.load("runs/expert1/leaf_ft_cpu2_best.pt"); n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); enc.load_state_dict(ck["enc"]); enc.eval(); H = enc.config.hidden_size
hs = torch.nn.ModuleDict({"topic": torch.nn.Linear(H, len(ck["topics"])), "story": torch.nn.Linear(H, len(ck["story_types"])), "pres": torch.nn.Linear(H, 2)}); hs.load_state_dict(ck["heads"]); ts = []
with torch.no_grad():
    for k, i in enumerate(sid):
        t = time.perf_counter(); x = tok(txt[i], max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state.mean(1); [m(h) for m in hs.values()]; dt = (time.perf_counter() - t) * 1000
        if k >= 20: ts.append(dt)
ts = np.array(ts); out = {"threads": 1, "batch": 1, "items_timed": len(ts), "median_ms": round(float(np.median(ts)), 1), "p95_ms": round(float(np.percentile(ts, 95)), 1), "mean_ms": round(float(ts.mean()), 1), "includes": "tokenise + encoder + three heads; excludes model load"}
json.dump(out, open("runs/pulse/latency_encoder.json", "w"), indent=1); print(out)
