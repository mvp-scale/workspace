"""T33 step 3: grouped cross-validated supervised factuality head on human labelled MAVEN-FACT validation events, CPU embedding + logistic regression.
    /workspace/models/embed-zs/.venv/bin/python factuality_head_cv.py   (from projects/world-state)"""
import json, sys, math, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert3
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.feature_extraction.text import TfidfVectorizer
import scipy.sparse as sp, re, os
WINDOW = int(os.environ.get("WINDOW", "0"))
e = Expert3("runs/expert1/expert1_v5_leaf.pkl")
items = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")]; G = json.load(open("/workspace/data/anchors/maven_fact/gold_T33b.json"))
X = np.array([e.embed(x["text"]) for x in items], dtype=np.float32); y = np.array([1 if G[x["id"]]["yes"] else 0 for x in items]); grp = np.array([x["id"].split(":")[1] for x in items])
def win(t, k=4):
    w = t.split(); a = w.index("«") if "«" in w else 0; b = w.index("»") if "»" in w else a
    return " ".join(w[max(0, a - k):a] + ["TRIGGER"] + w[b + 1:b + 1 + k]).lower()
WT = [win(x["text"]) for x in items]
oof = np.zeros(len(y)); 
for tr, te in GroupKFold(n_splits=5).split(X, y, grp):
    if WINDOW:
        tv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit([WT[i] for i in tr]); Xtr = sp.hstack([sp.csr_matrix(X[tr]), tv.transform([WT[i] for i in tr])]).tocsr(); Xte = sp.hstack([sp.csr_matrix(X[te]), tv.transform([WT[i] for i in te])]).tocsr()
    else: Xtr, Xte = X[tr], X[te]
    m = LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000).fit(Xtr, y[tr]); oof[te] = m.predict(Xte)
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(max(c - h, 0), 3), round(c + h, 3)]
tp = int(((oof == 1) & (y == 1)).sum()); tn = int(((oof == 0) & (y == 0)).sum()); P = int((y == 1).sum()); N = int((y == 0).sum())
ba = (tp / P + tn / N) / 2
# interval for balanced accuracy by normal approximation of the mean of two proportions
se = 0.5 * math.sqrt((tp / P) * (1 - tp / P) / P + (tn / N) * (1 - tn / N) / N)
cls = {}
for x, p in zip(items, oof):
    f = G[x["id"]]["factuality"]; cls.setdefault(f, [0, 0]); cls[f][1] += 1; cls[f][0] += int((p == 1) == (f == "CT+"))
res = {"n": len(y), "documents": len(set(grp)), "recall_happened": [tp, P, round(tp / P, 3)], "recall_not_happened": [tn, N, round(tn / N, 3)], "balanced_accuracy": round(ba, 3), "ci95_normal": [round(ba - 1.96 * se, 3), round(ba + 1.96 * se, 3)], "correct_by_class": {k: [a, b, round(a / b, 2)] for k, (a, b) in cls.items()}, "qwen_zero_shot_same_items": 0.774, "window_features": bool(WINDOW), "line_pass": bool(ba >= 0.85 and ba - 1.96 * se >= 0.82), "ms_embed_per_event": None}
json.dump(res, open("runs/xtest/B11/factuality_head_cv%s.json" % ("_window" if WINDOW else ""), "w"), indent=1); print(json.dumps(res))
