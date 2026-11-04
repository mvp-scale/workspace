"""Embed the pool with granite-embedding-small-english-r2 (CLS pooling, normalised, 64-token cap for parity with bge_small_64) and export the ONNX encoder (CLS vector).
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python granite_embed.py      local GPU about 1 min for the embedding, ONNX export on CPU"""
import os, sys, json, re, time, numpy as np, torch
sys.path.append("/workspace/models/onnx-export-pkgs")   # onnxscript for the dynamo exporter (as for bge)
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
RID = "ibm-granite/granite-embedding-small-english-r2"; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
ids = json.load(open("runs/embeds/bge_small_ids.json")); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}
out = "runs/embeds/granite_small_64_fp32.npy"   # fp32 on purpose: transformers 5 loads bf16 by default, which onnxruntime CPU cannot run
if not os.path.exists(out):
    st = SentenceTransformer(RID, device="cuda", model_kwargs={"dtype": torch.float32}); st.max_seq_length = 64; t0 = time.time()
    E = st.encode([re.sub(r"\s+", " ", pool[i]["text"])[:1200] for i in ids], batch_size=256, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
    np.save(out, E); print("embedded", E.shape, f"{time.time() - t0:.0f}s", flush=True); del st; torch.cuda.empty_cache()
from transformers import AutoTokenizer, AutoModel
tok = AutoTokenizer.from_pretrained(RID); m = AutoModel.from_pretrained(RID, attn_implementation="eager", dtype=torch.float32).eval().to("cpu")
class Wrap(torch.nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, input_ids, attention_mask): return s.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]   # CLS vector, as the model's pooling config says
w = Wrap(m); b = tok([pool[ids[0]]["text"][:300], pool[ids[1]]["text"][:300]], padding=True, truncation=True, max_length=64, return_tensors="pt"); p = "runs/embeds/granite_small.onnx"
try:
    from torch.export import Dim
    bd, sd = Dim("b", min=1, max=64), Dim("s", min=2, max=256)
    torch.onnx.export(w, (b["input_ids"], b["attention_mask"]), dynamo=True, dynamic_shapes={"input_ids": {0: bd, 1: sd}, "attention_mask": {0: bd, 1: sd}}, input_names=["input_ids", "attention_mask"], output_names=["cls"]).save(p); how = "dynamo"
except Exception as e:
    print("dynamo export failed:", str(e)[:200], flush=True)
    torch.onnx.export(w, (b["input_ids"], b["attention_mask"]), p, input_names=["input_ids", "attention_mask"], output_names=["cls"], dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}}, opset_version=17, dynamo=False); how = "legacy"
tok.save_pretrained("runs/embeds/granite_tok"); tok.backend_tokenizer.save("runs/embeds/granite_tokenizer.json")
import onnxruntime as ort
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; sess = ort.InferenceSession(p, so, providers=["CPUExecutionProvider"]); torch.set_num_threads(1)
cos = []; ms = []
for k in range(2, 62):
    t = re.sub(r"\s+", " ", pool[ids[k]]["text"])[:1200]; e = tok([t], truncation=True, max_length=64, return_tensors="np"); a = time.perf_counter()
    v = sess.run(None, {"input_ids": e["input_ids"].astype(np.int64), "attention_mask": e["attention_mask"].astype(np.int64)})[0]; ms.append((time.perf_counter() - a) * 1000); v = v / np.linalg.norm(v, axis=1, keepdims=True)
    cos.append(float((v[0] * np.load(out, mmap_mode="r")[k]).sum()))
res = {"export": how, "onnx_mb": round(os.path.getsize(p) / 1e6, 1), "min_cosine_onnx_vs_saved_gpu_embedding": round(min(cos), 5), "onnx_ms_one_thread_p50": round(float(np.percentile(ms[2:], 50)), 1), "onnx_ms_one_thread_p95": round(float(np.percentile(ms[2:], 95)), 1)}
json.dump(res, open("runs/snapshots/granite_onnx.json", "w"), indent=1); print(json.dumps(res, indent=1))
