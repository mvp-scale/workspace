import json, glob, re, pickle, pathlib, sys, time, os, numpy as np, scipy.sparse as sp, warnings, torch
warnings.filterwarnings("ignore"); os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb, gpu_lr as G
from sentence_transformers import SentenceTransformer
import onnxruntime as ort; from tokenizers import Tokenizer
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hb.beat("t35-truncation", where="[5090]+[CPU]", task="T10", state="running", why="What does cutting the encoder input to fewer tokens cost in quality?", success="64 tokens costs 0.01 or less", next="Ask MM3 about the design", need="Nothing", progress="loading", spent=0.0, cap=0.0)
art = pickle.load(open(H0 / "runs/expert1/expert1_v2.pkl", "rb")); ids_all = json.load(open(H0 / "runs/embeds/bge_small_ids.json")); eid = {i: k for k, i in enumerate(ids_all)}
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
yt = np.array([hk[i]["topic"] for i in trn]); tcl = np.array(sorted(set(yt))); ys = np.array([sn[i]["topic"] for i in vt]); Tt = art["vt"].transform([clean(i) for i in trn]); Tv = art["vt"].transform([clean(i) for i in vt])
rows, yc = [], []
for i in trn:
    for c in hk[i]["conditions"]: rows.append(i); yc.append(c["condition"])
ccl = np.array(sorted(set(yc))); wc = lambda ids: sp.hstack([art["vw"].transform([clean(i) for i in ids]), art["vc"].transform([clean(i) for i in ids])]).tocsr()[:, art["keepc"]]
vs = [i for i in test if i in sn and sn[i]["conditions"]]; sset = [{c["condition"] for c in sn[i]["conditions"]} for i in vs]; Xc, Xcv = wc(rows), wc(vs)
need = sorted(set(trn) | set(vt) | set(vs)); st = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda"); tk = Tokenizer.from_file(str(H0 / "runs/embeds/bge_tokenizer.json")); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; sess = ort.InferenceSession(str(H0 / "runs/embeds/bge_small.onnx"), so, providers=["CPUExecutionProvider"])
lat_items = [clean(i) for i in test[:200]]; full_tokens = [len(tk.encode(t).ids) for t in lat_items]
res = {"token_stats_200_items": {"mean": round(float(np.mean(full_tokens)), 1), "p95": int(np.percentile(full_tokens, 95)), "share_over_64": round(float(np.mean(np.array(full_tokens) > 64)), 3), "share_over_128": round(float(np.mean(np.array(full_tokens) > 128)), 3)}, "sweep": {}}
for L in (32, 48, 64, 96, 128, 256):
    st.max_seq_length = L; E = {i: None for i in need}; M = st.encode([clean(i) for i in need], batch_size=256, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32) * 1.5; pos_ = {i: k for k, i in enumerate(need)}
    g = lambda ids: M[[pos_[i] for i in ids]]
    mt = G.fit(Tt, g(trn), np.searchsorted(tcl, yt), len(tcl), C=3.0); P = G.predict(mt, Tv, g(vt)); t = np.argsort(-P, 1)[:, :2]
    topic = {"top1": round(float(np.mean(tcl[t[:, 0]] == ys)), 3), "top2": round(float(np.mean([ys[k] in set(tcl[t[k]]) for k in range(len(vt))])), 3)}
    mc = G.fit(Xc, g(rows), np.searchsorted(ccl, yc), len(ccl), C=3.0); Pc = G.predict(mc, Xcv, g(vs)); tc = np.argsort(-Pc, 1)[:, :2]
    cond = {"top1": round(float(np.mean([ccl[tc[k, 0]] in sset[k] for k in range(len(vs))])), 3), "top2": round(float(np.mean([bool({ccl[tc[k, 0]], ccl[tc[k, 1]]} & sset[k]) for k in range(len(vs))])), 3)}
    ts = []
    for tx in lat_items:
        e = tk.encode(tx); idv = np.array([e.ids[:L - 1] + [e.ids[-1]] if len(e.ids) > L else e.ids], dtype=np.int64); a = time.perf_counter(); sess.run(None, {"input_ids": idv, "attention_mask": np.ones_like(idv)}); ts.append((time.perf_counter() - a) * 1000)
    res["sweep"][str(L)] = {"topic": topic, "condition": cond, "onnx_encoder_ms": {"p50": round(float(np.percentile(ts, 50)), 1), "p95": round(float(np.percentile(ts, 95)), 1)}}
    json.dump(res, open(H0 / "runs/snapshots/loop20_results.json", "w"), indent=1); hb.beat("t35-truncation", progress=f"max tokens {L} done")
print(json.dumps(res, indent=1)); hb.finish("t35-truncation", "done", last="; ".join(f"{k}: topic2 {v['topic']['top2']} cond1 {v['condition']['top1']} p95 {v['onnx_encoder_ms']['p95']}ms" for k, v in res["sweep"].items()), progress="6 lengths")
