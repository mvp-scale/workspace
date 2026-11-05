"""Reliability rules of playbook 13 for chosen traits of one bundle (Clef Gemma Qwen, variant A seed 0): majority yes = at least 2 of 3; measurable = at least 10 majority yes items; reliable = alpha lower end >= 0.667 and spread of yes-rates <= 0.10. Same computation as traits_natural_score.py.
    /workspace/kev/.venv/bin/python -I traits_bundle_score.py <bundle_dir> <out.json> <trait> [<trait> ...]"""
import json, sys, collections, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
B, OUT, TR = sys.argv[1], sys.argv[2], sys.argv[3:]; R = ["clef", "gemma", "qwen"]
ans = {r: collections.defaultdict(dict) for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][x["field"]][x["item"]] = 1 if x["label"] == "yes" else 0
out = {}
for t in TR:
    ids = sorted(set.intersection(*[set(ans[r][t]) for r in R])); n = len(ids)
    M = np.array([[ans[r][t][i] for r in R] for i in ids]); yr = M.mean(0); spread = float(yr.max() - yr.min()); maj = int((M.sum(1) >= 2).sum())
    if M.min() == M.max(): a, lo = None, None
    else: a = float(alpha_nominal(M)); lo = float(boot_alpha(M, np.ones(n), np.zeros(n, int), k=500, seed=0)[0])
    out[t] = {"n": n, "yes_rates": {r: round(float(x), 3) for r, x in zip(R, yr)}, "spread": round(spread, 3), "majority_yes_items": maj, "alpha": None if a is None else round(a, 3), "alpha_lo": None if lo is None else round(lo, 3), "measurable": maj >= 10, "reliable": bool(lo is not None and lo >= 0.667 and spread <= 0.10)}
json.dump(out, open(OUT, "w"), indent=1); print(json.dumps(out))
