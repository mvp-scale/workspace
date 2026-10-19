"""Matched comparison of every option from the cross-fitted voters (data/mm3-train/crossfit-voters-v2.pkl): each option's per-atom cut-off
(chosen on training scores for precision >= 0.8, or best F1 for jury voters) is shifted by the same amount for every atom, tracing a curve of
recall against false positives per 100 test stories; options are compared by recall at the same false-positive level. Test labels are only
used to draw the curves, not to pick any option's operating point (which stays the training-chosen one, also reported)."""
import json, hashlib, pickle, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold
D = "/workspace/data/mm3-train"; ids = json.load(open(f"{D}/features/ids.json")); res = pickle.load(open(f"{D}/crossfit-voters-v2.pkl", "rb"))
L = {n: lab for n, lab, _ in res}; PP = {n: pr for n, _, pr in res}
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); test = h == 0; TRN = ~test; NT = int(test.sum()); tr = np.where(TRN)[0]
COST = {"glance": 1.1, "scoped": 6.2, "sieve": 8.8, "echo": 0.9, "scholar_lead": 48.3, "scholar_full": 159.6}
def scores(views, single=None):
    """per atom: (train scores, test scores) of the option"""
    out = {}
    for n in PP:
        y = L[n]["agreed"]
        if y[TRN].sum() < 6: continue
        if single:
            if single not in PP[n]: continue
            out[n] = (PP[n][single][TRN], PP[n][single][test]); continue
        cols = [PP[n][v, a] for v in views for a in ("a", "b", "agreed", "reversed") if (v, a) in PP[n]]
        Xs = np.column_stack(cols); cv = cross_val_predict(LogisticRegression(class_weight="balanced", max_iter=3000), Xs[tr], y[tr], cv=StratifiedKFold(4, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        out[n] = (cv, LogisticRegression(class_weight="balanced", max_iter=3000).fit(Xs[tr], y[tr]).predict_proba(Xs[test])[:, 1])
    return out
def curve(sc, cut_rule="precision"):
    pts, chosen = [], None
    cuts = {}
    for n, (s_tr, _) in sc.items():
        y = L[n]["agreed"][TRN]
        cuts[n] = next((t for t in np.linspace(.05, .99, 95) if (s_tr >= t).sum() >= 3 and y[s_tr >= t].mean() >= .8), .99) if cut_rule == "precision" else max(np.linspace(.02, .98, 49), key=lambda t: f1_score(y, s_tr >= t))
    for d in np.linspace(-0.9, 0.95, 38):
        tp = fp = fn = 0
        for n, (_, s_te) in sc.items():
            c = cuts[n] + d * (1 - cuts[n]) if d >= 0 else cuts[n] * (1 + d); T = L[n]["T"][test]; q = (s_te >= c)[T]; yt = L[n]["agreed"][test][T]
            tp += (q & yt).sum(); fp += (q & ~yt).sum(); fn += (~q & yt).sum()
        pts.append((100 * fp / NT, tp / max(1, tp + fn), tp / max(1, tp + fp), d))
    return pts
def jury_curve(voters):
    """all-agree jury: each voter's best-F1 cut on its training scores, all shifted together"""
    pts = []
    for d in np.linspace(-0.6, 0.95, 32):
        tp = fp = fn = 0
        for n in PP:
            if any(v not in PP[n] for v in voters) or L[n]["agreed"][TRN].sum() < 6: continue
            q = np.ones(NT, bool)
            for v in voters:
                lab = {"a": L[n]["a"], "b": L[n]["b"], "agreed": L[n]["agreed"], "reversed": L[n]["reversed"]}[v[1]]
                s = PP[n][v]; c0 = max(np.linspace(.02, .98, 49), key=lambda t: f1_score(lab[TRN], s[TRN] >= t)); c = c0 + d * (1 - c0) if d >= 0 else c0 * (1 + d); q &= s[test] >= c
            T = L[n]["T"][test]; q = q[T]; yt = L[n]["agreed"][test][T]; tp += (q & yt).sum(); fp += (q & ~yt).sum(); fn += (~q & yt).sum()
        pts.append((100 * fp / NT, tp / max(1, tp + fn), tp / max(1, tp + fp), d))
    return pts
at = lambda pts, cap: max([r for f, r, p, d in pts if f <= cap] or [0.0])
OPTS = {"single head: Glance full": (curve(scores(None, ("glance_full", "agreed"))), COST["glance"]),
        "single head: Glance + scoped Sieve": (curve(scores(None, ("glance_full+scoped", "agreed"))), COST["glance"] + COST["scoped"]),
        "jury, all agree: Glance a, Scholar b, Glance lead": (jury_curve([("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed")]), COST["glance"] + COST["scholar_full"]),
        "jury, all agree: Glance+scoped a, Scholar lead b, Glance lead": (jury_curve([("glance_full+scoped", "a"), ("scholar_lead", "b"), ("glance_lead", "agreed")]), COST["glance"] + COST["scoped"] + COST["scholar_lead"]),
        "combiner: Glance only": (curve(scores(["glance_full", "glance_lead", "glance_title"])), COST["glance"]),
        "combiner tier 1: Glance+scoped, Sieve, Echo": (curve(scores(["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo"])), COST["glance"] + COST["scoped"] + COST["sieve"] + COST["echo"]),
        "combiner: Glance + Scholar lead": (curve(scores(["glance_full", "glance_lead", "glance_title", "scholar_lead"])), COST["glance"] + COST["scholar_lead"]),
        "combiner tier 2: tier 1 + Scholar lead+scoped": (curve(scores(["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo", "scholar_lead+scoped"])), COST["glance"] + COST["scoped"] + COST["sieve"] + COST["echo"] + COST["scholar_lead"]),
        "combiner: Glance + Scholar (full and lead)": (curve(scores(["glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead"])), COST["glance"] + COST["scholar_full"] + COST["scholar_lead"]),
        "combiner tier 3: tier 2 + Scholar full": (curve(scores(["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo", "scholar_lead+scoped", "scholar_full"])), COST["glance"] + COST["scoped"] + COST["sieve"] + COST["echo"] + COST["scholar_lead"] + COST["scholar_full"])}
print(f"{'option':58s} recall at false positives/100 <= 2 / 4 / 9 / 15    CPU ms")
out = {}
for name, (pts, c) in OPTS.items():
    out[name] = {"recall_at_fp": {k: round(float(at(pts, k)), 3) for k in (2, 4, 9, 15)}, "cost_ms": round(c, 1), "curve": [tuple(round(float(x), 3) for x in p) for p in pts]}
    print(f"{name:58s} " + "  ".join(f"{out[name]['recall_at_fp'][k]:.3f}" for k in (2, 4, 9, 15)) + f"     {c:.1f}")
json.dump(out, open(f"{D}/matched-compare.json", "w"), indent=1)
