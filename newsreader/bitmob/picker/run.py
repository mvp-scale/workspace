import json, sys, pickle, numpy as np, collections
from lib import *
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
rng = np.random.RandomState(0)
dials = json.load(open("dials.json"))
trn = load_jsonl("train_nlp.jsonl"); tsn = load_jsonl("test_nlp.jsonl")
trr = load_jsonl("train_in.jsonl"); tsr = load_jsonl("test_in.jsonl")
ytr = np.array([bool(dials[n["id"]]) for n in trn]); yts = np.array([bool(dials[n["id"]]) for n in tsn])
dtr = [set(dials[n["id"]]) for n in trn]; dts = [set(dials[n["id"]]) for n in tsn]
Ltr = [lemset(n) for n in trn]; Lts = [lemset(n) for n in tsn]
ctab = conc_table()
F = {"chg": lambda n: change_feats(n, ctab), "conc": lambda n: conc_feats(n, ctab), "ner": ner_feats}
X = {k: (np.array([f(n) for n in trn], float), np.array([f(n) for n in tsn], float)) for k, f in F.items()}
X["chg+conc+ner"] = tuple(np.hstack([X[k][i] for k in F]) for i in (0, 1))
TXT = ([" ".join(n["lem"]) for n in trn], [" ".join(n["lem"]) for n in tsn])
folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(np.zeros(len(ytr)), ytr))
MODELS = {}
SIG = {}  # name -> (oof_train, test)
def cv(name, fit_score):
    """fit_score(tr_idx, ev_idx_or_None) ; returns scores for given set"""
    oof = np.zeros(len(ytr))
    for a, b in folds: oof[b] = fit_score(a, ("tr", b))
    SIG[name] = (oof, fit_score(np.arange(len(ytr)), ("ts", None)))
def sub(L, idx): return [L[i] for i in idx]
def kwfit(expand):
    def fs(a, ev):
        KW = mine(sub(Ltr, a), sub(dtr, a))
        if expand: KW = wn_expand(KW, sub(Ltr, a), sub(dtr, a))
        if ev[0] == "ts": MODELS["kw_wn" if expand else "kw_lemma"] = KW
        docs = sub(Ltr, ev[1]) if ev[0] == "tr" else Lts
        return kw_score(docs, KW)
    return fs
def lrfit(key, C=1.0):
    def fs(a, ev):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000)); m.fit(X[key][0][a], ytr[a])
        if ev[0] == "ts": MODELS[key] = m
        Z = X[key][0][ev[1]] if ev[0] == "tr" else X[key][1]
        return m.decision_function(Z)
    return fs
def bowfit(C):
    def fs(a, ev):
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, stop_words=list(STOP)); A = v.fit_transform(sub(TXT[0], a))
        m = LogisticRegression(C=C, max_iter=3000).fit(A, ytr[a])
        if ev[0] == "ts": MODELS["bow"] = (v, m)
        return m.decision_function(v.transform(sub(TXT[0], ev[1]) if ev[0] == "tr" else TXT[1]))
    return fs
# choose BoW C by inner CV on train only
best = None
for C in (.25, .5, 1, 4):
    oof = np.zeros(len(ytr))
    for a, b in folds: oof[b] = bowfit(C)(a, ("tr", b))
    from sklearn.metrics import roc_auc_score
    au = roc_auc_score(ytr, oof); print("bow C", C, "train-CV AUC", round(au, 4)); best = max(best or (0, C), (au, C))
CBOW = best[1]
cv("kw_lemma", kwfit(False)); print("kw_lemma"); cv("kw_lemma+wordnet", kwfit(True)); print("wn")
cv("change_language", lrfit("chg")); cv("concreteness", lrfit("conc")); cv("entity_density", lrfit("ner")); cv("bow_logreg", bowfit(CBOW))
# baselines on test
import re
KW0 = json.load(open("../kw.json")); T0 = lambda t: set(w for w in re.findall(r"[a-z]{3,}", t.lower()) if w not in STOP)
SIG["BASE kw_raw (kw.json)"] = (None, kw_score([T0(r["state_text"]) for r in tsr], KW0))
bm_ok = os.path.exists("bm_train.npy") and os.path.exists("bm_test.npy")
if bm_ok: SIG["bitmob"] = (np.load("bm_train.npy"), np.load("bm_test.npy"))
# combiners (fit on TRAIN OOF scores only)
def comb(names, name, C=1.0):
    A = np.column_stack([SIG[k][0] for k in names]); B = np.column_stack([SIG[k][1] for k in names])
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000)).fit(A, ytr)
    SIG[name] = (None, m.decision_function(B)); return m
free = ["kw_lemma", "kw_lemma+wordnet", "change_language", "concreteness", "entity_density", "bow_logreg"]
mfree = comb(free, "COMBINED free (LR on train-OOF)")
comb([k for k in free if not k.startswith("kw")], "combined no-keyword (non-obvious)")
if bm_ok:
    comb(free + ["bitmob"], "COMBINED free+BitMob (LR; BitMob train scores may be leaky)")
    from scipy.stats import rankdata
    rk = lambda s: rankdata(s) / len(s)
    SIG["rank-avg free + BitMob (no fitting)"] = (None, rk(SIG["COMBINED free (LR on train-OOF)"][1]) + rk(SIG["bitmob"][1]))
# evaluate on test
alld = set().union(*dts); res = {}
print("test: %d stories, %d with condition, %d distinct dials among them" % (len(yts), yts.sum(), len(alld)))
for name, (_, s) in SIG.items():
    o = np.argsort(-(s + rng.rand(len(s)) * 1e-9)); r = {}
    for kp in (.11, .2, .37):
        k = int(round(kp * len(s))); sel = o[:k]
        r[f"keep{int(kp*100)}"] = {"share": round(float(yts[sel].mean()), 3), "catch": round(float(yts[sel].sum() / yts.sum()), 3),
                                   "dials_covered": len(set().union(*[dts[i] for i in sel]))}
    from sklearn.metrics import roc_auc_score as A_
    r["auc"] = round(float(A_(yts, s)), 3); res[name] = r
    print(f"{name:55s} AUC {r['auc']:.3f} | " + " | ".join(f"{k}: share {v['share']:.0%} catch {v['catch']:.0%} dials {v['dials_covered']}" for k, v in r.items() if k.startswith("keep")))
res["_meta"] = {"bow_C": CBOW, "n_train": len(ytr), "n_test": len(yts), "test_dials_total": len(alld), "bitmob_in_run": bm_ok}
json.dump(res, open("results.json", "w"), indent=1)
MODELS["comb_free"] = mfree
if bm_ok: MODELS["comb_bm"] = comb(free + ["bitmob"], "tmp")
MODELS["free"] = free
pickle.dump(MODELS, open("picker_meta.pkl", "wb"))
