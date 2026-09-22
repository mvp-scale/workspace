#!/usr/bin/env python3
"""A live Slicer, without a generative LLM call. Classification over a fixed, generic library
(tools/gap-library.yaml) instead of generation: each of the twelve candidate gaps gets one live
noul question, in the context of a specific idea+customer, across every checked model. Whichever
categories clear the confidence bar are the decomposition -- selected by the tools, not authored
by Claude. This is the actual fix for the "you predefined the pieces" correction: the library is
generic and front-loaded (fine), but which of its entries apply to THIS idea is a live, per-idea
result, not something written by hand.

Input: exactly the two-question intake -- idea and ideal customer/user, from ideas/<id>.json.
Nothing else is authored here. Output: problems/<id>.json, in the same shape every other problem
file uses, but with source tagged as live-selected, and depends_on left empty (dependency
inference isn't built -- an honest gap, not a silent one).

    python3 foundry/slicer_live.py --idea oncall-rotation
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402
import funnel  # noqa: E402 -- reuses MODEL_META/MODEL_P/MODEL_RANK/ALL_LOCAL_MODELS/CONFIDENCE_THRESHOLD

LIBRARY = yaml.safe_load((HERE / "tools" / "gap-library.yaml").read_text())["categories"]


def gap_question(category, idea, customer):
    return {"type": "noul",
            "instructions": f"{category['text']}\n\nQuestion: given the idea and who it's for, is this a real gap that needs to be addressed for the idea to work?",
            "criteria": {"true": "Yes, a real, relevant gap here.", "false": "No, not a real or relevant gap for this specific idea."}}


def select(idea, customer, models):
    """One live call per category per model. Returns {category_id: {model: p}}."""
    state = f"Idea: {idea}\n\nWho this is for: {customer}"
    results = {c["id"]: {} for c in LIBRARY}
    for model in models:
        cfg = server.BACKENDS[model]
        if cfg.get("hosted"):
            continue
        for category in LIBRARY:
            q = {"gap": gap_question(category, idea, customer)}
            r = server.call(model, cfg, {"state": state, "model": "jev-latest", "questions": q}, whole=True)
            if "error" in r:
                continue
            p = (r.get("answers") or {}).get("gap", {}).get("noul")
            if p is not None:
                results[category["id"]][model] = p
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True, help="id of an ideas/<id>.json file (idea + customer, no pieces)")
    ap.add_argument("--models", nargs="+", default=funnel.ALL_LOCAL_MODELS, choices=funnel.ALL_LOCAL_MODELS)
    a = ap.parse_args()

    src = HERE / "ideas" / f"{a.idea}.json"
    if not src.exists():
        sys.exit(f"no ideas/{a.idea}.json")
    raw = json.loads(src.read_text())
    idea, customer = raw["idea"], raw["customer"]

    print(f"Idea: {idea}")
    print(f"Customer: {customer}\n")
    print(f"Checking {len(LIBRARY)} library categories across {len(a.models)} models "
          f"({len(LIBRARY) * len(a.models)} live calls)...\n")
    print("Models checked, fixed order (same P-number mapping as funnel.py):")
    for m in funnel.MODEL_RANK:
        code, name, pct, hosted = funnel.MODEL_META[m]
        note = "reference only, never called from this script" if hosted \
            else "checked this run" if m in a.models else "not checked this run"
        print(f"  {funnel.MODEL_P[m]}  {note}")
    print()

    results = select(idea, customer, a.models)

    selected, rejected = [], []
    for category in LIBRARY:
        ps = list(results[category["id"]].values())
        if not ps:
            continue
        mean_p = sum(ps) / len(ps)
        spread = f"{min(ps):.2f}-{max(ps):.2f}"
        line = f"  {category['id']:<24} mean={mean_p:.2f}  range={spread}  {category['text']}"
        if mean_p >= funnel.CONFIDENCE_THRESHOLD:
            selected.append((category, mean_p))
            print(f"SELECTED{line}")
        else:
            rejected.append((category, mean_p))
            print(f"  not selected{line}")

    print(f"\n{len(selected)}/{len(LIBRARY)} categories selected as this idea's decomposition.")

    pieces = [{"id": c["id"], "text": c["text"], "depends_on": [], "lens": c["lens"]} for c, _ in selected]
    problem = {
        "id": a.idea,
        "idea": idea,
        "source": (f"live-selected via tools/gap-library.yaml: {len(LIBRARY)} generic categories, "
                   f"one noul question each per model, in context of this idea+customer -- "
                   f"selected categories crossed the {funnel.CONFIDENCE_THRESHOLD} confidence bar. "
                   f"No idea-specific piece text authored by Claude. depends_on left empty -- "
                   f"dependency inference isn't built. See foundry/slicer_live.py."),
        "pieces": pieces,
    }
    out = HERE / "problems" / f"{a.idea}.json"
    out.write_text(json.dumps(problem, indent=2))
    print(f"\n-> wrote {out}")


if __name__ == "__main__":
    main()
