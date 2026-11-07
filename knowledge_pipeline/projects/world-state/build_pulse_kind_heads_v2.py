"""T35 v2 (kinds admitted by the L934 rule: disruption and job_security added): build the per kind condition heads and the biodiversity_loss direction head served by probes/pulse_reader.py (spec ledger L890 to L898, pre-registered L899).
Recipes copied from perkind_condition_cv.py (kind heads: logistic C=3 balanced on the v6b-student embedding, threshold = best F1 on a fixed 20 percent hold, seed 0) and biodiv_direction.py (direction: logistic C=1 balanced, down=1, all Sonnet labelled items).
Labels: Sonnet ws-v2-frozen only (agreement between two Claude labellers, no outside truth set, L896). Weights are fit on the 80 percent part so the stored threshold belongs to the stored weights.
Output: runs/expert1/pulse_kind_heads_v2.npz and pulse_kind_heads_v1.json (sha256 of the npz, counts, hold figures).
    /workspace/models/embed-zs/.venv/bin/python -I build_pulse_kind_heads_v2.py   (from projects/world-state; CPU, about 6 minutes)"""
import json, re, glob, hashlib, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
KINDS = ["air_pollution", "biodiversity_loss", "civil_unrest", "cyber_insecurity", "disruption", "job_security"]; DIR_KIND = "biodiversity_loss"
OUT = "runs/expert1/pulse_kind_heads_v2"; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = set(r["kinds"])
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
dq = [r["id"] for r in J("runs/pulse/devq_items.jsonl") if r["id"] in S]; dqs = set(dq)
tr = sorted(i for i in S if i in pool and i not in dqs); allid = tr + dq; print("items", len(allid), "(train", len(tr), "devq", len(dq), ")", flush=True)
E = np.array([emb(pool[i]) for i in allid], dtype=np.float32); print("embedded", E.shape, flush=True)
r = np.random.RandomState(0).permutation(len(allid)); c = int(0.8 * len(allid)); fa, ha = r[:c], r[c:]
W, B, T, meta = [], [], [], {}
for k in KINDS:
    y = np.array([int(k in S[i]) for i in allid]); m = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(E[fa], y[fa]); ph = m.predict_proba(E[ha])[:, 1]; best, thr = 0, 0.5
    for t in np.linspace(0.1, 0.95, 35):
        p = ph >= t; f = 2 * int((p & (y[ha] == 1)).sum()) / max(int(p.sum()) + int(y[ha].sum()), 1)
        if f > best: best, thr = f, float(t)
    W.append(m.coef_[0]); B.append(m.intercept_[0]); T.append(thr); meta[k] = {"positives_all": int(y.sum()), "positives_hold": int(y[ha].sum()), "hold_f1_vs_sonnet": round(best, 3), "threshold": round(thr, 4)}; print(k, meta[k], flush=True)
# direction head (biodiversity_loss): Sonnet ws-v2-frozen direction labels, same item selection as biodiv_direction.py
D = {}
for f in glob.glob("runs/**/labels.jsonl", recursive=True):
    if "label_store" in f: continue
    for rec in J(f):
        pv = rec.get("provenance") or {}; mo = pv.get("model", ""); v = pv.get("prompt_version", "")
        cc = {x["condition"]: x["direction"] for x in (rec.get("label") or {}).get("conditions", [])}
        if DIR_KIND in cc and "sonnet" in mo and v == "ws-v2-frozen": D[rec["item_id"]] = cc[DIR_KIND]
dids = sorted(i for i in D if i in pool); idx = {i: n for n, i in enumerate(allid)}
Ed = np.array([E[idx[i]] if i in idx else emb(pool[i]) for i in dids], dtype=np.float32); yd = np.array([int(D[i] == "down") for i in dids])
dm = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(Ed, yd)
meta["direction_" + DIR_KIND] = {"items": len(dids), "down": int(yd.sum()), "up": int((1 - yd).sum()), "labels": "down=1, up=0", "train_accuracy_not_a_score": round(float((dm.predict(Ed) == yd).mean()), 3), "cv_score": "runs/pulse/biodiv_direction.json (L898)"}; print(meta["direction_" + DIR_KIND], flush=True)
np.savez(OUT + ".npz", kinds=np.array(KINDS), W=np.array(W, dtype=np.float32), b=np.array(B, dtype=np.float32), thr=np.array(T, dtype=np.float32), dir_kind=np.array(DIR_KIND), dir_W=dm.coef_[0].astype(np.float32), dir_b=np.array(dm.intercept_[0], dtype=np.float32))
sha = hashlib.sha256(open(OUT + ".npz", "rb").read()).hexdigest()
json.dump({"name": "pulse_kind_heads_v2", "npz": OUT.split("/")[-1] + ".npz", "sha256": sha, "embedding": "runs/embeds/student_v6b-student.onnx, runs/embeds/leaf_tokenizer.json, 64 tokens (the v6b-student embedding)", "labels": "Sonnet ws-v2-frozen; agreement between two Claude labellers, no outside truth set (L896); size dropped (L895)",
           "recipe": "perkind_condition_cv.py and biodiv_direction.py", "hold": "20 percent of all labelled items, RandomState(0).permutation, weights fit on the other 80 percent", "items": len(allid), "kinds": meta}, open(OUT + ".json", "w"), indent=1)
print("saved", OUT, sha)
