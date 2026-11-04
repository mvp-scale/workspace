"""T21: production reader (registered version) presence precision/recall on devq, then my leaf presence head at the same precision. Reads score_end2end.py lines 1-39 unchanged. /workspace/models/embed-zs/.venv/bin/python prod_presence_pr.py v6b-student"""
import sys, numpy as np, json
ver = sys.argv[1]; src = open("score_end2end.py").read().split("\n"); sys.argv = ["score_end2end.py", ver, "devq"]
exec("\n".join(src[:39]))
yes = np.array([bool(r["condition_present"].get("answer")) for r in R]); ansd = np.array([r["condition_present"].get("status") == "answered" for r in R]); conf = np.array([float(r["condition_present"].get("confidence", 0)) for r in R]); pos = np.array([bool(s["conditions"]) for s in S])
tp = (yes & ansd & pos).sum(); pred = (yes & ansd).sum(); print(ver, "devq n", len(ids), "pos", int(pos.sum()), "| says yes (answered)", int(pred), "tp", int(tp), "precision", round(tp / pred, 3), "recall", round(tp / pos.sum(), 3))
from sklearn.metrics import roc_auc_score
print("production confidence AUC for presence (all items, yes-prob proxy):", round(float(roc_auc_score(pos, np.where(yes, conf, -conf))), 3))
z = np.load("runs/pulse/presence_scores_v2mix.npz"); di = list(z["di"]); pd = z["pd"]; m = {i: p for i, p in zip(di, pd)}; keep = [k for k, i in enumerate(ids) if i in m]; pm = np.array([m[ids[k]] for k in keep]); ym = pos[keep]
o = np.argsort(-pm); t = np.cumsum(ym[o]); nn = np.arange(1, len(o) + 1)
for P in (0.80, 0.85, 0.90, 0.92, round(float(tp / pred), 2)):
    ok = np.where(t / nn >= P)[0]; print(f"my leaf head at precision >= {P}: recall {t[ok.max()] / ym.sum():.3f}" if len(ok) else f"my head precision >= {P}: none")
print("my head AUC", round(float(roc_auc_score(ym, pm)), 3), "n", len(keep))
np.savez("runs/pulse/prod_presence_scores.npz", ids=np.array(ids), yes=yes, ansd=ansd, conf=conf, pos=pos)
