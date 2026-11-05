"""T32 round scorer: yes-rate spread and alpha on the 597 paired B1 items, and false-yes on the MAVEN-FACT negatives, for a round bundle.
    /workspace/kev/.venv/bin/python -I score_t32_round.py <round_bundle_dir e.g. runs/xtest/B8>   (run from projects/world-state)
Pre-registered lines: spread <= 0.10; alpha >= old alpha + 0.05 (old = B1 v3b, 0.580); MAVEN-FACT false-yes < 0.10 per rater and not up more than 0.02 over L730."""
import json, sys, math, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
B = sys.argv[1]; R = ["clef", "gemma", "qwen"]
def load(b):
    out = {}
    for r in R:
        d = {}
        try:
            for l in open(f"{b}/runs/{r}_A_s0/results.jsonl"):
                x = json.loads(l)
                if x["field"] == "presence" and x["ok"]: d[x["item"]] = 1 if x["label"] == "yes" else 0
        except FileNotFoundError: pass
        out[r] = d
    return out
old, new = load("runs/xtest/B1"), load(B)
R = [r for r in R if new[r]]; print("raters present:", R)
ids = sorted(set.intersection(*[set(old[r]) & set(new[r]) for r in R])); n = len(ids)
res = {"bundle": B, "paired_items": n}
for name, D in (("old_v3b", old), ("new", new)):
    M = np.array([[D[r][i] for r in R] for i in ids]); yr = {r: round(float(M[:, k].mean()), 3) for k, r in enumerate(R)}
    a = alpha_nominal(M); ci = boot_alpha(M, np.ones(n), np.zeros(n, int), k=1000, seed=0)
    res[name] = {"yes_rates": yr, "spread": round(max(yr.values()) - min(yr.values()), 3), "alpha": round(a, 3), "alpha_ci95": [round(c, 3) for c in ci]}
g = json.load(open("/workspace/data/anchors/maven_fact/gold_T29.json")); l730 = {"clef": 0.047, "gemma": 0.002, "qwen": 0.004}
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(max(c - h, 0), 3), round(c + h, 3)]
fy = {}
for r in R:
    neg = [i for i, v in g.items() if v["no_ct_plus"] and i in new[r]]
    if not neg: continue
    k = sum(new[r][i] for i in neg)
    ctrl = [i for i, v in g.items() if not v["no_ct_plus"] and i in new[r]]; kc = sum(new[r][i] for i in ctrl)
    fy[r] = {"false_yes": k, "n": len(neg), "rate": round(k / len(neg), 3), "ci95": wil(k, len(neg)), "was_L730": l730[r], "ct_plus_controls_yes_rate": round(kc / len(ctrl), 3)}
res["maven_false_yes"] = fy
res["lines"] = {"spread_le_0.10": bool(res["new"]["spread"] <= 0.10), "alpha_up_0.05": bool(res["new"]["alpha"] >= res["old_v3b"]["alpha"] + 0.05), "false_yes_ok": (all(v["rate"] < 0.10 and v["rate"] <= l730[r] + 0.02 for r, v in fy.items()) if fy else None)}
print(json.dumps(res, indent=1))
