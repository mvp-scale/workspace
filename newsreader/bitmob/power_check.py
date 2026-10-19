"""Secondary measure for the next round (deviation in docs/value-indicators.md): macro average precision over atoms with >= 3 test positives
(threshold-free), with 95% intervals of differences against the single head, and the minimum detectable difference (1.96 x the bootstrap standard
deviation of the difference) for both macro AP and R@9. Juries are scored by the lowest of their voters' probabilities.
Uses saved scores only: crossfit-voters-v2.pkl, proof/a1b2-scores.npz."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.metrics import average_precision_score
S = np.load(f"{V.D}/proof/a1b2-scores.npz"); A = V.ATOMS
single = {n: V.PP[n]["glance_full", "agreed"] for n in A}
jury = {n: np.minimum.reduce([V.PP[n][v] for v in (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"))]) for n in A}
mt = {n: S["Sg"][:, k] for k, n in enumerate(A)}; jury4 = {n: np.minimum(jury[n], mt[n]) for n in A}
OPTS = {"single Glance head": single, "jury (min of voters)": jury, "A1b'' multi-task": mt, "jury + A1b'' (min)": jury4}
te = np.where(V.test)[0]
def macro_ap(sc, w):
    v = []
    for k, n in enumerate(A):
        T = V.M[k]; y = V.Y[k][T]; s = sc[n][te][T]; ww = w[T]
        if (y * ww).sum() < 3: continue
        v.append(average_precision_score(y, s, sample_weight=ww))
    return float(np.mean(v))
rng = np.random.default_rng(0); point = {k: macro_ap(v, np.ones(V.NT)) for k, v in OPTS.items()}; dr = {k: [] for k in OPTS}
for _ in range(200):
    w = np.bincount(rng.integers(0, V.NT, V.NT), minlength=V.NT).astype(float)
    for k, v in OPTS.items(): dr[k].append(macro_ap(v, w))
out = {}
for k in OPTS:
    a = np.array(dr[k]); d = a - np.array(dr["single Glance head"])
    out[k] = {"macro_ap": round(point[k], 3), "ci95": [round(float(x), 3) for x in np.percentile(a, [2.5, 97.5])],
              "vs_single": [round(float(d.mean()), 3)] + [round(float(x), 3) for x in np.percentile(d, [2.5, 97.5])], "min_detectable": round(float(1.96 * d.std()), 3)}
    print(f"{k:28s} macro AP {out[k]['macro_ap']:.3f} {out[k]['ci95']}  vs single {out[k]['vs_single']}  smallest difference this test can detect ~{out[k]['min_detectable']}")
r9 = json.load(open(f"{V.D}/proof/a1b2-results.json")); ci = r9["jury + A1b'' as 4th voter"]["vs single Glance head"]["R@9"]
print(f"R@9 for comparison: jury + A1b'' vs single {ci}; smallest detectable ~{round((ci[2] - ci[1]) / 2, 3)}")
json.dump(out, open(f"{V.D}/proof/power-check.json", "w"), indent=1)
