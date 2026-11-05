"""T33 round 2 scorer: per-event factuality (eventhappened) on MAVEN-FACT human labelled events, two sided, plus alpha over the raters, plus breakdown by factuality class.
    /workspace/kev/.venv/bin/python -I score_t33b.py   (from projects/world-state)"""
import json, sys, math, collections, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
R = ["clef", "gemma", "qwen"]; G = json.load(open("/workspace/data/anchors/maven_fact/gold_T33b.json"))
H = {}
for r in R:
    d = {}
    for l in open(f"runs/xtest/B11/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["field"] == "eventhappened" and x["ok"]: d[x["item"]] = 1 if x["label"] == "yes" else 0
    H[r] = d
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(max(c - h, 0), 3), round(c + h, 3)]
res = {"per_rater": {}}
for r in R:
    pos = [i for i, v in G.items() if v["yes"] and i in H[r]]; neg = [i for i, v in G.items() if not v["yes"] and i in H[r]]
    tp = sum(H[r][i] for i in pos); tn = sum(1 - H[r][i] for i in neg)
    by = collections.defaultdict(lambda: [0, 0])
    for i in neg: by[G[i]["factuality"]][1] += 1; by[G[i]["factuality"]][0] += 1 - H[r][i]
    res["per_rater"][r] = {"recall_happened": [tp, len(pos), round(tp / len(pos), 3), wil(tp, len(pos))], "recall_not_happened": [tn, len(neg), round(tn / len(neg), 3), wil(tn, len(neg))], "balanced_accuracy": round((tp / len(pos) + tn / len(neg)) / 2, 3), "correct_by_class_for_non_CT+": {k: [a, b, round(a / b, 2)] for k, (a, b) in by.items()}, "yes_rate": round(sum(H[r][i] for i in pos + neg) / len(pos + neg), 3)}
ids = sorted(set.intersection(*[set(H[r]) for r in R])); M = np.array([[H[r][i] for r in R] for i in ids]); n = len(ids)
res["alpha"] = {"n": n, "alpha": round(float(alpha_nominal(M)), 3), "ci95": [round(c, 3) for c in boot_alpha(M, np.ones(n), np.zeros(n, int), k=1000, seed=0)], "all_agree_share": round(float(((M.sum(1) == 0) | (M.sum(1) == 3)).mean()), 3)}
maj = (M.sum(1) >= 2).astype(int); gold = np.array([1 if G[i]["yes"] else 0 for i in ids]); res["majority_vote_balanced_accuracy"] = round(float((maj[gold == 1].mean() + (1 - maj[gold == 0]).mean()) / 2), 3)
res["lines"] = {"every_balanced_ge_0.85": all(v["balanced_accuracy"] >= 0.85 for v in res["per_rater"].values()), "alpha_ge_0.70": bool(res["alpha"]["alpha"] >= 0.70)}
json.dump(res, open("runs/xtest/B11/score_t33b.json", "w"), indent=1); print(json.dumps(res, indent=1))
