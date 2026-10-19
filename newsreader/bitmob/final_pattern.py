"""Final pattern: the learned combiner with sentence-scoped Sieve features (no spaCy) inside Glance and Scholar heads, at three cost tiers. Minimum viable set for the learned combiner (setup copied from engines_eval.py). Evidence card for every engine: alone, inside the jury (added, replacing, removed), as features inside Glance (the second approach), and a
learned combiner over every voter; then the minimum viable set. Verdict rules were fixed before any result was seen (docs/cpu-reader-plan.md):
  DECIDES      alone: pooled precision >= 0.80 at recall >= 0.30 (cut-off chosen on validation for precision)
  SUPPORTS     added to the base jury, or removed from the best set: false positives per 100 stories -1.0 or better with recall down <= 2 points,
               or recall +2 points or better with false positives up <= 1.0 per 100
  SIGNAL ONLY  alone: precision in its top 2% of scores >= 3x the base rate, but not SUPPORTS
  NO VALUE     below that
Truth: Clef's agreed label (both wordings yes); scored on test pairs where Clef's two wordings agree. Splits by id hash: fit >= 2, val 1, test 0.
A voter = (engine view, angle it was trained on: a, b, agreed, reversed). Jury = all voters yes (STRONG) and the veto (Glance, reversed) not yes.
Run after engines_features.py: models/embed-zs/.venv/bin/python -I newsreader/bitmob/engines_eval.py"""
import json, glob, hashlib, itertools, re, numpy as np
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


# ---- sentence-scoped Sieve: per atom, sentences (split on . ! ?) that contain the atom's own words, counted per part, plus up/down/negation words in them
SPLIT = re.compile(r"(?<=[.!?])\s+"); NEG = re.compile(r"\b(not|no|never|\w+n't|without)\b", re.I)
_rows = [Q["first"][i] for i in ids]; _parts = [(r["title"], " ".join(r["text"].split()[:80]), " ".join(r["text"].split()[80:1200])) for r in _rows]
_sents = [[SPLIT.split(p) for p in ps] for ps in _parts]
LEX2 = {a: re.compile(r"\b(" + "|".join(map(re.escape, ws)) + r")\w*", re.I) for a, ws in SN["lexicon"].items()}
UPW, DNW = re.compile(r"\b(rise|rose|risen|rising|jump\w*|soar\w*|surge\w*|climb\w*|increas\w*|hike\w*|higher|up)\b", re.I), re.compile(r"\b(fall\w*|fell|drop\w*|plung\w*|slump\w*|declin\w*|cut\w*|lower\w*|eas\w*|down)\b", re.I)
SCOPED_CACHE = {}
def scoped(atom):
    if atom not in SCOPED_CACHE:
        rx = LEX2[atom]; out = []
        for ss in _sents:
            v = []
            for part in ss:
                m = [x for x in part if rx.search(x)]; v += [np.log1p(len(m)), np.log1p(sum(bool(UPW.search(x)) for x in m)), np.log1p(sum(bool(DNW.search(x)) for x in m)), np.log1p(sum(bool(NEG.search(x)) for x in m))]
            out.append(v)
        SCOPED_CACHE[atom] = np.array(out, float)
    return SCOPED_CACHE[atom]
import time as _t; _t0 = _t.perf_counter(); [scoped(a) for a in list(ANG)[:5]]; COST["scoped"] = round((_t.perf_counter() - _t0) * 1000 / (5 * len(ids)) * len(ANG), 2)
print("sentence-scoped Sieve cost ms per story (all atoms):", COST["scoped"], flush=True)
_X_of = X_of
def X_of(view, atom):
    if view == "glance_full+scoped": return np.hstack([VIEWS["glance_full"], StandardScaler().fit(scoped(atom)[fit]).transform(scoped(atom)) * 0.1])
    if view == "scholar_lead+scoped": return np.hstack([VIEWS["scholar_lead"], StandardScaler().fit(scoped(atom)[fit]).transform(scoped(atom)) * 0.1])
    if view == "scoped": return StandardScaler().fit(scoped(atom)[fit]).transform(scoped(atom))
    return _X_of(view, atom)
COST["glance_full+scoped"] = COST["glance_full"] + COST["scoped"]; COST["scholar_lead+scoped"] = COST["scholar_lead"]; ENGINE_OF.update({"glance_full+scoped": "Glance+Sieve", "scholar_lead+scoped": "Scholar+Sieve", "scoped": "Sieve"})
# ---- minimum viable set for the learned combiner (the Jury): every voter trained once (in parallel over atoms), then the combiner is fitted on
# validation stories with each engine group removed in turn, and with cheap-only and short-text-only groups. Cut-off for precision >= 0.8 on validation.
from joblib import Parallel, delayed
VIEWSALL = ["glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead", "sieve", "echo", "scoped", "glance_full+scoped", "scholar_lead+scoped"]
def one_atom(n):
    w, ka, kb, kr = ANG[n]; g = lambda k: np.array([Q[w][i]["answers"][k] >= .5 for i in ids]); a, b, r = g(ka), g(kb), g(kr)
    lab = {"a": a, "b": b, "agreed": a & b, "reversed": r, "T": test & (a == b)}; probs = {}
    for view in VIEWSALL:
        X = X_of(view, n)
        for ang in ("a", "b", "agreed", "reversed"):
            out = train(X, lab[ang])
            if out: probs[view, ang] = out[0].astype(np.float32)
    return n, lab, probs
res = Parallel(n_jobs=16)(delayed(one_atom)(n) for n in ANG)
L = {n: lab for n, lab, _ in res}; PP = {n: pr for n, _, pr in res}
def combiner(views):
    tp = fp = fn = 0
    for n in ANG:
        cols = [PP[n][v, a] for v in views for a in ("a", "b", "agreed", "reversed") if (v, a) in PP[n]]; y = L[n]["agreed"]
        if not cols or y[val].sum() < 4: continue
        Xs = np.column_stack(cols); lr = lambda: LogisticRegression(class_weight="balanced", max_iter=3000)
        cv = cross_val_predict(lr(), Xs[val], y[val], cv=StratifiedKFold(4, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        cut = next((t for t in np.linspace(.05, .99, 95) if (cv >= t).sum() >= 2 and y[val][cv >= t].mean() >= .8), .99)
        T = L[n]["T"]; q = lr().fit(Xs[val], y[val]).predict_proba(Xs[T])[:, 1] >= cut; yt = y[T]; tp += (q & yt).sum(); fp += (q & ~yt).sum(); fn += (~q & yt).sum()
    return {"precision": round(float(tp / max(1, tp + fp)), 3), "recall": round(float(tp / max(1, tp + fn)), 3), "fp_per_100": round(float(100 * fp / NT), 1),
            "cost_ms": round(sum(COST[v] for v in views if v != "glance_full+scoped") + (COST["glance_full"] if "glance_full+scoped" in views else 0) + (COST["scoped"] if "scoped" not in views and "glance_full+scoped" in views else 0), 1)}
SETS = {"before: Glance + Scholar (full and lead)": ["glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead"],
        "tier 1: Glance+scoped Sieve, Glance lead/title, Sieve, Echo": ["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo"],
        "tier 2: tier 1 + Scholar lead+scoped": ["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo", "scholar_lead+scoped"],
        "tier 3: tier 2 + Scholar full": ["glance_full+scoped", "glance_lead", "glance_title", "sieve", "scoped", "echo", "scholar_lead+scoped", "scholar_full"]}
out = {}
for name, vs in SETS.items():
    out[name] = combiner(vs); print(f"{name:52s} " + json.dumps(out[name]), flush=True)
json.dump(out, open(f"{D}/final-pattern.json", "w"), indent=1)
