"""T33 scorer: the happened question. (1) MAVEN-FACT sentences, two sided, per rater; (2) agreement and yes-rate spread on the 597 paired news items, against presence under v3b (B1); (3) logical consistency presence yes implies happened yes.
    /workspace/kev/.venv/bin/python -I score_t33.py   (from projects/world-state)"""
import json, sys, math, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
R = ["clef", "gemma", "qwen"]
def load(b, field):
    out = {}
    for r in R:
        d = {}
        for l in open(f"runs/xtest/{b}/runs/{r}_A_s0/results.jsonl"):
            x = json.loads(l)
            if x["field"] == field and x["ok"]: d[x["item"]] = 1 if x["label"] == "yes" else 0
        out[r] = d
    return out
H, PR = load("B10", "happened"), load("B1", "presence")
g = json.load(open("/workspace/data/anchors/maven_fact/gold_T29.json"))
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(max(c - h, 0), 3), round(c + h, 3)]
res = {"maven": {}}
for r in R:
    pos = [i for i, v in g.items() if not v["no_ct_plus"] and i in H[r]]; neg = [i for i, v in g.items() if v["no_ct_plus"] and i in H[r]]
    tp = sum(H[r][i] for i in pos); tn = sum(1 - H[r][i] for i in neg)
    res["maven"][r] = {"recall_yes": [tp, len(pos), round(tp / len(pos), 3), wil(tp, len(pos))], "recall_no": [tn, len(neg), round(tn / len(neg), 3), wil(tn, len(neg))], "balanced_accuracy": round((tp / len(pos) + tn / len(neg)) / 2, 3), "yes_rate_all": round(sum(H[r][i] for i in pos + neg) / len(pos + neg), 3)}
ids = sorted(set.intersection(*[set(H[r]) & set(PR[r]) for r in R])); n = len(ids)
for name, D in (("happened", H), ("presence_v3b", PR)):
    M = np.array([[D[r][i] for r in R] for i in ids]); yr = {r: round(float(M[:, k].mean()), 3) for k, r in enumerate(R)}
    res[name] = {"n": n, "yes_rates": yr, "spread": round(max(yr.values()) - min(yr.values()), 3), "alpha": round(float(alpha_nominal(M)), 3), "alpha_ci95": [round(c, 3) for c in boot_alpha(M, np.ones(n), np.zeros(n, int), k=1000, seed=0)]}
res["presence_yes_but_happened_no"] = {r: [sum(1 for i in ids if PR[r][i] == 1 and H[r][i] == 0), sum(PR[r][i] for i in ids)] for r in R}
res["lines"] = {"maven_balanced_ge_0.90": all(v["balanced_accuracy"] >= 0.90 for v in res["maven"].values()), "news_alpha_ge_0.68": bool(res["happened"]["alpha"] >= 0.68), "news_spread_le_0.10": bool(res["happened"]["spread"] <= 0.10)}
json.dump(res, open("runs/xtest/B10/score_t33.json", "w"), indent=1); print(json.dumps(res, indent=1))
