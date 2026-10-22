# run from free_signals/: CUDA_VISIBLE_DEVICES= python tricks/run_tricks.py
import os, sys, io, contextlib
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.insert(0, os.getcwd())
src = open("run.py").read().split("# evaluate on test")[0]
with contextlib.redirect_stdout(io.StringIO()): exec(src)   # reuse harness: data, folds, existing signals (writes nothing)
import scipy.sparse as sp, math
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_selection import chi2, SelectKBest
from sklearn.naive_bayes import ComplementNB
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
rawtr = [r["state_text"] for r in trr]; rawts = [r["state_text"] for r in tsr]
assert [r["id"] for r in trr] == [n["id"] for n in trn]
TRN = {}  # new signals
def cvn(name, fs):
    oof = np.zeros(len(ytr))
    for a, b in folds: oof[b] = fs(a, ("tr", b))
    SIG[name] = (oof, fs(np.arange(len(ytr)), ("ts", None))); TRN[name] = 1
    print(name, "trainCV AUC %.3f" % roc_auc_score(ytr, oof), flush=True)
def pick(ev, a): return (sub(rawtr, ev[1]) if ev[0] == "tr" else rawts)
# T1 tf-idf sublinear word 1-2 + char_wb 3-5, class-weighted LR
def tfidf_fs(char, cw, C):
    def fs(a, ev):
        vw = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, stop_words=list(STOP)); A = [vw.fit_transform(sub(rawtr, a))]; vs = [vw]
        if char:
            vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=150000); A.append(vc.fit_transform(sub(rawtr, a))); vs.append(vc)
        m = LogisticRegression(C=C, max_iter=3000, class_weight=cw).fit(sp.hstack(A).tocsr(), ytr[a])
        return m.decision_function(sp.hstack([v.transform(pick(ev, a)) for v in vs]).tocsr())
    return fs
def best_C(fsmaker, Cs):
    out = []
    for C in Cs:
        oof = np.zeros(len(ytr))
        for a, b in folds: oof[b] = fsmaker(C)(a, ("tr", b))
        out.append((roc_auc_score(ytr, oof), C))
    print("  C search (train CV only):", [(round(x, 3), c) for x, c in out]); return max(out)[1]
C1 = best_C(lambda C: tfidf_fs(False, "balanced", C), (.5, 2, 8)); cvn("T1 tfidf word sublinear+balanced LR", tfidf_fs(False, "balanced", C1))
C2 = best_C(lambda C: tfidf_fs(True, "balanced", C), (.5, 2, 8)); cvn("T1b tfidf word+char_wb LR balanced", tfidf_fs(True, "balanced", C2))
# T2 chi2 top-k + ComplementNB on counts
def cnb_fs(k):
    def fs(a, ev):
        v = CountVectorizer(ngram_range=(1, 2), min_df=3, stop_words=list(STOP), binary=True); A = v.fit_transform(sub(rawtr, a))
        sel = SelectKBest(chi2, k=min(k, A.shape[1])).fit(A, ytr[a]); m = ComplementNB(alpha=.5).fit(sel.transform(A), ytr[a])
        Z = sel.transform(v.transform(pick(ev, a))); return m.predict_log_proba(Z)[:, 1] - m.predict_log_proba(Z)[:, 0] if hasattr(m, "predict_log_proba") else m.decision_function(Z)
    return fs
cvn("T2 chi2(2000)+ComplementNB", cnb_fs(2000))
# T3 per-dial one-vs-rest LR on tf-idf, noisy-or / max
DL = sorted({d for ds in dtr for d in ds}); cnt = collections.Counter(d for ds in dtr for d in ds); DL = [d for d in DL if cnt[d] >= 15]
def perdial_fs(mode):
    def fs(a, ev):
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, stop_words=list(STOP)); A = v.fit_transform(sub(rawtr, a)); Z = v.transform(pick(ev, a)); P = []
        for d in DL:
            y = np.array([d in dtr[i] for i in a])
            if y.sum() < 5: continue
            P.append(LogisticRegression(C=4, max_iter=2000, class_weight="balanced").fit(A, y).predict_proba(Z)[:, 1])
        P = np.array(P).T; PERD[mode] = P
        return 1 - np.prod(1 - P, 1) if mode == "noisyor" else P.max(1)
    return fs
PERD = {}
cvn("T3 per-dial LR (noisy-or of 1-vs-rest)", perdial_fs("noisyor")); cvn("T3b per-dial LR (max)", perdial_fs("max"))
# T4 BM25 similarity of story to per-dial centroid documents (train positives), vs a 'no condition' centroid
def tok(t): return [w for w in re.findall(r"[a-z]{3,}", t.lower()) if w not in STOP]
TKtr = [tok(t) for t in rawtr]; TKts = [tok(t) for t in rawts]
def bm25_fs(k1=1.2, b=.75):
    def fs(a, ev):
        docs = {d: collections.Counter(w for i in a if d in dtr[i] for w in TKtr[i]) for d in DL}
        docs["_none"] = collections.Counter(w for i in a if not dtr[i] for w in TKtr[i])
        names = list(docs); N = len(names); dl = np.array([sum(docs[n].values()) for n in names], float); avg = dl.mean()
        dfw = collections.Counter(w for n in names for w in docs[n]); idf = {w: math.log(1 + (N - c + .5) / (c + .5)) for w, c in dfw.items()}
        Q = [TKtr[i] for i in ev[1]] if ev[0] == "tr" else TKts; out = np.zeros((len(Q), N))
        for qi, q in enumerate(Q):
            for w in set(q):
                if w not in idf: continue
                for j, n in enumerate(names):
                    tf = docs[n].get(w, 0)
                    if tf: out[qi, j] += idf[w] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl[j] / avg))
        out = out / (out.sum(1, keepdims=True) + 1e-9)   # share of similarity going to each document
        BMS[ev[0]] = out; return out[:, :-1].max(1) - out[:, -1]
    return fs
BMS = {}
cvn("T4 BM25 to per-dial centroid docs (max share - 'none' share)", bm25_fs())
# T5 compromise lemma/pattern + wink sentiment/negation features
FT = [load_jsonl("tricks/feat_train.jsonl"), load_jsonl("tricks/feat_test.jsonl")]; keys = [k for k in FT[0][0] if k != "id"]
assert [r["id"] for r in FT[0]] == [r["id"] for r in trr]
XF = [np.log1p(np.abs(np.array([[r[k] for k in keys] for r in R], float))) * np.sign(np.array([[r[k] for k in keys] for r in R], float)) for R in FT]
def feat_fs(sel):
    ix = [keys.index(k) for k in sel]
    def fs(a, ev):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=.5, max_iter=2000, class_weight="balanced")).fit(XF[0][a][:, ix], ytr[a])
        return m.decision_function(XF[0][ev[1]][:, ix] if ev[0] == "tr" else XF[1][:, ix])
    return fs
pat = ["up_val", "dn_val", "up_pct", "dn_pct", "val_pct_chg", "scar", "rec", "neg_chg", "amt_chg", "sent_chg_num", "sent_frac"]
cvn("T5a compromise change patterns", feat_fs(pat))
cvn("T5b wink sentiment+negation, verb tense", feat_fs(["vneg", "nverbs", "fut", "past", "neg_tok", "sent_mean", "sent_min", "sent_max"]))
cvn("T5c both", feat_fs(keys))
# T6 WordNet hyponym-closure + derivationally-related expansion of mined keywords (train-lift filtered, and unfiltered)
import nltk; nltk.data.path.insert(0, "data/nltk"); from nltk.corpus import wordnet as wn
def wn_closure(KW, docs, dsets, filt):
    N = len(docs); df = collections.Counter(w for t in docs for w in t); out = {}
    for d, ws in KW.items():
        prior = sum(1 for ds in dsets if d in ds) / N; cands = set()
        for w in ws:
            for s in wn.synsets(w)[:2]:
                for h in s.closure(lambda x: x.hyponyms(), depth=2):
                    cands.update(l.lower() for l in h.lemma_names())
                for l in s.lemmas():
                    cands.update(x.name().lower() for x in l.derivationally_related_forms())
        cands = {c for c in cands if W.fullmatch(c) and c not in STOP and c not in ws and df[c] >= (3 if filt else 1)}
        keep = []
        for c in cands:
            if not filt: keep.append(c); continue
            k = sum(1 for t, ds in zip(docs, dsets) if c in t and d in ds)
            if k >= 2 and k / df[c] >= 2 * prior: keep.append(c)
        out[d] = list(ws) + keep
    return out
def wncl_fs(filt):
    def fs(a, ev):
        KW = mine(sub(Ltr, a), sub(dtr, a)); KW = wn_closure(KW, sub(Ltr, a), sub(dtr, a), filt)
        return kw_score(sub(Ltr, ev[1]) if ev[0] == "tr" else Lts, KW)
    return fs
cvn("T6 WordNet hyponym+derived expansion (train-lift filtered)", wncl_fs(True)); cvn("T6b WordNet hyponym+derived expansion (unfiltered)", wncl_fs(False))
# stacking
def stack(names, name, C=1.0):
    A = np.column_stack([SIG[k][0] for k in names]); B = np.column_stack([SIG[k][1] for k in names])
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000))
    oof = np.zeros(len(ytr))
    for a, b in folds: oof[b] = m.fit(A[a], ytr[a]).decision_function(A[b])
    m.fit(A, ytr); SIG[name] = (oof, m.decision_function(B)); print(name, "stack trainCV AUC %.3f" % roc_auc_score(ytr, oof)); return roc_auc_score(ytr, oof)
new = list(TRN)
oldfree = free
stack(oldfree, "S0 old free (re-stacked, nested CV)")
cands = {"S1 free + all new": oldfree + new}
for n in new: cands["S+ free + " + n.split()[0]] = oldfree + [n]
cands["S2 new only (no old signals)"] = new
cands["S3 free + T1b+T3+T4+T5c+T6"] = oldfree + [n for n in new if n.split()[0] in ("T1b", "T3", "T4", "T5c", "T6")]
tcv = {k: stack(v, k) for k, v in cands.items()}
bestfree = max(tcv, key=tcv.get); print("BEST by train-CV AUC:", bestfree)
bmn = {}
for k, v in cands.items(): stack(v + ["bitmob"], k + " + BitMob")
stack(oldfree + ["bitmob"], "S0 old free + BitMob (re-stacked)")
# diversity pick: per-dial round-robin using per-dial probs from T3 test, on top of final score
from scipy.stats import rankdata
def evaluate(name, s):
    o = np.argsort(-(s + rng.rand(len(s)) * 1e-9)); r = {}
    for kp in (.11, .2, .37):
        k = int(round(kp * len(s))); sel = o[:k]
        r[f"keep{int(kp*100)}"] = {"share": round(float(yts[sel].mean()), 3), "catch": round(float(yts[sel].sum() / yts.sum()), 3), "dials_covered": len(set().union(*[dts[i] for i in sel]))}
    r["auc"] = round(float(roc_auc_score(yts, s)), 3); return r
def diversified(score, P, frac_div=.5):
    """pick: first half of budget by pure score; second half by best per-dial prob among dials not yet represented (round-robin)."""
    def sel_fn(k):
        o = list(np.argsort(-score)); chosen = o[:int(k * (1 - frac_div))]; seen = set(np.argmax(P[chosen], 1)); rest = o[len(chosen):]
        chosen = list(chosen)
        while len(chosen) < k and rest:
            # take the unchosen story with highest dial-prob in an under-represented dial
            cnt = collections.Counter(np.argmax(P[chosen], 1)); best = max(rest[:400], key=lambda i: score[i] - 0.5 * cnt[int(np.argmax(P[i]))] / max(1, k / len(DL)))
            chosen.append(best); rest.remove(best)
        return chosen
    return sel_fn
res = {n: evaluate(n, s) for n, (_, s) in SIG.items()}
# diversity eval on the best free stack and best with BitMob
Pts = PERD["noisyor"]  # NOTE: from last fit call (full-train fit on test) of per-dial model
for base in (bestfree, bestfree + " + BitMob"):
    s = SIG[base][1]
    for fd in (.3, .6):
        r = {}
        for kp in (.11, .2, .37):
            k = int(round(kp * len(s))); sel = np.array(diversified(s, Pts, fd)(k))
            r[f"keep{int(kp*100)}"] = {"share": round(float(yts[sel].mean()), 3), "catch": round(float(yts[sel].sum() / yts.sum()), 3), "dials_covered": len(set().union(*[dts[i] for i in sel]))}
        r["auc"] = res[base]["auc"]; res[f"{base} | diversity-picked {int(fd*100)}%"] = r
res["_meta"] = {"chosen_free": bestfree, "C_tfidf_word": C1, "C_tfidf_wordchar": C2, "train_cv_auc": {k: round(v, 4) for k, v in tcv.items()}, "n_train": len(ytr), "n_test": len(yts), "note": "bitmob train scores may be leaky as in results.json; all new signals fit on TRAIN only"}
json.dump(res, open("tricks_results.json", "w"), indent=1)
for n, r in res.items():
    if n.startswith("_"): continue
    print(f"{n[:70]:70s} AUC {r['auc']:.3f} | " + " | ".join(f"{k[4:]}%: sh {v['share']:.0%} ca {v['catch']:.0%} d{v['dials_covered']}" for k, v in r.items() if k.startswith("keep")))
