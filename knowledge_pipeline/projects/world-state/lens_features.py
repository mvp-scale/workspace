"""Lens linkage features (owner idea 2026-11-05, added to the L942 plan): for each story, embed the title (first sentence), the lead (second sentence), the snapshot (first 250 characters), every sentence of the first 600 characters and the whole 600 characters, then measure how well the lenses agree: cosine of title with lead, snapshot, whole and each sentence, the share of sentences close to the title (topical density), and TF-IDF overlap of title with the rest. 12 dense features per story. Unlabelled text only.
    /workspace/models/embed-zs/.venv/bin/python lens_features.py   (from projects/world-state)"""
import json, re, time, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = 1
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
z = np.load("runs/pulse/kind_cascade_emb.npz"); assert list(z["ids"]) == ids; EW = z["E1"]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 2
sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(t); i = np.array([e.ids], dtype=np.int64); v = sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]; return v / (np.linalg.norm(v) + 1e-9)
tf = TfidfVectorizer(stop_words="english", min_df=3).fit(T); cos = lambda a, b: float(a @ b)
def lex(a, b):
    if not a or not b: return 0.0
    va, vb = tf.transform([a]), tf.transform([b]); return float((va @ vb.T).toarray()[0, 0])
F = np.zeros((len(ids), 12), np.float32); t0 = time.time()
for n, t in enumerate(T):
    ss = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'])", t) if len(s) > 15][:5] or [t[:120]]; title = ss[0]; lead = ss[1] if len(ss) > 1 else ""
    et = emb(title); el = emb(lead) if lead else None; es = emb(t[:250]); ew = EW[n] / (np.linalg.norm(EW[n]) + 1e-9); sims = [cos(et, emb(s)) for s in ss[1:]]
    rest = " ".join(ss[1:]); tw = set(w for w in re.findall(r"[a-z]{4,}", title.lower())); rw = set(re.findall(r"[a-z]{4,}", rest.lower()))
    F[n] = [cos(et, el) if el is not None else 0, cos(et, es), cos(et, ew), cos(el, ew) if el is not None else 0, np.mean(sims) if sims else 0, max(sims) if sims else 0, min(sims) if sims else 0, (np.mean([s >= 0.6 for s in sims]) if sims else 0), len(ss) / 5, lex(title, rest), len(tw & rw) / max(len(tw), 1), lex(title, lead)]
    if n % 3000 == 0: print("lens", n, round(time.time() - t0), "s", flush=True)
np.savez("runs/pulse/lens_features.npz", ids=np.array(ids), F=F, names=np.array(["cos_title_lead", "cos_title_snapshot", "cos_title_whole", "cos_lead_whole", "mean_cos_title_sentences", "max_cos_title_sentences", "min_cos_title_sentences", "density_close_to_title", "sentence_count", "tfidf_title_rest", "title_terms_in_rest", "tfidf_title_lead"])); print("saved", F.shape, flush=True)
