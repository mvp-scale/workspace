"""B3b (ledger T18, prediction L419): claim-aware pair builder (similar claim sentences from different articles, two cosine bands) + NLI xsmall fp32 vs int8 (torch dynamic quantisation) vs local Clef. Local only; sentence text is never written.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python claim_pairs.py"""
import os, sys, re, json, time, random, sqlite3, collections, urllib.request, concurrent.futures as cf, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
import spacy
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
MODEL = "cross-encoder/nli-deberta-v3-xsmall"; R = random.Random(33)
L = [json.loads(l) for l in open("runs/tag_head/labels.jsonl")]; db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
text = {}; tagset = {}
for r in L:
    row = db.execute("select title, body from items where id = ?", (r["id"][2:],)).fetchone()
    if not row or not row[0] or not row[1]: continue
    text[r["id"]] = row[0].strip() + ". " + re.sub(r"\s+", " ", row[1]).strip()[:3500]; tagset[r["id"]] = {c for c, a in zip(r["cands"], r["ans"]) if sum(x >= 0.5 for x in a) >= 2}
nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"]); S = []; art = []; t0 = time.time()
for i, d in zip(text, nlp.pipe(text.values(), batch_size=32, n_process=4)):
    for s in d.sents:
        t = s.text.strip()
        if not 50 <= len(t) <= 250: continue
        subj = any(w.dep_ in ("nsubj", "nsubjpass") and w.head.pos_ in ("VERB", "AUX") for w in s); fact = bool(s.ents) or any(w.like_num for w in s)
        if subj and fact: S.append(t); art.append(i)
print("claim sentences", len(S), "from", len(set(art)), "articles", f"{time.time() - t0:.0f}s", flush=True)
enc = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cpu"); enc.max_seq_length = 128; E = enc.encode(S, batch_size=128, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
aid = np.array([hash(a) for a in art]); best = []
for k in range(0, len(S), 2000):
    M = E[k:k + 2000] @ E.T; M[aid[k:k + 2000, None] == aid[None, :]] = -1; j = M.argmax(1); best += [(k + n, int(j[n]), float(M[n, j[n]])) for n in range(len(j))]
seen = set(); cand = []
for i, j, c in sorted(best, key=lambda x: -x[2]):
    key = (min(i, j), max(i, j))
    if key in seen or S[i] == S[j] or c >= 0.97: continue
    seen.add(key); cand.append((i, j, c))
print("candidate pairs", len(cand), "cos>=0.75:", sum(c >= 0.75 for _, _, c in cand), "0.55-0.75:", sum(0.55 <= c < 0.75 for _, _, c in cand), flush=True)
pairs = []; use = collections.Counter()
for band, lo, hi in (("high", 0.75, 0.97), ("mid", 0.55, 0.75)):
    pool = [x for x in cand if lo <= x[2] < hi]; R.shuffle(pool); n = 0
    for i, j, c in pool:
        if use[art[i]] >= 2 or use[art[j]] >= 2: continue
        use[art[i]] += 1; use[art[j]] += 1; pairs.append({"kind": band, "cos": round(c, 3), "a": S[i], "b": S[j]}); n += 1
        if n == 150: break
ids = list(text)
while sum(p["kind"] == "control" for p in pairs) < 100:
    a, b = R.sample(ids, 2)
    if tagset[a] & tagset[b]: continue
    ia = [n for n, x in enumerate(art) if x == a]; ib = [n for n, x in enumerate(art) if x == b]
    if ia and ib: pairs.append({"kind": "control", "cos": 0, "a": S[R.choice(ia)], "b": S[R.choice(ib)]})
print("pairs", collections.Counter(p["kind"] for p in pairs), flush=True)
torch.set_num_threads(1); tok = AutoTokenizer.from_pretrained(MODEL); m32 = AutoModelForSequenceClassification.from_pretrained(MODEL, dtype=torch.float32).eval(); m8 = torch.quantization.quantize_dynamic(m32, {torch.nn.Linear}, dtype=torch.qint8); lab = [m32.config.id2label[i].lower() for i in range(3)]
lat = {"fp32": [], "int8": []}
for p in pairs:
    e = tok(p["a"], p["b"], return_tensors="pt", truncation=True, max_length=256)
    for name, m in (("fp32", m32), ("int8", m8)):
        t1 = time.time()
        with torch.no_grad(): lg = m(**e).logits[0]
        lat[name].append((time.time() - t1) * 1000); p[name] = lab[int(lg.argmax())]
Q = {"same": "Does statement B say the same thing as statement A?", "opp": "Does statement B say the opposite of statement A?"}
def ask(p):
    body = {"state": f"Statement A: {p['a']}\nStatement B: {p['b']}", "questions": {k: {"type": "noul", "instructions": v} for k, v in Q.items()}, "model": "clef-flash-q4km"}
    for _ in range(3):
        try: a = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600))["answers"]; return {k: float(v["noul"]) for k, v in a.items()}
        except Exception: time.sleep(2)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: A = list(ex.map(ask, pairs))
print(f"clef {time.time() - t0:.0f}s", flush=True)
for p, a in zip(pairs, A): p["clef"] = None if a is None else ("contradiction" if a["opp"] >= 0.5 else ("entailment" if a["same"] >= 0.5 else "neutral"))
ok = [p for p in pairs if p["clef"]]; res = {"model": MODEL, "clef_errors": len(pairs) - len(ok), "claim_sentences": len(S), "ms_per_pair": {k: {"p50": round(float(np.percentile(v, 50)), 1), "p95": round(float(np.percentile(v, 95)), 1)} for k, v in lat.items()}, "flip_int8_vs_fp32": round(float(np.mean([p["fp32"] != p["int8"] for p in ok])), 3), "bands": {}}
for band in ("high", "mid", "control"):
    s = [p for p in ok if p["kind"] == band]; out = {"n": len(s), "cos_mean": round(float(np.mean([p["cos"] for p in s])), 3), "clef": dict(collections.Counter(p["clef"] for p in s))}
    cn = [p for p in s if p["clef"] != "neutral"]; out["clef_nonneutral_share"] = round(len(cn) / max(1, len(s)), 3); out["n_clef_contradiction"] = sum(p["clef"] == "contradiction" for p in s)
    for name in ("fp32", "int8"):
        nn = [p for p in s if p[name] != "neutral"]
        out[name] = {"labels": dict(collections.Counter(p[name] for p in s)), "agreement_3class": round(float(np.mean([p["clef"] == p[name] for p in s])), 3), "precision_nonneutral": round(float(np.mean([p["clef"] == p[name] for p in nn])), 3) if nn else None, "recall_clef_nonneutral": round(float(np.mean([p["clef"] == p[name] for p in cn])), 3) if cn else None, "false_contradiction_share": round(float(np.mean([p[name] == "contradiction" for p in s])), 3)}
    res["bands"][band] = out
os.makedirs("runs/snapshots", exist_ok=True); json.dump(res, open("runs/snapshots/claim_pairs.json", "w"), indent=1); print(json.dumps(res, indent=1))
