"""T37 steps 3 and 4 pre-check (L881): do CPU event features (trigger tagger + MAVEN happened head, both trained on MAVEN-FACT validation only) add to the v6b-student presence score for Sonnet condition presence on the 1997 devq items?
    /workspace/models/embed-zs/.venv/bin/python event_features_probe.py   (from projects/world-state)"""
import json, re, sys, time, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert3
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
import scipy.sparse as sp
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
# 1. trigger tagger on all MAVEN validation documents
docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]
X, Y = [], []
for d in docs:
    trig = {(m["sent_id"], m["offset"][0]) for e in d["events"] for m in e["mention"]}
    for si, s in enumerate(d["tokens"]):
        for ti, f in enumerate(feats(s)): X.append(f); Y.append(int((si, ti) in trig))
dv = DictVectorizer(); tag = LogisticRegression(max_iter=300, C=2.0).fit(dv.fit_transform(X), Y); print("tagger trained", len(Y))
# 2. happened head on the 1818 human labelled events (embedding + window n-grams, as L806)
e = Expert3("runs/expert1/expert1_v5_leaf.pkl")
items = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")]; G = json.load(open("/workspace/data/anchors/maven_fact/gold_T33b.json"))
def win(t, k=4):
    w = t.split(); a = w.index("«") if "«" in w else 0; b = w.index("»") if "»" in w else a
    return " ".join(w[max(0, a - k):a] + ["TRIGGER"] + w[b + 1:b + 1 + k]).lower()
Xh = np.array([e.embed(x["text"]) for x in items], dtype=np.float32); yh = np.array([1 if G[x["id"]]["yes"] else 0 for x in items])
tv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit([win(x["text"]) for x in items])
hap = LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000).fit(sp.hstack([sp.csr_matrix(Xh), tv.transform([win(x["text"]) for x in items])]).tocsr(), yh); print("happened head trained", len(yh))
# 3. devq items: event features
dq = [json.loads(l) for l in open("runs/pulse/devq_items.jsonl")]; ids = [x["id"] for x in dq]
lab = {}
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": lab[r["item_id"]] = int(r["n_conditions"] > 0)
z = np.load("runs/pulse/prod_presence_scores.npz", allow_pickle=True); zi = list(z["ids"]); print("score arrays", {k: (z[k].dtype, z[k][:3]) for k in ("yes", "conf", "pos")})
score = {i: float(c) for i, c in zip(zi, z["conf"])}
tok = lambda s: re.findall(r"\w+|[^\w\s]", s)
sent_split = lambda t: [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
F = []; t0 = time.time()
for x in dq:
    n_trig = n_hap = 0; mx = 0.0; ps = []
    for s in sent_split(x["text"]):
        w = tok(s)
        if not w: continue
        p = tag.predict_proba(dv.transform(feats(w)))[:, 1]
        for ti in np.where(p >= 0.4)[0][:8]:
            n_trig += 1; marked = " ".join(w[:ti] + ["«", w[ti], "»"] + w[ti + 1:])
            xe = sp.hstack([sp.csr_matrix(e.embed(marked).reshape(1, -1)), tv.transform([win(marked)])]).tocsr(); ph = hap.predict_proba(xe)[0, 1]
            ps.append(ph); n_hap += int(ph >= 0.5); mx = max(mx, ph)
    F.append([n_trig, n_hap, mx, n_hap / max(n_trig, 1), float(np.mean(ps)) if ps else 0.0])
print("event features done", round(time.time() - t0), "s")
keep = [k for k, i in enumerate(ids) if i in lab and i in score]; print("items with label and score", len(keep), "of", len(ids)); F = np.array(F)[keep]; ids = [ids[k] for k in keep]; y = np.array([lab[i] for i in ids]); s = np.array([score[i] for i in ids]); print("positives", int(y.sum()), "of", len(y))
def cv(Xm, name):
    oof = np.zeros(len(y))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(Xm, y):
        oof[te] = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(Xm[tr], y[tr]).predict_proba(Xm[te])[:, 1]
    auc = roc_auc_score(y, oof); thr = np.sort(oof)[::-1]; out = {"auc": round(auc, 4)}
    for target in (0.5, 0.8):  # precision at recall target
        o = np.argsort(-oof); tp = np.cumsum(y[o]); k = int(np.searchsorted(tp, target * y.sum())) + 1; out[f"precision_at_recall_{target}"] = round(tp[k - 1] / k, 3)
    print(name, out); return out
A = cv(s.reshape(-1, 1), "A v6b score only"); Fz = (F - F.mean(0)) / (F.std(0) + 1e-9); B = cv(np.hstack([s.reshape(-1, 1), Fz]), "B score + event features"); C = cv(Fz, "C event features only")
json.dump({"n": len(y), "positives": int(y.sum()), "A": A, "B": B, "C_event_only": C, "auc_gain_B_over_A": round(B["auc"] - A["auc"], 4), "feature_means": F.mean(0).round(3).tolist()}, open("runs/pulse/event_features_probe.json", "w"), indent=1)
