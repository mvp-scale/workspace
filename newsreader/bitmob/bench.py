"""CPU-only, deterministic classifiers for the World engine's story tags, all on one benchmark. Method and bars fixed before running.
Data: Clef-tagged stories (data/newsreader/labels/clef-q4km.jsonl); held-out split = sha256(id) % 5 == 0 (same as train.py / train2.py / route_test.py).
Tags: 78 condition tags (condition x up/down; Clef's readings after read()), plus story tags (happened, announced, opinion, forecast, recent; scope national/local/new).
Scores per method:  replacement = micro precision / recall / F1 of condition tags vs Clef (threshold picked by 5-fold out-of-fold F1 on training stories only);
                    routing = share of Clef's condition tags inside the top-k conditions (k = 8, 12, 20) and the smallest k keeping >= 85%;
                    CPU ms per story. Bars: replacement precision and recall >= 0.85; routing keeps >= 0.85 with as small a shortlist as possible.
No GPU: CUDA_VISIBLE_DEVICES is emptied before anything loads. Seeds fixed.
Run (from /workspace/probes/world-engine): WE_RULES=rules_v2 HF_HOME=/workspace/data/hf python -I /workspace/newsreader/bitmob/bench.py [method ...]"""
import os, sys, json, time, hashlib, re, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.naive_bayes import ComplementNB
from sklearn.model_selection import KFold

OUT = "/workspace/data/newsreader/bitmob"; os.makedirs(OUT, exist_ok=True); RNG = 0
rows = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
is_test = np.array([int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 5 == 0 for r in rows])
PAIRS = sorted({(d, s) for (d, s) in C.ATTRS}); CONDS = sorted({d for d, _ in PAIRS}); PI = {p: i for i, p in enumerate(PAIRS)}
Y = np.zeros((len(rows), len(PAIRS)), bool)
for k, r in enumerate(rows):
    for x in r["readings"]:
        if x["direction"] != "conflict": Y[k, PI[(x["dial"], x["direction"])]] = True
full = [r["title"] + ". " + r["text"] for r in rows]; short = [r["title"] + ". " + " ".join(r["text"].split()[:300]) for r in rows]
tr, te = np.where(~is_test)[0], np.where(is_test)[0]
print(f"{len(rows)} stories: {len(tr)} train, {len(te)} test; {Y.sum()} condition tags ({Y.sum(1).mean():.2f} a story); tags with >= 5 train examples: {(Y[tr].sum(0) >= 5).sum()}/78", flush=True)

# ---------- encoders (cached) ----------
def cache(name, fn):
    f = f"{OUT}/emb_{name}.npy"
    if os.path.exists(f): return np.load(f), json.load(open(f + ".ms"))
    t = time.perf_counter(); V = fn(); ms = (time.perf_counter() - t) * 1000 / len(rows); np.save(f, V); json.dump(ms, open(f + ".ms", "w")); return V, ms
unit = lambda V: V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
def e5_int8():
    import onnxruntime as ort; from tokenizers import Tokenizer; from huggingface_hub import hf_hub_download
    tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); tok.enable_truncation(512)
    o = ort.SessionOptions(); o.intra_op_num_threads = 8; s = ort.InferenceSession("/workspace/data/embed-zs/engine/e5.int8.onnx", o, providers=["CPUExecutionProvider"]); out = []
    for i in range(0, len(short), 32):
        e = tok.encode_batch(["query: " + t for t in short[i:i + 32]]); L = max(len(x.ids) for x in e)
        ids = np.array([x.ids + [0] * (L - len(x.ids)) for x in e], np.int64); m = np.array([x.attention_mask + [0] * (L - len(x.ids)) for x in e], np.int64)
        h = s.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0]; out.append((h * m[..., None]).sum(1) / m.sum(1, keepdims=True))
    return unit(np.concatenate(out))
def st(model, prefix=""):
    def f():
        import torch; torch.set_num_threads(8); from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model, device="cpu").encode([prefix + t for t in short], batch_size=32, normalize_embeddings=True)
    return f
def potion(model):
    def f():
        from model2vec import StaticModel; return unit(np.asarray(StaticModel.from_pretrained(model).encode(full), np.float32))
    return f

# ---------- scoring ----------
def thresholds_oof(fit_score, Xtr, Ytr):
    oof = np.zeros(Ytr.shape)
    for a, b in KFold(5, shuffle=True, random_state=RNG).split(Xtr): oof[b] = fit_score(Xtr[a] if not isinstance(Xtr, list) else [Xtr[i] for i in a], Ytr[a], Xtr[b] if not isinstance(Xtr, list) else [Xtr[i] for i in b])
    grid = np.unique(np.quantile(oof, np.linspace(0.5, 0.9995, 200)))
    f1 = [(2 * ((oof >= t) & Ytr).sum() / max(1, (oof >= t).sum() + Ytr.sum()), t) for t in grid]; return max(f1)[1]
def evaluate(name, fit_score, X, ms):
    Xtr = X[tr] if not isinstance(X, list) else [X[i] for i in tr]; Xte = X[te] if not isinstance(X, list) else [X[i] for i in te]
    t = thresholds_oof(fit_score, Xtr, Y[tr]); S = fit_score(Xtr, Y[tr], Xte); P = S >= t; Yt = Y[te]
    tp = (P & Yt).sum(); prec, rec = tp / max(1, P.sum()), tp / max(1, Yt.sum()); f1 = 2 * prec * rec / max(1e-9, prec + rec)
    cs = np.stack([S[:, [PI[(c, d)] for d in ("up", "down") if (c, d) in PI]].max(1) for c in CONDS], 1); yc = np.stack([Yt[:, [PI[(c, d)] for d in ("up", "down") if (c, d) in PI]].any(1) for c in CONDS], 1)
    order = np.argsort(-cs, 1); keep = {k: (np.take_along_axis(yc, order[:, :k], 1).sum() / max(1, yc.sum())) for k in range(1, 40)}
    k85 = next((k for k in range(1, 40) if keep[k] >= .85), 39)
    res = {"method": name, "precision": round(float(prec), 3), "recall": round(float(rec), 3), "f1": round(float(f1), 3), "keep@8": round(float(keep[8]), 3), "keep@12": round(float(keep[12]), 3),
           "keep@20": round(float(keep[20]), 3), "k_for_85": k85, "gpu_work_at_85": round(k85 / 39, 3), "cpu_ms_story": round(float(ms), 2), "PASS_replace": bool(prec >= .85 and rec >= .85)}
    print(json.dumps(res), flush=True); return res, S

# linear heads: one per tag; tags with < 2 positives get their training rate
def heads(make):
    def fit_score(Xtr, Ytr, Xte):
        S = np.zeros((Xte.shape[0], Ytr.shape[1]))
        for j in range(Ytr.shape[1]):
            if Ytr[:, j].sum() < 2: S[:, j] = Ytr[:, j].mean(); continue
            m = make().fit(Xtr, Ytr[:, j]); S[:, j] = m.predict_proba(Xte)[:, 1] if hasattr(m, "predict_proba") else m.predict(Xte)
        return S
    return fit_score
ridge = lambda Xtr, Ytr, Xte: Ridge(alpha=1.0, random_state=RNG).fit(Xtr, Ytr.astype(float)).predict(Xte)       # all tags at once
def knn(k=15):
    def f(Xtr, Ytr, Xte):
        sim = Xte @ Xtr.T; idx = np.argsort(-sim, 1)[:, :k]; w = np.take_along_axis(sim, idx, 1).clip(0) ** 3
        return (w[..., None] * Ytr[idx]).sum(1) / np.maximum(w.sum(1, keepdims=True), 1e-9)
    return f

METHODS = {}
def method(name): return lambda f: METHODS.__setitem__(name, f)

QTEXT = {p: " ".join([C.QS[f"a|{p[0]}|{p[1]}|{i}|{w}"] for i in range(len(C.ATTRS[p])) for w in (0, 1)]) for p in PAIRS}

@method("rules_question_words")         # 1: no training: words from our own question wordings, minus words common to all questions
def _():
    import collections
    stop = set("this story reports a an the of to in on for and or is are be been being that with as by at from its it more less than people their".split())
    toks = {p: [w for w in re.findall(r"[a-z]+", QTEXT[p].lower()) if w not in stop and len(w) > 3] for p in PAIRS}
    df = collections.Counter(w for p in PAIRS for w in set(toks[p])); kw = {p: {w for w in toks[p] if df[w] <= 3} for p in PAIRS}
    X = [set(re.findall(r"[a-z]+", t.lower())) for t in full]; t0 = time.perf_counter()
    S = np.array([[len(kw[p] & x) / max(1, len(kw[p])) for p in PAIRS] for x in X]); ms = (time.perf_counter() - t0) * 1000 / len(rows)
    return evaluate("1 rules from question words (no training)", lambda Xtr, Ytr, Xte: Xte, S, ms)

def tfidf(): v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000, sublinear_tf=True, stop_words="english"); t0 = time.perf_counter(); X = v.fit_transform(full); return X, (time.perf_counter() - t0) * 1000 / len(rows)
@method("lexicon_logodds")               # 2: learned keyword lexicon: per tag, words' log-odds of appearing in tagged vs untagged training stories
def _():
    X, ms = tfidf(); Xb = (X > 0).astype(float)
    def f(Xtr, Ytr, Xte):
        S = np.zeros((Xte.shape[0], Ytr.shape[1]))
        for j in range(Ytr.shape[1]):
            pos = Ytr[:, j]
            if pos.sum() < 2: S[:, j] = 0; continue
            a = np.asarray(Xtr[pos].sum(0)).ravel() + .5; b = np.asarray(Xtr[~pos].sum(0)).ravel() + .5
            lo = np.log(a / pos.sum()) - np.log(b / (~pos).sum()); w = np.where(lo > np.quantile(lo, .995), lo, 0); S[:, j] = Xte @ w
        return S
    return evaluate("2 learned keyword lexicon (log-odds)", f, Xb.tocsr(), ms)
@method("tfidf_logreg")                  # 3
def _(): X, ms = tfidf(); return evaluate("3 word statistics + logistic", heads(lambda: LogisticRegression(C=8.0, max_iter=2000, class_weight="balanced", random_state=RNG)), X.tocsr(), ms)
@method("tfidf_ridge")                   # 4
def _(): X, ms = tfidf(); return evaluate("4 word statistics + ridge", ridge, X.tocsr(), ms)
@method("tfidf_nb")                      # 5
def _(): X, ms = tfidf(); return evaluate("5 naive Bayes on words", heads(lambda: ComplementNB(alpha=0.3)), X.tocsr(), ms)
@method("e5_ridge")                      # 6: today's router (baseline)
def _(): V, ms = cache("e5_int8", e5_int8); return evaluate("6 e5-small int8 + ridge (today)", ridge, V, ms)
@method("potion_ridge")                  # 7
def _(): V, ms = cache("potion32", potion("minishlab/potion-base-32M")); return evaluate("7 static embeddings potion-32M + ridge", ridge, V, ms)
@method("bge_ridge")                     # 8
def _(): V, ms = cache("bge_small", st("BAAI/bge-small-en-v1.5")); return evaluate("8 bge-small + ridge", ridge, V, ms)
@method("e5_knn")                        # 9
def _(): V, ms = cache("e5_int8", e5_int8); return evaluate("9 e5 nearest neighbours (k=15)", knn(15), V, ms)
@method("zeroshot")                      # 10: no training: similarity of the story to each tag's question wordings
def _():
    V, ms = cache("e5_int8", e5_int8)
    import onnxruntime as ort; from tokenizers import Tokenizer; from huggingface_hub import hf_hub_download
    tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); tok.enable_truncation(512)
    s = ort.InferenceSession("/workspace/data/embed-zs/engine/e5.int8.onnx", providers=["CPUExecutionProvider"])
    def enc1(t): e = tok.encode("query: " + t); ids = np.array([e.ids], np.int64); m = np.array([e.attention_mask], np.int64); h = s.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0][0]; v = h.mean(0); return v / np.linalg.norm(v)
    Q = np.stack([enc1(QTEXT[p]) for p in PAIRS]); S = V @ Q.T; S = S - S.mean(0)
    return evaluate("10 zero-shot: story vs question wordings (no training)", lambda Xtr, Ytr, Xte: Xte, S, ms)
@method("ensemble")                      # 11: average of rank-normalised word logistic and e5 ridge scores
def _():
    X, ms1 = tfidf(); V, ms2 = cache("e5_int8", e5_int8); lr = heads(lambda: LogisticRegression(C=8.0, max_iter=2000, class_weight="balanced", random_state=RNG))
    from scipy.stats import rankdata
    def f(Xtr, Ytr, Xte):
        a = lr(Xtr[0], Ytr, Xte[0]); b = ridge(Xtr[1], Ytr, Xte[1]); nrm = lambda M: rankdata(M, axis=0) / M.shape[0]; return (nrm(a) + nrm(b)) / 2
    class Pair:
        def __init__(s, A, B): s.A, s.B = A, B
        def __getitem__(s, i): return (s.A[i], s.B[i]) if not isinstance(i, int) else None
    Xc = X.tocsr()
    def fs(Xtr, Ytr, Xte): return f(Xtr, Ytr, Xte)
    # evaluate() slices X by index arrays; give it an object holding both feature sets
    class Both(list): pass
    both = np.empty(len(rows), object)
    for i in range(len(rows)): both[i] = i
    def fit_score(itr, Ytr, ite): itr, ite = itr.astype(int), ite.astype(int); return f((Xc[itr], V[itr]), Ytr, (Xc[ite], V[ite]))
    return evaluate("11 ensemble: word logistic + e5 ridge", fit_score, both, ms1 + ms2)
@method("cascade")                       # 12: condition first (does the story touch it?), then direction (up vs down) among touched
def _():
    V, ms = cache("e5_int8", e5_int8)
    def f(Xtr, Ytr, Xte):
        S = np.zeros((Xte.shape[0], Ytr.shape[1])); Ycond = np.stack([Ytr[:, [PI[(c, d)] for d in ("up", "down") if (c, d) in PI]].any(1) for c in CONDS], 1)
        touch = Ridge(alpha=1.0).fit(Xtr, Ycond.astype(float)).predict(Xte)
        for ci, c in enumerate(CONDS):
            u, d = PI.get((c, "up")), PI.get((c, "down")); has = Ycond[:, ci]
            if u is None or d is None: S[:, u if u is not None else d] = touch[:, ci]; continue
            pu = Ytr[has, u].mean() if has.sum() else .5
            if has.sum() >= 4 and 0 < Ytr[has, u].sum() < has.sum(): pu = LogisticRegression(C=1.0, max_iter=2000, random_state=RNG).fit(Xtr[has], Ytr[has, u]).predict_proba(Xte)[:, 1]
            S[:, u] = touch[:, ci] * pu; S[:, d] = touch[:, ci] * (1 - pu)
        return S
    return evaluate("12 cascade: touch condition, then direction", f, V, ms)

if __name__ == "__main__":
    pick = sys.argv[1:] or list(METHODS); allres = []
    for n in pick:
        try: allres.append(METHODS[n]()[0])
        except Exception as e: print(json.dumps({"method": n, "error": f"{type(e).__name__}: {e}"[:200]}), flush=True)
    prev = json.load(open(f"{OUT}/bench.json")) if os.path.exists(f"{OUT}/bench.json") else {}
    prev.update({r["method"]: r for r in allres}); json.dump(prev, open(f"{OUT}/bench.json", "w"), indent=1)
