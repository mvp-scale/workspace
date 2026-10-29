"""Two-teacher span consensus (stages S3/S2: silver labels, disagreement review; feeds D1/D2 and the M1 ruler). Stdlib only.

Input: teacher A and B files in the score_spans.py shape. Per item and label:
  exact   : agreed = identical (start, end, label)
  overlap : agreed = same label, greedy 1:1 by Jaccard (score_spans.overlap_pairs); the agreed span is
            --span intersect (default) | union | a | b
Everything unmatched is a disagreement: kind a_only / b_only, or label_conflict when it overlaps an unmatched span of
the other teacher with a different label. Each disagreement region that does not overlap an agreed span goes into the
item's "ignore" list, so the output is directly a reference with ignore regions for score_spans.py (split = unknown,
as consensus_v1 did); a disagreement touching an agreed span stays scored, so agreed spans are never hidden.
Stats = agreement per layer (score_spans.score of A vs B, with bootstrap CI).

CLI:
  python consensus.py A.json B.json [--mode overlap|exact] [--span intersect|union|a|b] [--out merged.json]
                      [--disagreements dis.json] [--n 1000] [--seed 0]
  python consensus.py --sha
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score_spans as S  # noqa: E402


def _join(a, b, how):
    if how == "a":
        return a
    if how == "b":
        return b
    if how == "union":
        return (min(a[0], b[0]), max(a[1], b[1]), a[2])
    return (max(a[0], b[0]), min(a[1], b[1]), a[2])


def merge_item(A, B, mode="overlap", how="intersect"):
    """-> (agreed spans, disagreements [(teacher, span, kind)])"""
    if mode == "exact":
        left = list(B)
        agreed, ua = [], []
        for x in A:
            if x in left:
                left.remove(x)
                agreed.append(x)
            else:
                ua.append(x)
        ub = left
    else:
        m = S.overlap_pairs(A, B)
        agreed = [_join(A[i], B[j], how) for i, j in m]
        mi, mj = {i for i, _ in m}, {j for _, j in m}
        ua = [x for i, x in enumerate(A) if i not in mi]
        ub = [x for j, x in enumerate(B) if j not in mj]
    dis = []
    for t, own, other in (("a", ua, ub), ("b", ub, ua)):
        for x in own:
            conflict = any(S.ov(x, y) and x[2] != y[2] for y in other)
            dis.append((t, x, "label_conflict" if conflict else f"{t}_only"))
    return sorted(set(agreed)), dis


def consensus(a, b, mode="overlap", how="intersect", n=1000, seed=0):
    A, B = S.load(a), S.load(b)
    ids = sorted(set(A) | set(B))
    items, dis = [], []
    for i in ids:
        sa, sb = A.get(i, {"spans": []})["spans"], B.get(i, {"spans": []})["spans"]
        agreed, d = merge_item(sa, sb, mode, how)
        reg = {(x[0], x[1]) for _, x, _ in d if not any(S.ov(x, g) for g in agreed)}   # never hide an agreed span
        ign = sorted(reg | set(A.get(i, {}).get("ignore", [])) | set(B.get(i, {}).get("ignore", [])))
        items.append({"id": i, "spans": [{"start": s, "end": e, "label": l} for s, e, l in agreed],
                      "ignore": [{"start": s, "end": e} for s, e in ign]})
        dis += [{"id": i, "teacher": t, "start": x[0], "end": x[1], "label": x[2], "kind": k} for t, x, k in d]
    sc = S.score(a, b, None, n, seed)
    kinds = {}
    for x in dis:
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    stats = {"n_items": len(ids), "agreed_spans": sum(len(it["spans"]) for it in items), "disagreements": len(dis),
             "by_kind": kinds, "mode": mode, "span": how if mode == "overlap" else "exact",
             "agreement": {L: {m: {k: v[m][k] for k in ("f1", "lo", "hi", "n_cand", "n_ref")} for m in S.MODES}
                           for L, v in sc["layers"].items()}}
    meta = {"tool": "kit/eval/consensus.py", "sha": S.sha(__file__), "scorer_sha": S.sha(), "n_boot": n, "seed": seed}
    return {"meta": meta, "items": items}, dis, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("a", nargs="?")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--mode", choices=["overlap", "exact"], default="overlap")
    ap.add_argument("--span", choices=["intersect", "union", "a", "b"], default="intersect")
    ap.add_argument("--out")
    ap.add_argument("--disagreements")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sha", action="store_true")
    x = ap.parse_args()
    if x.sha:
        print(S.sha(__file__))
        return
    if not (x.a and x.b):
        ap.error("need A B")
    merged, dis, stats = consensus(x.a, x.b, x.mode, x.span, x.n, x.seed)
    if x.out:
        pathlib.Path(x.out).write_text(json.dumps(merged, indent=1), encoding="utf-8")
    if x.disagreements:
        pathlib.Path(x.disagreements).write_text(json.dumps({"disagreements": dis}, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
