#!/usr/bin/env python3
"""Monte Carlo Schedule Risk Analysis (PMI/PMBOK "QSRA") over the one real worked example in this
repo: build_tree_edge.py's Cloudflare Edge Workers plan (24 leaves, real predecessor edges, real
hand-authored durations). Samples each leaf's duration from a triangular distribution
(optimistic/most-likely/pessimistic, all hand-authored in build_tree_edge.py -- see
duration_basis on each leaf) many thousands of times, runs build_tree_edge's own cpm() on every
sampled set, and reports two things a single deterministic CPM pass cannot:

1. A probabilistic completion distribution (percentiles, histogram, P(finish within the 20-day
   horizon)) instead of one number.
2. A criticality index per task -- the share of sampled runs where that task landed on the
   critical path. This is the principled basis for "front-load the tasks that most consistently
   drive the schedule", since a task that is *sometimes* critical under realistic uncertainty is a
   real risk even if it isn't on the single deterministic critical path.

Ground rule, unchanged from build_tree_edge.py: this script only runs against that one real
worked example. It does not fabricate duration or dependency data for any other foundry idea.

Writes probes/decompose/monte_carlo_schedule.json.
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "monte_carlo_schedule.json"
sys.path.insert(0, str(HERE))
import build_tree_edge as bte  # noqa: E402

N_RUNS = 10000
SEED = 20260101  # arbitrary, fixed -- reproducible, not tuned to produce a particular result


def build_by_id():
    return {n["id"]: dict(n) for n in bte.LEAVES}


def sample_durations(by_id, rng):
    """One triangular draw per leaf. random.triangular(low, high, mode) -- mode is the
    hand-authored duration_days, i.e. "most likely", not the mean of the other two."""
    return {
        nid: {**n, "duration_days": rng.triangular(n["duration_optimistic_days"], n["duration_pessimistic_days"], n["duration_days"])}
        for nid, n in by_id.items()
    }


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo), 2)


def histogram(vals, n_bins=24):
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [{"start": lo, "end": lo + 1, "count": len(vals)}]
    width = (hi - lo) / n_bins
    bins = [0] * n_bins
    for v in vals:
        i = min(n_bins - 1, int((v - lo) / width))
        bins[i] += 1
    return [{"start": round(lo + i * width, 2), "end": round(lo + (i + 1) * width, 2), "count": c} for i, c in enumerate(bins)]


def main():
    by_id = build_by_id()
    rng = random.Random(SEED)

    # deterministic (point-estimate) pass, for comparison -- identical method to build_tree_edge.main()
    det_cpm, det_span = bte.cpm(by_id, None)
    det_critical = {nid for nid, r in det_cpm.items() if r["on_critical_path"]}

    spans = []
    critical_counts = {nid: 0 for nid in by_id}
    starts = {nid: [] for nid in by_id}
    finishes = {nid: [] for nid in by_id}
    for _ in range(N_RUNS):
        sampled = sample_durations(by_id, rng)
        cpm_out, span = bte.cpm(sampled, None)
        spans.append(span)
        for nid, r in cpm_out.items():
            if r["on_critical_path"]:
                critical_counts[nid] += 1
            starts[nid].append(r["earliest_start_day"])
            finishes[nid].append(r["earliest_finish_day"])
    for nid in by_id:
        starts[nid].sort()
        finishes[nid].sort()

    spans.sort()
    horizon = bte.HORIZON_DAYS
    prob_within_horizon = round(sum(1 for s in spans if s <= horizon) / N_RUNS, 4)

    groups = [{"id": g["id"], "title": g["title"]} for g in bte.GROUPS]
    tasks = []
    for nid, n in by_id.items():
        ci = round(critical_counts[nid] / N_RUNS, 4)
        det = det_cpm[nid]
        tasks.append({
            "id": nid, "title": n["title"], "group": n["group"], "phase": n["phase"],
            "duration_days": n["duration_days"], "optimistic_days": n["duration_optimistic_days"],
            "pessimistic_days": n["duration_pessimistic_days"], "duration_basis": n["duration_basis"],
            "criticality_index": ci, "deterministic_on_critical_path": nid in det_critical,
            "deterministic_start_day": det["earliest_start_day"], "deterministic_finish_day": det["earliest_finish_day"],
            "start_p10": percentile(starts[nid], 0.10), "start_p50": percentile(starts[nid], 0.50), "start_p90": percentile(starts[nid], 0.90),
            "finish_p10": percentile(finishes[nid], 0.10), "finish_p50": percentile(finishes[nid], 0.50), "finish_p90": percentile(finishes[nid], 0.90),
        })
    tasks.sort(key=lambda t: -t["criticality_index"])

    OUT.write_text(json.dumps({
        "pitch": bte.PITCH, "horizon_working_days": horizon, "n_runs": N_RUNS, "seed": SEED,
        "deterministic": {"span_days": det_span, "critical_path": [nid for nid in sorted(by_id, key=lambda k: det_cpm[k]["earliest_start_day"]) if nid in det_critical]},
        "distribution": {
            "min": round(spans[0], 2), "max": round(spans[-1], 2), "mean": round(sum(spans) / len(spans), 2),
            "p10": percentile(spans, 0.10), "p50": percentile(spans, 0.50), "p80": percentile(spans, 0.80), "p90": percentile(spans, 0.90),
            "prob_within_horizon": prob_within_horizon,
        },
        "histogram": histogram(spans),
        "groups": groups, "tasks": tasks,
    }, indent=1))
    print(f"{N_RUNS} runs -> {OUT}")
    print(f"deterministic span {det_span}d; sampled p10={percentile(spans,0.10)} p50={percentile(spans,0.50)} p80={percentile(spans,0.80)} p90={percentile(spans,0.90)}")
    print(f"P(finish within {horizon}d horizon) = {prob_within_horizon:.1%}")
    print("top-5 by criticality index:", ", ".join(f"{t['id']}={t['criticality_index']:.2f}" for t in tasks[:5]))


if __name__ == "__main__":
    main()
