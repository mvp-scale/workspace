#!/usr/bin/env python3
"""ONE shared priority queue, not a per-branch depth-first walk with a fixed top-k at every level.

Rewritten this session (see PLAN.md and BRIDGE.md for the reasoning): the old design picked a
fixed top-4 gap_categories by one pooled composite score, then walked each selected branch to
completion with a fixed number of children kept at every node (GAP_TOPK / CHILD_TOPK_BOOSTED /
CHILD_TOPK_NORMAL) -- three undiagnosed constants, and real evidence it stopped at ~22.5% of its
own paid-for budget every run (18/80 across the 7-idea run) while the 21 gap_categories' own
shape tags (functional/non-functional/architectural/user-story/technical-spec/operational) sat
unused, letting spec/NFR categories dominate every idea's selection regardless of actual domain.

Now: `classify_root` still fans out all 21 gap_categories as one noul battery (unchanged), but
selection is SHAPE-GUARANTEED (top-SHAPE_TOPK per shape seeded first, so every dimension gets
real representation) plus BUDGET-RANKED (every other category is also seeded, at lower priority,
so a bigger budget can still reach them -- the frontier isn't artificially cut off at 4). Every
seeded node -- categories and, as they're visited, their children -- goes onto ONE shared
max-priority queue (`run_walk`), popped highest-score-first, until the queue empties or the
budget runs out. No more fixed top-k at any level; the budget itself is the only real cutoff,
same principle applied top to bottom.

Also: Level 0's domain/audience trust check is margin-based now (`choice_trust`), not a flat 0.6
floor on both (`DOMAIN_AUDIENCE_FLOOR`, retired) -- the flat floor discarded real signal (found
this session: oncall-rotation's domain came back workflow-automation at 55%, standup-async's at
39%, both plausible plurality picks among 10 options, both thrown away, both skipping
world-knowledge enrichment for no good reason). And Level 0 now also asks a `decomposition_depth`
score (new) -- informational this pass, not yet load-bearing in any decision, same honesty
standard as everything else undiagnosed in this file.

Budget is a real, enforced cap on total live calls for the whole run (`BUDGET` below), not just a
per-branch depth limit -- "until you exceed the budget" made literal, not implied.

Writes a structured JSONL ledger to runs/<idea>-layered-walk.jsonl as it goes. report.py and
sort_and_rank.py both read that ledger; record types are additive relative to the prior version
(new fields, no removed ones report.py depends on), so both stay compatible.

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
import heapq
import itertools
import json
import sys
from collections import defaultdict
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

# Margin-based, not a flat floor (replaces DOMAIN_AUDIENCE_FLOOR=0.6 on both -- see module
# docstring for why). A first attempt, not diagnosed against real data the way ATOMIC_THRESHOLD
# was -- same open-item caveat as everything else marked "first attempt" in this file.
DOMAIN_AUDIENCE_MIN = 0.3      # low sanity floor -- guards against trusting a genuine near-tie
                                # across many options, not a load-bearing cutoff on its own.
DOMAIN_AUDIENCE_MARGIN = 0.15  # the real check: top pick must beat the runner-up by this much.

SHAPE_TOPK = 1                 # guaranteed picks per gap_categories shape (6 shapes: functional,
                                # non-functional, architectural, user-story, technical-spec,
                                # operational) -- every dimension gets at least this many seeded
                                # into the queue regardless of how they'd rank in one pooled
                                # ranking. Replaces the old flat GAP_TOPK=4 pool, which let
                                # nonfunctional-performance/-availability dominate nearly every
                                # idea's top-4 in the 7-idea run regardless of actual domain. A
                                # first attempt (why 1, not 2?), not diagnosed.
GUARANTEED_BONUS = 10.0        # added to a shape-guaranteed category's priority so the queue
                                # always drains it before any non-guaranteed one; non-guaranteed
                                # categories still compete among themselves by real composite
                                # score once budget allows -- the budget becomes the real
                                # selector for "how many past the guaranteed 6 get walked," not an
                                # artificial top-k, while every dimension still gets a floor.
CHILD_MIN_SANITY = 0.05        # a low sanity floor beneath which a child is never even pushed
                                # onto the queue, regardless of budget remaining -- catches a node
                                # whose children are all genuinely irrelevant. Not the load-
                                # bearing selection mechanism anymore (the queue + budget is);
                                # just hygiene.
ATOMIC_THRESHOLD = 0.18        # terminal -- ends a branch and ships a requirement. Calibrated
                              # against a controlled diagnostic on the corrected P1/P2/P3 set:
                              # these models discriminate correctly in direction (atomic-mean 0.28
                              # vs compound-mean 0.085) but the whole scale is compressed and
                              # shifted low. Model-combination-specific; re-calibrate if MODELS
                              # changes. NOTE (this session): a broader 90-leaf-vs-21-category
                              # diagnostic (diagnose_atomic_gate.py) found ~zero separation on 2 of
                              # 3 default models in the abstract (no idea context) -- see PLAN.md.
                              # Not yet acted on here pending kev-4b's data; still load-bearing.
DISAGREEMENT_THRESHOLD = funnel.DISAGREEMENT_THRESHOLD  # reused, not reinvented
W_GAP, W_PROFILE = 0.7, 0.3   # Composite Scoring weights for category selection: own gap-check
                               # score vs. the profile-probe boost (see profile_boost). Explicit,
                               # adjustable, not a first-attempt-and-forget number.
BUDGET = 60                   # hard cap on live calls (one call = one classify, regardless of how
                              # many questions are fanned into it) for the whole run, root through
                              # every leaf. Real, enforced -- "until you exceed the budget," not
                              # just a per-branch depth limit.

DEPTH_CRITERIA = [
    "Already essentially atomic -- one directly checkable fact, no further splitting needed.",
    "One additional decomposition level should be enough.",
    "Several meaningful child elements exist.",
    "Multiple hierarchical decomposition levels are needed.",
    "A broad solution space requiring deep recursive decomposition.",
]


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


def per_model_noul(per_model, key):
    """Raw per-model values for one noul key, keyed by model id (e.g. {"semif": 0.83, "kev-4b":
    0.71}) -- not just the mean/spread `combine_noul` returns. BRIDGE.md's own repeated lesson is
    that per-model behavior against known controls is what actually finds a non-discriminating
    model (the P3 diagnosis), but a ledger that only ever records mean/spread can't be used for
    that after the fact. Recorded on gap_check and the leaf half of grinder_node."""
    return {model: a[key]["noul"] for model, a in per_model.items() if (a.get(key) or {}).get("noul") is not None}


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


def combine_score(per_model, key):
    ss = [a[key]["score"] for a in per_model.values() if (a.get(key) or {}).get("score") is not None]
    if not ss:
        return None, None
    return sum(ss) / len(ss), (max(ss) - min(ss) if len(ss) > 1 else 0.0)


def choice_trust(answer):
    """Margin-based, not a flat floor -- see module docstring / DOMAIN_AUDIENCE_MIN/MARGIN above.
    The top pick must both clear a low sanity floor and beat the runner-up by a real margin."""
    if not answer:
        return False
    probs = sorted(answer["probabilities"].values(), reverse=True)
    top = probs[0] if probs else 0
    second = probs[1] if len(probs) > 1 else 0
    return top >= DOMAIN_AUDIENCE_MIN and (top - second) >= DOMAIN_AUDIENCE_MARGIN


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
    """The one non-recursive step: domain + audience (`choice`, used once to set context) fanned
    together with world-knowledge.yaml's profile_probes (`noul`) and a new `decomposition_depth`
    (`score`) question -- Speculative Fan-Out means not splitting what can go in one call just
    because the question types differ."""
    if budget.exhausted():
        return None, None, {}, (None, None)
    by_domain = [v for v in slicer["variants"] if v["id"] == "by-domain"][0]
    questions = dict(by_domain["calls"][0]["questions"])
    for p in world.get("profile_probes", []):
        questions[f"profile::{p['id']}"] = noul_question(p["text"], p["criteria"]["true"], p["criteria"]["false"])
    questions["depth_estimate"] = {
        "type": "score",
        "instructions": ("Question: how much additional decomposition is likely needed before "
                          "this idea reaches single, directly checkable requirements?"),
        "criteria": DEPTH_CRITERIA,
    }
    per_model = call_all(base_state, questions, budget)
    if not per_model:
        return None, None, {}, (None, None)
    domain, audience = combine_choice(per_model, "domain"), combine_choice(per_model, "audience")
    profile = {p["id"]: combine_noul(per_model, f"profile::{p['id']}")[0] for p in world.get("profile_probes", [])}
    depth = combine_score(per_model, "depth_estimate")
    return domain, audience, profile, depth


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
    """The 21 gap_categories -> whatever gap_category_detail supplies for each (all 21 have a
    library now). `shape` carried through explicitly -- classify_root groups by it now, where the
    old version ignored it entirely."""
    children = []
    for cat in world["gap_categories"]:
        detail = world.get("gap_category_detail", {}).get(cat["id"])
        children.append({"id": cat["id"], "text": cat["text"], "shape": cat.get("shape"),
                          "children": (detail or {}).get("tree", [])})
    return children


def classify_node(state, node_text, children, budget):
    """ONE call: the atomic question (leaf only -- ancestor context lives in `state`) plus one
    relevance question per candidate child, fanned into the same dict."""
    if budget.exhausted():
        return None, None, {}, {}
    questions = {}
    if not children:
        questions["atomic"] = noul_question(
            node_text + "\n\nQuestion: is this a single, directly checkable requirement -- something a person could look at the real system and confirm yes or no, without first splitting it into separate sub-checks?",
            "A single, directly checkable requirement -- one clear yes/no fact.",
            "Still a category or a compound of more than one checkable thing -- needs to split further.")
    for child in children:
        # Same explicit "NOT yet true" polarity as classify_root's Level 0 question (not just the
        # same meaning in different words) -- a second-review pass found the previous wording here
        # left the polarity to be inferred against a state string that, before the fix above, was
        # itself inverted; stating it explicitly removes the ambiguity regardless of state wording.
        questions[f"child::{child['id']}"] = noul_question(
            node_text + " " + child["text"] + "\n\nQuestion: given the gaps already identified so far, is this NOT yet true -- i.e., is this a real, relevant sub-gap that needs addressing?",
            "No, not yet true -- a real, relevant sub-gap here.", "Yes, this is already addressed, or not relevant given what's already identified.")
    per_model = call_all(state, questions, budget)
    if not per_model:
        return None, None, {}, {}
    atomic_mean, atomic_spread = (combine_noul(per_model, "atomic") if not children else (None, None))
    atomic_per_model = (per_model_noul(per_model, "atomic") if not children else {})
    child_means = {c["id"]: combine_noul(per_model, f"child::{c['id']}")[0] for c in children}
    return atomic_mean, atomic_spread, child_means, atomic_per_model


def process_node(node, path, breadcrumb, base_state, budget, ledger, progress, depth, max_depth, boosted, push):
    """Handles ONE node popped from the shared priority queue: classify it, emit its ledger
    record, and push any selected children back onto the queue at their own real priority.
    Replaces the old walk()'s recursive self-calls -- there's no per-branch recursion anymore, the
    whole tree drains by one global priority order."""
    if budget.exhausted():
        ledger.emit(type="grinder_node", path=path, id=node["id"], depth=depth, text=node["text"],
                     full_text=" ".join(breadcrumb + [node["text"]]), atomic_mean=None,
                     status="budget_exhausted", children=[])
        progress(f"  {'  ' * depth}[{node['id']}] -- BUDGET EXHAUSTED")
        return

    is_leaf = not node["children"]
    full_text = " ".join(breadcrumb + [node["text"]])
    # POLARITY: breadcrumb entries are gap_categories/gap_category_detail text, which reads as a
    # solved-state claim ("X is defined") -- but every entry got there because a live call judged
    # it NOT yet true for this idea (that's why the branch was selected). Framing it as
    # "Established so far: <solved-state text>" would assert the opposite of what was actually
    # found -- the same class of bug as the gap_categories/gap_category_detail polarity
    # contradiction (see README's "Lessons learned"), just in state-building code instead of
    # authored content. Found by a second-review pass, not caught by "polarity read clean" checks
    # of rendered requirement text, since this string never appears in report.py's output.
    state = base_state + (f"\n\nGaps already identified for this idea (confirmed NOT yet true, i.e. real, unaddressed gaps so far): {'; '.join(breadcrumb)}" if breadcrumb else "")
    atomic_mean, atomic_spread, child_means, atomic_per_model = classify_node(state, node["text"], node["children"], budget)
    progress(f"  {'  ' * depth}[{node['id']}]")

    call_failed = (is_leaf and atomic_mean is None) or (not is_leaf and not child_means)
    if call_failed:
        ledger.emit(type="grinder_node", path=path, id=node["id"], depth=depth, text=node["text"],
                     full_text=full_text, atomic_mean=None, status="no_answer", children=[])
        return

    # No fixed top-k here -- every child above the low sanity floor gets pushed onto the shared
    # queue at its own real score; the queue + budget decide which ones actually get visited.
    child_records = []
    for child in node["children"]:
        p = child_means.get(child["id"])
        selected = p is not None and p >= CHILD_MIN_SANITY
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
                atomic_per_model=atomic_per_model, status=status, children=child_records, boosted=boosted)

    if status == "not_atomic_recursing":
        for child in node["children"]:
            rec = next(c for c in child_records if c["id"] == child["id"])
            if rec["selected"]:
                push(child, path + [child["id"]], breadcrumb + [node["text"]], depth + 1, boosted, rec["p"])


def run_walk(seeds, base_state, budget, ledger, progress, max_depth):
    """Drains ONE shared max-priority queue -- highest score popped first -- until it's empty or
    the budget is exhausted. `seeds` is [(node, priority, boosted), ...] from classify_root
    (shape-guaranteed categories at a boosted priority, every other category seeded too at its
    real composite score). Replaces the old per-branch `for cat in selected: walk(...)` loop."""
    counter = itertools.count()
    heap = []
    for node, priority, boosted in seeds:
        heapq.heappush(heap, (-priority, next(counter), node, [node["id"]], [], 0, boosted))

    nodes_processed = 0
    while heap and not budget.exhausted():
        _, _, node, path, breadcrumb, depth, boosted = heapq.heappop(heap)

        def push(child, cpath, cbreadcrumb, cdepth, cboosted, priority, _heap=heap, _counter=counter):
            heapq.heappush(_heap, (-priority, next(_counter), child, cpath, cbreadcrumb, cdepth, cboosted))

        process_node(node, path, breadcrumb, base_state, budget, ledger, progress, depth, max_depth, boosted, push)
        nodes_processed += 1
    return nodes_processed


def classify_root(tree, state, budget, world, ledger, progress, profile):
    """Level 0's select-many step over the gap categories. Selection is shape-guaranteed +
    budget-ranked now, not one pooled top-k (see module docstring): every one of the 6 shapes
    (functional/non-functional/architectural/user-story/technical-spec/operational) gets its own
    top-SHAPE_TOPK seeded at a priority bonus that guarantees it drains first; every other
    category is also seeded, at its real composite score, so a bigger budget still reaches it
    instead of being cut off at a fixed count."""
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
    per_model_results = {n["id"]: per_model_noul(per_model, n["id"]) for n in tree}
    boosts = {n["id"]: profile_boost(n["id"], profile, world) for n in tree}

    def composite(n):
        mean = results[n["id"]][0] or 0
        return W_GAP * mean + W_PROFILE * min(boosts[n["id"]], 1.0)

    by_shape = defaultdict(list)
    for n in tree:
        by_shape[n.get("shape") or "(untagged)"].append(n)
    guaranteed_ids = set()
    for shape, cats in by_shape.items():
        ranked = sorted(cats, key=lambda n: -composite(n))
        for n in ranked[:SHAPE_TOPK]:
            guaranteed_ids.add(n["id"])

    for n in tree:
        mean, spread = results[n["id"]]
        ledger.emit(type="gap_check", id=n["id"], text=n["text"], mean=mean, spread=spread,
                    per_model=per_model_results[n["id"]], profile_boost=boosts[n["id"]],
                    composite=composite(n), selected=n["id"] in guaranteed_ids, shape=n.get("shape"))
    ledger.emit(type="gap_summary", selected_count=len(guaranteed_ids), total=len(tree),
                method=f"top-{SHAPE_TOPK} per shape (guaranteed, 6 shapes) + every other category budget-ranked")

    seeds = []
    for n in tree:
        is_boosted = boosts[n["id"]] > 0
        is_guaranteed = n["id"] in guaranteed_ids
        priority = composite(n) + (GUARANTEED_BONUS if is_guaranteed else 0.0)
        ledger.emit(type="category_recursion", id=n["id"], has_library=bool(n["children"]),
                    boosted=is_boosted, guaranteed=is_guaranteed)
        seeds.append((n, priority, is_boosted))
    return seeds


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

    # 1. Classify (domain/audience + the profile pre-scan + a depth estimate, one combined call).
    progress("TOOL: Slicer.by-domain (choice x2 + 10 profile probes + depth estimate, fanned into one call)")
    domain_a, audience_a, profile, depth = classify_domain_audience_and_profile(base_state, slicer, world, budget)
    ledger.emit(type="layer0_domain_audience", domain=domain_a, audience=audience_a)
    ledger.emit(type="profile", values=profile)
    ledger.emit(type="depth_estimate", mean=(depth[0] if depth else None), spread=(depth[1] if depth else None))
    trusted = choice_trust(domain_a) and choice_trust(audience_a)
    tools_used["Slicer.by-domain"] = (domain_a is not None, f"ran, {'trusted (margin-based)' if trusted else 'not trusted (margin-based)'}" if domain_a else "budget exhausted before this call")
    progress(f"  -> domain/audience: {'trusted' if trusted else 'not trusted'} "
             f"({domain_a['choice'] if domain_a else '?'}, {audience_a['choice'] if audience_a else '?'})")
    active_probes = sorted(((k, v) for k, v in profile.items() if v is not None and v >= 0.6), key=lambda kv: -kv[1])
    progress(f"  -> profile: {', '.join(f'{k} ({v:.2f})' for k, v in active_probes) or 'nothing scored >= 0.6'}")
    if depth and depth[0] is not None:
        progress(f"  -> depth estimate: {depth[0]:.2f}/4 (spread {depth[1]:.2f}, informational only this pass)")

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

    # 3. Classify all 21 gap_categories, shape-guaranteed + budget-ranked selection.
    progress("TOOL: Slicer.gap_categories (one noul per category, shape-guaranteed + budget-ranked, Composite Scoring)")
    tree = build_tree(world)
    seeds = classify_root(tree, enriched_state, budget, world, ledger, progress, profile)
    n_guaranteed = sum(1 for _, p, _ in seeds if p >= GUARANTEED_BONUS)
    tools_used["Slicer.gap_categories"] = (bool(seeds) or budget.spent > 0, f"{n_guaranteed} categories shape-guaranteed (of 6 shapes), {len(seeds)} total seeded onto the queue")
    progress(f"  -> {n_guaranteed} shape-guaranteed + {len(seeds) - n_guaranteed} budget-ranked seeded (budget spent: {budget.spent}/{budget.limit})")

    # 4. Drain the shared priority queue -- budget is the only real cutoff now, not a fixed top-k
    # at any level.
    progress("TOOL: Grinder.priority-queue (one shared max-priority queue, drains by score until budget exhausted)")
    nodes_walked = run_walk(seeds, enriched_state, budget, ledger, progress, max_depth=a.max_depth)
    tools_used["Grinder.priority-queue"] = (nodes_walked > 0, f"{nodes_walked} node classifications, budget-driven (not fixed top-k)")

    progress("\nTOOLS USED THIS RUN")
    for tool, (ran, note) in tools_used.items():
        progress(f"  {'✓' if ran else '✗'} {tool}: {note}")
    progress("  ✗ Sorter / Conveyor / Spotlight: not run by this script -- run sort_and_rank.py next")

    ledger.emit(type="run_end", budget_spent=budget.spent, budget_limit=budget.limit)
    ledger.close()
    progress(f"\nBudget spent: {budget.spent}/{budget.limit}. Render it: python3 foundry/report.py --idea {a.idea}")


if __name__ == "__main__":
    main()
