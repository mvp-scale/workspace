"""Embed the pool with a sentence-transformers trunk (frozen, normalised, 64-token cap) and export its ONNX encoder as ONE pooled vector, wrapping the model's own modules (transformer, pooling, optional dense).
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python trunk_embed.py <hf id> <tag>      local GPU about 1 min, ONNX export on CPU. Outputs runs/embeds/<tag>_64_fp32.npy, <tag>.onnx, <tag>_tokenizer.json"""
import os, sys, json, re, time, numpy as np, torch
sys.path.append("/workspace/models/onnx-export-pkgs")   # onnxscript for the dynamo exporter
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
RID, TAG = sys.argv[1], sys.argv[2]; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
ids = json.load(open("runs/embeds/bge_small_ids.json")); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; out = f"runs/embeds/{TAG}_64_fp32.npy"
txt = lambda i: re.sub(r"\s+", " ", pool[i]["text"])[:1200]
if not os.path.exists(out):
    st = SentenceTransformer(RID, device="cuda", model_kwargs={"dtype": torch.float32}); st.max_seq_length = 64; t0 = time.time()
    E = st.encode([txt(i) for i in ids], batch_size=256, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32); np.save(out, E); print("embedded", E.shape, f"{time.time() - t0:.0f}s", flush=True); del st; torch.cuda.empty_cache()
st = SentenceTransformer(RID, device="cpu", model_kwargs={"dtype": torch.float32}); st.max_seq_length = 64; st.eval()
for m in st._modules.values():
    if hasattr(m, "auto_model"): m.auto_model.config._attn_implementation = "eager"
class Wrap(torch.nn.Module):
    def __init__(s, st): super().__init__(); s.mods = torch.nn.ModuleList(list(st._modules.values()))
    def forward(s, input_ids, attention_mask):
        f = {"input_ids": input_ids, "attention_mask": attention_mask}
        for m in s.mods: f = m(f)
        return f["sentence_embedding"]
w = Wrap(st).eval(); tok = st.tokenizer; b = tok([txt(ids[0])[:300], txt(ids[1])[:300]], padding=True, truncation=True, max_length=64, return_tensors="pt"); p = f"runs/embeds/{TAG}.onnx"
from torch.export import Dim
bd, sd = Dim("b", min=1, max=64), Dim("s", min=2, max=256)
torch.onnx.export(w, (b["input_ids"], b["attention_mask"]), dynamo=True, dynamic_shapes={"input_ids": {0: bd, 1: sd}, "attention_mask": {0: bd, 1: sd}}, input_names=["input_ids", "attention_mask"], output_names=["emb"]).save(p)
tok.backend_tokenizer.save(f"runs/embeds/{TAG}_tokenizer.json")
import onnxruntime as ort
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; sess = ort.InferenceSession(p, so, providers=["CPUExecutionProvider"]); torch.set_num_threads(1); E = np.load(out, mmap_mode="r"); cos = []; ms = []
for k in range(2, 62):
    e = tok([txt(ids[k])], truncation=True, max_length=64, return_tensors="np"); a = time.perf_counter(); v = sess.run(None, {"input_ids": e["input_ids"].astype(np.int64), "attention_mask": e["attention_mask"].astype(np.int64)})[0]; ms.append((time.perf_counter() - a) * 1000); v = v / np.linalg.norm(v, axis=1, keepdims=True); cos.append(float((v[0] * E[k]).sum()))
res = {"model": RID, "onnx_mb": round(os.path.getsize(p) / 1e6, 1), "min_cosine_onnx_vs_saved_gpu_embedding": round(min(cos), 5), "onnx_ms_one_thread_p50": round(float(np.percentile(ms[2:], 50)), 1), "onnx_ms_one_thread_p95": round(float(np.percentile(ms[2:], 95)), 1)}
json.dump(res, open(f"runs/snapshots/{TAG}_onnx.json", "w"), indent=1); print(json.dumps(res, indent=1))
