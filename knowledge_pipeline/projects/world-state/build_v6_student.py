"""T20: build the v6-student challenger artefact (ledger L474). Uses the fine-tuned student ft_B_e16lr5 (full state), its ONNX export and linear heads; fits the presence stack and cuts on DEVQ + old only (DEVQ2 stays a clean holdout). CPU, local.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python build_v6_student.py"""
import os, sys, json, glob, shutil, pickle, numpy as np, torch, onnxruntime as ort
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, ".")
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
TAG = sys.argv[1] if len(sys.argv) > 1 else "B_e16lr5"; VER = sys.argv[2] if len(sys.argv) > 2 else "v6-student"; TR = "--tranche" in sys.argv; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb")); ck = torch.load(f"runs/ceiling_dummy" if False else f"runs/pulse/ceiling/ft_{TAG}.pt", map_location="cpu"); Hd = {k: v.float().numpy() for k, v in ck["heads"].items()}
# class lists exactly as in finetune_distill.py (no tranche)
M = json.load(open("runs/pulse/ceiling/main_ids.json")); ids = M["ids"]; nt = M["n_train"]; hk = {}; sn = {}; dsn = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}
for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl") + (glob.glob("runs/pulse/tranche/c*/labels.jsonl") if TR else []):
    for r in J(f): sn[r["item_id"]] = r["label"]
lab = [sn.get(i, hk[i]) for i in ids[:nt]]; story_cl = sorted({l["story_type"] for l in lab} | {l["story_type"] for l in dsn.values()}); topic_cl = sorted({l["topic"] for l in lab} | {l["topic"] for l in dsn.values()}); cond_cl = sorted({c["condition"] for l in lab for c in l["conditions"]})
assert Hd["s.weight"].shape[0] == len(story_cl) and Hd["t.weight"].shape[0] == len(topic_cl) and Hd["c.weight"].shape[0] == len(cond_cl), (Hd["s.weight"].shape, len(story_cl), Hd["t.weight"].shape, len(topic_cl), Hd["c.weight"].shape, len(cond_cl))
assert list(cond_cl) == [c for c in art["enc_heads"]["cond"]["classes"]] or set(cond_cl) == set(art["cond"].classes_), "condition set differs from v5"
shutil.copy(f"runs/pulse/ceiling/student_{TAG}.onnx", f"runs/embeds/student_{VER}.onnx"); so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession(f"runs/embeds/student_{VER}.onnx", so, providers=["CPUExecutionProvider"]); tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
def emb(text):
    import re; e = tk.encode(re.sub(r"\s+", " ", text)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
raw = json.load(open("runs/pulse/raw_v5-leaf.json")); items = [dict(r, set="devq") for r in raw["devq"]] + [dict(r, set="old") for r in raw["old"]]
E = np.array([emb(pool[r["id"]]) for r in items]); lp = E @ Hd["p.weight"].T + Hd["p.bias"]; zst = lp[:, 1] - lp[:, 0]; zs = np.array([(lg(r["ph"]) + lg(r["ps"])) / 2 for r in items])
y = np.array([bool(r["S"]["conditions"]) for r in items]); w = np.array([r.get("w", 1.0) if r["set"] == "old" else 1.0 for r in items]); X = np.stack([zs, zst], 1)
clf = LogisticRegression(C=10.0, max_iter=1000).fit(X, y, sample_weight=w); stack = [float(clf.coef_[0][0]), float(clf.coef_[0][1]), float(clf.intercept_[0])]; pr = clf.predict_proba(X)[:, 1]
o = np.argsort(-pr); tp = np.cumsum(y[o] * w[o]); n = np.cumsum(w[o]); prec = tp / n; ok = np.where(prec >= 0.83)[0]; cut_yes = float(pr[o][ok.max()]) if len(ok) else 0.9
# which-condition cut: half of the real conditions, running precision 0.80 (as v5 did)
Pc = (E @ Hd["c.weight"].T + Hd["c.bias"]); Pc = np.exp(Pc - Pc.max(1, keepdims=True)); Pc /= Pc.sum(1, keepdims=True); posi = np.where(y)[0]; hit = np.array([cond_cl[Pc[k].argmax()] in [c["condition"] for c in items[k]["S"]["conditions"]] for k in posi]); conf = Pc[posi].max(1)
perm = np.random.RandomState(3).permutation(len(posi)); A_ = perm[:len(posi) // 2]; q = np.argsort(-conf[A_]); run = np.cumsum(hit[A_][q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; cond_cut = float(conf[A_][q][idx.max()]) if len(idx) else 1.01
new = dict(art); new["student"] = {"onnx_path": f"runs/embeds/student_{VER}.onnx", "tok_path": "runs/embeds/leaf_tokenizer.json", "max_tokens": 64, "story_cl": story_cl, "topic_cl": topic_cl, "cond_cl": cond_cl, "stack": stack, "cut_yes": cut_yes, "cond_cut": cond_cut, **{k + "_W": Hd[k + ".weight"] for k in "stpc"}, **{k + "_b": Hd[k + ".bias"] for k in "stpc"}, "source": f"ft_{TAG} (distilled from Qwen3-Embedding-4B, no tranche)"}
pickle.dump(new, open(f"runs/expert1/expert1_{VER.replace('-', '_')}.pkl", "wb")); json.dump({"stack": stack, "cut_yes": cut_yes, "cond_cut": cond_cut, "fit_items": len(items), "fit_positives": int(y.sum())}, open(f"runs/snapshots/build_{VER}.json", "w"), indent=1); print(json.dumps({"stack": stack, "cut_yes": cut_yes, "cond_cut": cond_cut}))
reg = json.load(open("engine_versions.json"))
if not any(r["version"] == VER for r in reg): reg.append({"version": VER, "path": f"runs/expert1/expert1_{VER.replace('-', '_')}.pkl", "class": "ExpertS", "what": f"CHALLENGER. v5-leaf sparse parts + the fine-tuned leaf student {TAG} (distilled from Qwen3-Embedding-4B{', 16,000 Sonnet labels' if TR else ', 6,000 Sonnet labels'}) reading story, topic, presence (stacked with the sparse gate) and which-condition in one ONNX pass", "ms_note": 0}); json.dump(reg, open("engine_versions.json", "w"), indent=1)
