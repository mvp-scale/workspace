"""Paired comparison of two systems on the same items (gates M2, M8). Stdlib only.

Inputs: REF and one or more candidate files per arm (score_spans.py shape; several files = several seeds/runs).
Per layer and mode: diff = F1(B) - F1(A), pooled over items (each arm's counts summed over its runs).
Paired bootstrap: resample item ids once per draw (random.Random(seed)), recompute both arms on the same draw;
CI = percentile 95% of the diff. Verdict (M2): better if lo > 0, worse if hi < 0, else no-difference.
M8 (only when an arm has >= 2 runs): run noise = max sample sd of per-run F1 over the arms; verdict needs also
|diff| >= 2 x noise, else no-difference; m8_seeds_ok = both arms have >= 3 runs.

CLI:
  python compare.py REF --a base.json [base_s2.json ...] --b new.json [new_s2.json ...]
                    [--ignore IGN] [--n 1000] [--seed 0] [--out cmp.json]
  python compare.py --sha
"""
import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score_spans as S  # noqa: E402


def _arm(files, ref, ignore):
    """-> ids, union of layers, per-run count tables"""
    runs = [S.table(f, ref, ignore) for f in files]
    ids = runs[0][0]
    return ids, set().union(*(r[1] for r in runs)), [r[2] for r in runs]


def _sum(Ts, ids, L, m):
    tp = nc = nr = 0
    for T in Ts:
        if ids and L in T[ids[0]]:
            a, b, c = S.pooled(T, ids, L, m)
            tp, nc, nr = tp + a, nc + b, nr + c
    return tp, nc, nr


def compare(ref, a_files, b_files, ignore=None, n=1000, seed=0):
    ids, la, TA = _arm(a_files, ref, ignore)
    _, lb, TB = _arm(b_files, ref, ignore)
    layers = sorted(la | lb, key=lambda x: (x == S.ALL, x))
    D = S.draws(ids, n, seed)
    multi = len(TA) > 1 or len(TB) > 1
    res = {}
    for L in layers:
        res[L] = {}
        for m in S.MODES:
            fa, fb = S._f1(*_sum(TA, ids, L, m)), S._f1(*_sum(TB, ids, L, m))
            diff = fb - fa
            lo, hi = S.ci([S._f1(*_sum(TB, d, L, m)) - S._f1(*_sum(TA, d, L, m)) for d in D])
            v = "better" if lo is not None and lo > 0 else "worse" if hi is not None and hi < 0 else "no-difference"
            r = {"f1_a": round(fa, 4), "f1_b": round(fb, 4), "diff": round(diff, 4), "lo": lo, "hi": hi, "verdict": v}
            if multi:
                sd = [statistics.stdev(x) for x in ([S._f1(*_sum([T], ids, L, m)) for T in Ts] for Ts in (TA, TB))
                      if len(x) > 1]
                noise = max(sd) if sd else 0.0
                r["run_sd"] = round(noise, 4)
                r["m8_exceeds_noise"] = abs(diff) >= 2 * noise
                if not r["m8_exceeds_noise"]:
                    r["verdict"] = "no-difference"
            res[L][m] = r
    meta = {"tool": "kit/eval/compare.py", "sha": S.sha(__file__), "scorer_sha": S.sha(), "n_items": len(ids),
            "n_boot": n, "seed": seed, "runs_a": len(TA), "runs_b": len(TB), "m8_seeds_ok": len(TA) >= 3 and len(TB) >= 3,
            "diff": "F1(B) - F1(A), paired bootstrap by item, percentile 95%"}
    return {"meta": meta, "layers": res}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ref", nargs="?")
    ap.add_argument("--a", nargs="+")
    ap.add_argument("--b", nargs="+")
    ap.add_argument("--ignore")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--sha", action="store_true")
    x = ap.parse_args()
    if x.sha:
        print(S.sha(__file__))
        return
    if not (x.ref and x.a and x.b):
        ap.error("need REF --a ... --b ...")
    res = compare(x.ref, x.a, x.b, x.ignore, x.n, x.seed)
    txt = json.dumps(res, indent=1)
    if x.out:
        pathlib.Path(x.out).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
