"""Trained CPU heads for direction, off the condition chain (pre-registered L953). Same 4024 stories as direction_gate.py. Grouped 5-fold CV by title prefix.
    /workspace/models/embed-zs/.venv/bin/python direction_cls.py   (from projects/world-state)"""
import json, re, glob, numpy as np, scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
exec(open("direction_gate.py").read().split("res = {")[0])      # reuses the data load and the lexicon (UP, DOWN, S, H, pool, ids)
cache = np.load("runs/pulse/kind_cascade_emb.npz"); cid = {i: n for n, i in enumerate(cache["ids"])}; keep = [i for i in ids if i in cid]; print("stories", len(ids), "with cached embedding", len(keep), flush=True)
T = [re.sub(r"\s+", " ", pool[i])[:600] for i in keep]; y = np.array([int(S[i] == {"down"}) for i in keep]); E = cache["E1"][[cid[i] for i in keep]]
lex = np.array([[len(re.findall(UP, t, re.I)), len(re.findall(DOWN, t, re.I))] for t in T], dtype=float); lex = np.hstack([lex, (lex[:, 0] - lex[:, 1])[:, None]])
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T]); tf = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
def cv(make):
    oof = np.zeros(len(y))
    for a, b in GroupKFold(5).split(T, groups=gid):
        Xa, Xb = make(a, b); oof[b] = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(Xa, y[a]).predict_proba(Xb)[:, 1]
    return oof
def tfidf(a, b): v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True).fit([T[i] for i in a]); return v.transform([T[i] for i in a]), v.transform([T[i] for i in b])
def tfidf_lex(a, b): xa, xb = tfidf(a, b); return sp.hstack([xa, sp.csr_matrix(lex[a] / 3)]).tocsr(), sp.hstack([xb, sp.csr_matrix(lex[b] / 3)]).tocsr()
heads = {"lexicon_counts_only": lambda a, b: (lex[a], lex[b]), "tfidf_word_pairs": tfidf, "embedding": lambda a, b: (E[a], E[b]), "tfidf_plus_lexicon": tfidf_lex}
base_up = float(1 - y.mean()); res = {"stories": len(y), "always_up_accuracy": round(base_up, 3), "down_share": round(float(y.mean()), 3), "heads": {}}
for name, mk in heads.items():
    p = cv(mk); pred = (p >= 0.5).astype(int); acc = float((pred == y).mean()); tp = int(((pred == 1) & (y == 1)).sum()); out = {"accuracy": round(acc, 3), "down_precision": round(tp / max(int(pred.sum()), 1), 3), "down_recall": round(tp / max(int(y.sum()), 1), 3), "down_auc": round(float(roc_auc_score(y, p)), 3)}
    for cls, score in (("down", p), ("up", 1 - p)):
        truth = y if cls == "down" else 1 - y; best = 0
        for t in np.linspace(0.5, 0.99, 50):
            m = score >= t
            if m.sum() >= 20 and truth[m].mean() >= 0.85: best = max(best, float(m.sum() / len(y)))
        out[f"{cls}_coverage_at_precision_0_85"] = round(best, 3)
    res["heads"][name] = out; print(name, out, flush=True)
json.dump(res, open("runs/pulse/direction_cls.json", "w"), indent=1)
