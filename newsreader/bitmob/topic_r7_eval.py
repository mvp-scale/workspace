"""Topic reader trained on r5 data (Kaggle run 7, e5-base ep3) vs run 3 (r3 data): accuracy, macro-F1, recall of the six mined topics, TP-3 floor count (topics >=30 test positives with recall under bar 0.79 - 1.96 sqrt(bar(1-bar)/n)), paired bootstrap.
  kev/.venv/bin/python newsreader/bitmob/topic_r7_eval.py -> data/suite_kaggle7/topic_r7_eval.json"""
import numpy as np, json
from sklearn.metrics import f1_score
W = "/workspace/data/"; ld = lambda p: np.load(W + p + ".npz", allow_pickle=True); rs = np.random.RandomState(0)
a = ld("suite_kaggle3/e5b_ep3_lr3e-5/topic"); b = ld("suite_kaggle7/e5b_ep3_lr3e-5/topic"); t3 = ld("suite_r3/e5tfidf/topic")["P"]; t5 = ld("suite_r5/e5tfidf/topic")["P"]; Y = a["Y"].argmax(1); keys = list(a["keys"]); n = len(Y)
sets = {"r3 e5b": a["P"], "r7 e5b (r5 data)": b["P"], "r3 e5b + tfidf r3": (a["P"] + t3) / 2, "r7 e5b + tfidf r5": (b["P"] + t5) / 2}
six = ["mining_materials", "social_welfare_poverty", "family_demographics", "retirement_pensions", "water_utilities", "religion_identity"]; bar = .79; out = {}
for k, P in sets.items():
    pr = P.argmax(1); rec = {t: round(float((pr[Y == keys.index(t)] == keys.index(t)).mean()), 3) for t in six if (Y == keys.index(t)).sum()}
    fails = sum(1 for j in range(len(keys)) if (Y == j).sum() >= 30 and (pr[Y == j] == j).mean() < bar - 1.96 * (bar * (1 - bar) / (Y == j).sum()) ** .5)
    out[k] = {"accuracy": round(float((pr == Y).mean()), 4), "macroF1": round(float(f1_score(Y, pr, average="macro")), 4), "recall_six": rec, "mean_recall_six": round(float(np.mean(list(rec.values()))), 3), "TP3_fails": fails}
d = []; A = sets["r3 e5b + tfidf r3"].argmax(1) == Y; Bq = sets["r7 e5b + tfidf r5"].argmax(1) == Y
for _ in range(2000): i = rs.randint(0, n, n); d.append(Bq[i].mean() - A[i].mean())
out["blend r7/r5 minus r3/r3 acc [95% CI]"] = [round(float(Bq.mean() - A.mean()), 4), *[round(float(x), 4) for x in np.percentile(d, [2.5, 97.5])]]
json.dump(out, open(W + "suite_kaggle7/topic_r7_eval.json", "w"), indent=1); print(json.dumps(out, indent=1))
