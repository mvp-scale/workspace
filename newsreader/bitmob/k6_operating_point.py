"""K6 operating point: per-key threshold = smallest cut with false-positive rate <= target on night1 held-out; scored on testA (e5-base r4 + e5tfidf blend). Prints keys passing K6 (fpr <= 0.0025), mean recall and mean F1.
  kev/.venv/bin/python newsreader/bitmob/k6_operating_point.py"""
import numpy as np
z = np.load("/workspace/data/suite_kaggle4/e5-base-v2/conditions.npz", allow_pickle=True); tf = np.load("/workspace/data/suite_r3/e5tfidf/conditions.npz", allow_pickle=True)
P = (z["P"] + tf["P"]) / 2; Y = z["Y"].astype(bool); nn = int(z["n_night"]); Pv, Yv, Pt, Yt = P[:nn], Y[:nn], P[nn:], Y[nn:]
for target in (0.0025, 0.002, 0.0015, 0.001):
    k6 = nk = 0; rec = []; f1s = []
    for i in range(P.shape[1]):
        if Yt[:, i].sum() < 3 or Yv[:, i].sum() < 1: continue
        nk += 1; neg = ~Yv[:, i]; th = 1.01
        for t in np.sort(np.unique(Pv[:, i])):
            if ((Pv[:, i] >= t) & neg).sum() / max(1, neg.sum()) <= target: th = t; break
        pr = Pt[:, i] >= th; negt = ~Yt[:, i]; k6 += (pr & negt).sum() / negt.sum() <= 0.0025; tp = (pr & Yt[:, i]).sum(); rec.append(tp / Yt[:, i].sum()); f1s.append(2 * tp / max(1, pr.sum() + Yt[:, i].sum()))
    print("night1 fpr target", target, "K6 pass", int(k6), "of", nk, "mean recall", round(float(np.mean(rec)), 3), "mean F1", round(float(np.mean(f1s)), 3))
