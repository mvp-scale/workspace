"""B1 step 2 (ledger L389): token-level linear tag head on FROZEN encoder token vectors, same data and head for each encoder; scored on held-out articles against the Clef-accepted tags, and against the proposer-only baseline.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python tag_head.py [leaf bge granite]
Reads runs/tag_head/labels.jsonl (tag_label.py) and the article text from the local queue (never printed or written); writes runs/snapshots/tag_head.json (tag phrases and scores only)."""
import os, sys, re, json, time, random, sqlite3, collections, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from transformers import AutoTokenizer, AutoModel
from sklearn.linear_model import LogisticRegression
ENC = {"leaf": "MongoDB/mdbr-leaf-mt", "bge": "BAAI/bge-small-en-v1.5", "granite": "ibm-granite/granite-embedding-small-english-r2"}
which = [a for a in sys.argv[1:] if a in ENC] or list(ENC); K = 5; WIN = 1500
DET = {"the", "a", "an", "this", "that", "these", "those", "his", "her", "its", "their", "our", "my", "your", "some", "any", "each", "every"}
def norm(s):
    w = [x for x in re.sub(r"[^\w\s\-&.']", " ", s.lower()).split() if x]
    while w and w[0] in DET: w = w[1:]
    return " ".join(w).strip(" .-'")
L = [json.loads(l) for l in open("runs/tag_head/labels.jsonl")]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); A = []
for r in L:
    row = db.execute("select title, body from items where id = ?", (r["id"][2:],)).fetchone() or db.execute("select title, body from items where id = ?", (int(r["id"][2:]) if r["id"][2:].isdigit() else -1,)).fetchone()
    if not row or not row[1] or not row[0]: gone = globals().get('gone', 0) + 1; continue
    text = row[0].strip() + ". " + re.sub(r"\s+", " ", row[1]).strip()[:3500]
    gold = sorted({c for c, a in zip(r["cands"], r["ans"]) if sum(x >= 0.5 for x in a) >= 2})
    if gold: A.append({"id": r["id"], "text": text, "gold": gold, "cands": r["cands"]})
random.Random(3).shuffle(A); te, va, tr = A[:300], A[300:450], A[450:]; print("text gone from queue", globals().get("gone", 0), "articles", len(A), "train", len(tr), "val", len(va), "test", len(te), "gold/article", round(float(np.mean([len(a["gold"]) for a in A])), 2), flush=True)
def spans_of(a):  # char spans of every occurrence of each gold tag
    low = a["text"].lower(); out = []
    for g in a["gold"]:
        for m in re.finditer(r"(?<!\w)" + re.escape(g) + r"(?!\w)", low): out.append((m.start(), m.end()))
    return out
def tokens(tok, mdl, a):
    """-> list of (char_start, char_end, vector) over 1500-char windows"""
    out = []; t = a["text"]
    for w0 in range(0, len(t), WIN):
        seg = t[w0:w0 + WIN]; e = tok(seg, return_offsets_mapping=True, truncation=True, max_length=512, return_tensors="pt")
        off = e.pop("offset_mapping")[0].tolist()
        with torch.no_grad(): H = mdl(**e).last_hidden_state[0].numpy()
        for (s, f), h in zip(off, H):
            if f > s: out.append((w0 + s, w0 + f, h))
    return out
def featurize(tok, mdl, arts, lab):
    X, Y, idx = [], [], []
    for n, a in enumerate(arts):
        tk = tokens(tok, mdl, a); sp = spans_of(a) if lab else []
        for s, f, h in tk:
            X.append(h); idx.append((n, s, f))
            if lab: Y.append(any(s < e and f > b for b, e in sp))
    return np.array(X, dtype=np.float32), np.array(Y), idx
def decode(a, P, idx, thr):
    """runs of adjacent tokens with p >= thr -> phrases; top K by max p"""
    toks = [(s, f, p) for (n, s, f), p in zip(idx, P)]; runs = []; cur = []
    for s, f, p in toks:
        if p >= thr and (not cur or s - cur[-1][1] <= 1): cur.append((s, f, p))
        else:
            if p >= thr: runs.append(cur); cur = [(s, f, p)]
            elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    best = {}
    for r in runs:
        ph = norm(a["text"][r[0][0]:r[-1][1]]); sc = max(p for _, _, p in r)
        if len(ph) >= 3 and not ph.isdigit() and sc > best.get(ph, 0): best[ph] = sc
    return [p for p, _ in sorted(best.items(), key=lambda kv: -kv[1])[:K]]
def f1(pred, gold, loose):
    if not pred: return 0.0
    if loose: hit = lambda p, g: p == g or p in g or g in p
    else: hit = lambda p, g: p == g
    tp_p = sum(any(hit(p, g) for g in gold) for p in pred); tp_g = sum(any(hit(p, g) for p in pred) for g in gold)
    pr, rc = tp_p / len(pred), tp_g / len(gold); return 0 if pr + rc == 0 else 2 * pr * rc / (pr + rc)
def score(arts, preds): return {m: np.array([f1(p, a["gold"], m == "loose") for a, p in zip(arts, preds)]) for m in ("strict", "loose")}
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as SW
def cheap(text):
    """no spaCy: runs of capitalised words (not only sentence-initial) and repeated lowercase words, ranked by count"""
    c = collections.Counter()
    for m in re.finditer(r"(?:[A-Z][\w'&-]+)(?:\s+(?:of\s+|and\s+)?[A-Z][\w'&-]+){0,3}", text):
        ph = norm(m.group(0))
        if len(ph) >= 3 and ph not in SW and not ph.isdigit(): c[ph] += 1
    for w, n in collections.Counter(re.findall(r"[a-z][a-z'-]{3,}", text.lower())).items():
        if n >= 2 and w not in SW: c[w] += 0.5 * n
    return [p for p, _ in c.most_common(K)]
def rerank(a, P, idx):
    """same head, spaCy candidates: score = max token probability over each candidate's mentions"""
    sc = {}; low = a["text"].lower()
    for cnd in a["cands"]:
        best = 0.0
        for m in re.finditer(r"(?<!\w)" + re.escape(cnd) + r"(?!\w)", low):
            for (n, s0, f0), p in zip(idx, P):
                if s0 < m.end() and f0 > m.start() and p > best: best = p
        sc[cnd] = best
    return [c for c, _ in sorted(sc.items(), key=lambda kv: -kv[1])[:K]]
base = [a["cands"][:K] for a in te]; SB = score(te, base); SC = score(te, [cheap(a["text"]) for a in te]); res = {"n_articles": len(A), "n_test": len(te), "gold_per_article": round(float(np.mean([len(a["gold"]) for a in te])), 2), "baseline_proposer": {m: round(float(v.mean()), 3) for m, v in SB.items()}, "baseline_cheap": {m: round(float(v.mean()), 3) for m, v in SC.items()}, "encoders": {}}; per = {}; perR = {}
print("baseline proposer", res["baseline_proposer"], "cheap", res["baseline_cheap"], flush=True)
for name in which:
    t0 = time.time(); tok = AutoTokenizer.from_pretrained(ENC[name]); mdl = AutoModel.from_pretrained(ENC[name], dtype=torch.float32, **({"attn_implementation": "eager"} if name == "granite" else {})).eval()
    Xtr, Ytr, _ = featurize(tok, mdl, tr, True); Xva, Yva, iva = featurize(tok, mdl, va, True); Xte, _, ite = featurize(tok, mdl, te, False); tf = time.time() - t0
    clf = LogisticRegression(C=1.0, max_iter=300, class_weight="balanced").fit(Xtr, Ytr)
    Pva = clf.predict_proba(Xva)[:, 1]; vn = np.array([i[0] for i in iva]); bestthr, bestf = 0.5, -1
    for thr in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        pr = [decode(va[n], Pva[vn == n], [iva[k] for k in np.where(vn == n)[0]], thr) for n in range(len(va))]; fl = score(va, pr)["loose"].mean()
        if fl > bestf: bestthr, bestf = thr, fl
    t1 = time.time(); Pte = clf.predict_proba(Xte)[:, 1]; tn = np.array([i[0] for i in ite]); preds = []
    for n in range(len(te)): preds.append(decode(te[n], Pte[tn == n], [ite[k] for k in np.where(tn == n)[0]], bestthr))
    head_ms = (time.time() - t1) * 1000 / len(te); S = score(te, preds); per[name] = S; RR = score(te, [rerank(te[n], Pte[tn == n], [ite[k] for k in np.where(tn == n)[0]]) for n in range(len(te))]); perR[name] = RR
    res["encoders"][name] = {"model": ENC[name], "dim": int(Xtr.shape[1]), "threshold": bestthr, "val_loose_f1": round(float(bestf), 3), "strict_f1": round(float(S["strict"].mean()), 3), "loose_f1": round(float(S["loose"].mean()), 3), "rerank_strict_f1": round(float(RR["strict"].mean()), 3), "rerank_loose_f1": round(float(RR["loose"].mean()), 3), "head_ms_per_article": round(head_ms, 2), "train_positive_token_share": round(float(Ytr.mean()), 3), "featurize_s": round(tf), "examples": [{"gold": te[n]["gold"][:6], "pred": preds[n]} for n in range(3)]}
    print(name, json.dumps({k: v for k, v in res["encoders"][name].items() if k != "examples"}), flush=True)
    del Xtr, Xva, Xte, mdl
rng = np.random.default_rng(0); res["paired_bootstrap"] = {}
for m in ("strict", "loose"):
    ci = lambda d: (lambda bs: [round(float(d.mean()), 3), round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)])([d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)])
    if "leaf" in per:
        res["paired_bootstrap"][f"finder_leaf_minus_cheap_{m}"] = ci(per["leaf"][m] - SC[m]); res["paired_bootstrap"][f"reranker_leaf_minus_proposer_{m}"] = ci(perR["leaf"][m] - SB[m])
        for o in per:
            if o == "leaf": continue
            d = per[o][m] - per["leaf"][m]; bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]; res["paired_bootstrap"][f"{o}_minus_leaf_{m}"] = [round(float(d.mean()), 3), round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]
os.makedirs("runs/snapshots", exist_ok=True); json.dump(res, open("runs/snapshots/tag_head.json", "w"), indent=1); print(json.dumps(res["paired_bootstrap"], indent=1))
