"""Paired bootstrap (2000 resamples of test stories) of Kaggle bigger encoders vs round-3 e5ft and ensemble. data/suite_kaggle1 vs data/suite_r3."""
import numpy as np, json, sys
from sklearn.metrics import average_precision_score
W = "/workspace/data/"; rs = np.random.RandomState(0); B = 2000
ld = lambda p: np.load(W + p + ".npz", allow_pickle=True)
def cls(P):
    h, a, o, f = P.T; fact = ((h >= .5) | (a >= .5)) & (o < .5) & (f < .5)
    return np.where(fact, 0, np.where(f >= .5, 1, np.where(o >= .5, 2, 3)))
def ap_mean(Y, P, idx): return np.mean([average_precision_score(Y[idx, i], P[idx, i]) for i in range(Y.shape[1])])
def boot(n, fn):  # fn(idx)->value ; returns point, ci of paired diff computed by caller
    return [rs.randint(0, n, n) for _ in range(B)]
out = {}
for area in ["topic", "type"]:
    base = ld(f"suite_r3/e5ft/{area}"); ens = ld(f"suite_r3/ensemble/{area}"); tf = ld(f"suite_r3/e5tfidf/{area}"); Y = base["Y"]; n = len(Y)
    assert (ens["Y"] == Y).all() and (tf["Y"] == Y).all()
    idxs = [rs.randint(0, n, n) for _ in range(B)]
    if area == "topic": mets = {"acc": lambda Y, P, i: (Y[i].argmax(1) == P[i].argmax(1)).mean()}
    else:
        jc = cls(Y.astype(float)); mets = {"mAP": lambda Y, P, i: ap_mean(Y, P, i), "wclass": lambda Y, P, i: (cls(P)[i] == jc[i]).mean()}
    refs = {"e5ft": base["P"], "ensemble": ens["P"]}
    cands = {m: ld(f"suite_kaggle1/{m}/{area}")["P"] for m in ["e5-base-v2", "e5-large-v2"]}
    for m in list(cands): cands[m + "+e5tfidf"] = (cands[m] + tf["P"]) / 2
    for mn, f in mets.items():
        full = np.arange(n); vals = {}
        for name, P in {**refs, **cands}.items(): vals[name] = f(Y, P, full)
        for c in cands:
            for r in refs:
                if mn == "mAP" and n * B > 0 and False: pass
                d = [] ; 
                for i in idxs[:int(sys.argv[1]) if len(sys.argv) > 1 else B]: d.append(f(Y, cands[c], i) - f(Y, refs[r], i))
                lo, hi = np.percentile(d, [2.5, 97.5]); out[f"{area}|{mn}|{c} vs {r}"] = [round(float(vals[c] - vals[r]), 4), round(float(lo), 4), round(float(hi), 4)]
        for k, v in vals.items(): out[f"{area}|{mn}|{k}"] = round(float(v), 4)
json.dump(out, open(W + "suite_kaggle1/compare.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
