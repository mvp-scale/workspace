"""T183 (C2): does answering-when-sure hurt against human truth? Out-of-fold student scores (as t181b), thresholds from the L2254 rule fitted on all out-of-fold scores vs Jev labels; on the CheckThat rows compare accuracy vs human gold: student on answered rows, Jev on the same rows, Jev on all rows, hybrid (student where answered, Jev elsewhere). Prediction in ledger L2261.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t183_hybrid_vs_gold.py"""
import json, csv, numpy as np
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]
z = np.load("runs/pulse/t172/t173_embeddings.npz"); X = np.vstack([z["q"], z["c"]]); p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y = (p >= 0.5).astype(int)
grp = np.array([r["id"].split(":")[1] for r in q] + [r["id"] for r in ct]); nq = len(q)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
oof = np.zeros(len(y))
for a, b in GroupKFold(5).split(X, y, grp): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
neg = np.sort(oof[y == 0])[::-1]; hi = neg[int(np.floor(0.0025 * len(neg)))]; pos = np.sort(oof[y == 1]); lo = pos[int(np.floor(0.05 * len(pos)))]
s = oof[nq:]; g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int); pj = p[nq:]; jev = (pj >= 0.5).astype(int)
yes = s > hi; no = s < lo; ans = yes | no; stu = (s > hi).astype(int)
def bal(pred, gold, m):
    gg = gold[m]; pp = pred[m]
    if (gg == 1).sum() == 0 or (gg == 0).sum() == 0: return None
    return round(float((np.mean(pp[gg == 1] == 1) + np.mean(pp[gg == 0] == 0)) / 2), 3)
hyb = np.where(ans, stu, jev); allm = np.ones(len(g), bool)
res = {"n_checkthat": int(len(g)), "coverage_on_checkthat": round(float(ans.mean()), 3), "student_bal_acc_vs_gold_on_answered": bal(stu, g, ans), "jev_bal_acc_vs_gold_on_same_answered": bal(jev, g, ans), "jev_bal_acc_vs_gold_all": bal(jev, g, allm), "hybrid_bal_acc_vs_gold_all": bal(hyb, g, allm), "answered_n": int(ans.sum()), "answered_pos": int(g[ans].sum()), "answered_neg": int((g[ans] == 0).sum()), "student_acc_vs_gold_answered_plain": round(float((stu[ans] == g[ans]).mean()), 3), "jev_acc_vs_gold_answered_plain": round(float((jev[ans] == g[ans]).mean()), 3), "jev_acc_vs_gold_all_plain": round(float((jev == g).mean()), 3), "hybrid_acc_vs_gold_all_plain": round(float((hyb == g).mean()), 3)}
json.dump(res, open("runs/pulse/t179/t183_hybrid_vs_gold.json", "w"), indent=1); print(json.dumps(res))
