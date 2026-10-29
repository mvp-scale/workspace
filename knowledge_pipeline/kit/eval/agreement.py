"""Inter-annotator agreement (gates D1, D2): span F1 or Cohen's kappa per layer, bootstrap 95% CI by item. Stdlib only.

spans  : A and B in the score_spans.py shape. F1(A vs B) per layer (symmetric), exact and overlap, CI by item;
         item universe = B's ids (an item missing from A counts as empty).
labels : {"items": [{"id": "x1", "labels": ["POS"]}]} (or "label": "POS"). Items in both files only.
         Per label: binary kappa on presence (multi-label safe). If every item has exactly one label on both sides,
         also "ALL" = multi-class Cohen's kappa. kappa = (po - pe) / (1 - pe); None when pe == 1.
Each layer gets gate = 0.8 x IAA (M1 floor, point estimate) and the D2 verdict on the point estimate:
  go >= 0.6, review 0.4-0.6 (go, review the disagreements), fix < 0.4 (rewrite the guideline). D2 is defined on
  kappa; for span layers the same cut points are applied to F1 (no chance correction exists for open span sets).
D1 = n_items >= 30.

CLI:
  python agreement.py spans A.json B.json [--ignore IGN] [--n 1000] [--seed 0] [--out iaa.json]
  python agreement.py labels A.json B.json [--n 1000] [--seed 0] [--out iaa.json]
  python agreement.py --sha
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score_spans as S  # noqa: E402

GATE_K, GO, REVIEW, D1_MIN = 0.8, 0.6, 0.4, 30


def verdict(x):
    if x is None:
        return "undefined"
    return "go" if x >= GO else "review" if x >= REVIEW else "fix"


# ---------------------------------------------------------------- kappa
def kappa(pairs):
    """pairs [(a, b)] of hashable categories -> Cohen's kappa or None."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else None


def load_labels(x):
    d = S._read(x)
    out = {}
    for it in d.get("items", []):
        v = it.get("labels", [it["label"]] if "label" in it else [])
        out[str(it["id"])] = set(map(str, v))
    return out


def label_agreement(a, b, n=1000, seed=0):
    A, B = load_labels(a), load_labels(b)
    ids = sorted(set(A) & set(B))
    labels = sorted(set().union(*A.values(), *B.values())) if ids else []
    pairs = {L: {i: (L in A[i], L in B[i]) for i in ids} for L in labels}
    if ids and all(len(A[i]) == 1 == len(B[i]) for i in ids):
        pairs["ALL"] = {i: (next(iter(A[i])), next(iter(B[i]))) for i in ids}
    D = S.draws(ids, n, seed)
    res = {}
    for L, P in pairs.items():
        k = kappa([P[i] for i in ids])
        k = None if k is None else round(k, 4)   # verdict on the reported value (0.4 must not read as 0.3999)
        boots = [v for v in (kappa([P[i] for i in d]) for d in D) if v is not None]
        lo, hi = S.ci(boots)
        res[L] = {"kappa": k, "lo": lo, "hi": hi,
                  "agree": round(sum(x == y for x, y in P.values()) / len(ids), 4),
                  "n_a": sum(1 for x, _ in P.values() if x is True) if L != "ALL" else None,
                  "n_b": sum(1 for _, y in P.values() if y is True) if L != "ALL" else None,
                  "gate": None if k is None else round(GATE_K * k, 4), "verdict": verdict(k)}
    return _wrap("labels", ids, n, seed, res, {"only_in_a": len(set(A) - set(B)), "only_in_b": len(set(B) - set(A))})


def span_agreement(a, b, ignore=None, n=1000, seed=0):
    sc = S.score(a, b, ignore, n, seed)
    res = {}
    for L, v in sc["layers"].items():
        res[L] = {m: {"f1": v[m]["f1"], "lo": v[m]["lo"], "hi": v[m]["hi"], "n_a": v[m]["n_cand"], "n_b": v[m]["n_ref"],
                      "gate": round(GATE_K * v[m]["f1"], 4), "verdict": verdict(v[m]["f1"])} for m in S.MODES}
    return _wrap("spans", list(range(sc["meta"]["n_items"])), n, seed, res,
                 {"only_in_a": sc["meta"]["cand_items_not_in_ref"], "only_in_b": sc["meta"]["ref_items_missing_in_cand"]})


def _wrap(kind, ids, n, seed, res, extra):
    return {"meta": {"tool": "kit/eval/agreement.py", "sha": S.sha(__file__), "scorer_sha": S.sha(), "kind": kind,
                     "n_items": len(ids), "n_boot": n, "seed": seed, "gate_rule": f"{GATE_K} x IAA",
                     "d2_rule": f"go >= {GO}, review {REVIEW}-{GO}, fix < {REVIEW} (point estimate)", **extra},
            "D1": {"n_items": len(ids), "min": D1_MIN, "ok": len(ids) >= D1_MIN},
            "layers": res}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kind", nargs="?", choices=["spans", "labels"])
    ap.add_argument("a", nargs="?")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--ignore")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--sha", action="store_true")
    x = ap.parse_args()
    if x.sha:
        print(S.sha(__file__))
        return
    if not (x.kind and x.a and x.b):
        ap.error("need spans|labels A B")
    res = (span_agreement(x.a, x.b, x.ignore, x.n, x.seed) if x.kind == "spans"
           else label_agreement(x.a, x.b, x.n, x.seed))
    txt = json.dumps(res, indent=1)
    if x.out:
        pathlib.Path(x.out).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
