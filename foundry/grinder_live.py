#!/usr/bin/env python3
"""Live, recursive Grinder. Walks a nested, generic library (front-loaded, reusable -- not
idea-specific), accumulating breadcrumbs at each level, checking a live atomicity question at
every node before deciding whether to recurse into its children. Budget-capped. Prints the
breadcrumb trail live, step by step, as it happens -- the process itself is the output, not just
the final list.

Never authors idea-specific content: selection (does this child apply here) and atomicity (is
this already a single, directly-checkable requirement) are both live, per-node judgments. A
finished requirement's text is always the concatenation of the fixed, generic library text along
the path taken -- never something written by Claude for this specific idea.

    python3 foundry/grinder_live.py --idea oncall-rotation --root single-point-of-failure \\
        --library tools/gap-library-single-point-of-failure.yaml
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
import funnel  # noqa: E402

ATOMIC_THRESHOLD = 0.6
SELECT_THRESHOLD = 0.6


def live_vote(instructions, criteria, state, models, budget, spent):
    """One live noul call per model, budget-checked before each call. Returns (votes, spent)."""
    votes = {}
    for model in models:
        if spent[0] >= budget:
            break
        cfg = server.BACKENDS[model]
        if cfg.get("hosted"):
            continue
        q = {"q": {"type": "noul", "instructions": instructions, "criteria": criteria}}
        r = server.call(model, cfg, {"state": state, "model": "jev-latest", "questions": q}, whole=True)
        spent[0] += 1
        if "error" in r:
            continue
        p = (r.get("answers") or {}).get("q", {}).get("noul")
        if p is not None:
            votes[model] = p
    return votes


def check_atomic(breadcrumb_text, state, models, budget, spent):
    instructions = (breadcrumb_text + "\n\nQuestion: is this a single, directly checkable "
                     "requirement -- something a person could look at the real system and confirm "
                     "yes or no, without first splitting it into separate sub-checks?")
    criteria = {"true": "A single, directly checkable requirement -- one clear yes/no fact.",
                "false": "Still a category or a compound of more than one checkable thing -- needs to split further."}
    return live_vote(instructions, criteria, state, models, budget, spent)


def check_selected(child_text, breadcrumb_state, models, budget, spent):
    instructions = (child_text + "\n\nQuestion: given everything established so far, is this a "
                     "real, relevant sub-gap that needs addressing?")
    criteria = {"true": "Yes, a real, relevant sub-gap here.", "false": "No, not relevant given what's already established."}
    return live_vote(instructions, criteria, breadcrumb_state, models, budget, spent)


def mean(votes):
    return sum(votes.values()) / len(votes) if votes else None


def walk(node, breadcrumb, idea, customer, models, budget, spent, depth, max_depth, results, log):
    indent = "  " * depth
    full_text = " ".join(breadcrumb + [node["text"]])
    state = f"Idea: {idea}\n\nWho this is for: {customer}\n\nEstablished so far: {' '.join(breadcrumb)}" if breadcrumb else f"Idea: {idea}\n\nWho this is for: {customer}"

    log(f"{indent}[Level {depth}] {node['id']}")
    log(f"{indent}  breadcrumb: \"{full_text}\"")

    if spent[0] >= budget:
        log(f"{indent}  -> BUDGET EXHAUSTED before checking. Stopping here, unresolved.")
        results.append({"path": breadcrumb + [node["text"]], "text": full_text, "status": "budget exhausted"})
        return

    votes = check_atomic(full_text, state, models, budget, spent)
    m = mean(votes)
    if m is None:
        log(f"{indent}  -> no answers (errors or budget ran out mid-check). Stopping here.")
        results.append({"path": breadcrumb + [node["text"]], "text": full_text, "status": "no answers"})
        return

    vote_str = "  ".join(f"{funnel.MODEL_P[mo]}={p:.2f}" for mo, p in votes.items())
    log(f"{indent}  atomic check: {vote_str}  (mean={m:.2f})")

    if m >= ATOMIC_THRESHOLD:
        log(f"{indent}  -> ATOMIC. Final requirement:")
        log(f"{indent}     \"{full_text}\"\n")
        results.append({"path": breadcrumb + [node["text"]], "text": full_text, "status": "atomic", "mean_p": m})
        return

    children = node.get("children", [])
    if not children:
        log(f"{indent}  -> NOT atomic (mean={m:.2f}), but no deeper library exists under this node.")
        log(f"{indent}     Honest stop: needs further splitting, none available.\n")
        results.append({"path": breadcrumb + [node["text"]], "text": full_text, "status": "needs split, no deeper library", "mean_p": m})
        return

    if depth >= max_depth:
        log(f"{indent}  -> NOT atomic (mean={m:.2f}), but max depth {max_depth} reached. Stopping.\n")
        results.append({"path": breadcrumb + [node["text"]], "text": full_text, "status": "max depth reached", "mean_p": m})
        return

    log(f"{indent}  -> NOT atomic (mean={m:.2f}). Recursing into {len(children)} sub-categories...")
    for child in children:
        if spent[0] >= budget:
            log(f"{indent}  -> BUDGET EXHAUSTED, remaining children unchecked.")
            break
        cvotes = check_selected(child["text"], state, models, budget, spent)
        cm = mean(cvotes)
        cvote_str = "  ".join(f"{funnel.MODEL_P[mo]}={p:.2f}" for mo, p in cvotes.items()) if cvotes else "no answers"
        selected = cm is not None and cm >= SELECT_THRESHOLD
        log(f"{indent}    check child '{child['id']}': {cvote_str}  (mean={cm:.2f})  {'SELECTED' if selected else 'not selected'}" if cm is not None
            else f"{indent}    check child '{child['id']}': no answers")
        if selected:
            walk(child, breadcrumb + [node["text"]], idea, customer, models, budget, spent, depth + 1, max_depth, results, log)
    log()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True, help="id of an ideas/<id>.json file")
    ap.add_argument("--root", required=True, help="id of the root node in --library's top-level tree")
    ap.add_argument("--library", required=True, help="path to a nested library yaml (e.g. tools/gap-library-single-point-of-failure.yaml)")
    ap.add_argument("--models", nargs="+", default=funnel.ALL_LOCAL_MODELS, choices=funnel.ALL_LOCAL_MODELS)
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--max-depth", type=int, default=3)
    a = ap.parse_args()

    idea_data = json.loads((HERE / "ideas" / f"{a.idea}.json").read_text())
    idea, customer = idea_data["idea"], idea_data["customer"]

    # The root's own text comes from the Level 0 gap-library (already selected there); the
    # nested library file supplies its children -- Level 1 and deeper.
    top = yaml.safe_load((HERE / "tools" / "gap-library.yaml").read_text())
    top_by_id = {c["id"]: c for c in top["categories"]}
    if a.root not in top_by_id:
        sys.exit(f"no Level 0 category '{a.root}' in tools/gap-library.yaml -- available: {list(top_by_id)}")

    lib_path = HERE / a.library if not Path(a.library).is_absolute() else Path(a.library)
    lib = yaml.safe_load(lib_path.read_text())
    root_node = {"id": a.root, "text": top_by_id[a.root]["text"], "children": lib["tree"]}

    print(f"Idea: {idea}")
    print(f"Customer: {customer}")
    print(f"Root: {a.root}  (Level 0 breadcrumb -- the gap this recursion starts from)")
    print(f"Budget: {a.budget} live calls. Max depth: {a.max_depth}.\n")
    print("Models checked, fixed order:")
    for m in funnel.MODEL_RANK:
        code, name, pct, hosted = funnel.MODEL_META[m]
        note = "reference only, never called from this script" if hosted else "checked this run" if m in a.models else "not checked this run"
        print(f"  {funnel.MODEL_P[m]}  {note}")
    print(f"\n{'=' * 70}\nWALKING THE LOOP\n{'=' * 70}")

    results = []
    spent = [0]
    def log(s=""):
        print(s)

    walk(root_node, [], idea, customer, a.models, a.budget, spent, depth=0, max_depth=a.max_depth, results=results, log=log)

    atomic = [r for r in results if r["status"] == "atomic"]
    stuck = [r for r in results if r["status"] != "atomic"]
    print(f"{'=' * 70}\nDONE -- budget spent: {spent[0]}/{a.budget}\n{'=' * 70}")
    print(f"\n{len(atomic)} finished, atomic requirements:")
    for r in atomic:
        print(f"  \"{r['text']}\"")
    if stuck:
        print(f"\n{len(stuck)} branches did not bottom out (reported honestly, not fabricated):")
        for r in stuck:
            print(f"  [{r['status']}] \"{r['text']}\"")


if __name__ == "__main__":
    main()
