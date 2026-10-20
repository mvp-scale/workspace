"""First BitMob baseline bake-off on a Jev-labelled training set (CPU only). Two candidates per element:
(1) TF-IDF (1-2 grams) + logistic regression; (2) e5-small-v2 frozen embeddings ("query: " prefix, per its model card) + logistic regression.
Elements: story type (happened/announced/opinion/forecast, Jev p >= 0.5), topic (classes with >= 20 examples, rest 'other'),
country (top 15 + 'other'), condition keys with >= 30 positives (target_keys, MV of 3 wordings). Split: random 80/20, seed 0.
Scores are agreement with Jev labels, not accuracy against people. Writes <set>-bakeoff.json and .md next to the set.
Run (CPU): CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python newsreader/bitmob/bakeoff_baseline.py data/trainset/night1.jsonl"""
import sys, json, time, collections, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, accuracy_score
from sklearn.model_selection import train_test_split
F = sys.argv[1]; OUT = F.replace(".jsonl", "-bakeoff")
R = [json.loads(l) for l in open(F)]
X = [r["input"] for r in R]
def log(m): print(time.strftime("%T"), m, flush=True)
elements = {}
for g in ("happened", "announced", "opinion", "forecast"): elements[f"type:{g}"] = ("bin", np.array([r["P"][f"g|{g}"] >= 0.5 for r in R]))
tc = collections.Counter(r["topic"] for r in R); elements["topic"] = ("multi", np.array([r["topic"] if tc[r["topic"]] >= 20 else "other" for r in R]))
cc = collections.Counter(r["country"] for r in R); top = {c for c, _ in cc.most_common(15)}; elements["country"] = ("multi", np.array([r["country"] if r["country"] in top else "other" for r in R]))
kc = collections.Counter(k for r in R for k in r["target_keys"])
for k, n in kc.most_common():
    if n >= 30: elements[f"key:{k}"] = ("bin", np.array([k in r["target_keys"] for r in R]))
log(f"{len(R)} records, {len(elements)} elements ({sum(1 for e in elements if e.startswith('key:'))} condition keys with >= 30 positives)")
idx_tr, idx_te = train_test_split(np.arange(len(R)), test_size=0.2, random_state=0)
t = time.time(); tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); A = tf.fit_transform(X); t_tf = time.time() - t
from sentence_transformers import SentenceTransformer
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
t = time.time(); E = e5.encode(["query: " + x for x in X], batch_size=64, normalize_embeddings=True, show_progress_bar=False); t_e5 = time.time() - t
log(f"features: tfidf {A.shape} in {t_tf:.0f}s, e5 {E.shape} in {t_e5:.0f}s ({t_e5 / len(X) * 1000:.1f} ms/article, batch 64, CPU)")
res = {}
for name, (kind, y) in elements.items():
    if len(set(y[idx_tr])) < 2: continue
    row = {"kind": kind, "positives_or_classes": int(y.sum()) if kind == "bin" else len(set(y))}
    for cand, M in (("tfidf", A), ("e5", E)):
        clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0 if cand == "tfidf" else 1.0)
        clf.fit(M[idx_tr], y[idx_tr]); pr = clf.predict(M[idx_te])
        if kind == "bin":
            p = clf.predict_proba(M[idx_te])[:, 1]
            row[cand] = {"AP": round(average_precision_score(y[idx_te], p), 3), "F1": round(f1_score(y[idx_te], pr), 3), "test_pos": int(y[idx_te].sum())}
        else:
            row[cand] = {"acc": round(accuracy_score(y[idx_te], pr), 3), "macroF1": round(f1_score(y[idx_te], pr, average="macro"), 3)}
    res[name] = row
t = time.time(); _ = e5.encode(["query: " + x for x in X[:200]], batch_size=1, show_progress_bar=False); ms1 = (time.time() - t) / 200 * 1000
summary = {"records": len(R), "train": len(idx_tr), "test": len(idx_te), "e5_ms_per_article_batch1_cpu": round(ms1, 1), "e5_ms_per_article_batch64_cpu": round(t_e5 / len(X) * 1000, 1), "elements": res}
json.dump(summary, open(OUT + ".json", "w"), indent=1)
lines = ["| Element | Positives / classes | TF-IDF | e5-small frozen |", "|---|---|---|---|"]
for n, r in res.items():
    f = (lambda d: f"AP {d['AP']}, F1 {d['F1']} ({d['test_pos']} test pos)") if r["kind"] == "bin" else (lambda d: f"acc {d['acc']}, macro-F1 {d['macroF1']}")
    lines.append(f"| {n} | {r['positives_or_classes']} | {f(r['tfidf'])} | {f(r['e5'])} |")
open(OUT + ".md", "w").write(f"# Baseline bake-off on {F}\n\nAgreement with Jev labels (not human truth). Test = 20% held out. e5-small CPU: {ms1:.1f} ms/article one at a time, {t_e5 / len(X) * 1000:.1f} ms batched.\n\n" + "\n".join(lines) + "\n")
log(f"done: {OUT}.md")
