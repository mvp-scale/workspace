"""Tests of the sourced checks on our own voters. Stdlib only. Prediction: ledger note before this run.
A: prevalence paradox (Feinstein & Cicchetti 1990): raw agreement vs kappa vs PABAK vs Gwet AC1, plus specific agreement per answer.
C: Dawid-Skene (1979) aggregation vs plain majority, checked against Clef (third system) on contested items."""
import json, glob, collections, itertools
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def load(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for r in J(f): d[r["item_id"]] = r["label"]
    return d
V = {"S1": load(["runs/p7b/*/labels.jsonl"]), "S2": load(["runs/pulse/selfcons/labels.jsonl"]),
     "H1": load(["runs/p7/*/labels.jsonl"]), "H2": load(["runs/pulse/selfcons_haiku/labels.jsonl"])}
ids = [i for i in json.load(open("runs/pulse/selfcons/ids.json")) if all(i in V[k] for k in V)]
FIELD = {"story_type": lambda l: l.get("story_type"), "presence": lambda l: "yes" if l.get("conditions") else "no"}
def pair_stats(pairs):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    cats = sorted({x for p in pairs for x in p}); ma = collections.Counter(a for a, _ in pairs); mb = collections.Counter(b for _, b in pairs)
    pe = sum(ma[c] / n * mb[c] / n for c in cats); kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    q = len(cats); pi = {c: (ma[c] + mb[c]) / (2 * n) for c in cats}
    ac1 = (po - sum(p * (1 - p) for p in pi.values()) / (q - 1)) / (1 - sum(p * (1 - p) for p in pi.values()) / (q - 1)) if q > 1 else float("nan")
    spec = {c: round(2 * sum(a == c and b == c for a, b in pairs) / (ma[c] + mb[c]), 3) for c in cats if ma[c] + mb[c] >= 20}
    return {"n": n, "raw": round(po, 3), "kappa": round(kappa, 3), "pabak": round((q * po - 1) / (q - 1), 3) if q > 1 else float("nan"), "ac1": round(ac1, 3), "specific_by_answer": spec}
out = {"A": {}}
for f, g in FIELD.items():
    pairs = [(g(V["S1"][i]), g(V["H1"][i])) for i in ids] + [(g(V["S2"][i]), g(V["H2"][i])) for i in ids]
    out["A"][f] = pair_stats(pairs)
# C: Dawid-Skene
def ds(vals, cats, iters=30):
    K = len(cats); ci = {c: k for k, c in enumerate(cats)}; N = len(vals); R = len(vals[0])
    T = []
    for v in vals:
        cnt = [0.0] * K
        for x in v: cnt[ci[x]] += 1
        s = sum(cnt); T.append([c / s for c in cnt])
    for _ in range(iters):
        prior = [sum(T[n][k] for n in range(N)) / N for k in range(K)]
        conf = [[[1e-2] * K for _ in range(K)] for _ in range(R)]
        for n in range(N):
            for r in range(R):
                for k in range(K): conf[r][k][ci[vals[n][r]]] += T[n][k]
        for r in range(R):
            for k in range(K):
                s = sum(conf[r][k]); conf[r][k] = [x / s for x in conf[r][k]]
        for n in range(N):
            p = [prior[k] for k in range(K)]
            for k in range(K):
                for r in range(R): p[k] *= conf[r][k][ci[vals[n][r]]]
            s = sum(p); T[n] = [x / s for x in p]
    return [cats[max(range(K), key=lambda k: T[n][k])] for n in range(N)], conf
clef = {r["id"]: r["raw"]["noul"] for r in J("runs/clef_vote.jsonl") if "raw" in r and isinstance(r["raw"], dict) and "noul" in r["raw"]}
out["C"] = {}
for f, g in FIELD.items():
    vals = [[g(V[k][i]) for k in ["S1", "S2", "H1", "H2"]] for i in ids]; cats = sorted({x for v in vals for x in v})
    lab, conf = ds(vals, cats)
    maj = []
    for v in vals:
        c = collections.Counter(v).most_common(); maj.append(c[0][0] if len(c) == 1 or c[0][1] > c[1][1] else None)
    changed = sum(1 for a, b in zip(lab, maj) if b is not None and a != b)
    res = {"items": len(ids), "majority_ties": sum(m is None for m in maj), "ds_differs_from_clear_majority": changed}
    if f == "presence":
        split = [k for k, v in enumerate(vals) if len(set(v)) > 1]
        for name, labs in [("dawid_skene", lab), ("majority_ties_as_yes", [m or "yes" for m in maj])]:
            ok = tot = 0
            for k in split:
                cid = ids[k]
                if cid in clef: tot += 1; ok += (("yes" if clef[cid] > 0.5 else "no") == labs[k])
            res["clef_agree_on_split_" + name] = {"agree": ok, "n": tot, "rate": round(ok / tot, 3) if tot else None}
        res["ds_voter_accuracy_of_yes_given_true_yes"] = {k: round(conf[r][cats.index("yes")][cats.index("yes")], 2) for r, k in enumerate(["S1", "S2", "H1", "H2"])}
    out["C"][f] = res
json.dump(out, open("runs/pulse/sourced_checks_test.json", "w"), indent=1); print(json.dumps(out, indent=1))
