"""Finish the engine cards on CPU only (no new labels, no GPU): intervals for the checks still missing them.
  E1 Scholar removal: the jury without Scholar vs the jury, R@9 and macro average precision (jury scored by the lowest voter probability)
  E2 Echo: 95% bootstrap intervals (1,000 pair resamples) for same-event AUC on the 143 Clef-consensus pairs, and for Echo + titles minus Echo
  E3 A2 without a second model: every option re-scored against R1b (Clef agreed, minus "yes" cases where Clef also says yes to the reversed
     question), versus R1, to see how much of the measured error is Clef contradicting itself
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/finish_engines.py"""
import sys, os, json, re, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.metrics import roc_auc_score, average_precision_score
from scipy.stats import rankdata
D = V.D; A = V.ATOMS; te = np.where(V.test)[0]; out = {}
def macro_ap(sc, Y, M, w):
    v = []
    for k, n in enumerate(A):
        T = M[k]; y = Y[k][T]
        if (y * w[T]).sum() < 3: continue
        v.append(average_precision_score(y, sc[n][te][T], sample_weight=w[T]))
    return float(np.mean(v))
def ap_compare(opts, Y, M, base, draws=200):
    rng = np.random.default_rng(1); pt = {k: macro_ap(v, Y, M, np.ones(V.NT)) for k, v in opts.items()}; dr = {k: [] for k in opts}
    for _ in range(draws):
        w = np.bincount(rng.integers(0, V.NT, V.NT), minlength=V.NT).astype(float)
        for k, v in opts.items(): dr[k].append(macro_ap(v, Y, M, w))
    res = {}
    for k in opts:
        d = np.array(dr[k]) - np.array(dr[base]); res[k] = {"macro_ap": round(pt[k], 3), f"minus {base}": [round(float(d.mean()), 3)] + [round(float(x), 3) for x in np.percentile(d, [2.5, 97.5])]}
    return res
J = lambda n, vs: np.minimum.reduce([V.PP[n][v] for v in vs])
BASEV = (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed")); NOSCH = (("glance_full", "a"), ("glance_lead", "agreed"))
# ---- E1
print("== E1 Scholar removal", flush=True)
r = V.evaluate({"jury without Scholar": V.jury_preds(NOSCH)}); out["E1_R@9"] = r["jury without Scholar"]
out["E1_macroAP"] = ap_compare({"jury": {n: J(n, BASEV) for n in A}, "jury without Scholar": {n: J(n, NOSCH) for n in A}}, V.Y, V.M, "jury"); print(json.dumps(out["E1_macroAP"]))
# ---- E2
print("== E2 Echo intervals", flush=True)
F = f"{D}/features"; ids = V.ids; first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; rows = [first[i] for i in ids]; P = json.load(open(f"{D}/echo-pairs.json"))
y, keep = [], []
for k, p in enumerate(P):
    a = {int(n): v for n, v in p["a"].items()}
    if a[1] >= .5 and a[2] >= .5 and a[3] < .5: y.append(1); keep.append(k)
    elif a[1] < .5 and a[2] < .5 and a[3] >= .5: y.append(0); keep.append(k)
y = np.array(y); Pk = [P[k] for k in keep]; tw = lambda t: set(re.findall(r"[a-z]{3,}", t.lower()))
echo = np.array([p["glance_cos"] for p in Pk]); titles = np.array([len(tw(rows[p["i"]]["title"]) & tw(rows[p["j"]]["title"])) / max(1, len(tw(rows[p["i"]]["title"]) | tw(rows[p["j"]]["title"]))) for p in Pk])
rng = np.random.default_rng(2); e_, c_, d_ = [], [], []
for _ in range(1000):
    s = rng.integers(0, len(y), len(y))
    if 0 < y[s].sum() < len(s):
        ea = roc_auc_score(y[s], echo[s]); ca = roc_auc_score(y[s], (rankdata(echo[s]) + rankdata(titles[s])) / 2); e_.append(ea); c_.append(ca); d_.append(ca - ea)
pc = lambda v: [round(float(x), 3) for x in np.percentile(v, [2.5, 97.5])]
out["E2"] = {"pairs": int(len(y)), "same_event": int(y.sum()), "echo_auc": round(float(roc_auc_score(y, echo)), 3), "echo_ci95": pc(e_), "echo_plus_titles_auc": round(float(roc_auc_score(y, (rankdata(echo) + rankdata(titles)) / 2)), 3),
             "echo_plus_titles_ci95": pc(c_), "difference": [round(float(np.mean(d_)), 3)] + pc(d_)}
print(json.dumps(out["E2"]))
# ---- E3
print("== E3 R1b (Clef coherent) vs R1", flush=True)
srcmap = {}
for f in __import__("glob").glob("/workspace/newsreader/bitmob/batteries/*.json"):
    B = json.load(open(f))
    for c in B["concerns"]: srcmap[c["atom"]] = (B["name"], list(c["probes"]))
Q = {"first-v1": {r["id"]: r["answers"] for r in map(json.loads, open(f"{D}/queue.jsonl"))}}
for v in range(1, 7): Q[f"evidence-v{v}"] = {r["id"]: r["answers"] for r in map(json.loads, open(f"{D}/queue-evidence-v{v}.jsonl"))}
M1b = V.M.copy(); tid = [ids[i] for i in te]; dropped = 0
for k, n in enumerate(A):
    b, pr = srcmap.get(n, ("first-v1", ["states", "concrete", "reversed"])); C = Q[b]
    for j, i in enumerate(tid):
        c = C.get(i)
        if c and c[f"{n}|{pr[0]}"] >= .5 and c[f"{n}|{pr[1]}"] >= .5 and c[f"{n}|{pr[2]}"] >= .5: M1b[k, j] = False; dropped += 1
S2 = np.load(f"{D}/proof/a1b2-scores.npz"); S5 = np.load(f"{D}/proof/a5-scores-100.npy")
sc = {"single Glance head": {n: V.PP[n]["glance_full", "agreed"] for n in A}, "jury": {n: J(n, BASEV) for n in A}, "A1b'' multi-task": {n: S2["Sg"][:, k] for k, n in enumerate(A)},
      "jury + A1b''": {n: np.minimum(J(n, BASEV), S2["Sg"][:, k]) for k, n in enumerate(A)}, "A5 fine-tuned (100%)": {n: S5[:, k] for k, n in enumerate(A)}}
out["E3"] = {"R1b_dropped_pairs": dropped, "R1": ap_compare(sc, V.Y, V.M, "single Glance head"), "R1b": ap_compare(sc, V.Y, M1b, "single Glance head")}
print("dropped", dropped); print(json.dumps({k: out["E3"][k] for k in ("R1", "R1b")}, indent=0))
json.dump(out, open(f"{D}/proof/finish-engines.json", "w"), indent=1)
