import os, sys, time, json, re, glob, pathlib, numpy as np, torch
os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
from transformers import AutoTokenizer, AutoModel
import onnxruntime as ort
H0 = pathlib.Path(".").resolve(); tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5"); m = AutoModel.from_pretrained("BAAI/bge-small-en-v1.5").eval()
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; pool = [json.loads(l) for l in open(H0 / "data/pool_train.jsonl")][:3000]; texts = [re.sub(r"\s+", " ", r["text"])[:1200] for r in pool]
class Wrap(torch.nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, input_ids, attention_mask): return s.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]    # bge uses the CLS vector
w = Wrap(m); b = tok(texts[:2], padding=True, truncation=True, max_length=128, return_tensors="pt"); p = H0 / "runs/embeds/bge_small.onnx"
from torch.export import Dim
bd, sd = Dim("b", min=1, max=64), Dim("s", min=2, max=256)
onnx_prog = torch.onnx.export(w, (b["input_ids"], b["attention_mask"]), dynamo=True, dynamic_shapes={"input_ids": {0: bd, 1: sd}, "attention_mask": {0: bd, 1: sd}}, input_names=["input_ids", "attention_mask"], output_names=["cls"]); onnx_prog.save(str(p))
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL; sess = ort.InferenceSession(str(p), so, providers=["CPUExecutionProvider"])
def onnx_emb(t): e = tok([t], truncation=True, max_length=128, return_tensors="np"); v = sess.run(None, {"input_ids": e["input_ids"].astype(np.int64), "attention_mask": e["attention_mask"].astype(np.int64)})[0]; return v / np.linalg.norm(v, axis=1, keepdims=True)
torch.set_num_threads(1)
def torch_emb(t):
    with torch.no_grad(): e = tok([t], truncation=True, max_length=128, return_tensors="pt"); v = m(**e).last_hidden_state[:, 0]; return torch.nn.functional.normalize(v, dim=1).numpy()
S = texts[2000:2200]; to = []; tt = []; cos = []
onnx_emb(S[0]); torch_emb(S[0])
for t in S:
    a = time.perf_counter(); eo = onnx_emb(t); to.append((time.perf_counter() - a) * 1000); a = time.perf_counter(); et = torch_emb(t); tt.append((time.perf_counter() - a) * 1000); cos.append(float((eo * et).sum()))
saved = np.load(H0 / "runs/embeds/bge_small.npy"); ids = json.load(open(H0 / "runs/embeds/bge_small_ids.json")); tok_lens = [len(tok(t, truncation=True, max_length=128)["input_ids"]) for t in S]
res = {"onnx_mb": round(os.path.getsize(p) / 1e6, 1), "onnx_ms_one_thread": {"p50": round(float(np.percentile(to, 50)), 1), "p95": round(float(np.percentile(to, 95)), 1)}, "torch_ms_one_thread": {"p50": round(float(np.percentile(tt, 50)), 1), "p95": round(float(np.percentile(tt, 95)), 1)}, "min_cosine_onnx_vs_torch": round(min(cos), 6), "mean_cosine": round(float(np.mean(cos)), 6), "share_cosine_below_0.999": round(float(np.mean(np.array(cos) < 0.999)), 3), "mean_tokens": round(float(np.mean(tok_lens)), 1), "p95_tokens": int(np.percentile(tok_lens, 95))}
json.dump(res, open(H0 / "runs/snapshots/onnx_bge.json", "w"), indent=1); print(json.dumps(res, indent=1))
