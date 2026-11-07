"""Inline-training limit test (pre-registered L1033). Reads the 100k sample in 10 steps of 10000; tools mint URL-section Domain labels; a hashed word model is retrained after each step (A: labels only; B: plus its own top-20% most confident guesses on unlabelled articles). Judge: MN-DS human labels, never trained on.
    /workspace/models/embed-zs/.venv/bin/python inline_sim.py"""
import json, random, time, collections, numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.svm import LinearSVC
S = {r["row"]: r for r in map(json.loads, open("runs/harvest/sample100k.jsonl"))}; H = {r["row"]: r for r in map(json.loads, open("runs/harvest/labels100k.jsonl"))}
rows = sorted(S); random.Random(20261107).shuffle(rows); hv = HashingVectorizer(n_features=2**20, ngram_range=(1, 2), alternate_sign=False, norm="l2")
txt = lambda r: ((r["title"] or "") + ". " + (r["text"] or ""))[:3000]
t0 = time.time(); X = hv.transform([txt(S[k]) for k in rows]); print("features", round(time.time() - t0), "s", flush=True)
M = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; M = [m for m in M if m.get("category_level_1") and m.get("content")]
XT = hv.transform([(m["title"] or "") + ". " + m["content"][:3000] for m in M]); yT = np.array([m["category_level_1"] for m in M]); share = collections.Counter(yT)
lab = np.array([H[k].get("domain_label", {}).get("label") if k in H else None for k in rows], dtype=object); out = []
def fit_eval(idx, y):
    t = time.time(); c = LinearSVC(C=0.5).fit(X[idx], y); sec = time.time() - t; p = c.predict(XT); cov = set(c.classes_)
    return c, {"train_n": len(idx), "top1": round(float((p == yT).mean()), 4), "seconds": round(sec, 1), "classes": len(cov), "ceiling_all_classes": round(sum(v for k, v in share.items() if k in cov) / len(yT), 4)}
for step in range(1, 11):
    n = step * 10000; ids = np.arange(n); L = ids[[lab[i] is not None for i in ids]]; cnt = collections.Counter(lab[L])
    c, A = fit_eval(L, lab[L].astype(str)); A["labels"] = int(len(L)); A["classes_ge60"] = sum(v >= 60 for v in cnt.values()); A["ceiling_ge60"] = round(sum(v for k, v in share.items() if cnt.get(k, 0) >= 60) / len(yT), 4)
    U = ids[[lab[i] is None for i in ids]]; d = c.decision_function(X[U]); s = np.sort(d, axis=1); mar = s[:, -1] - s[:, -2]; top = U[np.argsort(-mar)[: int(0.2 * len(U))]]; ps = c.classes_[c.decision_function(X[top]).argmax(1)]
    _, B = fit_eval(np.concatenate([L, top]), np.concatenate([lab[L].astype(str), ps])); B["pseudo"] = int(len(top))
    out.append({"step": step, "articles": n, "A_labels_only": A, "B_self_training": B, "label_counts": dict(cnt)}); print(step, A["labels"], A["top1"], B["top1"], A["seconds"], B["seconds"], flush=True)
json.dump({"steps": out, "mnds_n": len(yT), "mnds_class_share": {k: round(v / len(yT), 4) for k, v in share.items()}}, open("runs/harvest/inline_sim.json", "w"), indent=1)
