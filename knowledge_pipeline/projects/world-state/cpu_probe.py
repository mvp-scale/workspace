#!/usr/bin/env python3
"""Free CPU probe: how close does a cheap local model get to the two teachers on TOPIC and STORY_TYPE?
Train on items where Haiku and Sonnet agreed (waves 1-5 dev slices); test on wave 6 against each teacher. Never uses the frozen 300.
Run with models/embed-zs/.venv/bin/python (CPU only)."""
import json, os, pathlib, sys, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
W = pathlib.Path(__file__).resolve().parent / "runs" / "waves"
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
def load(n):
    items = {r["id"]: r["text"] for r in J(W / f"w{n}_items.jsonl")}
    H = {r["item_id"]: r["label"] for r in J(W / f"w{n}/haiku/labels.jsonl")}; S = {r["item_id"]: r["label"] for r in J(W / f"w{n}/sonnet/labels.jsonl")}
    return [(i, items[i], H[i], S[i]) for i in items if i in H and i in S]
train = [x for n in range(1, 6) for x in load(n)]; test = load(6)
for key in ("topic", "story_type"):
    tr = [(t, h[key]) for _, t, h, s in train if h[key] == s[key]]
    X, y = [t for t, _ in tr], [l for _, l in tr]
    th, ts = [t for _, t, _, _ in test], None
    print(f"\n== {key}: train {len(tr)} consensus items (of {len(train)}), test {len(test)} items (W6)")
    print(f"   Haiku vs Sonnet on test: {np.mean([h[key]==s[key] for _,_,h,s in test]):.3f}")
    def report(name, clf, feat_tr, feat_te, secs):
        p = clf.predict(feat_te)
        a_h = np.mean([a == h[key] for a, (_, _, h, s) in zip(p, test)]); a_s = np.mean([a == s[key] for a, (_, _, h, s) in zip(p, test)])
        print(f"   {name:<28} vs Haiku {a_h:.3f}  vs Sonnet {a_s:.3f}   ({secs:.1f}s fit+predict)")
    t0 = time.time(); v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); Xt = v.fit_transform(X)
    clf = LogisticRegression(max_iter=300, C=10).fit(Xt, y); report("TF-IDF + logistic regression", clf, Xt, v.transform(th), time.time() - t0)
    try:
        from model2vec import StaticModel
        m = StaticModel.from_pretrained("minishlab/potion-base-8M"); t0 = time.time()
        E = m.encode(X); Et = m.encode(th); clf2 = LogisticRegression(max_iter=500, C=10).fit(E, y)
        report("static embedding (potion-8M)", clf2, E, Et, time.time() - t0)
    except Exception as e: print("   static embedding skipped:", type(e).__name__, str(e)[:80])
