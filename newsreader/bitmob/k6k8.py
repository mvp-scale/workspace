"""K6 (false alarms) and K8 (calibration) for a condition reader, from its saved test probabilities (ensemble_conditions.py -> test-probs.npz).

Thresholds per key are chosen on the night1 held-out part of the test (first n_night rows, max F1) and everything is scored on the testA part only.
K6: false-positive rate per key at its threshold; bar <= 0.0025 (2.5 per 1,000, F-0020). K8: of all (story, key) predictions with p >= 0.9, the share that are true; bar >= 0.90.
  python3 newsreader/bitmob/k6k8.py data/ensemble1
"""
import sys, json, numpy as np

D = sys.argv[1]; z = np.load(f"{D}/test-probs.npz", allow_pickle=True); P, Y, keys, nn = z["P"], z["Y"].astype(bool), list(z["keys"]), int(z["n_night"])
Pv, Yv, Pt, Yt = P[:nn], Y[:nn], P[nn:], Y[nn:]; out = {}
CAL = "--calibrate" in sys.argv      # isotonic calibration per key, fitted on the night1 held-out part only, applied to testA
if CAL:
    from sklearn.isotonic import IsotonicRegression
    for i in range(P.shape[1]):
        ir = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(Pv[:, i], Yv[:, i]); Pv[:, i] = ir.predict(Pv[:, i]); Pt[:, i] = ir.predict(Pt[:, i])
    D = D.rstrip("/") + "-cal"; import os; os.makedirs(D, exist_ok=True)
for i, k in enumerate(keys):
    best, th = -1, 0.5
    for t in np.unique(np.round(Pv[:, i], 3)):
        pr = Pv[:, i] >= t; tp = (pr & Yv[:, i]).sum(); f1 = 2 * tp / (pr.sum() + Yv[:, i].sum()) if pr.sum() + Yv[:, i].sum() else 0
        if f1 > best: best, th = f1, float(t)
    pr = Pt[:, i] >= th; neg = ~Yt[:, i]; tp = (pr & Yt[:, i]).sum()
    out[k] = {"threshold": round(th, 3), "fpr": round(float((pr & neg).sum() / max(1, neg.sum())), 5), "per_1000": round(1000 * float((pr & neg).sum() / max(1, neg.sum())), 2),
              "precision": round(float(tp / max(1, pr.sum())), 3), "recall": round(float(tp / max(1, Yt[:, i].sum())), 3), "test_pos": int(Yt[:, i].sum())}
hi = Pt >= 0.9; cal = float(Yt[hi].mean()) if hi.any() else None
bins = [(lo, round(float(Yt[(Pt >= lo) & (Pt < lo + 0.1)].mean()), 3) if ((Pt >= lo) & (Pt < lo + 0.1)).any() else None, int(((Pt >= lo) & (Pt < lo + 0.1)).sum())) for lo in np.round(np.arange(0, 1, 0.1), 1)]
res = {"K6_pass_keys": sum(v["fpr"] <= 0.0025 for v in out.values()), "keys": len(out), "K8_share_true_at_p_ge_0.9": round(cal, 3) if cal is not None else None, "K8_n": int(hi.sum()),
       "calibration_bins": [{"p_from": float(b), "share_true": s, "n": n} for b, s, n in bins], "per_key": out}
json.dump(res, open(f"{D}/k6k8.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "per_key"}))
