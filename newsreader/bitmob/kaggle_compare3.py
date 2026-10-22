"""Topic sweep (run 3 + run 5): accuracy of each model, blends with e5tfidf, and blends of the best 2-3, vs the D-0030 candidate (run-1 e5-base + e5tfidf) and the round-3 ensemble. Paired bootstrap B resamples.
  kev/.venv/bin/python newsreader/bitmob/kaggle_compare3.py [B=2000]  -> data/suite_kaggle3/compare.json"""
import numpy as np, json, sys, glob, os, itertools
W = "/workspace/data/"; rs = np.random.RandomState(0); B = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ld = lambda p: np.load(W + p + ".npz", allow_pickle=True)
tf = ld("suite_r3/e5tfidf/topic"); ens = ld("suite_r3/ensemble/topic"); Y = tf["Y"].argmax(1); n = len(Y)
single = {os.path.basename(os.path.dirname(f)): ld(os.path.dirname(f)[len(W):] + "/topic")["P"] for f in sorted(glob.glob(W + "suite_kaggle3/*/topic.json"))}
acc = lambda P, i=slice(None): float((P[i].argmax(1) == Y[i]).mean())
sets = {"ensemble r3": ens["P"], "D-0030 (run1 e5-base + tfidf)": (ld("suite_kaggle1/e5-base-v2/topic")["P"] + tf["P"]) / 2}
for k, P in single.items(): sets[k] = P; sets[k + "+tfidf"] = (P + tf["P"]) / 2
best = sorted(single, key=lambda k: -acc(single[k]))
for r in (2, 3):
    for c in itertools.combinations(best[:4], r): sets["+".join(c) + "+tfidf"] = (sum(single[k] for k in c) + tf["P"]) / (r + 1); sets["+".join(c)] = sum(single[k] for k in c) / r
val = {k: acc(P) for k, P in sets.items()}; top = sorted(val, key=lambda k: -val[k])[:6]; idxs = [rs.randint(0, n, n) for _ in range(B)]; out = {"accuracy": {k: round(v, 4) for k, v in sorted(val.items(), key=lambda x: -x[1])}}
for c in top:
    for r in ("D-0030 (run1 e5-base + tfidf)", "ensemble r3"):
        if c == r: continue
        d = [acc(sets[c], i) - acc(sets[r], i) for i in idxs]; lo, hi = np.percentile(d, [2.5, 97.5]); out[f"{c} vs {r}"] = [round(val[c] - val[r], 4), round(float(lo), 4), round(float(hi), 4)]
json.dump(out, open(W + "suite_kaggle3/compare.json", "w"), indent=1); print(json.dumps(out, indent=1))
