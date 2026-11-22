"""fact_join: pair scorer for the FACT JOIN (ledger T158). Says whether two event mentions from different articles report the same event, so "Fiona die None" / "Fiona die iso:US" / "Fiona die died aged" become one fact slot. A small classifier over cheap pair features (lemma match, string similarity, e5-small-v2 cosines of the event word, of the event with its local arguments and of the sentence, who/where/when overlap), trained on ECB+ cross-document event coreference (HF ahmeshaf/ecb_plus_mentions, Apache-2.0). CPU only, no hosted calls; inference needs numpy + scipy (+ sentence_transformers for the embeddings; without them the scorer runs in "no-embedding" mode with the cosine features held at their training mean).
    python3 fact_join.py --train <train.parquet> --dev <dev.parquet> --test <test.parquet>   # fit LR and GBM, pick the threshold by topic-held-out CV (+ dev), apply the shipping rule, write fact-join-model.json, print P/R/F1 vs the 4 baselines on the same test rows
    python3 fact_join.py --eval <parquet | fixture.json>                                      # one JSON line: P/R/F1 of the saved model at its threshold
    python3 fact_join.py --make-fixture <test.parquet> <out.json> [--topics 4]                # the K8 gate fixture: the N test topics with the most cross-doc event pairs
Inputs: ECB+ parquet rows (evt rows are the mentions; the ent rows of the same doc + sentence give who/where/when by gold_cluster prefix HUM/LOC/TIM, surface text only) or the json fixture written by --make-fixture.
Outputs: fact-join-model.json beside this file (model type, coefficients or trees, standardisation, threshold, dev/test scores, baselines); the API below for consolidate.py.
API: mention(...) -> dict; Scorer(path, embed).features(a, b) / .prob(a, b) / .cluster(mentions, thr) -> labels; evaluate(rows, scorer) -> P/R/F1 over cross-document pairs within topic (same protocol as the baseline script join-test.py: gold = gold_cluster equality, pairs of mentions from different articles only).
Shipping rule (T158): logistic regression unless the GBM beats it by > 0.03 F1 on dev at the CV thresholds AND exports without pickle; the GBM is exported as plain node arrays and reproduced in numpy, so both are shippable; the JSON says which.
Threshold: the dev split is 277 mentions / 171 positive pairs, too small to set it alone (its F1-vs-threshold curve is bimodal), so it is the best mean cluster F1 over 5 topic-held-out folds of train plus dev, weighted by topic count.
Determinism: cosines rounded to 4 decimals, torch 4 threads, average linkage over 1 - prob, labels relabelled in first-seen order; two runs over the same mentions give the same labels. Mentions from the same article get distance 1.0 and so never merge directly."""
import os, sys, re, json, time, itertools, collections, datetime
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); MODEL_PATH = os.path.join(HERE, "fact-join-model.json")
VERSION = "fact-join-v1"; EMBED_MODEL = "intfloat/e5-small-v2"; LICENSE = "ECB+ via HF ahmeshaf/ecb_plus_mentions, Apache-2.0"
FEATURES = ["same_lemma", "lemma_prefix4", "lemma_trigram_jaccard", "cos_word", "cos_args", "cos_sentence", "who_jaccard", "who_both", "where_jaccard", "where_both", "when_jaccard", "when_both", "same_obj", "obj_unknown"]
COS = [FEATURES.index(f) for f in ("cos_word", "cos_args", "cos_sentence")]
STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "by", "and", "or", "from", "with", "this", "that", "these", "those", "his", "her", "its", "their", "mr", "mrs", "ms", "dr"}
GRID = [round(x, 2) for x in np.arange(0.05, 0.96, 0.01)]; NEG_PER_POS = 5; SEED = 0; FOLDS = 5
def _tok(s): return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP]
def _norm(s): return " ".join(str(s).lower().split())
def mention(word, lemma, sentence, who=(), where=(), when=(), obj=None, day=None, art=None, id=None):
    """the unit the scorer compares; argument surfaces are strings found in the same sentence, stored lower-cased; day is kept but not a feature (ECB+ has none)"""
    return {"id": id, "art": art, "word": _norm(word), "lemma": _norm(lemma or word), "sentence": _norm(sentence), "who": tuple(sorted(set(_norm(x) for x in who if x))), "where": tuple(sorted(set(_norm(x) for x in where if x))), "when": tuple(sorted(set(_norm(x) for x in when if x))), "obj": _norm(obj) if obj else None, "day": day}
def _texts(m):   # the 3 texts embedded per mention
    args = " ".join(x for x in (m["word"],) + m["who"] + m["where"] + m["when"] + ((m["obj"],) if m["obj"] else ()) if x)
    return "query: " + m["word"], "query: " + args, "query: " + m["sentence"]
def _eq(xa, xb):   # pairwise string equality as 0/1 via int ids
    ids = {x: i for i, x in enumerate(sorted(set(xa) | set(xb)))}
    return np.equal.outer(np.array([ids[x] for x in xa]), np.array([ids[x] for x in xb])).astype(float)
def _tri(s): s = f" {s} "; return {s[i:i + 3] for i in range(len(s) - 2)}
def _jacc(sa, sb):
    """pairwise Jaccard of two lists of sets -> (jaccard matrix, both-non-empty matrix); dense 0/1 incidence so it is one matrix product"""
    voc = {x: i for i, x in enumerate(sorted(set().union(*sa, *sb)))}
    def M(S):
        m = np.zeros((len(S), max(len(voc), 1)), dtype=np.float32)
        for i, s in enumerate(S):
            for x in s: m[i, voc[x]] = 1
        return m
    A, B = M(sa), M(sb); inter = A @ B.T; na, nb = A.sum(1)[:, None], B.sum(1)[None, :]; union = na + nb - inter
    return np.where(union > 0, inter / np.maximum(union, 1), 0.0), ((na > 0) & (nb > 0)).astype(np.float32)
def default_embed():
    """lazy e5-small-v2 on CPU, offline; raises if sentence_transformers or the cached model is missing"""
    os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TOKENIZERS_PARALLELISM", "false"); os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    import torch; torch.set_num_threads(4)
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(EMBED_MODEL, device="cpu")
    return lambda texts: m.encode(list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
def _sigmoid(z): return 1.0 / (1.0 + np.exp(-z))
def _trees_raw(trees, base, X):
    """GBM raw score in numpy: X (n, nF) -> (n,); each tree = node arrays f (feature, -1 = leaf), t (threshold), l, r (children), v (leaf value); go left when x <= t (sklearn HistGradientBoosting semantics)"""
    out = np.full(len(X), base); rows = np.arange(len(X))
    for t in trees:
        f, th, L, R, V = (np.array(t[k]) for k in ("f", "t", "l", "r", "v")); node = np.zeros(len(X), dtype=int)
        while True:
            leaf = f[node] < 0
            if leaf.all(): break
            node = np.where(leaf, node, np.where(X[rows, np.where(leaf, 0, f[node])] <= th[node], L[node], R[node]))
        out += V[node]
    return out
class Scorer:
    def __init__(self, path=MODEL_PATH, embed=None):
        self.model = None; self.kind = "logistic-regression"; self.threshold = 0.5; self.mean = np.zeros(len(FEATURES)); self.std = np.ones(len(FEATURES)); self.coef = np.zeros(len(FEATURES)); self.intercept = 0.0; self.trees = []; self.base = 0.0
        if path and os.path.exists(path):
            with open(path) as f: self.model = json.load(f)
            self.kind = self.model["model"]; self.threshold = float(self.model["threshold"]); self.mean = np.array(self.model["mean"], dtype=float); self.std = np.array(self.model["std"], dtype=float)
            if self.kind == "logistic-regression": self.coef = np.array(self.model["coef"], dtype=float); self.intercept = float(self.model["intercept"])
            else: self.trees = self.model["trees"]; self.base = float(self.model["base"])
        self.cache = {}; self._embed = embed; self._mode = "e5-small-v2" if embed else None   # None = loader not tried yet (lazy)
    def _ensure_embed(self):
        if self._mode is None:
            try: self._embed = default_embed(); self._mode = "e5-small-v2"
            except Exception as e: self._embed = None; self._mode = "no-embedding"; self.embed_error = repr(e)
        return self._embed
    @property
    def mode(self):   # "e5-small-v2" | "no-embedding"; reading it resolves the lazy loader (never raises)
        self._ensure_embed(); return self._mode
    @mode.setter
    def mode(self, v): self._mode = v
    def embed(self, texts):
        """cached, deterministic: sorted unique misses encoded in batches of 64, rounded to 4 decimals, re-normalised; None in no-embedding mode"""
        fn = self._ensure_embed()
        if fn is None: return None
        miss = sorted({t for t in texts if t not in self.cache})
        for i in range(0, len(miss), 64):
            V = np.round(np.asarray(fn(miss[i:i + 64]), dtype=np.float64), 4)
            for t, v in zip(miss[i:i + 64], V): self.cache[t] = v / (np.linalg.norm(v) or 1.0)
        return np.stack([self.cache[t] for t in texts]) if texts else np.zeros((0, 1))
    def feature_matrix(self, A, B):
        """(len A, len B, len FEATURES) array of symmetric pair features"""
        F = np.zeros((len(A), len(B), len(FEATURES)), dtype=np.float64)
        if not A or not B: return F
        la, lb = [m["lemma"] for m in A], [m["lemma"] for m in B]
        F[..., 0] = _eq(la, lb); F[..., 1] = _eq([x[:4] for x in la], [x[:4] for x in lb]); F[..., 2] = _jacc([_tri(x) for x in la], [_tri(x) for x in lb])[0]
        E = self.embed([t for m in A for t in _texts(m)] + [t for m in B for t in _texts(m)])
        if E is not None:
            Ea, Eb = E[:3 * len(A)].reshape(len(A), 3, -1), E[3 * len(A):].reshape(len(B), 3, -1)
            for k, fi in enumerate(COS): F[..., fi] = np.round(Ea[:, k] @ Eb[:, k].T, 4)
        else: F[..., COS] = self.mean[COS]   # neutral under standardisation
        for role, fi in (("who", 6), ("where", 8), ("when", 10)):
            j, both = _jacc([set(itertools.chain.from_iterable(_tok(x) for x in m[role])) for m in A], [set(itertools.chain.from_iterable(_tok(x) for x in m[role])) for m in B])
            F[..., fi] = j; F[..., fi + 1] = both
        oa, ob = [m["obj"] for m in A], [m["obj"] for m in B]
        F[..., 12] = np.array([[1.0 if x and y and x == y else 0.0 for y in ob] for x in oa]); F[..., 13] = np.array([[1.0 if not (x and y) else 0.0 for y in ob] for x in oa])
        return F
    def features(self, a, b): return [float(x) for x in self.feature_matrix([a], [b])[0, 0]]
    def prob_matrix(self, F):
        if self.kind == "logistic-regression": return _sigmoid(((F - self.mean) / self.std) @ self.coef + self.intercept)
        return _sigmoid(_trees_raw(self.trees, self.base, F.reshape(-1, F.shape[-1]))).reshape(F.shape[:-1])
    def prob(self, a, b): return float(self.prob_matrix(self.feature_matrix([a], [b]))[0, 0])
    def distances(self, mentions, same_art_dist=1.0):
        """symmetric (n, n) distance 1 - prob, zero diagonal; same-article pairs set to same_art_dist (None = leave as scored)"""
        D = np.clip(1.0 - self.prob_matrix(self.feature_matrix(mentions, mentions)), 0.0, 1.0); D = (D + D.T) / 2
        if same_art_dist is not None:
            arts = [m.get("art") for m in mentions]; has = np.array([a is not None for a in arts])
            D = np.where(_eq([str(a) for a in arts], [str(a) for a in arts]).astype(bool) & has[:, None] & has[None, :], same_art_dist, D)
        np.fill_diagonal(D, 0.0); return D
    def cluster(self, mentions, thr=None, same_art_dist=1.0):
        """labels per mention: average linkage over 1 - prob, cut at distance 1 - thr; mentions of the same article get distance same_art_dist (1.0 = never merge directly)"""
        if not mentions: return []
        if len(mentions) == 1: return [0]
        return cut(linkage_of(self.distances(mentions, same_art_dist)), self.threshold if thr is None else thr)
def linkage_of(D):
    from scipy.cluster.hierarchy import linkage
    return linkage(D[np.triu_indices(len(D), 1)], "average")
def cut(Z, thr):
    from scipy.cluster.hierarchy import fcluster
    seen = {}; return [seen.setdefault(int(l), len(seen)) for l in fcluster(Z, 1.0 - thr, "distance")]   # relabel in first-seen order
# ---------- scoring protocol (join-test.py): cross-document pairs within topic ----------
def _pairs(labels, arts): return {(i, j) for i, j in itertools.combinations(range(len(labels)), 2) if arts[i] != arts[j] and labels[i] == labels[j]}
def _groups(rows, scope):
    g = collections.defaultdict(list)
    for i, r in enumerate(rows): g[r.get(scope) if scope else 0].append(i)
    return [g[k] for k in sorted(g, key=str)]
def score_labels(rows, pred, scope="topic"):
    """pred = list of labels aligned with rows; pairs only count across articles and within the scope key"""
    G, P = set(), set()
    for ix in _groups(rows, scope):
        arts = [rows[i]["art"] for i in ix]
        G |= {(ix[a], ix[b]) for a, b in _pairs([rows[i]["gold"] for i in ix], arts)}; P |= {(ix[a], ix[b]) for a, b in _pairs([pred[i] for i in ix], arts)}
    tp = len(G & P); p = tp / len(P) if P else 0.0; r = tp / len(G) if G else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "pairs_pred": len(P), "pairs_gold": len(G), "mentions": len(rows)}
def linkages(rows, scorer, scope="topic", same_art_dist=1.0):
    """per group: (indices, linkage or None) computed once so a threshold grid only re-cuts"""
    return [(ix, linkage_of(scorer.distances([rows[i] for i in ix], same_art_dist)) if len(ix) > 1 else None) for ix in _groups(rows, scope)]
def labels_at(rows, links, thr):
    pred = [None] * len(rows); base = 0
    for ix, Z in links:
        lab = cut(Z, thr) if Z is not None else [0]
        for i, l in zip(ix, lab): pred[i] = base + l
        base += max(lab) + 1
    return pred
def evaluate(rows, scorer, scope="topic", thr=None, same_art_dist=1.0, links=None):
    """cross-document pairwise P/R/F1 within scope at the scorer's threshold (or thr)"""
    links = links if links is not None else linkages(rows, scorer, scope, same_art_dist)
    return score_labels(rows, labels_at(rows, links, scorer.threshold if thr is None else thr), scope)
# ---------- loaders ----------
def load_parquet(path):
    """ECB+ parquet -> mention dicts with topic/gold/art; who/where/when = surface text of the ent rows of the same doc + sentence by gold_cluster prefix"""
    import pyarrow.parquet as pq
    t = pq.read_table(path).to_pandas(); args = collections.defaultdict(lambda: {"who": [], "where": [], "when": []})
    role = {"HUM": "who", "LOC": "where", "TIM": "when"}
    for r in t[t.men_type == "ent"].itertuples():
        k = role.get(str(r.gold_cluster)[:3])
        if k: args[(r.doc_id, str(r.sentence_id))][k].append(r.mention_text)
    out = []
    for r in t[t.men_type == "evt"].itertuples():
        a = args.get((r.doc_id, str(r.sentence_id)), {"who": (), "where": (), "when": ()})
        m = mention(r.mention_text, r.lemma, r.sentence, a["who"], a["where"], a["when"], art=r.doc_id, id=r.mention_id)
        m.update(topic=r.doc_id.split("_")[0], gold=r.gold_cluster, sentence_id=str(r.sentence_id)); out.append(m)
    return out
def load_fixture(path):
    with open(path) as f: d = json.load(f)
    sent = d.get("sentences", {}); out = []   # shared table "art|sentence_id" -> text; a mention may also carry its own "sentence"
    for r in d["mentions"]:
        m = mention(r["word"], r["lemma"], r.get("sentence") or sent["%s|%s" % (r["art"], r["sentence_id"])], r.get("who", ()), r.get("where", ()), r.get("when", ()), art=r["art"], id=r["id"])
        m.update(topic=r["topic"], gold=r["gold"], sentence_id=r.get("sentence_id")); out.append(m)
    return out
def load_any(path): return load_fixture(path) if path.endswith(".json") else load_parquet(path)
def make_fixture(rows, out, n_topics=4):
    """the n test topics with the most cross-doc event pairs, only the loader's fields; sentences stored once"""
    per = collections.Counter()
    for ix in _groups(rows, "topic"): per[rows[ix[0]]["topic"]] = len(_pairs([rows[i]["gold"] for i in ix], [rows[i]["art"] for i in ix]))
    keep = sorted(t for t, _ in per.most_common(n_topics)); sel = [r for r in rows if r["topic"] in keep]
    d = {"source": "ECB+ test split, HF ahmeshaf/ecb_plus_mentions data/test parquet, event mentions of topics " + ", ".join(keep) + " (the %d topics with the most cross-document event pairs); who/where/when = surface text of the HUM/LOC/TIM entity mentions of the same sentence" % n_topics,
         "license": LICENSE, "count": len(sel), "topics": keep, "cross_doc_gold_pairs": {t: per[t] for t in keep},
         "sentences": {"%s|%s" % (r["art"], r["sentence_id"]): r["sentence"] for r in sel},
         "mentions": [{k: r[k] for k in ("id", "art", "topic", "sentence_id", "word", "lemma", "who", "where", "when", "gold")} for r in sel]}
    with open(out, "w") as f: json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return d
# ---------- training ----------
def topic_feats(rows, scorer):
    """per topic: (indices, feature matrix, same-article mask, cross-article mask, cross-article positive mask) computed once"""
    out = []
    for ix in _groups(rows, "topic"):
        M = [rows[i] for i in ix]; F = scorer.feature_matrix(M, M); arts = [m["art"] for m in M]
        same = _eq(arts, arts).astype(bool); cross = np.triu(~same, 1); gold = _eq([m["gold"] for m in M], [m["gold"] for m in M]).astype(bool) & cross
        out.append((ix, F, same, cross, gold))
    return out
def sample_pairs(feats, topics=None, neg_per_pos=NEG_PER_POS, seed=SEED):
    """all positive cross-doc pairs within topic + neg_per_pos x as many seeded cross-doc negatives per topic -> (X, y)"""
    rng = np.random.RandomState(seed); X, y = [], []
    for k, (ix, F, same, cross, gold) in enumerate(feats):
        if topics is not None and k not in topics: continue
        pi = np.argwhere(gold); ni = np.argwhere(cross & ~gold)
        if len(ni) > neg_per_pos * len(pi): ni = ni[sorted(rng.choice(len(ni), neg_per_pos * len(pi), replace=False))]
        X += [F[pi[:, 0], pi[:, 1]], F[ni[:, 0], ni[:, 1]]]; y += [np.ones(len(pi)), np.zeros(len(ni))]
    return np.concatenate(X), np.concatenate(y)
def fit_lr(X, y):
    from sklearn.linear_model import LogisticRegression
    mu = X.mean(0); sd = np.where(X.std(0) > 0, X.std(0), 1.0); lr = LogisticRegression(C=1.0, max_iter=3000).fit((X - mu) / sd, y)
    return {"model": "logistic-regression", "mean": mu, "std": sd, "coef": lr.coef_[0].astype(float), "intercept": float(lr.intercept_[0])}
def fit_gbm(X, y):
    from sklearn.ensemble import HistGradientBoostingClassifier
    g = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=4, random_state=SEED).fit(X, y); trees = []
    for (p,) in g._predictors:
        n = p.nodes; trees.append({"f": [int(v) if not l else -1 for v, l in zip(n["feature_idx"], n["is_leaf"])], "t": [float(v) for v in n["num_threshold"]], "l": [int(v) for v in n["left"]], "r": [int(v) for v in n["right"]], "v": [float(v) for v in n["value"]]})
    m = {"model": "hist-gradient-boosting", "mean": X.mean(0), "std": np.ones(X.shape[1]), "trees": trees, "base": float(np.ravel(g._baseline_prediction)[0])}
    m["export_max_abs_diff"] = float(np.abs(g.predict_proba(X[:5000])[:, 1] - _sigmoid(_trees_raw(trees, m["base"], X[:5000]))).max()); return m
def as_scorer(params, template):
    """a Scorer from fitted parameters sharing the template's embedding cache"""
    S = Scorer(path=None, embed=template._embed); S.cache = template.cache; S.mode = template.mode; S.kind = params["model"]; S.mean = params["mean"]; S.std = params["std"]
    if S.kind == "logistic-regression": S.coef = params["coef"]; S.intercept = params["intercept"]
    else: S.trees = params["trees"]; S.base = params["base"]
    return S
def curve_feats(S, feats, topics=None, same_art_dist=1.0):
    """F1 per grid threshold over the given topics from cached features (no re-embedding)"""
    TP, P = collections.Counter(), collections.Counter(); G = 0
    for k, (ix, F, same, cross, gold) in enumerate(feats):
        if topics is not None and k not in topics: continue
        G += int(gold.sum())
        if len(ix) == 1: continue
        D = np.clip(1.0 - S.prob_matrix(F), 0, 1); D = (D + D.T) / 2
        if same_art_dist is not None: D = np.where(same, same_art_dist, D)
        np.fill_diagonal(D, 0.0); Z = linkage_of(D)
        for t in GRID:
            lab = np.array(cut(Z, t)); ps = (lab[:, None] == lab[None, :]) & cross; P[t] += int(ps.sum()); TP[t] += int((ps & gold).sum())
    out = {}
    for t in GRID:
        p = TP[t] / P[t] if P[t] else 0.0; r = TP[t] / G if G else 0.0; out[t] = round(2 * p * r / (p + r), 4) if p + r else 0.0
    return out
def tune_cv(fit, S0, ftr, fdv, same_art_dist=1.0):
    """threshold = best mean F1 over FOLDS topic-held-out folds of train (model refit without the held-out topics) plus dev, weighted by topic count"""
    folds = [list(range(len(ftr)))[i::FOLDS] for i in range(FOLDS)]; cv = collections.Counter()
    for hold in folds:
        Sk = as_scorer(fit(*sample_pairs(ftr, topics=set(range(len(ftr))) - set(hold))), S0); c = curve_feats(Sk, ftr, topics=set(hold), same_art_dist=same_art_dist)
        for t in GRID: cv[t] += c[t] / FOLDS
    params = fit(*sample_pairs(ftr)); full = as_scorer(params, S0); cd = curve_feats(full, fdv, same_art_dist=same_art_dist); nt, nd = len(ftr), len(fdv)
    comb = {t: round((cv[t] * nt + cd[t] * nd) / (nt + nd), 4) for t in GRID}; thr = max(GRID, key=lambda t: (comb[t], t)); full.threshold = thr
    return full, {"thr": thr, "cv_f1_at_thr": round(cv[thr], 4), "dev_f1_at_thr": cd[thr], "dev_best": list(max(((cd[t], t) for t in GRID))[::-1]), "grid": [GRID[0], GRID[-1], len(GRID)], "within_0.01_of_best": [t for t in GRID if comb[t] >= comb[thr] - 0.01], "folds": FOLDS, "weights": {"train_topics": nt, "dev_topics": nd}, "export_max_abs_diff": params.get("export_max_abs_diff")}
def baselines(dev_rows, test_rows, scorer):
    """the 4 outside-truth baselines of L2953 recomputed on the same test rows (join-test.py protocol: distance thresholds tuned on dev, no same-article rule)"""
    from scipy.cluster.hierarchy import fcluster
    out = {"exact_words": score_labels(test_rows, [(r["topic"], r["word"]) for r in test_rows]), "same_lemma": score_labels(test_rows, [(r["topic"], r["lemma"]) for r in test_rows])}
    if scorer._ensure_embed() is None: return out
    def links(rows, fn):
        L = []
        for ix in _groups(rows, "topic"):
            if len(ix) == 1: L.append((ix, None)); continue
            E = scorer.embed([fn(rows[i]) for i in ix]); D = np.clip(1 - E @ E.T, 0, 2); D = (D + D.T) / 2; np.fill_diagonal(D, 0); L.append((ix, linkage_of(D)))
        return L
    def lab(rows, L, th):
        pred = [None] * len(rows); base = 0
        for ix, Z in L:
            l = fcluster(Z, th, "distance") if Z is not None else [1]
            for i, x in zip(ix, l): pred[i] = base + int(x)
            base += int(max(l)) + 1
        return pred
    for name, fn in (("e5_event_word", lambda r: "query: " + r["word"]), ("e5_sentence", lambda r: "query: %s | %s" % (r["word"], r["sentence"]))):
        Ld, Lt = links(dev_rows, fn), links(test_rows, fn)
        th = max(((score_labels(dev_rows, lab(dev_rows, Ld, th))["f1"], th) for th in np.arange(0.005, 0.4, 0.005)))[1]
        out[name] = dict(score_labels(test_rows, lab(test_rows, Lt, th)), distance_threshold=round(float(th), 3))
    return out
def train(train_path, dev_path, test_path, out=MODEL_PATH):
    t0 = time.time(); S0 = Scorer(path=None); tr, dv, te = load_parquet(train_path), load_parquet(dev_path), load_parquet(test_path)
    log = lambda *a: print(*a, f"{time.time() - t0:.0f}s", file=sys.stderr)
    log(f"rows train {len(tr)} dev {len(dv)} test {len(te)}; embed mode {S0._ensure_embed() and S0.mode}")
    ftr, fdv, fte = topic_feats(tr, S0), topic_feats(dv, S0), topic_feats(te, S0); X, y = sample_pairs(ftr); log(f"features cached; pairs pos {int(y.sum())} neg {int((y == 0).sum())}")
    cand = {}
    for name, fit in (("logistic-regression", fit_lr), ("hist-gradient-boosting", fit_gbm)):
        S, info = tune_cv(fit, S0, ftr, fdv); info["test"] = evaluate(te, S); info["test_without_same_article_rule"] = evaluate(te, S, same_art_dist=None); info["dev"] = evaluate(dv, S)
        cand[name] = (S, info); log(f"{name}: thr {info['thr']} dev f1 {info['dev']['f1']} test f1 {info['test']['f1']}")
    lr, gbm = cand["logistic-regression"], cand["hist-gradient-boosting"]; gap = round(gbm[1]["dev"]["f1"] - lr[1]["dev"]["f1"], 4)
    exportable = bool(gbm[0].trees) and (gbm[1]["export_max_abs_diff"] or 0) < 1e-9
    ship = "hist-gradient-boosting" if gap > 0.03 and exportable else "logistic-regression"; S, info = cand[ship]; oname = "logistic-regression" if ship != "logistic-regression" else "hist-gradient-boosting"; other = cand[oname][1]
    base = baselines(dv, te, S0); log(f"ship {ship} (dev gap gbm-lr {gap}); baselines done")
    model = {"version": VERSION, "model": ship, "features": FEATURES, "mean": [round(float(c), 6) for c in S.mean], "std": [round(float(c), 6) for c in S.std], "threshold": S.threshold, "embed": EMBED_MODEL, "cosine_decimals": 4, "linkage": "average over 1 - prob, cut at 1 - threshold; same-article distance 1.0",
             "trained_on": {"train_mentions": len(tr), "dev_mentions": len(dv), "test_mentions": len(te), "train_topics": len(ftr), "dev_topics": len(fdv), "test_topics": len(fte), "pairs_pos": int(y.sum()), "pairs_neg": int((y == 0).sum()), "negatives_per_positive": NEG_PER_POS, "seed": SEED},
             "dev": {"p": info["dev"]["precision"], "r": info["dev"]["recall"], "f1": info["dev"]["f1"], "thr": info["thr"], "thr_selection": "best mean cluster F1 over %d topic-held-out folds of train plus dev, weighted by topic count" % FOLDS, "thr_grid": {k: info[k] for k in ("grid", "cv_f1_at_thr", "dev_f1_at_thr", "dev_best", "within_0.01_of_best", "weights")}},
             "test": {"p": info["test"]["precision"], "r": info["test"]["recall"], "f1": info["test"]["f1"], "pairs_pred": info["test"]["pairs_pred"], "pairs_gold": info["test"]["pairs_gold"], "without_same_article_rule": info["test_without_same_article_rule"], "baselines": base},
             "shipping_rule": {"rule": "logistic regression unless GBM beats it by > 0.03 F1 on dev at the CV thresholds and exports without pickle", "dev_gap_gbm_minus_lr": gap, "gbm_exportable": exportable, "gbm_export_max_abs_diff": gbm[1]["export_max_abs_diff"], "shipped": ship,
                               "other": {"model": oname, "thr": other["thr"], "dev": other["dev"], "test": other["test"], "test_without_same_article_rule": other["test_without_same_article_rule"]}},
             "gbm": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=4, random_state=0), exported as node arrays (f, t, l, r, v) per tree + base", "license": LICENSE, "created": datetime.date.today().isoformat()}
    if ship == "logistic-regression": model.update(coef=[round(float(c), 6) for c in S.coef], intercept=round(S.intercept, 6))
    else: model.update(trees=S.trees, base=S.base, n_trees=len(S.trees), n_nodes=sum(len(t["f"]) for t in S.trees), lr={"coef": [round(float(c), 6) for c in lr[0].coef], "intercept": round(lr[0].intercept, 6), "mean": [round(float(c), 6) for c in lr[0].mean], "std": [round(float(c), 6) for c in lr[0].std], "threshold": lr[1]["thr"]})
    with open(out, "w") as f: json.dump(model, f, separators=(",", ":")); f.write("\n")
    log(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")
    print(f"{'method (ECB+ test, cross-doc pairs within topic)':62s} {'prec':>6s} {'recall':>6s} {'F1':>6s} {'pairs':>7s}")
    for n, s in (("A exact words", base["exact_words"]), ("B same lemma", base["same_lemma"]), ("C e5 cosine, event word (thr dev)", base.get("e5_event_word")), ("D e5 cosine, word | sentence (thr dev)", base.get("e5_sentence")),
                 (f"LR fact-join, thr {lr[1]['thr']} (same-article never merge)", lr[1]["test"]), (f"LR fact-join, thr {lr[1]['thr']} (no same-article rule)", lr[1]["test_without_same_article_rule"]),
                 (f"GBM fact-join, thr {gbm[1]['thr']} (same-article never merge)", gbm[1]["test"]), (f"GBM fact-join, thr {gbm[1]['thr']} (no same-article rule)", gbm[1]["test_without_same_article_rule"])):
        if s: print(f"{n:62s} {s['precision']:6.3f} {s['recall']:6.3f} {s['f1']:6.3f} {s['pairs_pred']:7d}")
    print(f"dev F1: LR {lr[1]['dev']['f1']} GBM {gbm[1]['dev']['f1']} gap {gap} -> shipped {ship}")
    return model
def main(argv):
    if "--train" in argv:
        train(argv[argv.index("--train") + 1], argv[argv.index("--dev") + 1], argv[argv.index("--test") + 1]); return
    if "--make-fixture" in argv:
        i = argv.index("--make-fixture"); n = int(argv[argv.index("--topics") + 1]) if "--topics" in argv else 4
        d = make_fixture(load_parquet(argv[i + 1]), argv[i + 2], n); print(json.dumps({"out": argv[i + 2], "count": d["count"], "topics": d["topics"], "pairs": d["cross_doc_gold_pairs"], "bytes": os.path.getsize(argv[i + 2])})); return
    if "--eval" in argv:
        S = Scorer(); rows = load_any(argv[argv.index("--eval") + 1]); t0 = time.time(); r = evaluate(rows, S)
        print(json.dumps(dict(r, threshold=S.threshold, model=S.kind, mode=S.mode, version=S.model["version"] if S.model else None, seconds=round(time.time() - t0, 1), source=os.path.basename(argv[argv.index("--eval") + 1])))); return
    print(__doc__)
if __name__ == "__main__": main(sys.argv[1:])
