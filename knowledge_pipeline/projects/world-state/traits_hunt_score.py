"""T36 step 4 scorer: playbook 13 checks 2 and 3 on the 19 hunted traits (bundle B13, Clef Gemma Qwen, 80 items per trait: 40 top ranked and 40 random). Pre-registered at ledger L832.
    /workspace/kev/.venv/bin/python -I traits_hunt_score.py   (from projects/world-state)
Majority yes = at least 2 of the 3 raters say yes. Measurable = at least 10 majority-yes items. Reliable = alpha lower end >= 0.667 AND spread of the raters yes-rates <= 0.10."""
import json, sys, collections, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
R = ["clef", "gemma", "qwen"]; B = "runs/xtest/B13"; S = json.load(open("runs/xtest/B13_selection.json"))["selection"]
Q = {"t_" + x["id"]: x for x in json.load(open("specs/traits_v0.json"))["questions"]}
ans = {r: collections.defaultdict(dict) for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][x["field"]][x["item"]] = 1 if x["label"] == "yes" else 0
out = {}
for t, v in S.items():
    ids = sorted(set.intersection(*[set(ans[r][t]) for r in R])); n = len(ids)
    M = np.array([[ans[r][t][i] for r in R] for i in ids]); yr = M.mean(0); spread = float(yr.max() - yr.min()); maj = (M.sum(1) >= 2)
    top = [k for k, i in enumerate(ids) if i in set(v["top"])]; rnd = [k for k, i in enumerate(ids) if i in set(v["random"])]
    if M.min() == M.max(): a, lo = None, None
    else: a = float(alpha_nominal(M)); lo = float(boot_alpha(M, np.ones(n), np.zeros(n, int), k=500, seed=0)[0])
    measurable = int(maj.sum()) >= 10; reliable = bool(lo is not None and lo >= 0.667 and spread <= 0.10)
    out[t] = {"question": Q[t]["question"], "group": Q[t]["group"], "n": n, "yes_rates": {r: round(float(x), 3) for r, x in zip(R, yr)}, "spread": round(spread, 3), "alpha": None if a is None else round(a, 3), "alpha_lo": None if lo is None else round(lo, 3), "majority_yes_items": int(maj.sum()), "majority_yes_in_top40": int(maj[top].sum()), "majority_yes_in_random40": int(maj[rnd].sum()), "measurable": bool(measurable), "reliable": reliable, "provisional": ("PASS-measured" if (measurable and reliable) else ("REVISE-reliability" if measurable else "HUNT-more"))}
cnt = collections.Counter(v["provisional"] for v in out.values())
res = {"counts": dict(cnt), "measurable": sum(v["measurable"] for v in out.values()), "reliable_among_measurable": sum(1 for v in out.values() if v["measurable"] and v["reliable"]), "top40_majority_yes_total": sum(v["majority_yes_in_top40"] for v in out.values()), "random40_majority_yes_total": sum(v["majority_yes_in_random40"] for v in out.values()), "traits": out}
json.dump(res, open("runs/pulse/traits_hunt_result.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "traits"}))
for t, v in out.items(): print(t, v["group"], "pos", v["majority_yes_items"], "top", v["majority_yes_in_top40"], "rnd", v["majority_yes_in_random40"], "alpha", v["alpha"], "lo", v["alpha_lo"], "spr", v["spread"], v["provisional"])
