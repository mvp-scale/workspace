"""Per-label cuts for the type reader fitted on night1 held-out (first n_night rows, max F1), scored on testA only: per-label F1/precision/recall and weight-class agreement vs the 0.5 cut.
  kev/.venv/bin/python newsreader/bitmob/type_thresholds.py -> data/suite_kaggle4/type_thresholds.json"""
import numpy as np, json
W = "/workspace/data/"; ld = lambda p: np.load(W + p + ".npz", allow_pickle=True)
e = ld("suite_r3/ensemble/type"); b = ld("suite_kaggle4/e5-base-v2/type"); tf = ld("suite_r3/e5tfidf/type"); Y = e["Y"].astype(bool); nn = int(e["n_night"]); keys = list(e["keys"])
def cls(P, th):
    h, a, o, f = (P >= th).T; fact = (h | a) & ~o & ~f; return np.where(fact, 0, np.where(f, 1, np.where(o, 2, 3)))
out = {}
for name, P in {"ensemble r3": e["P"], "e5-base r4": b["P"], "e5-base r4 + tfidf": (b["P"] + tf["P"]) / 2}.items():
    th = []
    for i in range(4):
        best, t = -1, .5
        for c in np.arange(.05, .96, .01):
            pr = P[:nn, i] >= c; f1 = 2 * (pr & Y[:nn, i]).sum() / max(1, pr.sum() + Y[:nn, i].sum())
            if f1 > best: best, t = f1, c
        th.append(round(float(t), 2))
    th = np.array(th); r = {"cuts": dict(zip(keys, th.tolist()))}
    for lab, T in (("cut 0.5", np.full(4, .5)), ("tuned", th)):
        pr = P[nn:] >= T; y = Y[nn:]; per = {k: {"precision": round(float((pr[:, i] & y[:, i]).sum() / max(1, pr[:, i].sum())), 3), "recall": round(float((pr[:, i] & y[:, i]).sum() / max(1, y[:, i].sum())), 3)} for i, k in enumerate(keys)}
        jc = cls(Y[nn:].astype(float), np.full(4, .5)); r[lab] = {"weight_class_agreement_with_Jev": round(float((cls(P[nn:], T) == jc).mean()), 4), "per_label": per}
    out[name] = r
json.dump(out, open(W + "suite_kaggle4/type_thresholds.json", "w"), indent=1)
for n, r in out.items(): print(n, r["cuts"], "wclass 0.5:", r["cut 0.5"]["weight_class_agreement_with_Jev"], "tuned:", r["tuned"]["weight_class_agreement_with_Jev"], {k: (v["precision"], v["recall"]) for k, v in r["tuned"]["per_label"].items()})
