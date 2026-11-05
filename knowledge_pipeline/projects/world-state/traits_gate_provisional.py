"""T36 step 3: playbook 13 checks 2 and 3 on all 51 traits from the existing 4 rater panel (xtest B4, 150 items, variant A seed 0). Checks 1 and 5 are NOT measured, so outcomes are provisional.
    /workspace/kev/.venv/bin/python -I traits_gate_provisional.py   (from projects/world-state)"""
import json, sys, collections, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
R = ["clef", "jev", "gemma", "qwen"]; Q = {"t_" + x["id"]: x for x in json.load(open("specs/traits_v0.json"))["questions"]}
ans = {r: collections.defaultdict(dict) for r in R}
for r in R:
    for l in open(f"runs/xtest/B4/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][x["field"]][x["item"]] = 1 if x["label"] == "yes" else 0
out = {}
for t in sorted(Q):
    ids = sorted(set.intersection(*[set(ans[r][t]) for r in R])); n = len(ids)
    M = np.array([[ans[r][t][i] for r in R] for i in ids]); yr = M.mean(0); spread = float(yr.max() - yr.min()); maj = int((M.sum(1) >= 2).sum()); anyyes = int((M.sum(1) >= 1).sum())
    if M.min() == M.max(): a, ci = None, [None, None]
    else:
        a = float(alpha_nominal(M)); ci = boot_alpha(M, np.ones(n), np.zeros(n, int), k=500, seed=0)
    c2 = (ci[0] is not None and ci[0] >= 0.667 and spread <= 0.10); measurable = maj >= 10
    out[t] = {"question": Q[t]["question"] if "question" in Q[t] else Q[t].get("text"), "group": Q[t].get("group"), "n": n, "yes_rates": {r: round(float(v), 3) for r, v in zip(R, yr)}, "spread": round(spread, 3), "alpha": None if a is None else round(a, 3), "alpha_lo": None if ci[0] is None else round(ci[0], 3), "majority_yes_items": maj, "any_yes_items": anyyes, "check2_reliable": bool(c2), "check3_measurable_n_pos_ge_10": bool(measurable), "provisional": "PASS-measured" if (c2 and measurable) else ("HUNT-positives" if not measurable else "REVISE-reliability")}
cnt = collections.Counter(v["provisional"] for v in out.values()); bg = collections.defaultdict(collections.Counter)
for v in out.values(): bg[v["group"]][v["provisional"]] += 1
res = {"counts": dict(cnt), "by_group": {g: dict(c) for g, c in bg.items()}, "traits": out}
json.dump(res, open("runs/pulse/traits_gate_provisional.json", "w"), indent=1); print(json.dumps({"counts": res["counts"], "by_group": res["by_group"]}))
for t, v in out.items():
    if v["provisional"] == "PASS-measured": print("PASS", t, v["group"], v["alpha"], v["alpha_lo"], v["spread"], v["majority_yes_items"], (v["question"] or "")[:60])
print("spread<=0.10 alone:", sum(1 for v in out.values() if v["spread"] <= 0.10), "| alpha_lo>=0.667 alone:", sum(1 for v in out.values() if v["alpha_lo"] is not None and v["alpha_lo"] >= 0.667), "| n_pos>=10:", sum(1 for v in out.values() if v["check3_measurable_n_pos_ge_10"]))
