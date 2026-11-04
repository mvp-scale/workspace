"""T20 Phase C: export a fine-tuned student (ft_<tag>.pt) to ONNX in the same interface as runs/embeds/leaf.onnx (inputs input_ids, attention_mask; output emb, batch x 1024), check it against torch, and measure CPU speed on one thread. Registers heartbeat t20-export.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python export_student.py B_e16lr5"""
import os, sys, json, time, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live"); import heartbeat as hb
TAG = sys.argv[1]; PHASE = sys.argv[2] if len(sys.argv) > 2 else "all"
if PHASE == "convert":
    import torch
    ts = torch.jit.load(f"runs/pulse/ceiling/student_{TAG}.pt", map_location="cpu"); ids = torch.randint(5, 3000, (2, 12)); am = torch.ones(2, 12, dtype=torch.long)
    torch.onnx.export(ts, (ids, am), f"runs/pulse/ceiling/student_{TAG}.onnx", dynamo=False, opset_version=17, dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}, "emb": {0: "b"}}, input_names=["input_ids", "attention_mask"], output_names=["emb"]); print("converted"); sys.exit(0)
hb.beat("t20-export", pid=os.getpid(), where="[CPU] + [5090]", task="T20", state="running", progress=f"exporting student {TAG} to ONNX and timing it", why="Does the fine-tuned student keep the CPU speed budget (same size as leaf)? Overnight Phase C step 3.", success="ONNX matches torch (cosine 0.999+) and encoder p95 within 20% of leaf.onnx", next="Build the v6-student challenger and score it", need="Nothing", cap=3600)
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
m = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cpu"); m.max_seq_length = 64; ck = torch.load(f"runs/pulse/ceiling/ft_{TAG}.pt", map_location="cpu"); (m.load_state_dict(ck["st_full"]) if "st_full" in ck else m[0].auto_model.load_state_dict(ck["model"])); m.eval()
class Wrap(torch.nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, input_ids, attention_mask): return s.m({"input_ids": input_ids, "attention_mask": attention_mask})["sentence_embedding"]
w = Wrap(m).eval(); tok = m.tokenizer; texts = [json.loads(l)["text"] for l in open("runs/pulse/devq_items.jsonl")][:400]
b = tok(texts[:2], padding=True, truncation=True, max_length=64, return_tensors="pt"); out = f"runs/pulse/ceiling/student_{TAG}.onnx"
if PHASE == "trace":
    with torch.no_grad(): ts = torch.jit.trace(w, (b["input_ids"], b["attention_mask"]), check_trace=False)
    ts.save(f"runs/pulse/ceiling/student_{TAG}.pt"); print("traced"); hb.finish("t20-export", "done", last="traced; convert in the verdict environment next"); sys.exit(0)
import onnxruntime as ort
def sess(p): so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; return ort.InferenceSession(p, so, providers=["CPUExecutionProvider"])
new = sess(out); old = sess("runs/embeds/leaf.onnx")
def run(s, t): e = tok([t], truncation=True, max_length=64, return_tensors="np"); return s.run(None, {"input_ids": e["input_ids"].astype(np.int64), "attention_mask": e["attention_mask"].astype(np.int64)})[0][0]
cos = []
for t in texts[:50]:
    e = tok([t], truncation=True, max_length=64, return_tensors="pt")
    with torch.no_grad(): v = w(e["input_ids"], e["attention_mask"])[0].numpy()
    o = run(new, t); cos.append(float(v @ o / (np.linalg.norm(v) * np.linalg.norm(o))))
def timeit(s):
    for t in texts[:20]: run(s, t)
    ts = []
    for t in texts:
        a = time.perf_counter(); run(s, t); ts.append((time.perf_counter() - a) * 1000)
    return {"p50": round(float(np.percentile(ts, 50)), 2), "p95": round(float(np.percentile(ts, 95)), 2), "mean": round(float(np.mean(ts)), 2)}
res = {"student": TAG, "onnx_mb": round(os.path.getsize(out) / 1e6, 1), "cosine_vs_torch_min": round(min(cos), 5), "cosine_mean": round(float(np.mean(cos)), 5), "student_ms_one_thread": timeit(new), "leaf_ms_one_thread": timeit(old), "texts": len(texts)}
json.dump(res, open(f"runs/pulse/export_{TAG}.json", "w"), indent=1); print(json.dumps(res)); hb.finish("t20-export", "done", last=f"student p50 {res['student_ms_one_thread']['p50']} ms vs leaf {res['leaf_ms_one_thread']['p50']} ms; cosine min {res['cosine_vs_torch_min']}")
