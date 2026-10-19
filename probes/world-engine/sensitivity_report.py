"""Step 1 report (ledger S-0001): turns data/step1/*.npz from sensitivity.py into budget.json with the formulas fixed in sensitivity.py's docstring.
Run: /workspace/kev/.venv/bin/python sensitivity_report.py"""
import json, os, itertools
import numpy as np
OUT = "/workspace/data/step1"
TPRS = [1.0, 0.8, 0.6, 0.4, 0.2]; FPRS = [0.0, 0.005, 0.01, 0.02, 0.05]; REF = (0.4, 0.01)
nz = np.load(f"{OUT}/noise.npz"); band = nz["band"]
def ratio(delta): return float(np.max(np.abs(delta) / band))           # delta: 9 x 20 (or mean |delta| already)
rep = {"noise_band": {"median": float(np.median(band)), "max": float(band.max())}, "formulas": "see sensitivity.py docstring"}
freq = json.load(open(f"{OUT}/check.json"))["key_freq"]

if os.path.exists(f"{OUT}/grid.npz"):
    g = np.load(f"{OUT}/grid.npz"); clean = g["clean"]; keys = sorted(set(g["keys"]))
    drift = {}                                                         # (key, tpr, fpr) -> mean over seeds of |inj - clean|
    for k, (t, f, s), o in zip(g["keys"], g["cells"], g["outs"]): drift.setdefault((k, float(t), float(f)), []).append(np.abs(o - clean))
    drift = {c: np.mean(v, axis=0) for c, v in drift.items()}
    per = {}
    for k in keys:
        cells = {f"{t}|{f}": (0.0 if (t, f) == (1.0, 0.0) else ratio(drift[(k, t, f)])) for t in TPRS for f in FPRS}
        tk = [t for t in TPRS if cells[f"{t}|0.0"] <= 1]; fk = [f for f in FPRS if cells[f"1.0|{f}"] <= 1]
        per[k] = {"freq": freq[k], "ratio": cells, "pass": {c: r <= 1 for c, r in cells.items()},
                  "knee_tpr_at_fpr0": min(tk) if tk else None, "knee_fpr_at_tpr1": max(fk) if fk else None, "ref_ratio": cells[f"{REF[0]}|{REF[1]}"]}
    order = sorted(keys, key=lambda k: -per[k]["ref_ratio"])
    for i, k in enumerate(order): per[k]["rank"] = i + 1
    occur = [k for k in keys if freq[k] > 0]
    fail_ref = [k for k in keys if per[k]["ref_ratio"] > 1]
    fail_t4 = [k for k in keys if per[k]["ratio"]["0.4|0.0"] > 1]
    fp_dom = [k for k in occur if per[k]["ratio"]["1.0|0.02"] > per[k]["ratio"]["0.4|0.0"]]
    rep["grid"] = {"keys": len(keys), "keys_occurring": len(occur), "fail_at_ref_cell": len(fail_ref), "fail_at_tpr.4_fpr0": len(fail_t4),
                   "fpr_dominates_keys": len(fp_dom), "of_occurring": len(occur), "pass_everywhere": [k for k in keys if all(per[k]["pass"].values())],
                   "ratio_at_ref_median": float(np.median([per[k]["ref_ratio"] for k in keys])), "top10": [(k, round(per[k]["ref_ratio"], 1), freq[k]) for k in order[:10]]}
    rep["per_key"] = per

if os.path.exists(f"{OUT}/joint.npz") and "grid" in rep:
    j = np.load(f"{OUT}/joint.npz"); jc = j["clean"]; res = {}
    for a, o in zip(j["args"], j["outs"]): t, f, cl, s, _, _ = json.loads(a); res.setdefault((t, f, cl), []).append(o - jc)
    sig = {}
    for k, (t, f, s), o in zip(g["keys"], g["cells"], g["outs"]): sig.setdefault((float(t), float(f)), {}).setdefault(k, []).append(o - clean)
    out = {}
    for t, f in [(0.8, 0.005), (0.6, 0.01), (0.4, 0.01)]:
        ssum = sum(np.mean(v, axis=0) for v in sig[(t, f)].values())       # sum of single-key signed shifts
        ind = np.mean(res[(t, f, False)], axis=0); clu = np.mean(res[(t, f, True)], axis=0)
        out[f"{t}|{f}"] = {"joint_indep_ratio": ratio(np.mean([np.abs(x) for x in res[(t, f, False)]], axis=0)), "joint_clustered_ratio": ratio(np.mean([np.abs(x) for x in res[(t, f, True)]], axis=0)),
                           "additivity_rel_L1": float(np.abs(ind - ssum).sum() / np.abs(ssum).sum()), "clustered_vs_indep_L1": float(np.abs(clu).sum() / np.abs(ind).sum())}
    rep["joint"] = out; rep["morris_needed"] = any(v["additivity_rel_L1"] > 0.2 for v in out.values())

if os.path.exists(f"{OUT}/order.npz"):
    j = np.load(f"{OUT}/order.npz"); res = {tuple(json.loads(a)): o for a, o in zip(j["args"], j["outs"])}
    rows = {}
    for (t, f, cl, s, o, k), v in res.items():
        if t is None: continue
        c = res[(None, None, False, 0, o, k)]; rows[f"order{o}_ticks{k}"] = ratio(np.abs(v - c))
    rep["order_pace"] = {"joint_ref_ratio": rows, "spread_max_over_min": max(rows.values()) / max(1e-9, min(rows.values()))}

if os.path.exists(f"{OUT}/boot.npz") and "grid" in rep:
    j = np.load(f"{OUT}/boot.npz"); bc = j["boot_clean"]; rk = {}
    by_b = {}
    for a, o in zip(j["args"], j["outs"]):
        b, k = json.loads(a)
        if k is None: continue
        by_b.setdefault(b, {})[k] = ratio(np.abs(o - bc[b]))
    for b, d in by_b.items():
        for i, k in enumerate(sorted(d, key=lambda k: -d[k])): rk.setdefault(k, []).append(i + 1)
    rep["bootstrap_rank"] = {k: {"rank": rep["per_key"][k]["rank"], "p5": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))} for k, v in rk.items()}

if "grid" in rep:                                                     # budget in story counts (the method's rate units): stories misread before outputs leave the band, assuming drift grows linearly
    N = 880
    for k in keys:
        n = freq[k]; pk = rep["per_key"][k]
        drop = [((1 - t) * n) / pk["ratio"][f"{t}|0.0"] for t in TPRS[1:] if n and pk["ratio"][f"{t}|0.0"] > 0]
        add_ = [(f * (N - n)) / pk["ratio"][f"1.0|{f}"] for f in FPRS[1:] if pk["ratio"][f"1.0|{f}"] > 0]
        pk["tolerated_missed_stories"] = float(np.median(drop)) if drop else None
        pk["tolerated_false_stories"] = float(np.median(add_)) if add_ else None
    occ = [k for k in keys if freq[k] > 0]
    rep["budget_stories"] = {"median_missed_occurring": float(np.median([v for k in occ if (v := rep["per_key"][k]["tolerated_missed_stories"]) is not None])),
                             "occurring_keys_never_drifting": sum(rep["per_key"][k]["tolerated_missed_stories"] is None for k in occ),
                             "median_false_all": float(np.median([v for k in keys if (v := rep["per_key"][k]["tolerated_false_stories"]) is not None])),
                             "keys_tolerating_1plus_missed": sum((v := rep["per_key"][k]["tolerated_missed_stories"]) is None or v >= 1 for k in occ), "of_occurring": len(occ)}
if os.path.exists(f"{OUT}/self.npz"):                                  # after-the-fact context, not the limit: Clef against itself
    sf = np.load(f"{OUT}/self.npz"); rep["clef_self"] = {"wording0_ratio": ratio(np.abs(sf["w0"] - sf["clean"])), "wording1_ratio": ratio(np.abs(sf["w1"] - sf["clean"])),
        "wording0_vs_1_ratio": ratio(np.abs(sf["w0"] - sf["w1"])), "max_abs_points_w0_w1": float(np.abs(sf["w0"] - sf["w1"]).max()), "note": "context only; the limit was fixed before the run"}

if os.path.exists(f"{OUT}/self.npz") and "grid" in rep:              # tolerance (b), ledger D-0002: Clef's own wording-to-wording drift, floored at the noise band
    sf = np.load(f"{OUT}/self.npz"); tolb = np.maximum(np.abs(sf["w0"] - sf["w1"]), band)
    rb = lambda d: float(np.max(np.abs(d) / tolb))
    pb = {}
    for k in keys:
        cells = {f"{t}|{f}": (0.0 if (t, f) == (1.0, 0.0) else rb(drift[(k, t, f)])) for t in TPRS for f in FPRS}
        tk = [t for t in TPRS if cells[f"{t}|0.0"] <= 1]; fk = [f for f in FPRS if cells[f"1.0|{f}"] <= 1]
        pb[k] = {"ratio": cells, "knee_tpr_at_fpr0": min(tk) if tk else None, "knee_fpr_at_tpr1": max(fk) if fk else None, "ref_ratio": cells[f"{REF[0]}|{REF[1]}"]}
    occ = [k for k in keys if freq[k] > 0]; ordb = sorted(keys, key=lambda k: -pb[k]["ref_ratio"])
    for i, k in enumerate(ordb): pb[k]["rank"] = i + 1
    out = {"tol_median_points": float(np.median(tolb)), "tol_min_points": float(tolb.min()), "tol_max_points": float(tolb.max()),
           "occurring_pass_at_ref": sum(pb[k]["ref_ratio"] <= 1 for k in occ), "of_occurring": len(occ), "all_pass_at_ref": sum(pb[k]["ref_ratio"] <= 1 for k in keys),
           "knee_tpr_counts": {str(t): sum(pb[k]["knee_tpr_at_fpr0"] == t for k in occ) for t in TPRS}, "knee_fpr_counts": {str(f): sum(pb[k]["knee_fpr_at_tpr1"] == f for k in keys) for f in FPRS},
           "top10": [(k, round(pb[k]["ref_ratio"], 2), freq[k]) for k in ordb[:10]]}
    if "joint" in rep:
        j = np.load(f"{OUT}/joint.npz"); jc = j["clean"]; jr = {}
        for a_, o in zip(j["args"], j["outs"]): t, f, cl, s_, _, _ = json.loads(a_); jr.setdefault(f"{t}|{f}|{'clustered' if cl else 'indep'}", []).append(np.abs(o - jc))
        out["joint_ratio_b"] = {k: rb(np.mean(v, axis=0)) for k, v in jr.items()}
    rep["limit_b"] = out; rep["per_key_b"] = pb

if os.path.exists(f"{OUT}/boot.npz") and "limit_b" in rep:           # bootstrap rank intervals under tolerance (b) (ledger C-0001)
    j = np.load(f"{OUT}/boot.npz"); bc = j["boot_clean"]; by_b = {}
    for a_, o in zip(j["args"], j["outs"]):
        b, k = json.loads(a_)
        if k is not None: by_b.setdefault(b, {})[k] = float(np.max(np.abs(o - bc[b]) / tolb))
    rk = {}
    for b, d in by_b.items():
        for i, k in enumerate(sorted(d, key=lambda k: -d[k])): rk.setdefault(k, []).append(i + 1)
    bb = {k: {"rank": rep["per_key_b"][k]["rank"], "p5": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95)), "pass_share_at_ref": float(np.mean([by_b[b][k] <= 1 for b in by_b]))} for k, v in rk.items()}
    rep["bootstrap_rank_b"] = bb
    top = [k for k, *_ in rep["limit_b"]["top10"]]
    rep["bootstrap_b_summary"] = {"boots": len(by_b), "top10_intervals": [(k, bb[k]["rank"], bb[k]["p5"], bb[k]["p95"]) for k in top],
                                  "median_interval_width": float(np.median([v["p95"] - v["p5"] for v in bb.values()]))}

if os.path.exists(f"{OUT}/morris.npz") and "limit_b" in rep:          # Morris screening (SALib), scalar output = drift against tolerance (b)
    import sys; sys.path.insert(0, "/workspace/models/salib-lib"); from SALib.analyze import morris as MA
    m = np.load(f"{OUT}/morris.npz"); names = [str(x) for x in m["names"]]
    Y = np.array([float(np.max(np.abs(o - m["clean"]) / tolb)) for o in m["outs"]])
    Si = MA.analyze({"num_vars": len(names), "names": names, "bounds": [[0, 3]] * len(names)}, m["X"], Y, num_levels=4, seed=12)
    mu = dict(zip(names, Si["mu_star"])); sg = dict(zip(names, Si["sigma"])); top = sorted(names, key=lambda k: -mu[k])
    single = [k for k, *_ in rep["limit_b"]["top10"]]
    rep["morris"] = {"runs": len(Y), "top10": [(k, round(float(mu[k]), 2), round(float(sg[k]), 2)) for k in top[:10]], "overlap_with_single_key_top10": len(set(top[:10]) & set(single)),
                     "mu_star": {k: float(mu[k]) for k in names}, "sigma": {k: float(sg[k]) for k in names}, "zero_effect_keys": [k for k in names if mu[k] < 1e-9]}

if os.path.exists(f"{OUT}/self.npz") and "grid" in rep:              # tolerance (c), ledger D-0003: (b) pooled across outputs as a relative tolerance
    sf = np.load(f"{OUT}/self.npz"); cm = np.abs(sf["clean"]); rel = np.abs(sf["w0"] - sf["w1"]) / np.maximum(cm, 1e-9)
    r_ = float(np.median(rel)); tolc = np.maximum(r_ * cm, band); rc = lambda d: float(np.max(np.abs(d) / tolc))
    pc = {k: {"ref_ratio": rc(drift[(k, *REF)]), **{f"{t}|{f}": (0.0 if (t, f) == (1.0, 0.0) else rc(drift[(k, t, f)])) for t in TPRS for f in FPRS}} for k in keys}
    occ = [k for k in keys if freq[k] > 0]; ordc = sorted(keys, key=lambda k: -pc[k]["ref_ratio"])
    knee_t = {k: min([t for t in TPRS if pc[k][f"{t}|0.0"] <= 1], default=None) for k in keys}; knee_f = {k: max([f for f in FPRS if pc[k][f"1.0|{f}"] <= 1], default=None) for k in keys}
    out = {"r_relative": r_, "tol_quantiles_points": np.percentile(tolc, [5, 50, 95]).tolist(), "occurring_pass_at_ref": sum(pc[k]["ref_ratio"] <= 1 for k in occ), "of_occurring": len(occ),
           "knee_tpr_counts": {str(t): sum(knee_t[k] == t for k in occ) for t in TPRS}, "knee_fpr_counts": {str(f): sum(knee_f[k] == f for k in keys) for f in FPRS},
           "top10": [(k, round(pc[k]["ref_ratio"], 2), freq[k]) for k in ordc[:10]]}
    if os.path.exists(f"{OUT}/joint.npz"):
        j = np.load(f"{OUT}/joint.npz"); jc = j["clean"]; jr = {}
        for a_, o in zip(j["args"], j["outs"]): t, f, cl, s_, _, _ = json.loads(a_); jr.setdefault(f"{t}|{f}|{'clustered' if cl else 'indep'}", []).append(np.abs(o - jc))
        out["joint_ratio_c"] = {k: rc(np.mean(v, axis=0)) for k, v in jr.items()}
    if os.path.exists(f"{OUT}/morris.npz"):
        import sys; sys.path.insert(0, "/workspace/models/salib-lib"); from SALib.analyze import morris as MA
        m = np.load(f"{OUT}/morris.npz"); names = [str(x) for x in m["names"]]; Yc = np.array([rc(o - m["clean"]) for o in m["outs"]])
        Si = MA.analyze({"num_vars": len(names), "names": names, "bounds": [[0, 3]] * len(names)}, m["X"], Yc, num_levels=4, seed=12); mu = dict(zip(names, Si["mu_star"]))
        topm = sorted(names, key=lambda k: -mu[k])[:10]; dom = [tuple(int(x) for x in np.unravel_index(np.argmax(np.abs(o - m["clean"]) / tolc), tolc.shape)) for o in m["outs"]]
        from collections import Counter
        out["morris_top10"] = [(k, round(float(mu[k]), 2)) for k in topm]; out["morris_overlap_single_top10"] = len(set(topm) & {k for k, *_ in out["top10"]})
        out["morris_dominant_outputs"] = Counter(dom).most_common(3)
    for k in keys: rep["per_key"][k]["c"] = {"ratio": pc[k], "knee_tpr_at_fpr0": knee_t[k], "knee_fpr_at_tpr1": knee_f[k], "rank": ordc.index(k) + 1}
    rep["limit_c"] = out

if os.path.exists(f"{OUT}/self3.npz") and "grid" in rep:             # tolerance (d), ledger D-0004: median over Clef's three wording pairs, per output
    s3 = np.load(f"{OUT}/self3.npz"); ws = [s3["w0"], s3["w1"], s3["w2"]]; pairs = [np.abs(ws[i] - ws[j]) for i, j in ((0, 1), (0, 2), (1, 2))]
    told = np.maximum(np.median(pairs, axis=0), band); rd = lambda d: float(np.max(np.abs(d) / told))
    cm = np.abs(s3["clean"]); r3 = float(np.median([p_ / np.maximum(cm, 1e-9) for p_ in pairs])); tolr = np.maximum(r3 * cm, band); rr = lambda d: float(np.max(np.abs(d) / tolr))
    pd_ = {k: rd(drift[(k, *REF)]) for k in keys}; pr_ = {k: rr(drift[(k, *REF)]) for k in keys}
    from scipy.stats import spearmanr
    occ = [k for k in keys if freq[k] > 0]; ordd = sorted(keys, key=lambda k: -pd_[k])
    cells_d = {k: {f"{t}|{f}": (0.0 if (t, f) == (1.0, 0.0) else rd(drift[(k, t, f)])) for t in TPRS for f in FPRS} for k in keys}
    knee_t = {k: min([t for t in TPRS if cells_d[k][f"{t}|0.0"] <= 1], default=None) for k in keys}; knee_f = {k: max([f for f in FPRS if cells_d[k][f"1.0|{f}"] <= 1], default=None) for k in keys}
    out = {"pair_rel_medians": [float(np.median(p_ / np.maximum(cm, 1e-9))) for p_ in pairs], "r3_pooled": r3, "w2_vs_clean_rel_median": float(np.median(np.abs(s3["w2"] - s3["clean"]) / np.maximum(cm, 1e-9))),
           "tol_quantiles_points": np.percentile(told, [5, 50, 95]).tolist(), "occurring_pass_at_ref": sum(pd_[k] <= 1 for k in occ), "of_occurring": len(occ),
           "knee_tpr_counts": {str(t): sum(knee_t[k] == t for k in occ) for t in TPRS}, "knee_fpr_counts": {str(f): sum(knee_f[k] == f for k in keys) for f in FPRS},
           "top10": [(k, round(pd_[k], 2), freq[k]) for k in ordd[:10]], "spearman_d_vs_pooled": float(spearmanr([pd_[k] for k in keys], [pr_[k] for k in keys])[0])}
    if os.path.exists(f"{OUT}/joint.npz"):
        j = np.load(f"{OUT}/joint.npz"); jc = j["clean"]; jr = {}
        for a_, o in zip(j["args"], j["outs"]): t, f, cl, s_, _, _ = json.loads(a_); jr.setdefault(f"{t}|{f}|{'clustered' if cl else 'indep'}", []).append(np.abs(o - jc))
        out["joint_ratio_d"] = {k: rd(np.mean(v, axis=0)) for k, v in jr.items()}
    if os.path.exists(f"{OUT}/boot.npz"):
        j = np.load(f"{OUT}/boot.npz"); bc = j["boot_clean"]; by_b = {}
        for a_, o in zip(j["args"], j["outs"]):
            b, k = json.loads(a_)
            if k is not None: by_b.setdefault(b, {})[k] = float(np.max(np.abs(o - bc[b]) / told))
        rk = {}
        for b, d in by_b.items():
            for i, k in enumerate(sorted(d, key=lambda k: -d[k])): rk.setdefault(k, []).append(i + 1)
        iv = {k: (float(np.percentile(v, 5)), float(np.percentile(v, 95))) for k, v in rk.items()}
        out["top5_intervals"] = [(k, iv[k]) for k in ordd[:5]]; out["top5_inside_top15"] = all(iv[k][1] <= 15 for k in ordd[:5])
    if os.path.exists(f"{OUT}/morris.npz"):
        import sys; sys.path.insert(0, "/workspace/models/salib-lib"); from SALib.analyze import morris as MA
        m = np.load(f"{OUT}/morris.npz"); names = [str(x) for x in m["names"]]; Yd = np.array([rd(o - m["clean"]) for o in m["outs"]])
        Si = MA.analyze({"num_vars": len(names), "names": names, "bounds": [[0, 3]] * len(names)}, m["X"], Yd, num_levels=4, seed=12); mu = dict(zip(names, Si["mu_star"]))
        topm = sorted(names, key=lambda k: -mu[k])[:10]; out["morris_top10"] = [(k, round(float(mu[k]), 2)) for k in topm]; out["morris_overlap_single_top10"] = len(set(topm) & set(ordd[:10]))
    out["settled"] = out["spearman_d_vs_pooled"] >= 0.8 and out.get("top5_inside_top15", False)
    for k in keys: rep["per_key"][k]["d"] = {"ratio": cells_d[k], "knee_tpr_at_fpr0": knee_t[k], "knee_fpr_at_tpr1": knee_f[k], "rank": ordd.index(k) + 1}
    rep["limit_d"] = out

json.dump(rep, open(f"{OUT}/budget.json", "w"), indent=1)
print(json.dumps({k: v for k, v in rep.items() if k not in ("per_key", "per_key_b", "bootstrap_rank", "grid", "joint", "order_pace", "morris", "bootstrap_rank_b")}, indent=1))
