"""Fingerprint store v0: parts per item -> outcomes; stability, confirmed-vs-passing, floor, and a SQLite 'why' store.
Run: /workspace/models/embed-zs/.venv/bin/python fingerprint_store.py   (writes runs/fingerprint/{tokens.jsonl,fingerprints.db,store_results.json})"""
import json, os, re, glob, pathlib, warnings, collections, sqlite3, time, random
from urllib.parse import urlparse
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, scipy.sparse as sp, spacy
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(__file__).resolve().parent; R = H0 / "runs/fingerprint"; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
sn = {}
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
z = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True); assert list(z["ids"]) == ids; F = z["F"]
_ss = open(H0 / "structure.py").read().splitlines(); exec("\n".join(l for l in _ss if l.startswith(("ENT =", "NAMES "))))
def source(i):
    k = i.split(":")[0]
    if k == "cc": d = urlparse(i[3:]).netloc.lower().replace("www.", ""); return "reuters.com" if d.endswith("reuters.com") else d
    return pool[i]["from"].replace("newsreader-queue:", "") if k == "nq" else "unknown"
# ---- A: parts per item (cached)
tk = R / "tokens.jsonl"
if not tk.exists():
    nlp = spacy.load("en_core_web_sm", disable=["parser"]); SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
    texts = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]; heads = [(SPL.split(t, 1)[0]) for t in texts]
    def parts(doc):
        sents = []; cur = []
        for t in doc:
            if t.is_alpha and not t.is_stop and len(t.text) > 2 and t.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV"): cur.append(t.lemma_.lower())
            elif t.is_punct and t.text in ".!?;:": sents.append(cur); cur = []
            else: cur.append(None) if t.is_stop or not t.is_alpha else None
        sents.append(cur); return sents
    t0 = time.time()
    with open(tk, "w") as fo:
        hd = list(nlp.pipe(heads, batch_size=256, n_process=10)); full = nlp.pipe(texts, batch_size=256, n_process=10)
        for i, d, h in zip(ids, full, hd):
            w = [t.lemma_.lower() for t in d if t.is_alpha and not t.is_stop and len(t.text) > 2 and t.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV")]
            hw = [t.lemma_.lower() for t in h if t.is_alpha and not t.is_stop and len(t.text) > 2 and t.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV")]
            bg = []
            for s in d.sents if d.has_annotation("SENT_START") else []: pass
            seq = [t for t in d if not t.is_space]; prev = None
            for t in seq:
                ok = t.is_alpha and not t.is_stop and len(t.text) > 2 and t.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV")
                if ok and prev: bg.append(prev + "_" + t.lemma_.lower())
                prev = t.lemma_.lower() if ok else None
            ents = sorted({e.label_ for e in d.ents}); en = sorted({e.label_ + ":" + e.text.lower() for e in d.ents if e.label_ in ("GPE", "ORG", "NORP", "EVENT", "LOC")})
            fo.write(json.dumps({"id": i, "w": sorted(set(w)), "h": sorted(set(hw)), "b": sorted(set(bg)), "et": ents, "en": en}) + "\n")
    print("spaCy parts", round(time.time() - t0), "s", flush=True)
P = {r["id"]: r for r in J(tk)}
keys = []; rows = []
for n, i in enumerate(ids):
    r = P[i]; ks = ["w:" + x for x in r["w"]] + ["b:" + x for x in r["b"]] + ["h:" + x for x in r["h"]] + ["et:" + x for x in r["et"]] + ["en:" + x for x in r["en"]]
    ks += ["f:" + NAMES[j] for j in range(F.shape[1]) if F[n, j] > 0 and j < len(NAMES)] + ["s:" + source(i)]; rows.append(ks)
df = collections.Counter(k for ks in rows for k in set(ks)); vocab = sorted(k for k, c in df.items() if 25 <= c <= 0.95 * len(ids)); vi = {k: j for j, k in enumerate(vocab)}
X = sp.csr_matrix((np.ones(sum(1 for ks in rows for k in set(ks) if k in vi), dtype=np.float32), ([n for n, ks in enumerate(rows) for k in set(ks) if k in vi], [vi[k] for ks in rows for k in set(ks) if k in vi])), shape=(len(ids), len(vocab))).tocsc().tocsr()
print("parts per item", round(X.sum() / len(ids), 1), "vocab", len(vocab), flush=True)
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids]); st = np.array([hk[i]["story_type"] for i in ids]); topic = np.array([hk[i]["topic"] for i in ids])
def zscore(X, yb, a0=None):
    """log-odds ratio of presence in class vs rest from the 2x2 table, +0.5 smoothing (Haldane-Anscombe); z = ratio / standard error. Returns z, class count, rest count."""
    n1 = yb.sum(); n0 = len(yb) - n1; c1 = np.asarray(X[yb == 1].sum(0)).ravel(); c0 = np.asarray(X[yb == 0].sum(0)).ravel()
    A, B, C, D = c1 + .5, n1 - c1 + .5, c0 + .5, n0 - c0 + .5
    return np.log(A * D / (B * C)) / np.sqrt(1 / A + 1 / B + 1 / C + 1 / D), c1, c0
res = {"items": len(ids), "vocab": len(vocab), "parts_per_item": round(float(X.sum() / len(ids)), 1)}
# ---- M1 stability
rng = np.random.default_rng(0); res["M1_stability_jaccard_top50"] = {}
for name, yb in (("names_a_condition", y), ("opinion", (st == "opinion").astype(int)), ("forecast", (st == "forecast").astype(int))):
    out = {}
    for N in (100, 500, 1000, 2000, 5000, 12000):
        js = []
        for rep in range(10):
            p = rng.permutation(len(ids)); a, b = p[:N], p[N:2 * N]
            if yb[a].sum() < 2 or yb[b].sum() < 2: continue
            za = zscore(X[a], yb[a])[0]; zb = zscore(X[b], yb[b])[0]; ta = set(np.argsort(-za)[:50]); tb = set(np.argsort(-zb)[:50]); js.append(len(ta & tb) / len(ta | tb))
        out[N] = round(float(np.mean(js)), 3) if js else None
    res["M1_stability_jaccard_top50"][name] = out
print("M1", json.dumps(res["M1_stability_jaccard_top50"]), flush=True)
# ---- M2 confirmed vs passing (voted items, Haiku-positive)
vot = [n for n, i in enumerate(ids) if i in sn and hk[i]["conditions"]]
conf = np.array([1 if {c["condition"] for c in hk[ids[n]]["conditions"]} & {c["condition"] for c in sn[ids[n]]["conditions"]} else 0 for n in vot])
res["M2_voted_haiku_positive"] = len(vot); res["M2_share_sonnet_confirms_same_condition"] = round(float(conf.mean()), 3)
Xv = X[vot]; zc, c1, c0 = zscore(Xv, conf, a0=100.0); order = np.argsort(-zc); okv = (c1 + c0) >= 40
top_conf = [(vocab[j], round(float(zc[j]), 2)) for j in order if okv[j]][:12]; top_pass = [(vocab[j], round(float(zc[j]), 2)) for j in order[::-1] if okv[j]][:12]
res["M2_top_confirmed_parts"] = top_conf; res["M2_top_passing_parts"] = top_pass
cv = StratifiedKFold(5, shuffle=True, random_state=0); lr = lambda: LogisticRegression(max_iter=2000, C=0.05)
sub = lambda pref: np.array([j for j, k in enumerate(vocab) if k.startswith(pref)])
groups = {"structure_flags": sub("f:"), "headline_words": sub("h:"), "body_words": sub("w:"), "word_pairs": sub("b:"), "entities": np.concatenate([sub("et:"), sub("en:")]), "source": sub("s:"), "all": np.arange(len(vocab))}
res["M2_cv_auc_confirmed"] = {g: round(float(roc_auc_score(conf, cross_val_predict(lr(), Xv[:, cols], conf, cv=cv, method="predict_proba")[:, 1])), 4) for g, cols in groups.items() if len(cols)}
print("M2", res["M2_share_sonnet_confirms_same_condition"], res["M2_cv_auc_confirmed"], flush=True)
# ---- M3 floor: significant-part hits, learned out-of-fold
hits = np.zeros(len(ids)); 
for tr, te in cv.split(np.zeros(len(ids)), y):
    zt = zscore(X[tr], y[tr])[0]; sig = (zt >= 3).astype(np.float32); hits[te] = X[te] @ sig
res["M3_floor"] = {}
for k in (0, 1, 2, 3, 5):
    m = hits <= k if k == 0 else hits <= k; res["M3_floor"][f"hits_le_{k}"] = {"share_of_items": round(float(m.mean()), 3), "positive_rate": round(float(y[m].mean()), 3), "share_of_positives_lost": round(float(y[m].sum() / y.sum()), 3)}
res["M3_hit_score_auc"] = round(float(roc_auc_score(y, hits)), 4)
# ---- M4 store
db = R / "fingerprints.db"
if db.exists(): db.unlink()
con = sqlite3.connect(db); con.executescript("create table items(id text primary key, corpus text, source text, date text, topic text, story_type text, haiku_conditions text, sonnet_conditions text); create table part(item_id text, key text); create table stat(outcome text, key text, n_pos int, n_all int, z real); create table why(item_id text, outcome text, keys text);")
con.executemany("insert into items values(?,?,?,?,?,?,?,?)", [(i, i.split(":")[0], source(i), pool[i]["date"], hk[i]["topic"], hk[i]["story_type"], ",".join(c["condition"] + ":" + c["direction"] for c in hk[i]["conditions"]), ",".join(c["condition"] + ":" + c["direction"] for c in sn[i]["conditions"]) if i in sn else None) for i in ids])
Xc = X.tocoo(); con.executemany("insert into part values(?,?)", [(ids[a], vocab[b]) for a, b in zip(Xc.row, Xc.col)])
zf, c1f, c0f = zscore(X, y); con.executemany("insert into stat values('names_a_condition',?,?,?,?)", [(vocab[j], int(c1f[j]), int(c1f[j] + c0f[j]), float(zf[j])) for j in range(len(vocab))])
Xr = X.tocsr(); wh = []
for n, i in enumerate(ids):
    cols = Xr.indices[Xr.indptr[n]:Xr.indptr[n + 1]]; top = cols[np.argsort(-zf[cols])[:8]]; wh.append((i, "names_a_condition", json.dumps([[vocab[j], round(float(zf[j]), 1)] for j in top if zf[j] > 0])))
con.executemany("insert into why values(?,?,?)", wh); con.execute("create index p1 on part(item_id)"); con.execute("create index p2 on part(key)"); con.execute("create index w1 on why(item_id)"); con.commit()
sample = random.Random(0).sample(ids, 100); t0 = time.time()
for i in sample: con.execute("select keys from why where item_id=?", (i,)).fetchall(); con.execute("select key from part where item_id=?", (i,)).fetchall()
res["M4_store"] = {"mb": round(db.stat().st_size / 1e6, 1), "why_lookup_ms": round((time.time() - t0) / 100 * 1000, 2), "rows_part": int(Xc.nnz)}
res["top_parts_names_a_condition"] = [(vocab[j], round(float(zf[j]), 1)) for j in np.argsort(-zf)[:25]]; res["bottom_parts_names_a_condition"] = [(vocab[j], round(float(zf[j]), 1)) for j in np.argsort(zf)[:15]]
json.dump(res, open(R / "store_results.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k not in ("top_parts_names_a_condition", "bottom_parts_names_a_condition")}, indent=1))
os._exit(0)
