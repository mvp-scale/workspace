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

# Default, grounded in probes/report_v2.py's already-validated measurement (1,437 real labeled
# items, 15 published sets): semif 66.8% / kev-4b 66.9% / so1 64.8% accuracy, all three with a
# real calibration gap (0.10-0.13); laya drops to 56.9% with confident answers becoming rare at
# higher thresholds; verdict is 46.7% with a calibration gap of just 0.04 -- confidence carries
# almost no signal. Not an in-session guess. Override with --models, e.g. --models semif for a
# single model, or --models jev for the hosted reference -- same call_all/server.call path as
# every other backend, no special-cased exclusion. What actually happens when jev is selected
# depends on the environment, not this code: server.BACKENDS reads TYPESAFE_API_KEY from the
# process environment, and if that's empty (nothing sourced it), server.call's own existing check
# (`if name.startswith("jev") and not cfg["key"]`) returns a clean "TYPESAFE_API_KEY not set"
# error -- the same behavior every other script here has always had. Kept out of the *default*
# list for the reasons above (three comparable, calibrated local models); available on request.
ALL_MODELS = ["semif", "kev-4b", "so1", "laya", "verdict", "jev"]
MODELS = ["semif", "kev-4b", "so1"]  # P1, P2, P3 -- overwritten by --models in main()

DOMAIN_AUDIENCE_FLOOR = 0.6   # slicer.yaml's own written by-domain routing rule: both must clear
                              # this or the classification isn't trusted -- no composite average.
GAP_TOPK = 4                  # Level 0's selection policy differs from every deeper level on
                              # purpose: top-k by mean, not a floor. A floor near 1.0 for nearly
                              # every category selected everything in an early run -- not a
                              # decision, a rubber stamp.
CHILD_TOPK_BOOSTED = 3        # was a flat 0.6 floor (CHILD_RELEVANCE) -- replaced for the same
CHILD_TOPK_NORMAL = 1          # reason GAP_TOPK replaced one at Level 0: a real run against P0
                              # (hosted Jev) scored every single child across four branches
                              # 0.15-0.45 -- nowhere near 0.6, or even the boosted 0.5 -- so a
                              # flat floor selected nothing, silently, for a model whose score
                              # scale just sits lower. Top-k is robust to that; a floor isn't.
                              # Boosted branches (see profile_boost) get more room to dig in.
CHILD_MIN_SANITY = 0.05       # top-k still needs a floor beneath which nothing gets selected no
                              # matter how it ranks -- catches a node whose children are all
                              # genuinely irrelevant, not just low-ranked among themselves.
ATOMIC_THRESHOLD = 0.18       # terminal -- ends a branch and ships a requirement. Calibrated
                              # against a controlled diagnostic on the corrected P1/P2/P3 set:
                              # these models discriminate correctly in direction (atomic-mean 0.28
                              # vs compound-mean 0.085) but the whole scale is compressed and
                              # shifted low. Model-combination-specific; re-calibrate if MODELS
                              # changes.
DISAGREEMENT_THRESHOLD = funnel.DISAGREEMENT_THRESHOLD  # reused, not reinvented
W_GAP, W_PROFILE = 0.7, 0.3   # Composite Scoring weights for category selection: own gap-check
                               # score vs. the profile-probe boost (see profile_boost). Explicit,
                               # adjustable, not a first-attempt-and-forget number.
# Confidence-Gated Routing with more than one signal: a profile-boosted branch gets a higher k
# (CHILD_TOPK_BOOSTED, dig deeper where the profile says it matters); a non-boosted branch gets a
# lower one (CHILD_TOPK_NORMAL, back off sooner) -- see that comment above, not a separate
# constant of its own anymore now that child selection is top-k rather than a floor to shift.
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


def classify_domain_audience_and_profile(base_state, slicer, world, budget):
    """The one non-recursive step, and the one call that mixes kinds: domain + audience (`choice`,
    used once to set context) fanned together with world-knowledge.yaml's profile_probes (`noul`,
    ten generic speculative questions about the idea's tech/context) -- Speculative Fan-Out means
    not splitting what can go in one call just because the question types differ."""
    if budget.exhausted():
        return None, None, {}
    by_domain = [v for v in slicer["variants"] if v["id"] == "by-domain"][0]
    questions = dict(by_domain["calls"][0]["questions"])
    for p in world.get("profile_probes", []):
        questions[f"profile::{p['id']}"] = noul_question(p["text"], p["criteria"]["true"], p["criteria"]["false"])
    per_model = call_all(base_state, questions, budget)
    if not per_model:
        return None, None, {}
    domain, audience = combine_choice(per_model, "domain"), combine_choice(per_model, "audience")
    profile = {p["id"]: combine_noul(per_model, f"profile::{p['id']}")[0] for p in world.get("profile_probes", [])}
    return domain, audience, profile


def profile_boost(category_id, profile, world):
    """Deterministic, no live call: sum of profile signal strength for every probe that lists
    this category in its `boosts`."""
    boost = 0.0
    for p in world.get("profile_probes", []):
        if category_id in p.get("boosts", []):
            v = profile.get(p["id"])
            if v is not None:
                boost += v
    return boost


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


def walk(node, path, breadcrumb, base_state, budget, ledger, progress, depth, max_depth, boosted=False):
    """The one loop, recursive: classify -> (breadcrumb carries the expansion forward) -> recurse
    into whatever was selected -> stop when there's nothing left to select or the budget's gone.
    `boosted` is the profile-based second confidence signal: propagated unchanged down a whole
    branch from whichever root category it started at (a branch's relevance to the idea's actual
    profile doesn't change node to node), and shifts how easily a child gets selected."""
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

    # Top-k, not a floor (see CHILD_TOPK_BOOSTED/NORMAL comment) -- ranked by score among this
    # node's own children, with a low sanity floor beneath which nothing gets selected regardless
    # of rank.
    k = CHILD_TOPK_BOOSTED if boosted else CHILD_TOPK_NORMAL
    ranked_children = sorted(node["children"], key=lambda c: -(child_means.get(c["id"]) or -1))
    top_ids = {c["id"] for c in ranked_children[:k] if (child_means.get(c["id"]) or 0) >= CHILD_MIN_SANITY}
    child_records = []
    for child in node["children"]:
        p = child_means.get(child["id"])
        selected = child["id"] in top_ids
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
                status=status, children=child_records, boosted=boosted)

    if status == "not_atomic_recursing":
        for child in node["children"]:
            rec = next(c for c in child_records if c["id"] == child["id"])
            if rec["selected"]:
                walk(child, path + [child["id"]], breadcrumb + [node["text"]], base_state,
                     budget, ledger, progress, depth + 1, max_depth, boosted=boosted)


def classify_root(tree, state, budget, world, ledger, progress, profile):
    """Level 0's select-many step over the gap categories -- same mechanism as any deeper node's
    child-relevance check, except the selection policy is Composite Scoring + top-k, not a
    threshold alone (see GAP_TOPK): each category's rank is its own gap-check score combined with
    a profile-based boost, weighted (W_GAP, W_PROFILE), not the raw score alone."""
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
    boosts = {n["id"]: profile_boost(n["id"], profile, world) for n in tree}

    def composite(n):
        mean = results[n["id"]][0] or 0
        return W_GAP * mean + W_PROFILE * min(boosts[n["id"]], 1.0)

    ranked = sorted(tree, key=lambda n: -composite(n))
    selected = ranked[:GAP_TOPK]
    selected_ids = {n["id"] for n in selected}
    for n in tree:
        mean, spread = results[n["id"]]
        ledger.emit(type="gap_check", id=n["id"], text=n["text"], mean=mean, spread=spread,
                    profile_boost=boosts[n["id"]], composite=composite(n), selected=n["id"] in selected_ids)
    ledger.emit(type="gap_summary", selected_count=len(selected), total=len(tree), method=f"top-{GAP_TOPK} by composite score")
    result = []
    for n in selected:
        is_boosted = boosts[n["id"]] > 0
        ledger.emit(type="category_recursion", id=n["id"], has_library=bool(n["children"]), boosted=is_boosted)
        result.append((n, is_boosted))
    return result


def parse_models(spec):
    """Comma-separated P-numbers (the project's own legend, P0-P5) and/or raw backend ids, mixed
    freely -- e.g. --models P0,P1 or --models jev,semif. Just replaces the MODELS list; nothing
    else about the run changes based on how they were spelled."""
    p_to_model = {p: m for m, p in funnel.MODEL_P.items()}
    result = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if token in p_to_model:
            result.append(p_to_model[token])
        elif token in ALL_MODELS:
            result.append(token)
        else:
            sys.exit(f"unknown model '{token}' -- use a P-number ({', '.join(sorted(p_to_model))}) or a backend id ({', '.join(ALL_MODELS)})")
    if not result:
        sys.exit(f"--models '{spec}' resolved to no models")
    return result


def main():
    global MODELS
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--budget", type=int, default=BUDGET)
    ap.add_argument("--models", default=None,
                     help="comma-separated P-numbers or backend ids, e.g. --models P0,P1 or "
                          "--models jev,semif. Defaults to P1,P2,P3 (see MODELS comment above) if omitted.")
    a = ap.parse_args()
    if a.models:
        MODELS = parse_models(a.models)

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

    tools_used = {}  # tool.variant -> (ran: bool, note: str) -- the honest accounting printed at the end

    # 1. Classify (domain/audience + the profile pre-scan, one combined call) -- the one
    # non-recursive step.
    progress("TOOL: Slicer.by-domain (choice x2 + 10 profile probes, fanned into one call)")
    domain_a, audience_a, profile = classify_domain_audience_and_profile(base_state, slicer, world, budget)
    ledger.emit(type="layer0_domain_audience", domain=domain_a, audience=audience_a)
    ledger.emit(type="profile", values=profile)
    tools_used["Slicer.by-domain"] = (domain_a is not None, f"ran, {'trusted' if domain_a and audience_a and domain_a['confidence'] >= DOMAIN_AUDIENCE_FLOOR and audience_a['confidence'] >= DOMAIN_AUDIENCE_FLOOR else 'not trusted'}" if domain_a else "budget exhausted before this call")
    trusted = (domain_a and audience_a and domain_a["confidence"] >= DOMAIN_AUDIENCE_FLOOR
               and audience_a["confidence"] >= DOMAIN_AUDIENCE_FLOOR)
    progress(f"  -> domain/audience: {'trusted' if trusted else 'not trusted'} "
             f"({domain_a['choice'] if domain_a else '?'}, {audience_a['choice'] if audience_a else '?'})")
    active_probes = sorted(((k, v) for k, v in profile.items() if v is not None and v >= 0.6), key=lambda kv: -kv[1])
    progress(f"  -> profile: {', '.join(f'{k} ({v:.2f})' for k, v in active_probes) or 'nothing scored >= 0.6'}")

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
        reason = "domain/audience not trusted" if not trusted else "no domain_enrichment entry"
        ledger.emit(type="enrichment", domain=domain_a["choice"] if domain_a else None, applied=False, reason=reason)
    progress(f"  -> enrichment: {'applied' if enrich else f'skipped ({reason})'}\n")

    # 3-5. Classify -> recurse into whatever's selected -> stop at no-further-level or budget --
    # one tree, one function, from the gap categories all the way down. Selection is Composite
    # Scoring (own score + profile boost); recursion inside a selected branch carries that
    # branch's boosted-or-not status all the way down as a second confidence-gating signal.
    progress("TOOL: Slicer.gap_categories (one noul per category, all fanned into one call, Composite Scoring)")
    tree = build_tree(world)
    selected = classify_root(tree, enriched_state, budget, world, ledger, progress, profile)
    tools_used["Slicer.gap_categories"] = (bool(selected) or budget.spent > 0, f"selected {len(selected)} of {len(tree)} by composite score")
    progress(f"  -> top {GAP_TOPK} of {len(tree)} selected by composite score (budget spent: {budget.spent}/{budget.limit})")

    progress("TOOL: Grinder.atomic-threshold (one fanned call per node, per selected branch)")
    nodes_walked = 0
    for node, is_boosted in selected:
        before = budget.spent
        walk(node, [node["id"]], [], enriched_state, budget, ledger, progress, depth=0,
             max_depth=a.max_depth, boosted=is_boosted)
        nodes_walked += budget.spent - before
    tools_used["Grinder.atomic-threshold"] = (nodes_walked > 0, f"{nodes_walked} node classifications across {len(selected)} branches" if selected else "no branches selected to walk")

    progress("\nTOOLS USED THIS RUN")
    for tool, (ran, note) in tools_used.items():
        progress(f"  {'✓' if ran else '✗'} {tool}: {note}")
    progress("  ✗ Sorter / Conveyor / Spotlight: not run by this script -- run sort_and_rank.py next")

    ledger.emit(type="run_end", budget_spent=budget.spent, budget_limit=budget.limit)
    ledger.close()
    progress(f"\nBudget spent: {budget.spent}/{budget.limit}. Render it: python3 foundry/report.py --idea {a.idea}")


if __name__ == "__main__":
    main()
