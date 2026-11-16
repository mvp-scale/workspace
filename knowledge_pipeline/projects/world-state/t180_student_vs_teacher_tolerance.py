"""T180: the faithful tolerance test: CPU Function student vs the TEACHER's label (Jev p>=0.5), 5-fold out-of-fold on the 21,371 Jev-labelled sentences (v6b embeddings, t173), TPR at FPR 0.05, 0.01, 0.005, 0.0025. F-0020 asks TPR 0.90-0.95 at FPR 0.001-0.0025 against the reference reader. Free CPU.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t180_student_vs_teacher_tolerance.py"""
import json, csv, numpy as np, pathlib
OUT = pathlib.Path("runs/pulse/t179"); D = "/workspace/data/anchors/checkthat_subj/"
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
z = np.load("runs/pulse/t172/t173_embeddings.npz"); X = np.vstack([z["q"], z["c"]]); p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
oof = np.zeros(len(y))
for a, b in KFold(5, shuffle=True, random_state=0).split(X): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
neg = np.sort(oof[y == 0])[::-1]; res = {"n": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((y == 0).sum()), "tpr_at_fpr": {}}
for f in (0.05, 0.01, 0.005, 0.0025):
    k = int(np.floor(f * len(neg))); t = neg[k]; res["tpr_at_fpr"][str(f)] = round(float(np.mean(oof[y == 1] > t)), 3)
res["fpr_at_tpr"] = {}
pos = np.sort(oof[y == 1])
for tp in (0.8, 0.9, 0.95):
    t = pos[int(np.floor((1 - tp) * len(pos)))]; res["fpr_at_tpr"][str(tp)] = round(float(np.mean(oof[y == 0] >= t)), 3)
res["tolerance_target"] = "TPR 0.90-0.95 at FPR 0.001-0.0025 (F-0020)"
json.dump(res, open(OUT / "t180_student_vs_teacher.json", "w"), indent=1); print(json.dumps(res))
