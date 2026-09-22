#!/usr/bin/env python3
"""It's one loop: classify with the model, get results, expand with world-knowledge metadata,
move to the next level of classification for whatever was selected, and stop for a branch when
there's nothing further to classify into or the run's overall budget is exhausted.

Level 0's domain/audience call is the one exception in kind -- a single `choice` pick, used once
to set context, not a repeated select-many step. Everything from there down -- the 12 gap
categories, and every Grinder node beneath whichever ones get selected -- is the SAME recursive
select-many step over one merged tree with a virtual root (`build_tree`), walked by one function
(`walk`). That used to be three separate functions (layer0_gaps, a for-loop in main, walk_gap)
doing the same shape of thing three different ways; this version doesn't.

Budget is now a real, enforced cap on total live calls for the whole run (`BUDGET` below), not
just a per-branch depth limit -- "until you exceed the budget" made literal, not implied.

Writes a structured JSONL ledger to runs/<idea>-layered-walk.jsonl as it goes. report.py and
sort_and_rank.py both read that ledger; their schema expectations are unchanged by this rewrite.

Multi-model (P1/P2/P3 -- semif/kev-4b/so1), grounded in probes/report_v2.py's already-validated
measurement, not an in-session guess -- see MODELS below.

Never authors idea-specific content. Every candidate (domains, audiences, gap categories, atomic
checks) comes from tools/slicer.yaml's and tools/world-knowledge.yaml's fixed, generic content,
loaded and executed as written. Only which ones apply to THIS idea, and how far each recurses, is
live.

    python3 foundry/layered_walk.py --idea oncall-rotation
    python3 foundry/report.py --idea oncall-rotation          # then render it
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

# Grounded in probes/report_v2.py's already-validated measurement (1,437 real labeled items, 15
# published sets): semif 66.8% / kev-4b 66.9% / so1 64.8% accuracy, all three with a real
# calibration gap (0.10-0.13); laya drops to 56.9% with confident answers becoming rare at higher
# thresholds; verdict is 46.7% with a calibration gap of just 0.04 -- confidence carries almost no
# signal. Not an in-session guess.
MODELS = ["semif", "kev-4b", "so1"]  # P1, P2, P3

DOMAIN_AUDIENCE_FLOOR = 0.6   # slicer.yaml's own written by-domain routing rule: both must clear
                              # this or the classification isn't trusted -- no composite average.
GAP_TOPK = 4                  # Level 0's selection policy differs from every deeper level on
                              # purpose: top-k by mean, not a floor. A floor near 1.0 for nearly
                              # every category selected everything in an early run -- not a
                              # decision, a rubber stamp.
CHILD_RELEVANCE = 0.6         # cheap, recoverable -- a wrongly-followed recursion just costs a
                              # few more calls.
ATOMIC_THRESHOLD = 0.18       # terminal -- ends a branch and ships a requirement. Calibrated
                              # against a controlled diagnostic on the corrected P1/P2/P3 set:
                              # these models discriminate correctly in direction (atomic-mean 0.28
                              # vs compound-mean 0.085) but the whole scale is compressed and
                              # shifted low. Model-combination-specific; re-calibrate if MODELS
                              # changes.
DISAGREEMENT_THRESHOLD = funnel.DISAGREEMENT_THRESHOLD  # reused, not reinvented
BUDGET = 60                   # hard cap on live calls (one call = one classify, regardless of how
                              # many questions are fanned into it) for the whole run, root through
                              # every leaf. Real, enforced -- "until you exceed the budget," not
                              # just a per-branch depth limit.


class Budget:
    def __init__(self, limit):
        self.limit = limit
        self.spent = 0

    def exhausted(self):
        return self.spent >= self.limit

    def spend(self):
        self.spent += 1


def call_all(state, questions, budget):
    """Fire the same fanned-out call at every model in MODELS -- ONE call against the budget,
    regardless of model count or question count. Returns {model: answers}; a model that errors is
    silently excluded (server.call already reports the error)."""
    budget.spend()
    out = {}
    for model in MODELS:
        cfg = server.BACKENDS[model]
        r = server.call(model, cfg, {"state": state, "model": "jev-latest", "questions": questions}, whole=True)
        if "error" not in r:
            out[model] = r["answers"]
    return out


def combine_noul(per_model, key):
    ps = [a[key]["noul"] for a in per_model.values() if (a.get(key) or {}).get("noul") is not None]
    if not ps:
        return None, None
    return sum(ps) / len(ps), (max(ps) - min(ps) if len(ps) > 1 else 0.0)


def combine_choice(per_model, key):
    option_sums, n = {}, 0
    for a in per_model.values():
        ans = a.get(key)
        if not ans:
            continue
        n += 1
        for opt, p in ans["probabilities"].items():
            option_sums[opt] = option_sums.get(opt, 0) + p
    if not n:
        return None
    probs = {opt: total / n for opt, total in option_sums.items()}
    top = max(probs, key=probs.get)
    return {"choice": top, "confidence": probs[top], "probabilities": probs, "n_models": n}


class Ledger:
    def __init__(self, path):
        self.fp = open(path, "w")

    def emit(self, **record):
        self.fp.write(json.dumps(record) + "\n")
        self.fp.flush()

    def close(self):
        self.fp.close()


def noul_question(text, true_label, false_label):
    return {"type": "noul", "instructions": text, "criteria": {"true": true_label, "false": false_label}}


def classify_domain_audience(base_state, slicer, budget):
    """The one exception in kind: a single `choice` pick, used once, not a select-many step."""
    if budget.exhausted():
        return None, None
    by_domain = [v for v in slicer["variants"] if v["id"] == "by-domain"][0]
    per_model = call_all(base_state, by_domain["calls"][0]["questions"], budget)
    if not per_model:
        return None, None
    return combine_choice(per_model, "domain"), combine_choice(per_model, "audience")


def build_tree(world):
    """One tree, virtual root -> the 12 gap_categories -> whatever gap_category_detail supplies
    for each (empty for the 8 that have nothing built yet). Same shape at every level from here
    down -- the root's children ARE gap_categories, exactly like any deeper node's children come
    from its own library entry."""
    children = []
    for cat in world["gap_categories"]:
        detail = world.get("gap_category_detail", {}).get(cat["id"])
        children.append({"id": cat["id"], "text": cat["text"], "children": (detail or {}).get("tree", [])})
    return children


def classify_node(state, node_text, children, budget):
    """ONE call: the atomic question (leaf only -- ancestor context lives in `state`) plus one
    relevance question per candidate child, fanned into the same dict."""
    if budget.exhausted():
        return None, None, {}
    questions = {}
    if not children:
        questions["atomic"] = noul_question(
            node_text + "\n\nQuestion: is this a single, directly checkable requirement -- something a person could look at the real system and confirm yes or no, without first splitting it into separate sub-checks?",
            "A single, directly checkable requirement -- one clear yes/no fact.",
            "Still a category or a compound of more than one checkable thing -- needs to split further.")
    for child in children:
        questions[f"child::{child['id']}"] = noul_question(
            node_text + " " + child["text"] + "\n\nQuestion: given everything established so far, is this a real, relevant sub-gap that needs addressing?",
            "Yes, a real, relevant sub-gap here.", "No, not relevant given what's already established.")
    per_model = call_all(state, questions, budget)
    if not per_model:
        return None, None, {}
    atomic_mean, atomic_spread = (combine_noul(per_model, "atomic") if not children else (None, None))
    child_means = {c["id"]: combine_noul(per_model, f"child::{c['id']}")[0] for c in children}
    return atomic_mean, atomic_spread, child_means


def walk(node, path, breadcrumb, base_state, budget, ledger, progress, depth, max_depth):
    """The one loop, recursive: classify -> (breadcrumb carries the expansion forward) -> recurse
    into whatever was selected -> stop when there's nothing left to select or the budget's gone."""
    if budget.exhausted():
        ledger.emit(type="grinder_node", path=path, id=node["id"], depth=depth, text=node["text"],
                     full_text=" ".join(breadcrumb + [node["text"]]), atomic_mean=None,
                     status="budget_exhausted", children=[])
        progress(f"  {'  ' * depth}[{node['id']}] -- BUDGET EXHAUSTED")
        return

    is_leaf = not node["children"]
    full_text = " ".join(breadcrumb + [node["text"]])
    state = base_state + (f"\n\nEstablished so far: {'; '.join(breadcrumb)}" if breadcrumb else "")
    atomic_mean, atomic_spread, child_means = classify_node(state, node["text"], node["children"], budget)
    progress(f"  {'  ' * depth}[{node['id']}]")

    # The call failed entirely (not "leaf with no children" or "internal node, some answers null")
    # -- distinguishable because classify_node only ever returns an empty child_means dict on
    # total failure; a real internal-node success always has one entry per child.
    call_failed = (is_leaf and atomic_mean is None) or (not is_leaf and not child_means)
    if call_failed:
        ledger.emit(type="grinder_node", path=path, id=node["id"], depth=depth, text=node["text"],
                     full_text=full_text, atomic_mean=None, status="no_answer", children=[])
        return

    child_records = []
    for child in node["children"]:
        p = child_means.get(child["id"])
        selected = p is not None and p >= CHILD_RELEVANCE
        child_records.append({"id": child["id"], "text": child["text"], "p": p, "selected": selected})

    if is_leaf:
        if atomic_spread is not None and atomic_spread >= DISAGREEMENT_THRESHOLD:
            status = "uncertain"
        elif atomic_mean is not None and atomic_mean >= ATOMIC_THRESHOLD:
            status = "atomic"
        else:
            status = "needs_split_no_library"
    else:
        # A node with children was authored as a category, by construction -- no live score
        # overrides that; only a true leaf can ever terminate as atomic.
        status = "max_depth" if depth >= max_depth else "not_atomic_recursing"

    ledger.emit(type="grinder_node", path=path, id=node["id"], depth=depth, text=node["text"],
                full_text=full_text, atomic_mean=atomic_mean, atomic_spread=atomic_spread,
                status=status, children=child_records)

    if status == "not_atomic_recursing":
        for child in node["children"]:
            rec = next(c for c in child_records if c["id"] == child["id"])
            if rec["selected"]:
                walk(child, path + [child["id"]], breadcrumb + [node["text"]], base_state,
                     budget, ledger, progress, depth + 1, max_depth)


def classify_root(tree, state, budget, world, ledger, progress):
    """Level 0's select-many step over the 12 gap categories -- same mechanism as any deeper
    node's child-relevance check, except the selection policy is top-k, not a threshold (see
    GAP_TOPK)."""
    if budget.exhausted():
        return []
    questions = {n["id"]: noul_question(
        n["text"] + "\n\nQuestion: is this NOT yet true for this idea as currently described -- i.e., is this a real, unaddressed gap?",
        "No, not yet true -- a real, unaddressed gap here.", "Yes, this is already true, or not a relevant concern here.")
        for n in tree}
    per_model = call_all(state, questions, budget)
    if not per_model:
        return []
    results = {n["id"]: combine_noul(per_model, n["id"]) for n in tree}
    ranked = sorted(tree, key=lambda n: -(results[n["id"]][0] or 0))
    selected = ranked[:GAP_TOPK]
    selected_ids = {n["id"] for n in selected}
    for n in tree:
        mean, spread = results[n["id"]]
        ledger.emit(type="gap_check", id=n["id"], text=n["text"], mean=mean, spread=spread, selected=n["id"] in selected_ids)
    ledger.emit(type="gap_summary", selected_count=len(selected), total=len(tree), method=f"top-{GAP_TOPK}")
    for n in selected:
        ledger.emit(type="category_recursion", id=n["id"], has_library=bool(n["children"]))
    return selected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args()

    idea_data = json.loads((HERE / "ideas" / f"{a.idea}.json").read_text())
    idea, customer = idea_data["idea"], idea_data["customer"]
    base_state = f"Idea: {idea}\n\nWho this is for: {customer}"

    slicer = yaml.safe_load((HERE / "tools" / "slicer.yaml").read_text())
    world = yaml.safe_load((HERE / "tools" / "world-knowledge.yaml").read_text())

    runs_dir = HERE / "runs"
    runs_dir.mkdir(exist_ok=True)
    ledger = Ledger(runs_dir / f"{a.idea}-layered-walk.jsonl")
    budget = Budget(a.budget)

    def progress(s):
        print(s)

    progress(f"Idea: {idea}")
    progress(f"Models: {', '.join(funnel.MODEL_P[m] for m in MODELS)}   Budget: {a.budget} live calls\n")
    ledger.emit(type="run_meta", idea=idea, customer=customer, models=MODELS,
                model_ps=[funnel.MODEL_P[m] for m in MODELS])

    # 1. Classify (domain/audience) -- the one non-recursive step.
    domain_a, audience_a = classify_domain_audience(base_state, slicer, budget)
    ledger.emit(type="layer0_domain_audience", domain=domain_a, audience=audience_a)
    trusted = (domain_a and audience_a and domain_a["confidence"] >= DOMAIN_AUDIENCE_FLOOR
               and audience_a["confidence"] >= DOMAIN_AUDIENCE_FLOOR)
    progress(f"domain/audience: {'trusted' if trusted else 'not trusted'} "
             f"({domain_a['choice'] if domain_a else '?'}, {audience_a['choice'] if audience_a else '?'})")

    # 2. Expand with world-knowledge metadata (no call -- a lookup).
    enrich = world["domain_enrichment"].get(domain_a["choice"]) if (domain_a and trusted) else None
    if enrich:
        pp = {p["id"]: p["text"] for p in world["pain_points"]}
        dl = {d["id"]: d["text"] for d in world["delights"]}
        cj = {c["id"]: c["text"] for c in world["customer_journey"]}
        enriched_state = (base_state +
            f"\n\nThis is a {domain_a['choice']} idea, for {audience_a['choice']}."
            f" Known from similar {domain_a['choice']} ideas: pain points often include "
            f"{'; '.join(pp[i] for i in enrich['likely_pain_points'])}. Delights often include "
            f"{'; '.join(dl[i] for i in enrich['likely_delights'])}."
            f" The riskiest stage is usually: {cj[enrich['riskiest_journey_stage']]}")
        ledger.emit(type="enrichment", domain=domain_a["choice"], applied=True,
                    likely_pain_points=enrich["likely_pain_points"], likely_delights=enrich["likely_delights"],
                    riskiest_journey_stage=enrich["riskiest_journey_stage"])
    else:
        enriched_state = base_state
        ledger.emit(type="enrichment", domain=domain_a["choice"] if domain_a else None, applied=False,
                    reason="domain/audience not trusted" if not trusted else "no domain_enrichment entry")
    progress(f"enrichment: {'applied' if enrich else 'skipped'}\n")

    # 3-5. Classify -> recurse into whatever's selected -> stop at no-further-level or budget --
    # one tree, one function, from the 12 gap categories all the way down.
    tree = build_tree(world)
    selected = classify_root(tree, enriched_state, budget, world, ledger, progress)
    progress(f"gap categories: top {GAP_TOPK} of {len(tree)} selected (budget spent: {budget.spent}/{budget.limit})")
    for node in selected:
        walk(node, [node["id"]], [], enriched_state, budget, ledger, progress, depth=0, max_depth=a.max_depth)

    ledger.emit(type="run_end", budget_spent=budget.spent, budget_limit=budget.limit)
    ledger.close()
    progress(f"\nBudget spent: {budget.spent}/{budget.limit}. Render it: python3 foundry/report.py --idea {a.idea}")


if __name__ == "__main__":
    main()
