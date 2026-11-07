"""T37 step 2: event trigger detector feasibility on CPU. Token tagger (logistic regression on word, suffix, shape and neighbour features), 5 fold CV grouped by document, MAVEN-FACT validation file only. Exact token match of the trigger.
    /workspace/kev/.venv/bin/python -I event_trigger_cv.py"""
import json, time, numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
P = "/workspace/data/anchors/maven_fact/valid.jsonl"; OUT = "runs/pulse/event_trigger_cv.json"
docs = [json.loads(l) for l in open(P)]
def shape(w): return ("C" if w[:1].isupper() else "l" if w[:1].islower() else "d" if w[:1].isdigit() else "p") + str(min(len(w), 9))
def feats(sent):
    out = []
    for i, w in enumerate(sent):
        lw = w.lower(); f = {"w=" + lw: 1, "s2=" + lw[-2:]: 1, "s3=" + lw[-3:]: 1, "s4=" + lw[-4:]: 1, "p3=" + lw[:3]: 1, "sh=" + shape(w): 1, "first": int(i == 0)}
        for d in (-2, -1, 1, 2):
            j = i + d; v = sent[j].lower() if 0 <= j < len(sent) else "<pad>"
            f[f"w{d}=" + v] = 1; f[f"s{d}=" + v[-3:]] = 1
        out.append(f)
    return out
X, Y, G, S = [], [], [], []
for di, d in enumerate(docs):
    trig = set()
    for e in d["events"]:
        for m in e["mention"]: trig.add((m["sent_id"], m["offset"][0]))  # first token of the trigger; multi word triggers are rare
    for si, sent in enumerate(d["tokens"]):
        F = feats(sent)
        for ti, f in enumerate(F): X.append(f); Y.append(int((si, ti) in trig)); G.append(di); S.append((di, si))
Y = np.array(Y); G = np.array(G); print("tokens", len(Y), "positives", int(Y.sum()), "documents", len(docs))
tp = fp = fn = 0; ms = []
for k, (tr, te) in enumerate(GroupKFold(5).split(X, Y, G)):
    dv = DictVectorizer(); Xtr = dv.fit_transform([X[i] for i in tr]); clf = LogisticRegression(max_iter=300, C=2.0, class_weight=None).fit(Xtr, Y[tr])
    t0 = time.time(); Xte = dv.transform([X[i] for i in te]); p = clf.predict_proba(Xte)[:, 1]; dt = time.time() - t0
    nsent = len({S[i] for i in te}); ms.append(1000 * dt / nsent)
    pred = p >= 0.4; y = Y[te]; tp += int((pred & (y == 1)).sum()); fp += int((pred & (y == 0)).sum()); fn += int((~pred & (y == 1)).sum())
    print("fold", k, "ms per sentence", round(ms[-1], 2))
pr = tp / (tp + fp); rc = tp / (tp + fn); f1 = 2 * pr * rc / (pr + rc)
res = {"precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3), "threshold": 0.4, "ms_per_sentence_mean": round(float(np.mean(ms)), 2), "tokens": int(len(Y)), "positives": int(Y.sum()), "documents": len(docs), "cv": "5 fold GroupKFold by document"}
json.dump(res, open(OUT, "w"), indent=1); print(res)
