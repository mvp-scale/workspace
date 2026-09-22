#!/usr/bin/env python3
"""Reads a layered_walk.py ledger (runs/<idea>-layered-walk.jsonl) and renders it as tables --
not prose, not a nested tree. Never authors content -- every requirement text and every number
below is read verbatim from the ledger, which itself only ever recorded live model answers. This
script does formatting, not judgment.

    python3 foundry/report.py --idea oncall-rotation
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def by_type(records, t):
    return [r for r in records if r["type"] == t]


def one(records, t):
    matches = by_type(records, t)
    return matches[0] if matches else None


def table(headers, rows, widths=None):
    """Plain fixed-width table -- no markdown pipes needed for terminal reading, but formatted
    consistently enough to paste into markdown if wanted."""
    if not rows:
        print("  (none)")
        return
    widths = widths or [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    def fmt(row):
        return "  ".join(str(c).ljust(w) for c, w in zip(row, widths))
    print(fmt(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))


def wrap(text, width):
    if len(text) <= width:
        return text
    return text[:width - 3] + "..."


def collect_nodes(node_by_path, path, category_label, rows_by_status):
    rec = node_by_path.get(tuple(path))
    if rec is None:
        return
    status = rec["status"]
    if status == "atomic":
        rows_by_status["atomic"].append((rec["full_text"], category_label, f"{rec['atomic_mean']:.2f}"))
    elif status == "uncertain":
        rows_by_status["uncertain"].append((rec["text"], category_label, f"spread {rec.get('atomic_spread', 0):.2f}"))
    elif status == "needs_split_no_library":
        rows_by_status["no_library"].append((rec["text"], category_label, f"{rec['atomic_mean']:.2f}"))
    elif status == "max_depth":
        rows_by_status["max_depth"].append((rec["text"], category_label, ""))
    elif status == "no_answer":
        rows_by_status["no_answer"].append((rec.get("id", ""), category_label, ""))
    elif status == "not_atomic_recursing":
        for child in rec["children"]:
            if child["selected"]:
                collect_nodes(node_by_path, path + [child["id"]], category_label, rows_by_status)
            else:
                p = child["p"]
                rows_by_status["dropped"].append((child["text"], category_label, f"{p:.2f}" if p is not None else "no answer"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--width", type=int, default=90, help="max characters per text cell before truncating")
    a = ap.parse_args()

    path = HERE / "runs" / f"{a.idea}-layered-walk.jsonl"
    if not path.exists():
        raise SystemExit(f"no ledger at {path} -- run layered_walk.py --idea {a.idea} first")
    records = load(path)

    meta = one(records, "run_meta")
    print(f"IDEA: {meta['idea']}")
    print(f"FOR:  {meta['customer']}")
    print(f"MODELS: {', '.join(meta['model_ps'])}")
    print()

    da = one(records, "layer0_domain_audience")
    enrich = one(records, "enrichment")
    if da and da["domain"] and da["audience"]:
        domain, audience = da["domain"], da["audience"]
        print(f"DOMAIN: {domain['choice']} ({domain['confidence']:.0%})   AUDIENCE: {audience['choice']} ({audience['confidence']:.0%})"
              f"   ENRICHMENT: {'applied' if (enrich and enrich['applied']) else 'skipped'}")
        profile = one(records, "profile")
        if profile and profile.get("values"):
            active = sorted(((k, v) for k, v in profile["values"].items() if v is not None and v >= 0.6), key=lambda kv: -kv[1])
            print(f"PROFILE (>=0.6): " + (", ".join(f"{k} ({v:.2f})" for k, v in active) if active else "nothing scored this high"))
        depth = one(records, "depth_estimate")
        if depth and depth.get("mean") is not None:
            print(f"DEPTH ESTIMATE: {depth['mean']:.2f}/4 (spread {depth['spread']:.2f}) -- informational only, not yet load-bearing")
        print()

    gaps = by_type(records, "gap_check")
    gsum = one(records, "gap_summary")
    if gaps:
        print(f"GAP CATEGORIES CHECKED ({gsum['selected_count']}/{gsum['total']} shape-guaranteed, {gsum['method']})")
        has_composite = any(g.get("composite") is not None for g in gaps)
        sort_key = (lambda r: -(r.get("composite") or 0)) if has_composite else (lambda r: -(r["mean"] or 0))
        has_shape = any(g.get("shape") for g in gaps)
        if has_composite and has_shape:
            rows = [(wrap(g["text"], a.width), g.get("shape") or "-", "yes" if g["selected"] else "no",
                     f"{g['mean']:.2f}" if g["mean"] is not None else "-",
                     f"{g.get('profile_boost', 0):.2f}", f"{g['composite']:.2f}")
                    for g in sorted(gaps, key=sort_key)]
            table(["category", "shape", "guaranteed", "own score", "profile boost", "composite"], rows)
            print("  (\"guaranteed\" = shape-guaranteed top pick; a \"no\" may still get walked if the budget reaches it -- see grinder_node/category_recursion below)")
        elif has_composite:
            rows = [(wrap(g["text"], a.width), "yes" if g["selected"] else "no",
                     f"{g['mean']:.2f}" if g["mean"] is not None else "-",
                     f"{g.get('profile_boost', 0):.2f}", f"{g['composite']:.2f}")
                    for g in sorted(gaps, key=sort_key)]
            table(["category", "selected", "own score", "profile boost", "composite"], rows)
        else:
            rows = [(wrap(g["text"], a.width), "yes" if g["selected"] else "no",
                     f"{g['mean']:.2f}" if g["mean"] is not None else "-",
                     f"{g['spread']:.2f}" if g["spread"] is not None else "-")
                    for g in sorted(gaps, key=sort_key)]
            table(["category", "selected", "mean", "spread"], rows)
        print()

    nodes = by_type(records, "grinder_node")
    node_by_path = {tuple(r["path"]): r for r in nodes}
    recursions = by_type(records, "category_recursion")
    has_lib = [r for r in recursions if r["has_library"]]
    no_lib = [r for r in recursions if not r["has_library"]]

    rows_by_status = {k: [] for k in ["atomic", "uncertain", "no_library", "max_depth", "no_answer", "dropped"]}
    for r in has_lib:
        collect_nodes(node_by_path, [r["id"]], r["id"], rows_by_status)

    print(f"REQUIREMENTS FOUND ({len(rows_by_status['atomic'])})")
    table(["requirement", "category", "score"],
          [(wrap(t, a.width), c, s) for t, c, s in rows_by_status["atomic"]])
    print()

    print(f"NEEDS A DECISION -- models disagreed, not forced either way ({len(rows_by_status['uncertain'])})")
    table(["item", "category", "note"],
          [(wrap(t, a.width), c, s) for t, c, s in rows_by_status["uncertain"]])
    print()

    print(f"NOT YET CHECKABLE -- no deeper library to split into ({len(rows_by_status['no_library'])})")
    table(["item", "category", "score"],
          [(wrap(t, a.width), c, s) for t, c, s in rows_by_status["no_library"]])
    print()

    if no_lib:
        print(f"SELECTED, BUT NOTHING BUILT YET ({len(no_lib)})")
        table(["category"], [(r["id"],) for r in no_lib])
        print()

    print(f"SUMMARY: {len(rows_by_status['atomic'])} requirement(s) found. "
          f"{len(rows_by_status['uncertain'])} item(s) need a decision. "
          f"{len(rows_by_status['no_library']) + len(no_lib)} item(s) have no library to go deeper into yet.")


if __name__ == "__main__":
    main()
