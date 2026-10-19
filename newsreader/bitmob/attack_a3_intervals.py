"""Attack A3 (docs/value-indicators.md): the open verdicts F02 (Grammar), F03 (Locate), F07 (chunks), F08 (teasers) on the one scorer
(value_eval.py: R@9 with 95% intervals against the single head and the jury). Every option is a per-atom logistic head, cross-fitted with the
same folds as the baselines, differing from the single Glance head only in the one thing being tested:
  G1 Glance + sentence count (sentences containing the atom's words, per part)       G2 G1 + tense / modal / negation in those sentences (spaCy)
  L1 Glance + Locate features (spaCy entities, countries, actor types)
  C1 chunk max: the Glance head applied to each 80-word chunk (title + chunk), story score = highest chunk     C2 Glance + chunk-max as a feature
  T1 Glance head trained without teaser stories (test unchanged)
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/attack_a3_intervals.py"""
import sys, os, json, re, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from joblib import Parallel, delayed
from model2vec import StaticModel
F = f"{V.D}/features"; G = np.load(f"{F}/glance_full.npy"); LOC = np.load(f"{F}/locate.npy")
first = {r["id"]: r for r in map(json.loads, open(f"{V.D}/queue.jsonl"))}; rows = [first[i] for i in V.ids]; teaser = np.array([r.get("depth") == "teaser" for r in rows])
SN = json.load(open(f"{F}/sieve_names.json")); LEX = {a: re.compile(r"\b(" + "|".join(map(re.escape, ws)) + r")\w*", re.I) for a, ws in SN["lexicon"].items()}
import spacy
nlp = spacy.load("en_core_web_sm", disable=["lemmatizer", "ner"])
texts = [r["title"] + ". " + " ".join(r["text"].split()[:1200]) for r in rows]
SENTS = [[(s.text, any(t.dep_ == "neg" for t in s), any(t.tag_ == "MD" and t.lower_ != "will" for t in s), any(t.lower_ == "will" for t in s), any(t.tag_ == "VBD" for t in s)) for s in d.sents] for d in nlp.pipe(texts, n_process=12, batch_size=32)]
pm = StaticModel.from_pretrained("minishlab/potion-base-32M"); CH, OWN = [], []
for k, r in enumerate(rows):
    w = r["text"].split()
    for i in range(0, max(1, min(len(w), 1200)), 80): CH.append(r["title"] + ". " + " ".join(w[i:i + 80])); OWN.append(k)
CV = pm.encode(CH); OWN = np.array(OWN)
tr_idx = np.where(V.TRN)[0]; te_idx = np.where(V.test)[0]
def gfeat(a, grammar):
    rx = LEX.get(a)
    if rx is None: return None
    out = []
    for ss in SENTS:
        m = [s for s in ss if rx.search(s[0])]; v = [np.log1p(len(m))]
        if grammar: v += [np.mean([s[j] for s in m]) for j in (1, 2, 3, 4)] if m else [0, 0, 0, 0]
        out.append(v)
    X = np.array(out, float); return StandardScaler().fit(X[V.TRN]).transform(X)
def head(X, y, fit_mask=None, chunk=False):
    """cross-fitted scores; fit_mask limits which training stories are used; chunk=True scores each story by its best chunk"""
    s = np.zeros(len(V.ids)); fm = V.TRN if fit_mask is None else (V.TRN & fit_mask)
    for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(tr_idx, y[tr_idx]):
        fit = np.intersect1d(tr_idx[a], np.where(fm)[0]); m = LogisticRegression(C=4, class_weight="balanced", max_iter=5000).fit(X[fit], y[fit])
        if chunk:
            pc = m.predict_proba(CV)[:, 1]; best = np.full(len(V.ids), 0.0); np.maximum.at(best, OWN, pc); s[tr_idx[b]] = best[tr_idx[b]]; s[te_idx] += best[te_idx] / 5
        else: s[tr_idx[b]] = m.predict_proba(X[tr_idx[b]])[:, 1]; s[te_idx] += m.predict_proba(X[te_idx])[:, 1] / 5
    return s
LOCs = StandardScaler().fit(LOC[V.TRN]).transform(LOC)
def one(n):
    y = V.L[n]["agreed"]; out = {}
    g1, g2 = gfeat(n, False), gfeat(n, True)
    if g1 is not None: out["G1"] = head(np.hstack([G, g1 * 0.5]), y); out["G2"] = head(np.hstack([G, g2 * 0.5]), y)
    out["L1"] = head(np.hstack([G, LOCs * 0.1]), y); out["C1"] = head(G, y, chunk=True); out["T1"] = head(G, y, fit_mask=~teaser)
    out["C2"] = head(np.hstack([G, out["C1"][:, None] * 3]), y)
    return n, out
res = dict(Parallel(n_jobs=12)(delayed(one)(n) for n in V.ATOMS))
NAME = {"G1": "G1 Glance + sentence count", "G2": "G2 + tense/modal/negation (Grammar)", "L1": "L1 Glance + Locate", "C1": "C1 chunk max", "C2": "C2 Glance + chunk max feature", "T1": "T1 trained without teasers"}
opts = {NAME[k]: {n: res[n][k] for n in V.ATOMS if k in res[n]} for k in NAME}
V.evaluate(opts, out_file=f"{V.D}/proof/a3-results.json")
