"""Evidence card for every engine: alone, inside the jury (added, replacing, removed), as features inside Glance (the second approach), and a
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

# ---- every voter for every atom
L, P, V = {}, {}, {}           # labels per atom; probabilities and votes per (atom, view, angle)
for n, (w, ka, kb, kr) in ANG.items():
    g = lambda k: np.array([Q[w][i]["answers"][k] >= .5 for i in ids]); a, b, r = g(ka), g(kb), g(kr); L[n] = {"a": a, "b": b, "agreed": a & b, "reversed": r, "T": test & (a == b)}
    for view in list(VIEWS) + ["sieve"]:
        X = X_of(view, n)
        for ang in ("a", "b", "agreed", "reversed"):
            out = train(X, L[n][ang])
            if out: P[n, view, ang], V[n, view, ang] = out[0], out[0] >= out[1]
    for extra in ("sieve", "grammar", "locate", "echo"):                                   # second approach: the engine as features inside Glance's head
        X = np.hstack([VIEWS["glance_full"], X_of(extra, n) * 0.1]); out = train(X, L[n]["agreed"])
        if out: P[n, f"glance_full+{extra}", "agreed"], V[n, f"glance_full+{extra}", "agreed"] = out[0], out[0] >= out[1]
print(f"{len(ANG)} atoms, {len(P)} trained voters", flush=True)
ATOMS = [n for n in ANG if all((n, v, a) in V for v, a in (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"), ("glance_full", "agreed")))]

def pooled(pred_of, atoms=None):
    tp = fp = fn = 0
    for n in atoms or ATOMS:
        p = pred_of(n)
        if p is None: continue
        T = L[n]["T"]; y = L[n]["agreed"][T]; p = p[T]; tp += int((p & y).sum()); fp += int((p & ~y).sum()); fn += int((~p & y).sum())
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn); return {"precision": round(pr, 3), "recall": round(rc, 3), "fp_per_100": round(100 * fp / NT, 1), "tp": tp, "fp": fp, "fn": fn}
def jury(voters, veto=True):
    def f(n):
        vs = [V.get((n, v, a)) for v, a in voters]
        if any(x is None for x in vs): return None
        out = np.all(vs, 0)
        if veto and (n, "glance_full", "reversed") in V: out &= ~V[n, "glance_full", "reversed"]
        return out
    return f
BASE = [("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed")]
R = {"atoms": len(ATOMS), "test_stories": NT, "cost_ms": COST, "base_jury": pooled(jury(BASE)), "single_head": pooled(lambda n: V.get((n, "glance_full", "agreed")))}
print("base jury", R["base_jury"], "| single head", R["single_head"], flush=True)

# ---- cards
def solo(view):
    """Alone, trained on the agreed label: at its F1 cut; and its top 2% lift; and precision-targeted cut (val) for DECIDES."""
    at = pooled(lambda n: V.get((n, view, "agreed"))); lifts, hits, tot = [], 0, 0; dec_tp = dec_fp = dec_fn = 0
    for n in ATOMS:
        if (n, view, "agreed") not in P: continue
        p, y, T = P[n, view, "agreed"], L[n]["agreed"], L[n]["T"]
        if y[T].sum() < 2: continue
        k = max(1, int(round(0.02 * T.sum()))); top = np.argsort(-p[T])[:k]; hits += y[T][top].sum(); tot += k
        cut = next((t for t in np.linspace(.05, .99, 95) if (p[val] >= t).sum() >= 2 and y[val][p[val] >= t].mean() >= .8), None)
        q = p[T] >= cut if cut is not None else np.zeros(T.sum(), bool); dec_tp += (q & y[T]).sum(); dec_fp += (q & ~y[T]).sum(); dec_fn += (~q & y[T]).sum()
    base = np.mean([L[n]["agreed"][L[n]["T"]].mean() for n in ATOMS]); lift = (hits / max(1, tot)) / base
    dp = dec_tp / max(1, dec_tp + dec_fp); dr = dec_tp / max(1, dec_tp + dec_fn)
    return {**at, "top2pct_precision": round(hits / max(1, tot), 3), "base_rate": round(float(base), 4), "lift": round(float(lift), 1), "precision_cut": {"precision": round(float(dp), 3), "recall": round(float(dr), 3)}}
def delta(a, b): return {"fp_per_100": round(b["fp_per_100"] - a["fp_per_100"], 1), "recall_pts": round(100 * (b["recall"] - a["recall"]), 1)}
def supports(d): return (d["fp_per_100"] <= -1.0 and d["recall_pts"] >= -2) or (d["recall_pts"] >= 2 and d["fp_per_100"] <= 1.0)
CARDS = {}
for view in ("glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead", "sieve", "grammar", "locate", "echo"):
    c = {"engine": ENGINE_OF[view], "view": view, "cost_ms": COST[view], "alone": solo(view), "in_jury": {}}
    base = R["base_jury"]
    for ang in ("agreed", "a", "b"):
        if (view, ang) in BASE: continue
        r_ = pooled(jury(BASE + [(view, ang)])); c["in_jury"][f"added ({ang})"] = {**r_, "delta": delta(base, r_)}
    if view.startswith("scholar_lead"): r_ = pooled(jury([("glance_full", "a"), ("scholar_lead", "b"), ("glance_lead", "agreed")])); c["in_jury"]["replaces scholar_full"] = {**r_, "delta": delta(base, r_)}
    if view in ("sieve", "grammar", "locate", "echo"):
        r_ = pooled(jury([("glance_full", "a"), (view, "b"), ("glance_lead", "agreed")])); c["in_jury"]["replaces scholar_full"] = {**r_, "delta": delta(base, r_)}
        r_ = pooled(lambda n, v=view: V.get((n, f"glance_full+{v}", "agreed"))); s0 = R["single_head"]; c["as_features_in_glance"] = {**r_, "delta_vs_single_head": delta(s0, r_)}
    for (v_, a_) in BASE:
        if v_ == view:
            r_ = pooled(jury([x for x in BASE if x != (v_, a_)])); c["in_jury"]["removed"] = {**r_, "delta": delta(r_, base)}       # delta = what keeping it adds
    sup = any(supports(x["delta"]) for x in c["in_jury"].values()) or ("as_features_in_glance" in c and supports(c["as_features_in_glance"]["delta_vs_single_head"]))
    al = c["alone"]; c["verdict"] = "DECIDES" if al["precision_cut"]["precision"] >= .8 and al["precision_cut"]["recall"] >= .3 else "SUPPORTS" if sup else "SIGNAL ONLY" if al["lift"] >= 3 else "NO VALUE"
    if c["verdict"] == "DECIDES" and sup: c["verdict"] = "DECIDES + SUPPORTS"
    CARDS[view] = c; print(f"{view:14s} {c['verdict']:18s} alone F1-cut P{al['precision']:.2f}/R{al['recall']:.2f} lift {al['lift']}x; " + "; ".join(f"{k}: dFP {x['delta']['fp_per_100']:+.1f} dR {x['delta']['recall_pts']:+.1f}" for k, x in c["in_jury"].items()), flush=True)
R["cards"] = CARDS

# ---- learned combiner over every voter (second approach to "how to combine"): fit on val with cross-validation, cut for precision >= 0.8, scored on test
def stack(views):
    tp = fp = fn = 0
    for n in ATOMS:
        cols = [P[n, v, a] for v in views for a in ("a", "b", "agreed", "reversed") if (n, v, a) in P]
        Xs = np.column_stack(cols); y = L[n]["agreed"]
        if y[val].sum() < 4: continue
        cv = cross_val_predict(LogisticRegression(class_weight="balanced", max_iter=3000), Xs[val], y[val], cv=StratifiedKFold(4, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        cut = next((t for t in np.linspace(.05, .99, 95) if (cv >= t).sum() >= 2 and y[val][cv >= t].mean() >= .8), .99)
        m = LogisticRegression(class_weight="balanced", max_iter=3000).fit(Xs[val], y[val]); T = L[n]["T"]; q = m.predict_proba(Xs[T])[:, 1] >= cut; yt = y[T]
        tp += (q & yt).sum(); fp += (q & ~yt).sum(); fn += (~q & yt).sum()
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn); return {"precision": round(float(pr), 3), "recall": round(float(rc), 3), "fp_per_100": round(100 * fp / NT, 1)}
R["combiner_all_engines"] = stack(["glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead", "sieve", "grammar", "locate", "echo"])
R["combiner_glance_scholar"] = stack(["glance_full", "glance_lead", "scholar_full"])
print("combiner all", R["combiner_all_engines"], "| glance+scholar only", R["combiner_glance_scholar"], flush=True)

# ---- minimum viable set: greedy, chosen on validation, scored on test. Jury = all voters agree (+ veto), at least two different engines.
POOL = [(v, a) for v in ("glance_full", "glance_lead", "glance_title", "scholar_full", "scholar_lead", "sieve", "grammar", "locate") for a in ("a", "b", "agreed")]
def val_score(voters):
    tp = fp = fn = 0
    for n in ATOMS:
        vs = [V.get((n, v, a)) for v, a in voters]
        if any(x is None for x in vs): continue
        p = np.all(vs, 0) & ~V.get((n, "glance_full", "reversed"), np.zeros(len(ids), bool)); Tv = val & (L[n]["a"] == L[n]["b"]); y = L[n]["agreed"][Tv]; p = p[Tv]
        tp += (p & y).sum(); fp += (p & ~y).sum(); fn += (~p & y).sum()
    return tp / max(1, tp + fn), 100 * fp / val.sum()
FP_CAP = R["base_jury"]["fp_per_100"]
best, cur = None, []
for size in range(1, 6):
    cands = []
    for v in POOL:
        if v in cur: continue
        s = cur + [v]
        if size >= 2 and len({ENGINE_OF[x[0]] for x in s}) < 2: continue
        rc, fpv = val_score(s); c_ = sum(COST[x] for x in {x[0] for x in s}); cands.append((rc if fpv <= FP_CAP else -fpv, -c_, s, rc, fpv))
    if not cands: break
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True); cur = cands[0][2]
    if size >= 2 and cands[0][4] <= FP_CAP and (best is None or cands[0][3] > best[1] + 0.005): best = (list(cur), cands[0][3], cands[0][4])
R["minimum_viable_set"] = {"voters": best[0] if best else None, "val_recall": round(best[1], 3) if best else None, "val_fp_per_100": round(best[2], 1) if best else None,
                           "test": pooled(jury(best[0])) if best else None, "cost_ms": round(sum(COST[x] for x in {v for v, _ in best[0]}), 2) if best else None, "fp_cap_from_base_jury": FP_CAP}
print("minimum viable set", json.dumps(R["minimum_viable_set"]), flush=True)
json.dump(R, open(f"{D}/engines-eval.json", "w"), indent=1, default=float); print("saved", f"{D}/engines-eval.json")
