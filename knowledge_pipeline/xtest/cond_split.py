"""EXPLORATORY conditional split declared in ledger L684 before the final B2 result: restrict to items where every rater answered yes on presence in bundle B1 (main run A seed 0), then alpha for which / direction / size among the raters on those items. Unweighted (small set). /workspace/models/embed-zs/.venv/bin/python -I cond_split.py <B1> <B2> rater1 rater2 ..."""
import json, sys, itertools, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
b1, b2, raters = sys.argv[1], sys.argv[2], sys.argv[3:]
def res(b, r, fld):
    out = {}
    for l in open(f"{b}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["field"] == fld and x["ok"]: out[x["item"]] = x["label"]
    return out
pres = {r: res(b1, r, "presence") for r in raters}; common = set.intersection(*[set(p) for p in pres.values()]); S = sorted(i for i in common if all(pres[r][i] == "yes" for r in raters))
print(f"items where all {len(raters)} raters said yes on presence: {len(S)} of {len(common)}")
for fld in ("which", "direction", "size"):
    R = {r: res(b2, r, fld) for r in raters}; ids = [i for i in S if all(i in R[r] for r in raters)]; cls = sorted({R[r][i] for r in raters for i in ids}); cid = {c: n for n, c in enumerate(cls)}
    M = np.array([[cid[R[r][i]] for r in raters] for i in ids]); st = np.array(["a"] * len(ids)); w = np.ones(len(ids))
    pa = alpha_nominal(M, w); lo, hi = boot_alpha(M, w, st, 1000)
    pairs = {f"{p}|{q}": round(alpha_nominal(M[:, [raters.index(p), raters.index(q)]], w), 3) for p, q in itertools.combinations(raters, 2)}
    none = float(np.mean([R[r][i] == "none" for r in raters for i in ids]))
    print(f"  {fld:9s} n {len(ids):3d}  panel alpha {pa:.3f} [{lo:.3f},{hi:.3f}]  share answering none {none:.2f}  pairs {pairs}")
