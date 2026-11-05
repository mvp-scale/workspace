"""T36 natural confirmation scorer (bundle B14: 11 candidate traits on 800 natural DEVQ items, Clef Gemma Qwen). Pre-registered at ledger L837.
    /workspace/kev/.venv/bin/python -I traits_natural_score.py   (from projects/world-state)
Majority yes = at least 2 of 3 raters. Measurable = at least 10 majority yes items. Reliable = alpha lower end >= 0.667 AND spread of the raters yes-rates <= 0.10.
Controls: x025 and x034 (reliable on the natural B4 panel, L830). Enriched passers: the 9 traits of runs/pulse/traits_hunt_result.json marked PASS-measured."""
import json, sys, collections, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
R = ["clef", "gemma", "qwen"]; B = "runs/xtest/B14"; CAND = json.load(open(f"{B}/bundle.json"))["fields"]
Q = {"t_" + x["id"]: x for x in json.load(open("specs/traits_v0.json"))["questions"]}
EN = json.load(open("runs/pulse/traits_hunt_result.json"))["traits"]; passers = [t for t, v in EN.items() if v["provisional"] == "PASS-measured"]; controls = ["t_x025", "t_x034"]
ans = {r: collections.defaultdict(dict) for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][x["field"]][x["item"]] = 1 if x["label"] == "yes" else 0
out = {}
for t in CAND:
    ids = sorted(set.intersection(*[set(ans[r][t]) for r in R])); n = len(ids)
    M = np.array([[ans[r][t][i] for r in R] for i in ids]); yr = M.mean(0); spread = float(yr.max() - yr.min()); maj = int((M.sum(1) >= 2).sum())
    if M.min() == M.max(): a, lo = None, None
    else: a = float(alpha_nominal(M)); lo = float(boot_alpha(M, np.ones(n), np.zeros(n, int), k=500, seed=0)[0])
    measurable = maj >= 10; reliable = bool(lo is not None and lo >= 0.667 and spread <= 0.10)
    out[t] = {"question": Q[t]["question"], "n": n, "yes_rates": {r: round(float(x), 3) for r, x in zip(R, yr)}, "spread": round(spread, 3), "majority_yes_items": maj, "majority_yes_share": round(maj / n, 3), "alpha": None if a is None else round(a, 3), "alpha_lo": None if lo is None else round(lo, 3), "measurable": bool(measurable), "reliable": reliable, "enriched_alpha": EN[t]["alpha"] if t in EN else None}
P = [t for t in passers if t in out]
meas = [t for t in P if out[t]["measurable"]]; keep = [t for t in meas if out[t]["reliable"]]
drops = [EN[t]["alpha"] - out[t]["alpha"] for t in meas if out[t]["alpha"] is not None]
res = {"controls": {t: {"alpha_lo": out[t]["alpha_lo"], "reliable": out[t]["reliable"], "measurable": out[t]["measurable"]} for t in controls},
       "pred1_controls_alpha_lo_ge_0.667": all(out[t]["alpha_lo"] is not None and out[t]["alpha_lo"] >= 0.667 for t in controls),
       "enriched_passers": len(P), "measurable_among_passers": len(meas), "keep_reliable_among_measurable": len(keep), "not_measurable": len(P) - len(meas),
       "pred2_at_least_5_keep": len(keep) >= 5, "pred3_at_least_3_not_measurable": (len(P) - len(meas)) >= 3,
       "mean_alpha_drop_enriched_to_natural_among_measurable": None if not drops else round(float(np.mean(drops)), 3), "pred4_mean_drop_ge_0.05": bool(drops and np.mean(drops) >= 0.05), "traits": out}
json.dump(res, open("runs/pulse/traits_natural_result.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "traits"}))
for t, v in out.items(): print(t, "maj", v["majority_yes_items"], "share", v["majority_yes_share"], "alpha", v["alpha"], "lo", v["alpha_lo"], "spr", v["spread"], "enriched", v["enriched_alpha"], "measurable" if v["measurable"] else "NOT-measurable", "reliable" if v["reliable"] else "")
