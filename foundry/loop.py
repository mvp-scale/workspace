#!/usr/bin/env python3
"""The decompositional loop -- real, live, budgeted. Validator, not planner: this script never
authors piece text. It only asks, for a given piece, "is this already atomic?" -- a live judgment
question the loaded models can genuinely answer -- and reports what they say, showing the actual
claim text, not just an id label. It does not generate splits for pieces that aren't atomic,
because that needs something generative (a live Slicer), which doesn't exist yet (no
ANTHROPIC_API_KEY). When the loop hits a piece that isn't atomic, it says so honestly and stops
there, rather than filling the gap with more authored text.

The atomic question is lab_decompose.py's exact question -- real precedent, not invented -- and
matches grinder.yaml's atomic-threshold variant.

Budget: a hard ceiling on total live calls this run is allowed to spend, enforced in code, so the
loop can never run forever even once real splitting exists. Today, with no splitting, the loop
makes exactly one pass -- but the budget mechanism and the halt-and-report-when-blocked behavior
are the real, general shape, not a special case.

Models are shown as P-numbers only, per the same fixed mapping funnel.py uses -- stated once in
the legend, never repeated as a raw model name after that.

    python3 foundry/loop.py --problem 1                  # check one problem's pieces
    python3 foundry/loop.py                                # check every problem
    python3 foundry/loop.py --budget 20                    # cap total live calls
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402
import funnel  # noqa: E402 -- reuses MODEL_META/MODEL_P/MODEL_RANK/ALL_LOCAL_MODELS, not duplicated

ATOMIC_THRESHOLD = 0.6  # same bar lab_decompose.py's simulate_loop() already uses


def atomic_question(piece):
    """lab_decompose.py's exact 'atomic' question -- reused, not reinvented."""
    return {"type": "noul",
            "instructions": piece["text"] + "\n\nQuestion: is this a single, atomic unit of work that should be executed as one piece, not split into smaller pieces?",
            "criteria": {"true": "A single indivisible unit of work.", "false": "Really a group of smaller pieces of work."}}


def run_loop(pieces, models, budget):
    """One real pass: for each piece, ask every model (one live call each, within budget)
    whether it's atomic. Never generates a split -- flags 'needs split, no live splitter' and
    stops on that branch instead. Returns (results, calls_spent). results[pid]['votes'] is
    {model_id: p}, kept internally; only the caller decides how to display it (P-numbers)."""
    calls_spent = 0
    results = {}
    for piece in pieces:
        votes = {}
        for model in models:
            if calls_spent >= budget:
                results[piece["id"]] = {"votes": votes, "status": "budget exhausted mid-piece"}
                return results, calls_spent
            cfg = server.BACKENDS[model]
            if cfg.get("hosted"):
                continue
            r = server.call(model, cfg, {"state": piece["text"], "model": "jev-latest",
                                          "questions": {"atomic": atomic_question(piece)}}, whole=True)
            calls_spent += 1
            if "error" in r:
                continue
            p = (r.get("answers") or {}).get("atomic", {}).get("noul")
            if p is not None:
                votes[model] = p
        if not votes:
            results[piece["id"]] = {"votes": {}, "status": "no answers"}
            continue
        mean_p = sum(votes.values()) / len(votes)
        n_atomic = sum(1 for p in votes.values() if p >= ATOMIC_THRESHOLD)
        status = "atomic" if mean_p >= ATOMIC_THRESHOLD else "needs split, no live splitter -- loop stops here"
        results[piece["id"]] = {"votes": votes, "mean_p": mean_p, "n_atomic": n_atomic, "status": status}
    return results, calls_spent


def print_legend(models):
    print("Models checked, fixed order (same P-number mapping as funnel.py, never a raw model name after this):")
    for m in funnel.MODEL_RANK:
        code, name, pct, hosted = funnel.MODEL_META[m]
        note = "reference only, never called from this script" if hosted \
            else "checked this run" if m in models else "not checked this run"
        print(f"  {funnel.MODEL_P[m]}  {note}")
    print()


def print_piece(pid, by_id, r):
    print(f"  {pid}")
    print(f"    \"{by_id[pid]['text']}\"")
    votes = r.get("votes", {})
    if votes:
        vote_str = "  ".join(f"{funnel.MODEL_P[m]}={p:.2f}" for m, p in votes.items())
        n_atomic = r.get("n_atomic")
        print(f"    {vote_str}   ({n_atomic}/{len(votes)} models call it atomic)" if n_atomic is not None else f"    {vote_str}")
    print(f"    -> {r.get('status')}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", help="a number from funnel.py --list, a problem id, or omit for every problem")
    ap.add_argument("--models", nargs="+", default=funnel.ALL_LOCAL_MODELS, choices=funnel.ALL_LOCAL_MODELS)
    ap.add_argument("--budget", type=int, default=None, help="hard cap on live calls this run may spend (default: one call per piece per model)")
    a = ap.parse_args()
    problems = funnel.load_problems(a.problem)
    all_pieces = [p for prob in problems for p in prob["pieces"]]
    by_id = {p["id"]: p for p in all_pieces}
    budget = a.budget if a.budget is not None else len(all_pieces) * len(a.models)

    print("Decompositional loop -- validator only, never authors content.")
    print(f"Checking {len(all_pieces)} pieces across {len(a.models)} models. Budget: {budget} live calls.\n")
    print_legend(a.models)

    results, spent = run_loop(all_pieces, a.models, budget)

    atomic, needs_split, unresolved = [], [], []
    for pid, r in results.items():
        status = r.get("status", "")
        if status == "atomic":
            atomic.append(pid)
        elif "needs split" in status:
            needs_split.append(pid)
        else:
            unresolved.append(pid)

    print(f"Budget spent: {spent}/{budget} live calls\n")
    print(f"{'=' * 70}\nLEVEL 1 -- genuinely atomic per live model judgment ({len(atomic)}/{len(all_pieces)})\n{'=' * 70}")
    for pid in atomic:
        print_piece(pid, by_id, results[pid])

    print(f"{'=' * 70}\nNEEDS SPLITTING -- loop stops here, no live splitter exists ({len(needs_split)}/{len(all_pieces)})\n{'=' * 70}")
    for pid in needs_split:
        print_piece(pid, by_id, results[pid])

    if unresolved:
        print(f"{'=' * 70}\nUNRESOLVED -- budget exhausted or no answers ({len(unresolved)}/{len(all_pieces)})\n{'=' * 70}")
        for pid in unresolved:
            print_piece(pid, by_id, results[pid])


if __name__ == "__main__":
    main()
