"""xtest scorer and fairness lint (M2/M3, ledger L676). Reference-free: every pairwise Krippendorff alpha (nominal, weighted by the sampling design), a panel alpha, a same-rater control for EVERY rater (order shuffle and paraphrase), bootstrap intervals by stratum. The LINT runs first; if any check fails the output says NOT SCORED and lists the failures: there is no softer verdict.
    /workspace/models/embed-zs/.venv/bin/python -I score.py --bundle runs/xtest/B1 --raters clef jev [...] --fields presence story topic
Verdict (fixed in ledger L677 before any result): CLEAR if the panel interval's lower end >= 0.80; TENTATIVE if it is >= 0.667; REJECT if the upper end < 0.667; otherwise BORDERLINE."""
import argparse, json, os, sys, itertools
import numpy as np
# ---------- statistics ----------
def alpha_nominal(M, w=None):
    """M: (n_items, m) integer class ids, no missing. w: item weights. Krippendorff nominal alpha via the coincidence matrix."""
    M = np.asarray(M); n, m = M.shape; w = np.ones(n) if w is None else np.asarray(w, float); K = int(M.max()) + 1
    o = np.zeros((K, K))
    for u in range(m):
        for v in range(m):
            if u != v: np.add.at(o, (M[:, u], M[:, v]), w / (m - 1))
    nc = o.sum(1); N = nc.sum(); Do = o.sum() - np.trace(o); De = (nc.sum() ** 2 - (nc ** 2).sum()) / (N - 1)
    return float("nan") if De == 0 else 1 - Do / De
def boot_alpha(M, w, strata, k=1000, seed=0):
    rng = np.random.RandomState(seed); M = np.asarray(M); w = np.asarray(w); groups = [np.where(strata == s)[0] for s in np.unique(strata)]; v = []
    for _ in range(k):
        idx = np.concatenate([rng.choice(g, len(g)) for g in groups]); v.append(alpha_nominal(M[idx], w[idx]))
    return [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
def verdict(lo, hi):
    return "CLEAR" if lo >= 0.80 else "TENTATIVE" if lo >= 0.667 else "REJECT" if hi < 0.667 else "BORDERLINE"
# ---------- loading ----------
def load_run(bundle, name):
    d = f"{bundle}/runs/{name}"; card = json.load(open(f"{d}/run_card.json")); res = {}
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l); res[r["task"]] = r
    return card, res
# ---------- lint ----------
def lint(bundle_dir, B, runs, raters, fields):
    f = []; main = {r: runs[(r, "A", 0)] for r in raters if (r, "A", 0) in runs}
    for r in raters:
        for key, what in (((r, "A", 0), "main run"), ((r, "A", 1), "order-shuffle control"), ((r, "P", 0), "paraphrase control")):
            if key not in runs: f.append(f"F4 {r}: missing {what}")
    if f: return f
    ds = {r: main[r][0]["tasks_file_dataset_hash"] for r in raters}
    if len(set(ds.values())) != 1: f.append(f"F1 main runs used different task sets: {ds}")
    if any(v != B["dataset_hash"]["A"] for v in ds.values()): f.append("F1 a main run does not match the bundle dataset hash")
    ins = {r: json.dumps(main[r][0]["instruction_sha256"], sort_keys=True) for r in raters}
    if len(set(ins.values())) != 1: f.append("F1 instruction text differs between raters")
    gl = {main[r][0]["guideline_sha256"] for r in raters}
    if gl != {B["guideline_sha256"]}: f.append("F1 guideline sha differs from the bundle")
    for r in raters:
        c = main[r][0]
        if c["decoding_declared"] in ("unspecified", "", None): f.append(f"F3 {r}: decoding not declared")
        if c["n_tasks"] and (c["n_failed"] + c["n_not_attempted"]) / c["n_tasks"] > 0.05: f.append(f"F7 {r}: more than 5% of tasks failed or were not attempted ({c['n_failed']} failed, {c['n_not_attempted']} not attempted)")
        for key in ((r, "A", 1), (r, "P", 0)):
            cc = runs[key][0]
            if cc["n_ok"] / max(cc["n_tasks"], 1) < 0.95: f.append(f"F4 {r}: control {key[1]}{key[2]} has under 95% answered")
        if main[r][0]["order_seed"] != 0 or runs[(r, "A", 1)][0]["order_seed"] == 0: f.append(f"F4 {r}: order seeds are not distinct (main 0, control 1 expected)")
    sel = B["selection"]
    if not sel["blind"]:
        d = sel.get("design") or {}
        if not d.get("weights") or len(d["weights"]) < B["n_items"]: f.append("F2 selection is not blind and the design has no weights for every item")
    for fld in fields:
        if fld not in B["question_types"]: f.append(f"unknown field {fld}")
    return f
# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bundle", required=True); ap.add_argument("--raters", nargs="+", required=True); ap.add_argument("--fields", nargs="+", default=["presence"]); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--out"); a = ap.parse_args()
    B = json.load(open(f"{a.bundle}/bundle.json")); runs = {}
    for r in a.raters:
        for v, s in (("A", 0), ("A", 1), ("P", 0)):
            nm = f"{r}_{v}_s{s}"
            if os.path.exists(f"{a.bundle}/runs/{nm}/run_card.json"): runs[(r, v, s)] = load_run(a.bundle, nm)
    fails = lint(a.bundle, B, runs, a.raters, a.fields)
    if fails:
        print("NOT SCORED. Fairness lint failed:"); [print("  -", x) for x in fails]; json.dump({"scored": False, "lint_failures": fails}, open(a.out or f"{a.bundle}/score.json", "w"), indent=1); sys.exit(2)
    d = B["selection"].get("design") or {}; items = [json.loads(l)["id"] for l in open(B["items_file"])]; w = np.array([d.get("weights", {}).get(i, 1.0) for i in items]); strata = np.array([d.get("strata", {}).get(i, "all") for i in items])
    out = {"scored": True, "bundle": B["id"], "n_items": len(items), "lint": "passed", "fields": {}}
    for fld in a.fields:
        labs = None
        def col(key):
            card, res = runs[key]; lst = [res.get(f"{fld}:{i}", {}) for i in items]; return lst
        main = {r: col((r, "A", 0)) for r in a.raters}; ok = np.array([all(main[r][k].get("ok") for r in a.raters) for k in range(len(items))])
        classes = sorted({x["label"] for r in a.raters for x in main[r] if x.get("ok")}); cid = {c: i for i, c in enumerate(classes)}
        mat = lambda lst: np.array([cid.get(x.get("label"), -1) for x in lst])
        res = {"n_complete_items": int(ok.sum()), "n_dropped_items": int((~ok).sum()), "classes_seen": len(classes), "self": {}, "pairs": {}, "panel": None}
        for r in a.raters:
            sc = {}
            for nm, key in (("order", (r, "A", 1)), ("paraphrase", (r, "P", 0))):
                x, y = mat(main[r]), mat(col(key)); g = ok & (y >= 0); M = np.stack([x[g], y[g]], 1)
                sc[nm] = {"alpha": round(alpha_nominal(M, w[g]), 3), "ci95": [round(v, 3) for v in boot_alpha(M, w[g], strata[g], a.boot)], "n": int(g.sum()), "raw_agree": round(float(np.average(x[g] == y[g], weights=w[g])), 3)}
            res["self"][r] = sc
        mats = {r: mat(main[r]) for r in a.raters}
        for p, q in itertools.combinations(a.raters, 2):
            M = np.stack([mats[p][ok], mats[q][ok]], 1); res["pairs"][f"{p}|{q}"] = {"alpha": round(alpha_nominal(M, w[ok]), 3), "ci95": [round(v, 3) for v in boot_alpha(M, w[ok], strata[ok], a.boot)], "raw_agree": round(float(np.average(M[:, 0] == M[:, 1], weights=w[ok])), 3)}
        if len(a.raters) >= 3:
            M = np.stack([mats[r][ok] for r in a.raters], 1); pa = alpha_nominal(M, w[ok]); lo, hi = boot_alpha(M, w[ok], strata[ok], a.boot)
            res["panel"] = {"raters": a.raters, "alpha": round(pa, 3), "ci95": [round(lo, 3), round(hi, 3)], "verdict": verdict(lo, hi)}
        out["fields"][fld] = res
    json.dump(out, open(a.out or f"{a.bundle}/score.json", "w"), indent=1)
    for fld, res in out["fields"].items():
        print(f"== {fld}: complete items {res['n_complete_items']} (dropped {res['n_dropped_items']})")
        for r, sc in res["self"].items(): print(f"   same-rater {r:8s} order {sc['order']['alpha']:.3f} {sc['order']['ci95']} | paraphrase {sc['paraphrase']['alpha']:.3f} {sc['paraphrase']['ci95']}")
        for k, v in res["pairs"].items(): print(f"   pair {k:14s} alpha {v['alpha']:.3f} {v['ci95']}  raw agree {v['raw_agree']}")
        if res["panel"]: print(f"   PANEL alpha {res['panel']['alpha']} {res['panel']['ci95']} -> {res['panel']['verdict']}")
if __name__ == "__main__": main()
