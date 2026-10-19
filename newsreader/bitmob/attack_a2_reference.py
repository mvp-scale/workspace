"""Attack A2 (docs/value-indicators.md): is the ceiling partly Clef's noise? References on the 486 test stories:
  R1  Clef agreed (both wordings) where the two wordings agree (the reference used so far)
  R1b R1 plus coherence: a Clef "yes" whose reversed question is also yes is dropped (Clef contradicts itself)
  R2  teacher jury: Clef and Winnow-12B (a different model family) agree, each on both wordings; pairs where they disagree are left out
Questions: (1) how often do the two teachers agree, per atom? (2) scored against R2 instead of R1, do the CPU options look better (part of the
ceiling was Clef's noise)? (3) where the CPU disagrees with Clef, does Winnow side with the CPU more often than chance?
Options scored: the two baselines and the A1 formulations (data/mm3-train/proof/a1-scores.npz), all through value_eval.py.
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/attack_a2_reference.py"""
import sys, os, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
D = V.D; tid = [V.ids[i] for i in np.where(V.test)[0]]
src = {}
for f in glob.glob("/workspace/newsreader/bitmob/batteries/*.json"):
    B = json.load(open(f)); n = B["name"]
    for c in B["concerns"]: src[c["atom"]] = (n, list(c["probes"]))
def load(path): return {r["id"]: r["answers"] for r in map(json.loads, open(path))} if os.path.exists(path) else {}
clef = {"first-v1": load(f"{D}/queue.jsonl")}; win = {"first-v1": load(f"{D}/queue-first-v1-winnow-12b.jsonl")}
for v in range(1, 7): clef[f"evidence-v{v}"] = load(f"{D}/queue-evidence-v{v}.jsonl"); win[f"evidence-v{v}"] = load(f"{D}/queue-evidence-v{v}-winnow-12b.jsonl")
def angles(atom):
    b, pr = src.get(atom, ("first-v1", ["states", "concrete", "reversed"]))
    return b, [f"{atom}|{pr[0]}", f"{atom}|{pr[1]}", f"{atom}|{pr[2]}"]
Y1, M1 = V.Y.copy(), V.M.copy(); Y1b, M1b = Y1.copy(), M1.copy(); Y2 = np.zeros_like(Y1); M2 = np.zeros_like(M1); rep = {"atoms": {}}
for k, atom in enumerate(V.ATOMS):
    b, (ka, kb, kr) = angles(atom); C, W = clef[b], win[b]
    for j, i in enumerate(tid):
        c, w = C.get(i), W.get(i)
        if c is None: continue
        ca, cb, cr = c[ka] >= .5, c[kb] >= .5, c[kr] >= .5
        if ca and cb and cr: M1b[k, j] = False                                              # Clef says yes and also yes to the opposite
        if w is None: continue
        wa, wb = w[ka] >= .5, w[kb] >= .5
        if ca == cb and wa == wb and ca == wa: Y2[k, j] = ca; M2[k, j] = True             # both teachers clear and agreeing
    both = [(C[i][ka] >= .5 and C[i][kb] >= .5, W[i][ka] >= .5 and W[i][kb] >= .5) for i in tid if i in C and i in W]
    if both:
        cy, wy = np.array(both).T; agree_yes = (cy & wy).sum() / max(1, (cy | wy).sum())
        rep["atoms"][atom] = {"clef_yes": int(cy.sum()), "winnow_yes": int(wy.sum()), "agree_on_yes": round(float(agree_yes), 3), "pairs_clear_R2": int(M2[k].sum())}
print("teacher agreement on yes (Clef vs Winnow), median over atoms:", np.median([a["agree_on_yes"] for a in rep["atoms"].values()]) if rep["atoms"] else "no Winnow labels")
def with_ref(Yr, Mr):
    V.Y, V.M = Yr, Mr
    V.YC = np.array([(Yr[V.CI[i]]).any(0) for i in range(len(V.CONDS))]); V.MC = np.array([(Mr[V.CI[i]]).all(0) for i in range(len(V.CONDS))])
A1 = np.load(f"{D}/proof/a1-scores.npz") if os.path.exists(f"{D}/proof/a1-scores.npz") else None
opts = {}
if A1 is not None:
    for key, name in (("Sa", "A1a pair model"), ("Sb", "A1b multi-task network"), ("Sd", "A1d nearest neighbours")): opts[name] = {n: A1[key][:, k] for k, n in enumerate(V.ATOMS)}
for ref, (Yr, Mr) in (("R1 Clef agreed", (Y1, M1)), ("R1b Clef agreed + coherent", (Y1b, M1b)), ("R2 Clef and Winnow agree", (Y2, M2))):
    with_ref(Yr, Mr); print(f"\n== reference {ref}: positives {int((Yr & Mr).sum())}, clear pairs {int(Mr.sum())}", flush=True)
    rep[ref] = V.evaluate(dict(opts), out_file=None)
# (3) where the single head disagrees with Clef (at its R@9 operating point under R1), does Winnow side with the CPU?
with_ref(Y1, M1); P = V.baselines()["single Glance head"]
yt, no = Y1 & M1, ~Y1 & M1; f = [100 * ((P[j] & no).sum()) / V.NT for j in range(len(V.DS))]; rc = [((P[j] & yt).sum()) / max(1, yt.sum()) for j in range(len(V.DS))]
ok = [j for j, x in enumerate(f) if x <= 9]; j9 = max(ok, key=lambda j: rc[j]); pr = P[j9]
wy = np.zeros_like(Y1); has = np.zeros_like(Y1)
for k, atom in enumerate(V.ATOMS):
    b, (ka, kb, kr) = angles(atom); W = win[b]
    for j, i in enumerate(tid):
        if i in W: has[k, j] = True; wy[k, j] = W[i][ka] >= .5 and W[i][kb] >= .5
cpu_fp = pr & no & has; cpu_fn = ~pr & yt & has; agree_pos = pr & yt & has; base_neg = no & has
rep["sides"] = {"cpu_yes_clef_no": int(cpu_fp.sum()), "winnow_yes_there": round(float(wy[cpu_fp].mean()), 3) if cpu_fp.any() else None, "winnow_yes_rate_on_all_clef_no": round(float(wy[base_neg].mean()), 4),
                "cpu_no_clef_yes": int(cpu_fn.sum()), "winnow_no_there": round(float((~wy[cpu_fn]).mean()), 3) if cpu_fn.any() else None, "winnow_no_rate_on_cpu_and_clef_yes": round(float((~wy[agree_pos]).mean()), 3) if agree_pos.any() else None}
print("\nwhere the CPU and Clef disagree:", json.dumps(rep["sides"]))
json.dump(rep, open(f"{D}/proof/a2-results.json", "w"), indent=1, default=str)
