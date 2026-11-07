"""Domain from many views (pre-registered L1047). Seeds on the pool: URL section (if the Reader topic set agrees) else confident Reader class. Views trained on seeds; Reader view untrained; one-coin Dawid-Skene combination estimated on the unlabelled ruler; MN-DS labels used only to score.
    /workspace/models/embed-zs/.venv/bin/python domain_evidence.py   -> runs/harvest/domain_evidence.json"""
import json, pickle, numpy as np, collections, itertools
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
D = pickle.load(open("runs/harvest/domain_feats.pkl", "rb")); pool, ruler, cl = D["pool"], D["ruler"], D["topic_cl"]; MAP = json.load(open("specs/topic_to_iptc_v1.json"))["map"]
C = sorted(set(json.load(open("specs/topic_to_iptc_v1.json"))["iptc"])); K = len(C); ci = {c: i for i, c in enumerate(C)}; yR = np.array([ci[o["ruler"]] for o in ruler])
def rvec(p):  # reader topic probs -> 17-class scores: primary class weight 1, other accepted classes 0.5
    v = np.zeros(K)
    for k, pk in enumerate(p):
        cs = MAP.get(cl[k], [])
        for j, c in enumerate(cs): v[ci[c]] += pk * (1.0 if j == 0 else 0.5)
    return v / max(v.sum(), 1e-9)
for o in pool: o["rv"] = rvec(o["reader"])
# seeds
seed = []; stats = collections.Counter()
for o in pool:
    top2 = set(c for k in np.argsort(-o["reader"])[:2] for c in MAP.get(cl[k], [])); rtop = float(o["reader"].max())
    if o["url_label"]:
        if o["url_label"] in top2: seed.append(ci[o["url_label"]]); stats["url_agrees_reader"] += 1
        else: seed.append(None); stats["url_disagrees_reader"] += 1
    elif rtop >= 0.5: seed.append(int(o["rv"].argmax())); stats["reader_confident"] += 1
    else: seed.append(None); stats["no_seed"] += 1
idx = [i for i, s in enumerate(seed) if s is not None]; ys = np.array([seed[i] for i in idx]); print("seeds", len(idx), dict(stats), "classes", len(set(ys)), flush=True)
def soft(d, classes):
    z = np.full((d.shape[0], K), -1e9); z[:, classes] = d; z = z - z.max(1, keepdims=True); p = np.exp(z); return p / p.sum(1, keepdims=True)
def hv(n): return HashingVectorizer(n_features=n, ngram_range=(1, 2), alternate_sign=False, norm="l2")
def fit_text(f, n=2**20):
    h = hv(n); m = LinearSVC(C=0.5).fit(h.transform([f(pool[i]) for i in idx]), ys); return soft(m.decision_function(h.transform([f(o) for o in ruler])), m.classes_)
def ent_doc(o): return " ".join(o["ents"])
hE = HashingVectorizer(n_features=2**18, alternate_sign=False, norm="l2", analyzer=lambda s: s.split(" "))
def struct(o):
    k = max(o["chars"], 1) / 1000; f = [np.log1p(o["chars"])]
    for dct, names in ((o["scan"], ["entity", "quote", "money", "percent", "date", "quantity", "attribution", "modal", "negation", "event", "change"]), (o["facts"], ["amount_stated", "date_stated", "name_stated", "triple_stated", "name_unbound", "triple_unbound"]), (o["func"], ["asserted", "reported", "planned", "predicted", "denied", "question", "request", "decision"]), (o["etypes"], ["PERSON", "ORG", "GPE", "DATE", "MONEY", "PERCENT", "CARDINAL", "NORP", "LOC", "TIME", "QUANTITY", "ORDINAL"])): f += [dct.get(n, 0) / k for n in names]
    return f
Xs = np.array([struct(o) for o in pool]); Xr = np.array([struct(o) for o in ruler]); sc = StandardScaler().fit(Xs[idx]); lr = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(Xs[idx]), ys)
P = {}
P["body words"] = fit_text(lambda o: o["text"][:3000]); P["headline + description words"] = fit_text(lambda o: o["title"] + ". " + o["desc"])
mE = LinearSVC(C=0.5).fit(hE.transform([ent_doc(pool[i]) for i in idx]), ys); P["entity names"] = soft(mE.decision_function(hE.transform([ent_doc(o) for o in ruler])), mE.classes_)
P["structure counts"] = soft(np.log(np.clip(lr.predict_proba(sc.transform(Xr)), 1e-6, 1)), lr.classes_)
probs = np.load("runs/harvest/domain_mnds_topic_probs.npy").astype(np.float32); P["reader topics"] = np.array([rvec(p) for p in probs])
names = list(P); votes = {n: P[n].argmax(1) for n in names}
def ds(use, iters=30):
    a = {n: 0.5 for n in use}; N = len(yR)
    for _ in range(iters):
        L = np.zeros((N, K))
        for n in use: v = votes[n]; L += np.log((1 - a[n]) / (K - 1)); L[np.arange(N), v] += np.log(a[n]) - np.log((1 - a[n]) / (K - 1))
        L -= L.max(1, keepdims=True); post = np.exp(L); post /= post.sum(1, keepdims=True)
        a = {n: float(np.clip(post[np.arange(N), votes[n]].mean(), 0.05, 0.95)) for n in use}
    return post, a
post, a = ds(names); comb = post.argmax(1); res = {"seeds": len(idx), "seed_stats": dict(stats), "pool": len(pool), "ruler": len(yR), "views": {}}
for n in names: res["views"][n] = {"top1": round(float((votes[n] == yR).mean()), 4), "estimated_reliability": round(a[n], 3)}
agree = np.array([[votes[n][i] == comb[i] for n in names] for i in range(len(yR))]).sum(1); ok = comb == yR
res["combined"] = {"top1": round(float(ok.mean()), 4), "top2_contains": round(float(np.mean([yR[i] in np.argsort(-post[i])[:2] for i in range(len(yR))])), 4)}
res["agreement"] = {str(k): {"coverage": round(float((agree >= k).mean()), 4), "precision": round(float(ok[agree >= k].mean()), 4) if (agree >= k).any() else None} for k in (2, 3, 4, 5)}
res["leave_one_out"] = {n: round(float((ds([m for m in names if m != n])[0].argmax(1) == yR).mean()), 4) for n in names}
cc = {}
for c in range(K):
    m = comb == c
    if m.sum() >= 20: cc[C[c]] = [int(m.sum()), round(float(ok[m].mean()), 3)]
res["combined_by_class"] = cc; json.dump(res, open("runs/harvest/domain_evidence.json", "w"), indent=1); print(json.dumps(res, indent=1))
# exploratory (not pre-registered): equal-weight probability averages and pairs with the Reader
ex = {}
avg = lambda ns, w=None: sum((w or {}).get(n, 1.0) * P[n] for n in ns)
ex["average, all 5 views"] = round(float((avg(names).argmax(1) == yR).mean()), 4)
for n in names:
    if n != "reader topics": ex["reader + " + n] = round(float(((P["reader topics"] + P[n]).argmax(1) == yR).mean()), 4)
ex["reader x2 + other 4"] = round(float((avg(names, {"reader topics": 2.0}).argmax(1) == yR).mean()), 4)
ex["reader x3 + other 4"] = round(float((avg(names, {"reader topics": 3.0}).argmax(1) == yR).mean()), 4)
res["exploratory_unregistered"] = ex; json.dump(res, open("runs/harvest/domain_evidence.json", "w"), indent=1); print(json.dumps(ex, indent=1))
