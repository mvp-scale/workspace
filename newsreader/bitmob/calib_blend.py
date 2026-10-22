"""Calibration of a Kaggle e5-base + e5tfidf blend. Calibrator fitted on the night1 held-out part of the frozen test (first n_night rows), scored on testA only
(the models trained on all of train, so a train hold-out does not exist for them; next Kaggle runs hold out train rows for this).
  kev/.venv/bin/python newsreader/bitmob/calib_blend.py <suite_dir e.g. data/suite_kaggle2> -> <suite_dir>/calibration.json"""
import sys, json, numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
D = sys.argv[1]; out = {}
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
z = np.load(f"{D}/blend_conditions/test-probs.npz", allow_pickle=True); P, Y, nn = z["P"], z["Y"].astype(bool), int(z["n_night"]); Pv, Yv, Pt, Yt = P[:nn], Y[:nn], P[nn:], Y[nn:]
def k8(Q): h = Q >= 0.9; return {"share_true": round(float(Yt[h].mean()), 3) if h.any() else None, "n": int(h.sum()), "keys_with_hi": int(h.any(0).sum())}
out["conditions_K8_raw"] = k8(Pt)
out["conditions_K8_pooled_isotonic"] = k8(IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(Pv.ravel(), Yv.ravel()).predict(Pt.ravel()).reshape(Pt.shape))
lr = LogisticRegression(C=100).fit(lg(Pv).reshape(-1, 1), Yv.ravel()); out["conditions_K8_pooled_platt"] = k8(lr.predict_proba(lg(Pt).reshape(-1, 1))[:, 1].reshape(Pt.shape))
Q = np.zeros_like(Pt)
for i in range(P.shape[1]):
    if Yv[:, i].sum() >= 3: Q[:, i] = LogisticRegression(C=10).fit(lg(Pv[:, i]).reshape(-1, 1), Yv[:, i]).predict_proba(lg(Pt[:, i]).reshape(-1, 1))[:, 1]
out["conditions_K8_perkey_platt"] = k8(Q)
out["conditions_K8_raw_cut"] = {str(t): {"share_true": round(float(Yt[Pt >= t].mean()), 3), "n": int((Pt >= t).sum())} for t in (.9, .95, .97, .98)}
z = np.load(f"{D}/blend_country/test-probs.npz", allow_pickle=True); P, Y, nn = z["P"], z["Y"].astype(bool), int(z["n_night"]); c = P.max(1); ok = P.argmax(1) == Y.argmax(1); ct, okt = c[nn:], ok[nn:]
out["country_testA_acc_by_top1_conf"] = {f"{lo}-{hi}": {"n": int(((ct >= lo) & (ct < hi)).sum()), "acc": round(float(okt[(ct >= lo) & (ct < hi)].mean()), 3)} for lo, hi in [(0, .5), (.5, .7), (.7, .9), (.9, 1.01)]}
json.dump(out, open(f"{D}/calibration.json", "w"), indent=1); print(json.dumps(out)[:1500])
