"""Sparse classifier (G3a) with triple tokens and a thesaurus built from our own text (LSA term neighbours). Train on Sonnet topic labels of short items; test on unseen-domain items (agreement) and on MN-DS full articles (human labels, scoring only).
    /workspace/models/embed-zs/.venv/bin/python sparse_expand_test.py -> runs/pulse/sparse_expand_test.json"""
import json, re, random, time, glob, sys, collections, warnings; warnings.filterwarnings("ignore")
import numpy as np, scipy.sparse as sp, spacy
from urllib.parse import urlparse
from multiprocessing import Pool
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import normalize
sys.path.insert(0, "."); import spo_chains as S, article_views as V
J = lambda p: [json.loads(l) for l in open(p)]
# ---- training data: the L1102 pool and test split (same seed)
ids = json.load(open("runs/embeds/bge_small_ids.json")); idset = set(ids); txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] != "sonnet" or not r.get("topic") or r["item_id"] not in idset or r["item_id"] not in txt: continue
    rk = RANK.get(r["version"], 2)
    if r["item_id"] not in best or rk < best[r["item_id"]][0]: best[r["item_id"]] = (rk, r)
items = sorted(best); dom = lambda i: (urlparse(i.split("cc:", 1)[-1]).netloc or i.split(":")[0]) if i.startswith("cc:") else i.split(":")[0]
domains = sorted({dom(i) for i in items}); rng = random.Random(20261108); test_dom = set(rng.sample(domains, max(1, int(0.12 * len(domains)))))
test_ids = [i for i in items if dom(i) in test_dom]; train_ids = [i for i in items if dom(i) not in test_dom]
ytr = np.array([best[i][1]["topic"] for i in train_ids]); yte = np.array([best[i][1]["topic"] for i in test_ids]); Ttr = [txt[i] for i in train_ids]; Tte = [txt[i] for i in test_ids]
print("train", len(Ttr), "test", len(Tte), flush=True)
# ---- MN-DS full articles with the views of L1104
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; rows = J("runs/harvest/mnds_variants.jsonl")
mn = {"V0": [r["title"] + ". " + r["content"][:300] for r in rows], "V1": [r["title"] + ". " + r["content"][:12000] for r in rows], "V2": [r["title"] + ". " + r["views"]["gist"] for r in rows]}; mn_y = [r["category"] for r in rows]
# ---- triple tokens
nlp = None
def init():
    global nlp; nlp = spacy.load("en_core_web_sm", disable=["ner"])
def triple_tokens(text):
    sents = V.split(re.sub(r"\s+", " ", text))[:60] or [text]; T = S.extract(nlp, sents); out = []
    for t in T:
        if not (t["s"] and t["o"]) or t["s_pronoun"] or t["o_pronoun"]: continue
        s, o, v = re.sub(r"\W+", "_", t["s_key"]), re.sub(r"\W+", "_", t["o_key"]), t["p_lemma"]
        out += [f"S_{s}", f"V_{v}", f"O_{o}", f"SV_{s}_{v}", f"VO_{v}_{o}"] + ([f"NEG_{v}"] if t["neg"] else [])
    return " ".join(out)
t0 = time.time()
with Pool(12, initializer=init) as P:
    TTr = P.map(triple_tokens, Ttr, chunksize=200); TTe = P.map(triple_tokens, Tte, chunksize=200); TM = {k: P.map(triple_tokens, v, chunksize=20) for k, v in mn.items()}
print("triple tokens built", round(time.time() - t0), "s", flush=True)
# ---- features
wv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=300000, stop_words="english").fit(Ttr)
tv = TfidfVectorizer(tokenizer=str.split, lowercase=False, min_df=2, sublinear_tf=True, token_pattern=None).fit(TTr)
uv = TfidfVectorizer(ngram_range=(1, 1), min_df=3, sublinear_tf=True, max_features=30000, stop_words="english").fit(Ttr); U = uv.transform(Ttr)
svd = TruncatedSVD(150, random_state=0).fit(U); tvec = normalize(svd.components_.T); voc = uv.get_feature_names_out(); n = len(voc); rows_i = []; cols_i = []; vals = []
for a in range(0, n, 2000):
    sim = tvec[a:a + 2000] @ tvec.T
    for k in range(sim.shape[0]): sim[k, a + k] = -1
    top = np.argpartition(-sim, 5, axis=1)[:, :5]
    for k in range(sim.shape[0]):
        for c in top[k]:
            if sim[k, c] >= 0.5: rows_i.append(a + k); cols_i.append(int(c)); vals.append(float(sim[k, c]))
EXP = sp.csr_matrix((vals, (rows_i, cols_i)), shape=(n, n)); print("thesaurus: terms", n, "with neighbours", len(set(rows_i)), "links", len(vals), flush=True)
EXAMPLES = {w: [voc[c] for c in EXP[list(voc).index(w)].nonzero()[1]] for w in ("police", "inflation", "election", "storm", "merger") if w in set(voc)}
def feats(texts, ttexts, variant):
    W = wv.transform(texts); parts = [W]
    if "T" in variant: parts.append(0.5 * tv.transform(ttexts))
    if "E" in variant:
        Ux = uv.transform(texts); parts.append(0.5 * (Ux @ EXP))
    return normalize(sp.hstack(parts).tocsr())
def fit(variant):
    return SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=25, tol=None, random_state=0).fit(feats(Ttr, TTr, variant), ytr)
def top2(model, X, gold, mapped):
    P = model.predict_proba(X); cl = model.classes_; o = np.argsort(-P, axis=1)[:, :2]
    if mapped: return [int(any(g in M.get(cl[k], []) for k in oo)) for g, oo in zip(gold, o)], [int(g in M.get(cl[oo[0]], [])) for g, oo in zip(gold, o)]
    return [int(g in cl[oo]) for g, oo in zip(gold, o)], [int(g == cl[oo[0]]) for g, oo in zip(gold, o)]

import analyze2 as A2; from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cl = list(e.S["topic_cl"]); rd = A2.Reader(e.S, threads=6, fit_headline=True)
def dense(texts):
    out = []
    for r, t in zip(rows, texts):
        body = t[len(r["title"]) + 2:] if t.startswith(r["title"] + ". ") else t; pt, _, _ = rd.read(r["title"], body); out.append(pt)
    return np.array(out)
D = {k: dense(mn[k]) for k in ("V0", "V1", "V2")}; print("dense probs done", flush=True)
mods = {"F0": fit(""), "F3": fit("TE")}; Sp = {}
for name, m in mods.items():
    var = "" if name == "F0" else "TE"; cls = list(m.classes_); idx = [cls.index(c) for c in cl]
    for k in ("V0", "V1", "V2"): P = m.predict_proba(feats(mn[k], TM[k], var))[:, idx]; Sp[(name, k)] = P / P.sum(axis=1, keepdims=True)
print("sparse probs done", flush=True)
def hit2(P):
    o = np.argsort(-P, axis=1)[:, :2]; return np.array([int(any(g in M.get(cl[x], []) for x in oo)) for g, oo in zip(mn_y, o)])
rs = np.random.RandomState(4); ix = [rs.randint(0, len(rows), len(rows)) for _ in range(2000)]
def ci(d): bs = [d[i].mean() for i in ix]; return [round(float(d.mean()), 4), round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
res = {"v": "ensemble-v0", "articles": len(rows), "results": {}}
for k in ("V0", "V1", "V2"):
    h = {"dense": hit2(D[k]), "sparse_F0": hit2(Sp[("F0", k)]), "sparse_F3": hit2(Sp[("F3", k)]), "ensemble_dense_F0": hit2(0.5 * D[k] + 0.5 * Sp[("F0", k)]), "ensemble_dense_F3": hit2(0.5 * D[k] + 0.5 * Sp[("F3", k)])}
    best_single = max(("dense", "sparse_F0", "sparse_F3"), key=lambda n: h[n].mean())
    res["results"][k] = {n: round(float(v.mean()), 4) for n, v in h.items()}; res["results"][k]["best_single"] = best_single
    res["results"][k]["ensemble_dense_F3_minus_best_single"] = ci(h["ensemble_dense_F3"] - h[best_single]); res["results"][k]["ensemble_dense_F0_minus_best_single"] = ci(h["ensemble_dense_F0"] - h[best_single])
json.dump(res, open("runs/pulse/ensemble_test.json", "w"), indent=1); print(json.dumps(res["results"], indent=0))
