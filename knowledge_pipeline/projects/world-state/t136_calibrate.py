"""T136 calibration (free CPU): turn the one-pass read's raw answers into the Condition head's decision rule. Per-dial thresholds are fitted on a development part of the stories and the rule is scored on the held-out part (5-fold cross-validation over stories), against Clef's stored reading when present (engine stories) and against the engine's own 328-question read. Compares: (a) any dial at or above 0.7 (the rule that scored 0.59), (b) each dial at its own fitted threshold, (c) the maximum of per-dial rank scores.
    ROWS=<jsonl rows from t135_full_read.py> OUT=<folder> python3 t136_calibrate.py -> <OUT>/t136_calibrate.json"""
import os, json, pathlib, collections, zlib
import numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t136")); OUT.mkdir(parents=True, exist_ok=True)
rows = [json.loads(l) for l in open(os.environ.get("ROWS", "/workspace/data/newsreader/labels/full-read-100.jsonl"))]; R = [r for r in rows if "error" not in r]
dials = sorted({k[5:] for r in R for k in r["answers_call1"] if k.startswith("cond_")})
X = np.array([[r["answers_call1"].get("cond_" + d, {}).get("noul", 0.0) for d in dials] for r in R])
is_eng = np.array([r["set"] == "engine" for r in R]); ref = {"engine_read": np.array([1 if r["readings_p328"] else 0 for r in R]), "clef_stored": np.array([1 if r.get("clef_reading") else 0 for r in R])}
Y = np.array([[1 if d in {x["dial"] for x in r["readings_p328"]} else 0 for d in dials] for r in R]); fold = np.array([zlib.crc32(r["id"].encode()) % 5 for r in R])
def fit_thresholds(Xd, Yd):
    th = []
    for j in range(Xd.shape[1]):
        best, bt = -1, 0.7
        for t in np.linspace(0.05, 0.95, 19):
            p = Xd[:, j] >= t; tp = (p & (Yd[:, j] == 1)).sum(); fp = (p & (Yd[:, j] == 0)).sum(); fn = ((~p) & (Yd[:, j] == 1)).sum(); f = 2 * tp / max(2 * tp + fp + fn, 1)
            if f > best: best, bt = f, t
        th.append(bt if Yd[:, j].sum() >= 3 else 0.7)
    return np.array(th)
pred = {"any_at_0.7": np.zeros(len(R), int), "per_dial_threshold": np.zeros(len(R), int)}
for f in range(5):
    tr = fold != f; te = fold == f; th = fit_thresholds(X[tr], Y[tr])
    pred["any_at_0.7"][te] = (X[te] >= 0.7).any(1); pred["per_dial_threshold"][te] = (X[te] >= th).any(1)
res = {"stories": len(R), "dials": len(dials), "dials_with_3_or_more_positive_stories": int((Y.sum(0) >= 3).sum())}
for rn, y in ref.items():
    m_ = is_eng if rn == "clef_stored" else np.ones(len(R), bool)   # Clef stored readings exist for engine stories only
    res[rn] = {m: round(float((p[m_] == y[m_]).mean()), 4) for m, p in pred.items()}; res[rn]["positive_share"] = round(float(y[m_].mean()), 4); res[rn]["stories"] = int(m_.sum())
res["note"] = "Cross-validated over stories, thresholds fitted on the other four folds. Agreement with the engine's reading or Clef's stored reading, not accuracy. n is small on 100 stories: plumbing for the calibration read."
json.dump(res, open(OUT / "t136_calibrate.json", "w"), indent=1); print(json.dumps(res, indent=1))
