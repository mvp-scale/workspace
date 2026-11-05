"""T39: isotonic recalibration of the v6b-student topic two guess confidence, fitted on DEVQ only, scored once on sealed.
    /workspace/models/embed-zs/.venv/bin/python calibrate_topic.py   (from projects/world-state)"""
import json, sys, numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS
from sklearn.isotonic import IsotonicRegression
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); TX = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}
def run(path):
    out = []
    for r in J(path):
        t = TX.get(r["item_id"])
        if not t: continue
        x = e.read(t)["topic_top2"]; out.append((x["confidence"], float(r["label"].get("topic") in x["answer"])))
    return np.array(out)
D = run("runs/pulse/devq/labels.jsonl"); S = run("runs/pulse/sealed/labels.jsonl")
def ece(c, ok, bins=10):
    b = np.minimum((c * bins).astype(int), bins - 1); t = 0.0
    for i in range(bins):
        m = b == i
        if m.any(): t += m.mean() * abs(ok[m].mean() - c[m].mean())
    return round(float(t), 3)
iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(D[:, 0], D[:, 1])
Dc, Sc = iso.predict(D[:, 0]), iso.predict(S[:, 0])
def cov(c, ok, tau=None):
    o = np.argsort(-c); hit = np.cumsum(ok[o]) / np.arange(1, len(c) + 1); g = np.where(hit >= 0.95)[0]; k = g[-1] if len(g) else None
    return None if k is None else (round(float((np.arange(len(c)) <= k).mean()), 3), round(float(c[o][k]), 3))
res = {"ece_devq_before": ece(D[:, 0], D[:, 1]), "ece_devq_after_fit_data": ece(Dc, D[:, 1]), "ece_sealed_before": ece(S[:, 0], S[:, 1]), "ece_sealed_after": ece(Sc, S[:, 1]), "mean_conf_vs_hit_sealed_before": [round(float(S[:, 0].mean()), 3), round(float(S[:, 1].mean()), 3)], "mean_conf_vs_hit_sealed_after": [round(float(Sc.mean()), 3), round(float(S[:, 1].mean()), 3)], "iso_x": [round(float(v), 4) for v in iso.X_thresholds_], "iso_y": [round(float(v), 4) for v in iso.y_thresholds_]}
json.dump(res, open("runs/pulse/topic_calibration.json", "w"), indent=1); print({k: v for k, v in res.items() if not k.startswith("iso")})
