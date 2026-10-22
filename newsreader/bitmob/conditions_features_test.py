"""Conditions on CPU vs engine (Jev) labels, with and without detection features (T-0016, D-0016, D-0017).

Same elements and split as bakeoff_baseline.py (keys with >= 30 positives; random 80/20, seed 0). Candidates, each logistic regression per key:
  tfidf, e5 (baselines, F-0048), e5+tfidf, e5+tfidf+det (det = significance.py parts + rise/fall cue counts).
Scores are agreement with Jev labels (the engine's teacher), not accuracy against people.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/conditions_features_test.py
"""
import json, re, collections, statistics, numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer

R = [json.loads(l) for l in open("/workspace/data/trainset/night1.jsonl")]
G = {r["id"]: r for r in map(json.loads, open("/workspace/data/topic-test/night1-significance.jsonl"))}
X = [r["input"] for r in R]
kc = collections.Counter(k for r in R for k in r["target_keys"]); keys = [k for k, n in kc.most_common() if n >= 30]
both = sum(1 for r in R if any(k.rsplit("|", 1)[0] + "|" + ("down" if k.endswith("|up") else "up") in r["target_keys"] for k in r["target_keys"]))
idx_tr, idx_te = train_test_split(np.arange(len(R)), test_size=0.2, random_state=0)

UP = re.compile(r"\b(rise[sn]?|rose|rising|up|surge[sd]?|jump(s|ed)?|increase[sd]?|climb(s|ed)?|soar(s|ed)?|double[sd]?|grow(s|n)?|grew|higher|more|record high|boost(s|ed)?)\b", re.I)
DOWN = re.compile(r"\b(fall(s|en|ing)?|fell|down|drop(s|ped)?|cut[s]?|decrease[sd]?|slump(s|ed)?|plunge[sd]?|halve[sd]?|shrink(s)?|shrank|lower|less|fewer|record low|ease[sd]?|curb(s|ed)?)\b", re.I)
def det(r):
    g = G[r["id"]]; t = r["input"]
    return [g["people"] == v for v in ("one", "few", "many", "unknown")] + [g["scale"] == v for v in ("narrow", "wide", "unknown")] + \
           [g["measured_change"], g["incident"], len(UP.findall(t)) / 3, len(DOWN.findall(t)) / 3, len(g["evidence"].get("magnitude", [])) / 2, len(g["evidence"].get("places", [])) / 3]
D = csr_matrix(np.array([det(r) for r in R], dtype=float))
A = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit_transform(X)
E = csr_matrix(SentenceTransformer("intfloat/e5-small-v2", device="cpu").encode(["query: " + x for x in X], batch_size=64, normalize_embeddings=True, show_progress_bar=False))
cands = {"tfidf": (A, 4.0), "e5": (E, 1.0), "e5+tfidf": (hstack([E, A]).tocsr(), 2.0), "e5+tfidf+det": (hstack([E, A, D]).tocsr(), 2.0), "e5+tfidf+det*0.2": (hstack([E, A, D * 0.2]).tocsr(), 2.0)}  # det*0.2: post-hoc scaling check (T-0016)
res = {}
for k in keys:
    y = np.array([k in r["target_keys"] for r in R]); res[k] = {"positives": int(y.sum()), "test_pos": int(y[idx_te].sum())}
    for c, (M, C) in cands.items():
        p = LogisticRegression(max_iter=3000, class_weight="balanced", C=C).fit(M[idx_tr], y[idx_tr]).predict_proba(M[idx_te])[:, 1]
        res[k][c] = round(average_precision_score(y[idx_te], p), 3)
summ = {c: {"mean_AP": round(statistics.mean(v[c] for v in res.values()), 3), "keys_AP_ge_0.70": sum(v[c] >= 0.70 for v in res.values())} for c in cands}
out = {"records": len(R), "keys": len(keys), "both_up_and_down_stories": both, "both_share": round(both / len(R), 4), "summary": summ, "per_key": res}
json.dump(out, open("/workspace/data/topic-test/conditions-features.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("keys", "both_up_and_down_stories", "both_share", "summary")}, indent=1))
for k, v in sorted(res.items(), key=lambda x: -x[1]["e5+tfidf"])[:0]: print(f"  {k:34s} pos {v['positives']:4d}  " + "  ".join(f"{c} {v[c]:.2f}" for c in cands))
