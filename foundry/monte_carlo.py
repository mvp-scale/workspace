#!/usr/bin/env python3
"""A DEMO of a possible future capability -- not a validated forecast. QUALITATIVE risk
prioritization (per PMBOK's own real distinction, checked before building this: qualitative risk
analysis uses ordinal scores for relative prioritization, no units, no forecast; quantitative risk
analysis / "Monte Carlo simulation" in the standard PM sense needs real time/cost units this
project doesn't have -- see tools/monte-carlo.yaml's methodology_note and foundry/PLAN.md for the
full reasoning behind why this is scoped the way it is).

Reads a run's persisted Sorter output (runs/<idea>-sort.jsonl -- sort_and_rank.py must run first)
plus tools/monte-carlo.yaml's demo-baseline priors, samples each requirement's live risk/effort
score as a distribution (not a fixed number), and reports which gap categories/shapes contribute
the most to the VARIANCE of simulated aggregate risk exposure -- a real sensitivity-analysis
technique, applied honestly to ordinal, unitless inputs. Output is a relative ranking of "where
unresolved gaps concentrate the most risk", never a schedule or budget number.

    python3 foundry/layered_walk.py --idea <id> --budget 80
    python3 foundry/sort_and_rank.py --idea <id>
    python3 foundry/monte_carlo.py --idea <id>
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

N_DRAWS_DEFAULT = 5000


def load_sort(idea):
    path = HERE / "runs" / f"{idea}-sort.jsonl"
    if not path.exists():
        sys.exit(f"no sort output at {path} -- run sort_and_rank.py --idea {idea} first "
                  f"(it now persists this automatically)")
    records = [json.loads(l) for l in open(path) if l.strip()]
    pieces = [r for r in records if r["type"] == "sort_piece"]
    if not pieces:
        sys.exit(f"{path} has no scored pieces -- nothing to sample")
    return pieces


def load_baselines():
    world = yaml.safe_load((HERE / "tools" / "world-knowledge.yaml").read_text())
    mc = yaml.safe_load((HERE / "tools" / "monte-carlo.yaml").read_text())
    shape_of = {c["id"]: c.get("shape") for c in world["gap_categories"]}
    baseline_of_shape = {b["shape"]: b for b in mc["shape_baselines"]}
    return shape_of, baseline_of_shape, mc["nominal_project"]


def triangular_draw(mode, half_width):
    """Bounded to [0,1]. half_width=0 (no cross-model spread, or a single-model run) degenerates
    to the point itself -- an honest reflection of "no disagreement signal available", not an
    invented spread."""
    if half_width <= 0:
        return max(0.0, min(1.0, mode))
    lo, hi = max(0.0, mode - half_width), min(1.0, mode + half_width)
    if lo >= hi:
        return mode
    return random.triangular(lo, hi, mode)


def run(idea, n_draws, seed):
    random.seed(seed)
    pieces = load_sort(idea)
    shape_of, baseline_of_shape, nominal_project = load_baselines()

    live_categories = {p["category"] for p in pieces}
    all_categories = set(shape_of.keys())
    missing_categories = all_categories - live_categories  # categories with no live Sorter score
                                                              # this run -- reported, not silently
                                                              # dropped or faked with a live-looking
                                                              # number.

    by_category = defaultdict(list)
    for p in pieces:
        by_category[p["category"]].append(p)

    # Per-draw exposure per category (live pieces only -- see report for which categories had no
    # live data and therefore aren't in the sensitivity ranking, just the baseline table).
    exposures = defaultdict(list)  # category -> [exposure_draw_1, exposure_draw_2, ...]
    for _ in range(n_draws):
        for cat, cat_pieces in by_category.items():
            draw_vals = []
            for p in cat_pieces:
                risk_spread = p.get("disagreement") or 0.0
                risk_draw = triangular_draw(p["risk"], risk_spread)
                # effort has no persisted per-model spread field today (only the mean) -- use a
                # small fixed fraction of the mean as a placeholder width, clearly weaker than the
                # real cross-model spread used for risk. Flagged, not hidden.
                effort_draw = triangular_draw(p["effort"], 0.1)
                draw_vals.append(risk_draw * effort_draw)
            exposures[cat].append(sum(draw_vals) / len(draw_vals) if draw_vals else 0.0)

    total_per_draw = [sum(exposures[cat][i] for cat in exposures) for i in range(n_draws)]
    total_var = _var(total_per_draw)

    # Sensitivity: correlation between each category's per-draw exposure and total exposure,
    # squared -- an approximate share of total variance "explained by" that category moving.
    # Real sensitivity-analysis shape (Sobol-style first-order approximation via correlation),
    # not just re-sorting by mean exposure (which would just repeat the existing risk-tier order).
    sensitivity = {}
    for cat, vals in exposures.items():
        corr = _corr(vals, total_per_draw)
        sensitivity[cat] = corr ** 2 if corr is not None else 0.0

    return {
        "idea": idea, "n_draws": n_draws,
        "categories_with_live_data": sorted(live_categories),
        "categories_missing_live_data": sorted(missing_categories),
        "total_exposure_mean": sum(total_per_draw) / n_draws,
        "total_exposure_var": total_var,
        "sensitivity_by_category": sensitivity,
        "shape_of": shape_of, "baseline_of_shape": baseline_of_shape,
        "mean_exposure_by_category": {c: sum(v) / len(v) for c, v in exposures.items()},
        "nominal_project": nominal_project,
    }


def _var(xs):
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def _corr(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--draws", type=int, default=N_DRAWS_DEFAULT)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    result = run(a.idea, a.draws, a.seed)

    print("=" * 78)
    print("DEMO -- qualitative risk-concentration pass, NOT a schedule or budget forecast")
    print("(see tools/monte-carlo.yaml's methodology_note for what this is and isn't)")
    print("=" * 78)
    print(f"\nIdea: {result['idea']}   Draws: {result['n_draws']}")
    print(f"Categories with live Sorter data this run: {len(result['categories_with_live_data'])}")
    if result["categories_missing_live_data"]:
        print(f"Categories with NO live data (excluded from ranking below, not faked): "
              f"{len(result['categories_missing_live_data'])}")

    print("\nRISK-CONCENTRATION RANKING (share of simulated exposure variance, live categories only)")
    print(f"{'category':<38}{'shape':<16}{'sensitivity':>12}{'mean exposure':>15}")
    ranked = sorted(result["sensitivity_by_category"].items(), key=lambda kv: -kv[1])
    total_sens = sum(v for _, v in ranked) or 1.0
    for cat, sens in ranked:
        shape = result["shape_of"].get(cat, "?")
        mean_exp = result["mean_exposure_by_category"][cat]
        print(f"{cat:<38}{shape:<16}{sens / total_sens:>11.1%} {mean_exp:>14.3f}")

    print("\nSHAPE BASELINE PRIORS (demo, from tools/monte-carlo.yaml -- for comparison only, "
          "never substituted for live data above)")
    print(f"{'shape':<16}{'risk_prior':>12}{'effort_prior':>14}")
    for shape, b in sorted(result["baseline_of_shape"].items()):
        print(f"{shape:<16}{b['risk_prior']:>12.2f}{b['effort_prior']:>14.2f}")

    np_ = result["nominal_project"]
    budget_pm = np_["computed_at_10_kloc"]["effort_person_months"]
    print(f"\nILLUSTRATIVE SCALE -- {np_['model']}")
    print(f"({np_['size_kloc']} KLOC reference point -> {budget_pm} person-months, "
          f"{np_['computed_at_10_kloc']['duration_months']} months, "
          f"{np_['computed_at_10_kloc']['average_staff']} avg staff -- NOT this idea's real size)")
    print(f"{'category':<38}{'share of budget':>17}{'illustrative PM':>18}")
    for cat, sens in ranked:
        share = sens / total_sens
        print(f"{cat:<38}{share:>16.1%} {share * budget_pm:>17.2f}")
    print(f"({np_['disclaimer'].strip().splitlines()[0]}...)")

    print(f"\nTotal simulated exposure: mean={result['total_exposure_mean']:.3f}  "
          f"variance={result['total_exposure_var']:.5f}")
    print("\nReminder: this ranks WHERE unresolved gaps concentrate relative to each other. It is")
    print("not a date, not a dollar figure, and has not been validated against any real outcome.")


if __name__ == "__main__":
    main()
