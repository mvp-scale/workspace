"""Receipts, item 5 of the proof standard (docs/proof-standard.md): 95% bootstrap intervals (story resampling, 300 draws) for every comparison
behind a "does not work" verdict that can be computed from the cross-fitted voters (data/mm3-train/crossfit-voters-v2.pkl).
Each option's per-atom cut-off is fixed on training stories; one shift applied to all atoms traces its curve; the statistic is recall at <= 9 false
positives per 100 test stories (and <= 4). Differences are taken against the base jury and the single head in the same resample.
Writes data/mm3-train/proof/bootstrap.json."""
import json, hashlib, pickle, os, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold
D = "/workspace/data/mm3-train"; os.makedirs(f"{D}/proof", exist_ok=True); ids = json.load(open(f"{D}/features/ids.json"))
res = pickle.load(open(f"{D}/crossfit-voters-v2.pkl", "rb")); L = {n: lab for n, lab, _ in res}; PP = {n: pr for n, _, pr in res}
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); test = h == 0; TRN = ~test; NT = int(test.sum()); tr = np.where(TRN)[0]
ATOMS = [n for n in PP if L[n]["agreed"][TRN].sum() >= 6 and all(k in PP[n] for k in (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"), ("glance_full", "agreed"), ("sieve", "agreed")))]
Y = np.array([L[n]["agreed"][test] for n in ATOMS]); M = np.array([L[n]["T"][test] for n in ATOMS])
DS = np.linspace(-0.9, 0.95, 38)
def shift(c, d): return c + d * (1 - c) if d >= 0 else c * (1 + d)
def prec_cut(s, y): return next((t for t in np.linspace(.05, .99, 95) if (s >= t).sum() >= 3 and y[s >= t].mean() >= .8), .99)
def f1_cut(s, y): return max(np.linspace(.02, .98, 49), key=lambda t: f1_score(y, s >= t))
def single(key):
    out = np.zeros((len(DS), len(ATOMS), NT), bool)
    for k, n in enumerate(ATOMS):
        s = PP[n][key]; c = prec_cut(s[TRN], L[n]["agreed"][TRN])
        for j, d in enumerate(DS): out[j, k] = s[test] >= shift(c, d)
    return out
def jury(voters):
    out = np.ones((len(DS), len(ATOMS), NT), bool)
    for k, n in enumerate(ATOMS):
        for v in voters:
            lab = L[n][v[1]]; s = PP[n][v]; c = f1_cut(s[TRN], lab[TRN])
            for j, d in enumerate(DS): out[j, k] &= s[test] >= shift(c, d)
    return out
def combiner(views):
    out = np.zeros((len(DS), len(ATOMS), NT), bool)
    for k, n in enumerate(ATOMS):
        y = L[n]["agreed"]; Xs = np.column_stack([PP[n][v, a] for v in views for a in ("a", "b", "agreed", "reversed") if (v, a) in PP[n]])
        cv = cross_val_predict(LogisticRegression(class_weight="balanced", max_iter=3000), Xs[tr], y[tr], cv=StratifiedKFold(4, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        st = LogisticRegression(class_weight="balanced", max_iter=3000).fit(Xs[tr], y[tr]).predict_proba(Xs[test])[:, 1]; c = prec_cut(cv, y[tr])
        for j, d in enumerate(DS): out[j, k] = st >= shift(c, d)
    return out
BASE = [("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed")]
OPT = {"single Glance head": single(("glance_full", "agreed")), "single Glance + scoped Sieve": single(("glance_full+scoped", "agreed")),
       "jury (base)": jury(BASE), "jury + Sieve as 4th voter": jury(BASE + [("sieve", "agreed")]), "jury + Echo as 4th voter": jury(BASE + [("echo", "agreed")]),
       "jury cheap (Glance+scoped, Scholar lead, Glance lead)": jury([("glance_full+scoped", "a"), ("scholar_lead", "b"), ("glance_lead", "agreed")]),
       "combiner Glance + Scholar": combiner(["glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead"]),
       "combiner tier 1 (Glance+scoped, Sieve, Echo)": combiner(["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo"])}
YT, NO = (Y & M), (~Y & M)
def stat(pred, w):
    """recall at <= 9 and <= 4 false positives per 100 stories, story weights w"""
    tp = ((pred & YT[None]) * w).sum((1, 2)); fp = ((pred & NO[None]) * w).sum((1, 2)); fn = ((~pred & YT[None]) * w).sum((1, 2)); n = w.sum()
    rec = tp / np.maximum(1, tp + fn); f = 100 * fp / n
    return [max([r for r, x in zip(rec, f) if x <= cap] or [0.0]) for cap in (9, 4)]
rng = np.random.default_rng(0); point = {k: stat(v, np.ones(NT)) for k, v in OPT.items()}; draws = {k: [] for k in OPT}
for b in range(300):
    w = np.bincount(rng.integers(0, NT, NT), minlength=NT).astype(float)
    for k, v in OPT.items(): draws[k].append(stat(v, w))
out = {"atoms": len(ATOMS), "test_stories": NT, "draws": 300, "options": {}}
for k in OPT:
    a = np.array(draws[k]); out["options"][k] = {"recall_at_fp9": round(point[k][0], 3), "ci95_fp9": [round(float(x), 3) for x in np.percentile(a[:, 0], [2.5, 97.5])],
                                                "recall_at_fp4": round(point[k][1], 3), "ci95_fp4": [round(float(x), 3) for x in np.percentile(a[:, 1], [2.5, 97.5])]}
    for ref in ("jury (base)", "single Glance head"):
        if k == ref: continue
        d = a - np.array(draws[ref]); out["options"][k][f"minus {ref}"] = {"fp9": [round(float(np.mean(d[:, 0])), 3)] + [round(float(x), 3) for x in np.percentile(d[:, 0], [2.5, 97.5])],
                                                                         "fp4": [round(float(np.mean(d[:, 1])), 3)] + [round(float(x), 3) for x in np.percentile(d[:, 1], [2.5, 97.5])]}
    o = out["options"][k]; print(f"{k:54s} R@9 {o['recall_at_fp9']:.3f} {o['ci95_fp9']}  vs jury " + (str(o.get('minus jury (base)', {}).get('fp9')) if 'minus jury (base)' in o else "-") + "  vs single " + (str(o.get('minus single Glance head', {}).get('fp9')) if 'minus single Glance head' in o else "-"), flush=True)
json.dump(out, open(f"{D}/proof/bootstrap.json", "w"), indent=1)
