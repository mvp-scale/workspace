"""The one scorer for every attack (docs/value-indicators.md). Fixed: 44 atoms (route-current.json), test split id hash % 5 == 0, reference R1 =
Clef agreed (both wordings) scored where the two wordings agree. An option is a dict atom -> score array over all stories (cross-fitted on the
training stories, test scored by the average of the fold models). Each atom's cut-off is chosen on training scores (precision >= 0.8); one shift
for all atoms traces the curve. Reports R@9, R@4, CR@9 (condition level: any atom of the condition) and usable atoms (R@9 >= 0.6), each with a 95%
bootstrap interval (300 story resamples), and differences against the two baselines in the same resamples.
Baselines (rebuilt here from data/mm3-train/crossfit-voters-v2.pkl, the same as proof/bootstrap.json): single Glance head; all-agree jury."""
import json, glob, hashlib, pickle, numpy as np
from sklearn.metrics import f1_score
D = "/workspace/data/mm3-train"; ids = json.load(open(f"{D}/features/ids.json"))
_res = pickle.load(open(f"{D}/crossfit-voters-v2.pkl", "rb")); L = {n: lab for n, lab, _ in _res}; PP = {n: pr for n, _, pr in _res}
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); test = h == 0; TRN = ~test; NT = int(test.sum())
ATOMS = [n for n in PP if L[n]["agreed"][TRN].sum() >= 6 and all(k in PP[n] for k in (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"), ("glance_full", "agreed")))]
COND = {}
for f in glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json"):
    for c in json.load(open(f))["concerns"]: COND[c["atom"]] = c["condition"]
for a in ATOMS: COND.setdefault(a, a)
CONDS = sorted({COND[a] for a in ATOMS}); DS = np.linspace(-0.9, 0.95, 38)
Y = np.array([L[n]["agreed"][test] for n in ATOMS]); M = np.array([L[n]["T"][test] for n in ATOMS])
def shift(c, d): return c + d * (1 - c) if d >= 0 else c * (1 + d)
def prec_cut(s, y): return next((t for t in np.linspace(.02, .99, 98) if (s >= t).sum() >= 3 and y[s >= t].mean() >= .8), .99)
def preds_from_scores(scores):
    """scores: atom -> array over all stories. Returns predictions (len(DS), atoms, test stories)."""
    out = np.zeros((len(DS), len(ATOMS), NT), bool)
    for k, n in enumerate(ATOMS):
        s = scores.get(n)
        if s is None: continue
        c = prec_cut(s[TRN], L[n]["agreed"][TRN])
        for j, d in enumerate(DS): out[j, k] = s[test] >= shift(c, d)
    return out
def jury_preds(voters=(("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"))):
    out = np.ones((len(DS), len(ATOMS), NT), bool)
    for k, n in enumerate(ATOMS):
        for v in voters:
            lab = L[n][v[1]]; s = PP[n][v]; c = max(np.linspace(.02, .98, 49), key=lambda t: f1_score(lab[TRN], s[TRN] >= t))
            for j, d in enumerate(DS): out[j, k] &= s[test] >= shift(c, d)
    return out
CI = np.array([[COND[a] == c for a in ATOMS] for c in CONDS])                     # condition x atom
YC = np.array([(Y[CI[i]]).any(0) for i in range(len(CONDS))]); MC = np.array([(M[CI[i]]).all(0) for i in range(len(CONDS))])
def _stats(pred, w):
    yt, no = Y & M, ~Y & M; tp = ((pred & yt[None]) * w).sum((1, 2)); fp = ((pred & no[None]) * w).sum((1, 2)); fn = ((~pred & yt[None]) * w).sum((1, 2)); n = w.sum()
    rec, f = tp / np.maximum(1, tp + fn), 100 * fp / n
    r9 = max([r for r, x in zip(rec, f) if x <= 9] or [0.0]); r4 = max([r for r, x in zip(rec, f) if x <= 4] or [0.0])
    ok = [j for j, x in enumerate(f) if x <= 9]; j9 = max(ok, key=lambda j: rec[j]) if ok else int(np.argmin(f))      # the shift that gives R@9 (best recall under the cap)
    pc = np.array([pred[j9][CI[i]].any(0) for i in range(len(CONDS))]); yct, noc = YC & MC, ~YC & MC
    ctp = ((pc & yct) * w).sum(); cfp = ((pc & noc) * w).sum(); cfn = ((~pc & yct) * w).sum(); cr = ctp / max(1, ctp + cfn); cf = 100 * cfp / n
    per_atom = ((pred[j9] & yt) * w).sum(1) / np.maximum(1, (yt * w).sum(1)); usable = float(np.mean(per_atom[(yt * w).sum(1) >= 3] >= .6)) if ((yt * w).sum(1) >= 3).any() else 0.0
    return np.array([r9, r4, cr, cf, usable])
NAMES = ["R@9", "R@4", "CR@9", "CR@9 false pos/100", "usable atoms"]
_BASE = None
def baselines():
    global _BASE
    if _BASE is None: _BASE = {"single Glance head": preds_from_scores({n: PP[n]["glance_full", "agreed"] for n in ATOMS}), "jury (all agree)": jury_preds()}
    return _BASE
def evaluate(options, draws=300, seed=0, out_file=None):
    """options: name -> predictions array or atom->scores dict. Prints and returns point values, intervals and differences vs both baselines."""
    opts = dict(baselines()); opts.update({k: (v if isinstance(v, np.ndarray) else preds_from_scores(v)) for k, v in options.items()})
    point = {k: _stats(v, np.ones(NT)) for k, v in opts.items()}; rng = np.random.default_rng(seed); dr = {k: [] for k in opts}
    for _ in range(draws):
        w = np.bincount(rng.integers(0, NT, NT), minlength=NT).astype(float)
        for k, v in opts.items(): dr[k].append(_stats(v, w))
    res = {}
    for k in opts:
        a = np.array(dr[k]); r = {NAMES[i]: {"value": round(float(point[k][i]), 3), "ci95": [round(float(x), 3) for x in np.percentile(a[:, i], [2.5, 97.5])]} for i in range(len(NAMES))}
        for b in ("single Glance head", "jury (all agree)"):
            if k != b:
                d = a - np.array(dr[b]); r[f"vs {b}"] = {NAMES[i]: [round(float(d[:, i].mean()), 3)] + [round(float(x), 3) for x in np.percentile(d[:, i], [2.5, 97.5])] for i in (0, 2)}
        res[k] = r
        vs = lambda b: (lambda x: f"{x[0]:+.3f} [{x[1]:+.3f},{x[2]:+.3f}]")(r[f"vs {b}"]["R@9"]) if f"vs {b}" in r else "-"
        print(f"{k:44s} R@9 {r['R@9']['value']:.3f} {r['R@9']['ci95']}  CR@9 {r['CR@9']['value']:.3f}  usable {r['usable atoms']['value']:.2f}  vs single {vs('single Glance head')}  vs jury {vs('jury (all agree)')}", flush=True)
    if out_file: json.dump(res, open(out_file, "w"), indent=1)
    return res
