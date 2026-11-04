"""Runtime tests for expert 1 (any version; pass the artefact path). Run: /workspace/models/embed-zs/.venv/bin/python test_runtime.py  (exit 0 = all pass)"""
import sys, json, numpy as np, pathlib
sys.path.insert(0, "."); from expert1_runtime import Expert3
import sys; P = sys.argv[1] if len(sys.argv) > 1 else "runs/expert1/expert1_v31.pkl"; e = Expert3(P); fails = []
def check(name, ok, info=""): print(("PASS " if ok else "FAIL ") + name, info); (None if ok else fails.append(name))
for t in ("", "a", "x" * 30, None):
    r = e.read(t); check(f"short or empty input {t!r:.12} returns unknown on every field", all(r[k]["status"] == "unknown" for k in ("story_type", "topic_top2", "condition_present")) and r.get("path") == "linear")
long_text = "Prices rose 10% in Cairo as protests spread across the city. Officials said the rise was temporary and blamed fuel costs. " * 6
r = e.read(long_text); check("long text answers all three base fields", all(r[k]["status"] in ("answered", "unknown") for k in ("story_type", "topic_top2", "condition_present")) and "path" in r)
check("condition fields appear only when presence is answered and true", all(("condition" not in x) or (x["condition_present"]["status"] == "answered" and x["condition_present"]["answer"]) for x in [e.read(long_text), e.read("Local council opens a new library on Main Street after two years of work and a public vote.")]))
check("encoder length is recorded in the artefact", e.M["enc_max_tokens"] == 64, e.M["enc_max_tokens"])
import os; _tag = os.path.basename(e.M["onnx_path"])[:-5] if "onnx_path" in e.M else None; EB = np.load(f"runs/embeds/{_tag}_64_fp32.npy" if _tag else "runs/embeds/bge_small_64.npy");   # the reference vectors belong to the artefact's own encoder
ids = json.load(open("runs/embeds/bge_small_ids.json")); pool = {json.loads(l)["id"]: json.loads(l) for l in open("data/pool_train.jsonl")}
cs = [float((e.embed(pool[ids[k]]["text"]) / 1.5) @ EB[k]) for k in range(0, 3000, 100)]; check("runtime embedding equals the 64-token sentence-transformers vector (cosine 0.9999+)", min(cs) >= 0.9999, round(min(cs), 6))
check("torch is not loaded by the serving path", "torch" not in sys.modules)
try:
    import pickle; M = pickle.load(open(P, "rb")); M.pop("enc_max_tokens"); open("/tmp/_no_len.pkl", "wb").write(pickle.dumps(M)); Expert3("/tmp/_no_len.pkl"); check("missing enc_max_tokens is refused", False)
except ValueError: check("missing enc_max_tokens is refused", True)
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"); sys.exit(1 if fails else 0)
