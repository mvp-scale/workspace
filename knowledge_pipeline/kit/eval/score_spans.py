"""Span scorer for the CPU model factory kit (gates M1, R6; core for agreement/consensus/compare). Stdlib only.

Input (cand and ref): {"items": [{"id": "x1", "spans": [{"start": 0, "end": 4, "label": "PER"}],
                                  "ignore": [{"start": 10, "end": 20}]}]}      # "ignore" optional, ref side
Layers: one per label, plus ALL (every span, label must still match). Per layer and mode:
  exact   = identical (start, end, label), multiset count
  overlap = same label and any char overlap, greedy 1:1 by Jaccard descending (same algorithm as pipeline/eval/score.py)
Ignore regions (ref "ignore" + --ignore file, same item shape with "spans" or "ignore"): every cand or ref span that
overlaps one is dropped before matching. Universe = ref item ids; a ref item missing from cand counts as empty.
P/R/F1 are pooled (micro) over items. CI = percentile 95% bootstrap over items (resample item ids with replacement,
random.Random(seed), n draws; the same draws serve every layer and mode, so layers are paired).

CLI:
  python score_spans.py CAND REF [--ignore IGN] [--n 1000] [--seed 0] [--out score.json] [--expect prior.json]
  python score_spans.py --sha            # sha256[:8] of this file, to freeze the scorer
--expect re-checks R6: exits 1 unless every layer number equals the prior score file exactly.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import random
import sys

ALL = "ALL"
MODES = ("exact", "overlap")


def sha(path=__file__):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:8]


# ---------------------------------------------------------------- io
def _read(x):
    if isinstance(x, (str, pathlib.Path)):
        return json.loads(pathlib.Path(x).read_text(encoding="utf-8"))
    return x


def load(x):
    """path or parsed doc -> {id: {"spans": [(s, e, label)], "ignore": [(s, e)]}}"""
    out = {}
    for it in _read(x).get("items", []):
        out[str(it["id"])] = {"spans": [(int(s["start"]), int(s["end"]), str(s.get("label", ""))) for s in it.get("spans", [])],
                              "ignore": [(int(g["start"]), int(g["end"])) for g in it.get("ignore", [])]}
    return out


def load_ignore(x):
    """ignore file -> {id: [(s, e)]}; regions from "ignore" and "spans" both count."""
    if x is None:
        return {}
    d = load(x)
    return {i: v["ignore"] + [(s, e) for s, e, _ in v["spans"]] for i, v in d.items()}


# ---------------------------------------------------------------- matching
def ov(a, b):
    return min(a[1], b[1]) > max(a[0], b[0])


def jac(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union else 0.0


def strip(spans, ign):
    return [s for s in spans if not any(ov(s, g) for g in ign)] if ign else list(spans)


def exact_tp(A, B):
    cb, tp = collections.Counter(B), 0
    for x in A:
        if cb[x] > 0:
            cb[x] -= 1
            tp += 1
    return tp


def overlap_pairs(A, B):
    """greedy 1:1, same label, Jaccard > 0, best first (ties as score.py: sorted reverse on (sim, i, j))."""
    pairs = sorted(((jac(a, b), i, j) for i, a in enumerate(A) for j, b in enumerate(B)
                    if a[2] == b[2] and jac(a, b) > 0), reverse=True)
    ua, ub, m = set(), set(), []
    for _, i, j in pairs:
        if i not in ua and j not in ub:
            ua.add(i)
            ub.add(j)
            m.append((i, j))
    return m


def prf(tp, nc, nr):
    p = tp / nc if nc else 0.0
    r = tp / nr if nr else 0.0
    return {"p": round(p, 4), "r": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            "tp": tp, "n_cand": nc, "n_ref": nr}


def _f1(tp, nc, nr):
    return 2 * tp / (nc + nr) if nc + nr else 0.0   # == 2PR/(P+R) when tp > 0, 0 otherwise


# ---------------------------------------------------------------- per-item count table
def item_counts(cs, rs, layers):
    """one item -> {layer: {mode: (tp, nc, nr)}}"""
    out = {}
    for L in layers:
        A = cs if L == ALL else [s for s in cs if s[2] == L]
        B = rs if L == ALL else [s for s in rs if s[2] == L]
        out[L] = {"exact": (exact_tp(A, B), len(A), len(B)), "overlap": (len(overlap_pairs(A, B)), len(A), len(B))}
    return out


def table(cand, ref, ignore=None):
    """-> (ids, layers, T) with T[id][layer][mode] = (tp, nc, nr), after ignore regions are stripped."""
    C, R, G = load(cand), load(ref), load_ignore(ignore)
    ids = sorted(R)
    rows = {}
    for i in ids:
        ign = R[i]["ignore"] + G.get(i, [])
        rows[i] = (strip(C.get(i, {"spans": []})["spans"], ign), strip(R[i]["spans"], ign))
    labels = sorted({s[2] for cs, rs in rows.values() for s in cs + rs})
    layers = labels + [ALL]
    T = {i: item_counts(cs, rs, layers) for i, (cs, rs) in rows.items()}
    return ids, layers, T, {"cand_items_not_in_ref": len(set(C) - set(R)), "ref_items_missing_in_cand": len(set(R) - set(C))}


def pooled(T, ids, L, mode):
    tp = nc = nr = 0
    for i in ids:
        a, b, c = T[i][L][mode]
        tp += a
        nc += b
        nr += c
    return tp, nc, nr


# ---------------------------------------------------------------- bootstrap
def draws(ids, n=1000, seed=0):
    rng = random.Random(seed)
    k = len(ids)
    return [[ids[rng.randrange(k)] for _ in range(k)] for _ in range(n)] if k else []


def pct(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


def ci(vals):
    lo, hi = pct(vals, .025), pct(vals, .975)
    return (round(lo, 4) if lo is not None else None), (round(hi, 4) if hi is not None else None)


def score(cand, ref, ignore=None, n=1000, seed=0):
    ids, layers, T, warn = table(cand, ref, ignore)
    D = draws(ids, n, seed)
    res = {}
    for L in layers:
        res[L] = {}
        for m in MODES:
            r = prf(*pooled(T, ids, L, m))
            r["lo"], r["hi"] = ci([_f1(*pooled(T, d, L, m)) for d in D])
            res[L][m] = r
    meta = {"tool": "kit/eval/score_spans.py", "scorer_sha": sha(), "n_items": len(ids), "n_boot": n, "seed": seed,
            "ci": "percentile 95%, bootstrap by item, same draws for every layer", **warn}
    return {"meta": meta, "layers": res}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cand", nargs="?")
    ap.add_argument("ref", nargs="?")
    ap.add_argument("--ignore")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--expect")
    ap.add_argument("--sha", action="store_true")
    a = ap.parse_args()
    if a.sha:
        print(sha())
        return
    if not (a.cand and a.ref):
        ap.error("need CAND REF")
    res = score(a.cand, a.ref, a.ignore, a.n, a.seed)
    txt = json.dumps(res, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(txt, encoding="utf-8")
    print(txt)
    if a.expect:
        prior = _read(a.expect)
        ok = prior.get("layers") == res["layers"]
        print(json.dumps({"R6_reproduced": ok}), file=sys.stderr)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
