"""Frontier test for the engine cards (setup copied from engines_eval.py). Evidence card for every engine: alone, inside the jury (added, replacing, removed), as features inside Glance (the second approach), and a
learned combiner over every voter; then the minimum viable set. Verdict rules were fixed before any result was seen (docs/cpu-reader-plan.md):
  DECIDES      alone: pooled precision >= 0.80 at recall >= 0.30 (cut-off chosen on validation for precision)
  SUPPORTS     added to the base jury, or removed from the best set: false positives per 100 stories -1.0 or better with recall down <= 2 points,
               or recall +2 points or better with false positives up <= 1.0 per 100
  SIGNAL ONLY  alone: precision in its top 2% of scores >= 3x the base rate, but not SUPPORTS
  NO VALUE     below that
Truth: Clef's agreed label (both wordings yes); scored on test pairs where Clef's two wordings agree. Splits by id hash: fit >= 2, val 1, test 0.
A voter = (engine view, angle it was trained on: a, b, agreed, reversed). Jury = all voters yes (STRONG) and the veto (Glance, reversed) not yes.
Run after engines_features.py: models/embed-zs/.venv/bin/python -I newsreader/bitmob/engines_eval.py"""
import json, glob, hashlib, itertools, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold

D = "/workspace/data/mm3-train"; F = f"{D}/features"; ids = json.load(open(f"{F}/ids.json"))
Q = {"first": {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}}; ANG = {}
for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up"): ANG[c] = ("first", f"{c}|states", f"{c}|concrete", f"{c}|reversed")
for f in sorted(glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json")):
    B = json.load(open(f)); Q[B["name"]] = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-{B['name']}.jsonl"))}
    for c in B["concerns"]: ANG[c["atom"]] = (B["name"], f"{c['atom']}|a", f"{c['atom']}|b", f"{c['atom']}|reversed")
use = json.load(open(f"{D}/route-current.json"))["atoms_used"]; ANG = {k: v for k, v in ANG.items() if k in use}
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); fit, val, test = h >= 2, h == 1, h == 0; NT = int(test.sum())
cost = json.load(open(f"{F}/cost.json"))
SN = json.load(open(f"{F}/sieve_names.json")); SATOMS = SN["atoms"]; NPAT = len(SN["patterns"])
sieve_all = np.load(f"{F}/sieve.npy"); n_univ = 3 * (NPAT + 3) + 1
def sieve_for(atom):                                   # universal pattern counts + this atom's own lexicon hits (3 parts)
    j = SATOMS.index(atom); return np.hstack([sieve_all[:, :n_univ], sieve_all[:, n_univ + 3 * j: n_univ + 3 * j + 3]])
VIEWS = {v: np.load(f"{F}/{v}.npy") for v in ("glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead", "grammar", "locate", "echo")}
ENGINE_OF = {"glance_full": "Glance", "glance_lead": "Glance", "glance_title": "Glance", "scholar_full": "Scholar", "scholar_lead": "Scholar", "sieve": "Sieve", "grammar": "Grammar", "locate": "Locate", "echo": "Echo"}
COST = {"glance_full": cost["glance_full"], "glance_lead": cost["glance_lead"], "glance_title": cost["glance_title"], "scholar_full": cost["scholar_full"], "scholar_lead": cost["scholar_lead"],
        "sieve": cost["sieve"], "grammar": cost["grammar+locate (spaCy, one pass)"], "locate": cost["grammar+locate (spaCy, one pass)"], "echo": cost["echo (vs a 7-day index, numpy)"]}
def X_of(view, atom):
    X = sieve_for(atom) if view == "sieve" else VIEWS[view]
    return X if view.startswith(("glance", "scholar")) else StandardScaler().fit(X[fit]).transform(X)
def train(X, y):
    if y[fit].sum() < 3 or y[val].sum() < 2: return None
    p = LogisticRegression(C=4 if X.shape[1] > 100 else 1, class_weight="balanced", max_iter=5000).fit(X[fit], y[fit]).predict_proba(X)[:, 1]
    return p, max(np.linspace(.02, .98, 49), key=lambda t: f1_score(y[val], p[val] >= t))


# ---- frontier test (fixes engines_eval.py's SUPPORTS rule: adding a voter to an all-agree jury always trades recall for false positives,
# so an engine only adds value if its jury beats the curve the base jury reaches by simply tightening its own cut-offs).
L, P, C = {}, {}, {}
NEED = [("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"), ("glance_full", "reversed")] + [(v, "agreed") for v in ("glance_title", "scholar_lead", "sieve", "grammar", "locate", "echo")]
for n, (w, ka, kb, kr) in ANG.items():
    g = lambda k: np.array([Q[w][i]["answers"][k] >= .5 for i in ids]); a, b, r = g(ka), g(kb), g(kr); L[n] = {"a": a, "b": b, "agreed": a & b, "reversed": r, "T": test & (a == b)}
    for view, ang in NEED:
        out = train(X_of(view, n), L[n][ang])
        if out: P[n, view, ang], C[n, view, ang] = out
    for extra in ("sieve", "locate"):
        out = train(np.hstack([VIEWS["glance_full"], X_of(extra, n) * 0.1]), L[n]["agreed"])
        if out: P[n, f"glance_full+{extra}", "agreed"], C[n, f"glance_full+{extra}", "agreed"] = out
ATOMS = [n for n in ANG if all((n, v, a) in P for v, a in NEED[:3])]
def curve(voters, veto=True):
    pts = []
    for d in np.linspace(0, .95, 20):
        tp = fp = fn = 0
        for n in ATOMS:
            if any((n, v, a) not in P for v, a in voters): continue
            q = np.all([P[n, v, a] >= C[n, v, a] + d * (1 - C[n, v, a]) for v, a in voters], 0)
            if veto and (n, "glance_full", "reversed") in P: q &= ~(P[n, "glance_full", "reversed"] >= C[n, "glance_full", "reversed"])
            T = L[n]["T"]; y = L[n]["agreed"][T]; q = q[T]; tp += (q & y).sum(); fp += (q & ~y).sum(); fn += (~q & y).sum()
        pts.append((100 * fp / NT, tp / max(1, tp + fn)))
    return pts
def recall_at(pts, cap):
    ok = [r for f, r in pts if f <= cap]; return round(max(ok), 3) if ok else 0.0
BASE = [("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed")]
JURIES = {"base jury (Glance a, Scholar b, Glance lead)": BASE}
for v in ("glance_title", "scholar_lead", "sieve", "grammar", "locate", "echo"): JURIES[f"base + {v}"] = BASE + [(v, "agreed")]
JURIES["Scholar lead instead of Scholar full"] = [("glance_full", "a"), ("scholar_lead", "agreed"), ("glance_lead", "agreed")]
JURIES["Glance+Sieve head instead of Glance full"] = [("glance_full+sieve", "agreed"), ("scholar_full", "b"), ("glance_lead", "agreed")]
JURIES["Glance+Sieve+Locate heads (two), Scholar"] = [("glance_full+sieve", "agreed"), ("glance_full+locate", "agreed"), ("scholar_full", "b")]
JURIES["cheap only: Glance+Sieve, Glance+Locate, Glance lead"] = [("glance_full+sieve", "agreed"), ("glance_full+locate", "agreed"), ("glance_lead", "agreed")]
out = {}
print(f"{'jury':56s} recall at false positives/100 <= 4 / 6 / 9 / 15     cost ms")
for name, vs in JURIES.items():
    pts = curve(vs); cst = round(sum(COST[v.split("+")[0]] + (COST["sieve"] if "+sieve" in v else 0) + (COST["locate"] if "+locate" in v else 0) for v in {x[0] for x in vs}), 1)
    out[name] = {"recall_at_fp": {c: recall_at(pts, c) for c in (4, 6, 9, 15)}, "cost_ms": cst, "curve": [(round(float(f), 1), round(float(r), 3)) for f, r in pts]}
    print(f"{name:56s} " + "  ".join(f"{out[name]['recall_at_fp'][c]:.3f}" for c in (4, 6, 9, 15)) + f"    {cst}")
json.dump(out, open(f"{D}/engines-frontier.json", "w"), indent=1)
