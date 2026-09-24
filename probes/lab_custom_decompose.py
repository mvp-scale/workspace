#!/usr/bin/env python3
"""Custom decomposition: freeform text in, live-scored against foundry's fixed, generic
requirements library, following the same one rule as everywhere else in this repo -- only the
user's text is idea-specific; every candidate category and requirement comes from
foundry/tools/world-knowledge.yaml, never written for this text.

Full design: docs/custom-decomposition-design.md. Summary of what this module is a hybrid of:
- Structure comes from foundry's Slicer+Grinder walk (foundry/layered_walk.py): shape-guaranteed
  category selection, one shared priority queue, a real enforced call budget. Read only, not
  imported -- layered_walk.py mutates a module-global MODELS list, writes a ledger keyed by
  --idea, and imports server via a sys.path hack; importing it here would either duplicate that
  state or collide with it.
- Leaf annotation comes from lab_decompose.py's leaf battery (gate/phase/risk/complexity/
  dependency), minus `atomic` and `parallel`. `atomic` is dropped because foundry/PLAN.md's own
  diagnostic found it scores at noise level (+0.006 separation between known-atomic and
  known-compound text) and every library tree is one level deep, so a failed atomic check has
  nowhere left to split anyway -- the call is better spent on richer, reference-free annotation.
  `parallel` is dropped because it asks about "siblings in its group", and the siblings here are
  whichever items the priority queue happened to reach, not a real group.

This module never calls a model itself -- `ask(model_id, item)` is injected (see `walk()`), so it
never imports `server` (that module already imports this one when running as the live endpoint,
and `server` imports itself as __main__ when run directly -- a two-way import would either fail or
silently create a second copy of server's BACKENDS/_cache, as lab_decompose.py's own `import
server` already does when run standalone).

CLI (offline runner, per this lab's "every structure has one" rule):
    python3 probes/lab_custom_decompose.py --text-file idea.txt [--who "..."] \\
        --models semif,kev-4b,so1 --budget 60 --out data/probe-runs-v2/_custom_decompose/run.jsonl
    python3 probes/lab_custom_decompose.py --intake foundry/ideas/oncall-rotation.json --models semif --budget 60
"""
import argparse
import hashlib
import heapq
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOUNDRY = ROOT / "foundry"
LIBRARY_PATH = FOUNDRY / "tools" / "world-knowledge.yaml"
SLICER_PATH = FOUNDRY / "tools" / "slicer.yaml"

CONTROL_INTAKE = "Idea: a software product.\n\nWho this is for: its users."
SPACE = 113  # 1 frame + 1 categories + 21 category nodes + 90 leaves -- foundry/PLAN.md's own count
MAX_TEXT, MAX_WHO = 4000, 1000

# Copied from foundry/layered_walk.py (SHAPE_TOPK, GUARANTEED_BONUS, CHILD_MIN_SANITY, W_GAP,
# W_PROFILE, DOMAIN_AUDIENCE_MIN, DOMAIN_AUDIENCE_MARGIN) and foundry/funnel.py
# (DISAGREEMENT_THRESHOLD) -- kept in sync by hand, each covered by
# test_lab_custom_decompose.py::test_constants_match_foundry where importable.
SHAPE_TOPK = 1
GUARANTEED_BONUS = 10.0
CHILD_MIN_SANITY = 0.05
W_GAP, W_PROFILE = 0.7, 0.3
DOMAIN_AUDIENCE_MIN = 0.3
DOMAIN_AUDIENCE_MARGIN = 0.15
DISAGREEMENT_THRESHOLD = 0.3
FLAT_RANGE = 0.10   # new here, first attempt: a model whose 21 category scores span less than
                     # this didn't tell them apart on this text -- see design doc section 1.3.
SCOPE_WARN = 0.40    # new here, first attempt -- see design doc section 1.4.

# Verbatim from probes/lab_decompose.py.
LEVELS5 = ["very low", "low", "medium", "high", "very high"]
PHASE_CRITERIA = {
    "spike": "Finding something out -- a measurement, an experiment, a check against documentation. Nothing is built or decided yet.",
    "decide": "A choice between real options that a person has to make; no new information is being gathered.",
    "build": "Writing the actual implementation, once what to build is already known.",
    "validate": "Checking that something already built actually works, at realistic scale or against a real baseline.",
    "launch": "Getting a working, validated system into production: deploy, rollback, runbook.",
}
DEPENDENCY_CRITERIA = {
    "none": "Nothing external; it just needs to be built.",
    "needs-user-decision": "It is blocked on a decision only the user can make.",
    "needs-other-item": "It depends on another item in this plan finishing first.",
    "needs-external-check": "It depends on an external resource or check (e.g. data access) not yet confirmed.",
}
# Verbatim from foundry/layered_walk.py's classify_domain_audience_and_profile.
DEPTH_CRITERIA = [
    "Already essentially atomic -- one directly checkable fact, no further splitting needed.",
    "One additional decomposition level should be enough.",
    "Several meaningful child elements exist.",
    "Multiple hierarchical decomposition levels are needed.",
    "A broad solution space requiring deep recursive decomposition.",
]
SCOPE_Q_TEXT = ("Question: does this text describe something a person or team would build, "
                "change or run -- a product, service, system or process?")


def noul(text, true_label, false_label):
    return {"type": "noul", "instructions": text, "criteria": {"true": true_label, "false": false_label}}


def choice(text, criteria):
    return {"type": "choice", "instructions": text, "criteria": criteria}


def score(text, levels):
    return {"type": "score", "instructions": text, "criteria": levels}


_LIBRARY_CACHE = {}  # path -> (mtime, parsed)


def _yaml():
    import yaml  # lazy: server.py stays stdlib-only at import time if PyYAML is missing
    return yaml


def load_library():
    """foundry/tools/world-knowledge.yaml + slicer.yaml's by-domain questions, read-only, cached
    by file mtime. Returns the shape load_library()'s docstring in lab_custom_decompose's own
    module docstring promises: sha256, shapes, categories (id/text/shape/children), profile_probes,
    domain_enrichment, pain_points, delights, customer_journey, by_domain_questions."""
    mtimes = (LIBRARY_PATH.stat().st_mtime, SLICER_PATH.stat().st_mtime)
    cached = _LIBRARY_CACHE.get("lib")
    if cached and cached[0] == mtimes:
        return cached[1]
    yaml = _yaml()
    raw = LIBRARY_PATH.read_bytes()
    world = yaml.safe_load(raw)
    slicer = yaml.safe_load(SLICER_PATH.read_bytes())
    by_domain = [v for v in slicer["variants"] if v["id"] == "by-domain"][0]
    bd_questions = by_domain["calls"][0]["questions"]

    categories = []
    shapes_seen = []
    for cat in world["gap_categories"]:
        detail = world.get("gap_category_detail", {}).get(cat["id"]) or {}
        children = [{"id": c["id"], "text": c["text"]} for c in detail.get("tree", [])]
        categories.append({"id": cat["id"], "text": cat["text"], "shape": cat.get("shape"), "children": children})
        if cat.get("shape") and cat["shape"] not in shapes_seen:
            shapes_seen.append(cat["shape"])

    lib = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "shapes": shapes_seen,
        "categories": categories,
        "profile_probes": world.get("profile_probes", []),
        "domain_enrichment": world.get("domain_enrichment", {}),
        "pain_points": {p["id"]: p["text"] for p in world.get("pain_points", [])},
        "delights": {d["id"]: d["text"] for d in world.get("delights", [])},
        "customer_journey": {c["id"]: c["text"] for c in world.get("customer_journey", [])},
        "by_domain_questions": bd_questions,
    }
    _LIBRARY_CACHE["lib"] = (mtimes, lib)
    return lib


def skeleton(lib):
    """Client-safe subset for GET /api/decompose-library -- everything the page needs to draw the
    whole candidate map before any call, nothing it doesn't."""
    return {
        "sha256": lib["sha256"],
        "space": SPACE,
        "shapes": lib["shapes"],
        "categories": lib["categories"],
        "profile_probes": [{"id": p["id"], "text": p["text"]} for p in lib["profile_probes"]],
        "questions": {"leaf": ["gate", "phase", "risk", "complexity", "dependency"], "phase_options": list(PHASE_CRITERIA)},
    }


# ---------- combining per-model answers into one V = {mean, spread, per_model} ----------

def combine_noul(per_model, key):
    vals = {m: a[key]["noul"] for m, a in per_model.items() if (a.get(key) or {}).get("noul") is not None}
    if not vals:
        return {"mean": None, "spread": None, "per_model": {}}
    xs = list(vals.values())
    return {"mean": sum(xs) / len(xs), "spread": (max(xs) - min(xs)) if len(xs) > 1 else 0.0, "per_model": vals}


def combine_score(per_model, key):
    vals = {m: a[key]["score"] / (len(LEVELS5) - 1) for m, a in per_model.items() if (a.get(key) or {}).get("score") is not None}
    if not vals:
        return {"mean": None, "spread": None, "per_model": {}}
    xs = list(vals.values())
    return {"mean": sum(xs) / len(xs), "spread": (max(xs) - min(xs)) if len(xs) > 1 else 0.0, "per_model": vals}


def combine_choice(per_model, key):
    option_sums, per_model_top, n = {}, {}, 0
    for m, a in per_model.items():
        ans = a.get(key)
        if not ans or not ans.get("probabilities"):
            continue
        n += 1
        for opt, p in ans["probabilities"].items():
            option_sums[opt] = option_sums.get(opt, 0) + p
        per_model_top[m] = max(ans["probabilities"], key=ans["probabilities"].get)
    if not n:
        return {"choice": None, "confidence": None, "probabilities": {}, "per_model": {}}
    probs = {opt: total / n for opt, total in option_sums.items()}
    top = max(probs, key=probs.get)
    return {"choice": top, "confidence": probs[top], "probabilities": probs, "per_model": per_model_top}


def choice_split(v):
    """A choice-type V counts as 'models split' when not every model's own top pick agrees with
    the combined top pick -- the choice-type analogue of a numeric spread >= DISAGREEMENT_THRESHOLD."""
    if not v.get("per_model") or v.get("choice") is None:
        return False
    disagree = sum(1 for c in v["per_model"].values() if c != v["choice"])
    return (disagree / len(v["per_model"])) >= DISAGREEMENT_THRESHOLD


def noul_split(v):
    return v.get("spread") is not None and v["spread"] >= DISAGREEMENT_THRESHOLD


def choice_trust(v):
    """Margin-based, verbatim rule from foundry/layered_walk.py's choice_trust: the top pick must
    clear a low sanity floor AND beat the runner-up by a real margin."""
    probs = sorted(v.get("probabilities", {}).values(), reverse=True)
    top = probs[0] if probs else 0
    second = probs[1] if len(probs) > 1 else 0
    return top >= DOMAIN_AUDIENCE_MIN and (top - second) >= DOMAIN_AUDIENCE_MARGIN


def profile_boost(category_id, profile_values, lib):
    """Deterministic, no live call: sum of profile signal strength for every probe that lists this
    category in its boosts -- verbatim rule from foundry/layered_walk.py's profile_boost."""
    total = 0.0
    for p in lib["profile_probes"]:
        if category_id in p.get("boosts", []):
            v = profile_values.get(p["id"])
            if v is not None:
                total += v
    return total


# ---------- the live calls ----------

def call_all_models(state, questions, models, ask):
    """Fans ONE call out to every selected model at once (ThreadPoolExecutor, same pattern as
    /api/compare) and returns {model: {"answers":..., "latency_ms":..., "cached":...}} for models
    that answered without error, plus the raw per-model results (including errors) for the ledger."""
    assert len(questions) <= 24, f"{len(questions)} questions in one call exceeds the 24-question safety cap (BRIDGE.md's kev-4b OOM was caused by 40)"
    item = {"state": state, "questions": questions}
    with ThreadPoolExecutor(max(1, len(models))) as ex:
        futs = {m: ex.submit(ask, m, item) for m in models}
        raw = {m: f.result() for m, f in futs.items()}
    per_model = {m: r["answers"] for m, r in raw.items() if "error" not in r and r.get("answers")}
    errors = {m: r["error"] for m, r in raw.items() if "error" in r}
    latency_ms = {m: r.get("latency_ms") for m, r in raw.items() if "error" not in r}
    cached = bool(raw) and all(r.get("cached") for r in raw.values() if "error" not in r)
    return per_model, errors, latency_ms, cached, item


def frame_questions(lib):
    bd = lib["by_domain_questions"]
    q = {"domain": bd["domain"], "audience": bd["audience"]}
    for p in lib["profile_probes"]:
        q[f"profile::{p['id']}"] = noul(p["text"], p["criteria"]["true"], p["criteria"]["false"])
    q["depth_estimate"] = score(
        "Question: how much additional decomposition is likely needed before this idea reaches single, directly checkable requirements?",
        DEPTH_CRITERIA)
    q["scope"] = noul(SCOPE_Q_TEXT,
                       "Yes, it describes something buildable: a product, service, system or process.",
                       "No -- a personal question, opinion, or something else not shaped like something to build.")
    return q


def category_questions(lib):
    return {c["id"]: noul(
        c["text"] + "\n\nQuestion: is this NOT yet true for this idea as currently described -- i.e., is this a real, unaddressed gap?",
        "No, not yet true -- a real, unaddressed gap here.", "Yes, this is already true, or not a relevant concern here.")
        for c in lib["categories"]}


def child_questions(node_text, children):
    return {f"child::{c['id']}": noul(
        node_text + " " + c["text"] + "\n\nQuestion: given the gaps already identified so far, is this NOT yet true -- i.e., is this a real, relevant sub-gap that needs addressing?",
        "No, not yet true -- a real, relevant sub-gap here.", "Yes, this is already addressed, or not relevant given what's already identified.")
        for c in children}


def leaf_questions(leaf_text):
    prefix = leaf_text + "\n\n"
    return {
        "gate": noul(prefix + "Question: if this work item turns out harder or different than expected, does the overall design of the idea have to change shape -- not just take longer?",
                     "A surprise here would force a redesign, not just a delay.", "A surprise here would only cost time, not change the design."),
        "phase": choice(prefix + "Question: which of these best describes this work item?", PHASE_CRITERIA),
        "risk": score(prefix + "Question: if this work item is left undone or wrong, how likely is it to make the overall idea run behind schedule (delay or rework)?",
                      [f"{l} risk of schedule delay or rework" for l in LEVELS5]),
        "complexity": score(prefix + "Question: how complex is this work item to actually do?", [f"{l} complexity" for l in LEVELS5]),
        "dependency": choice(prefix + "Question: what mainly stands between this work item and being done?", DEPENDENCY_CRITERIA),
    }


def walk(text, who, models, budget, ask, lib=None):
    """The whole live run, as a generator of event dicts (see docs/custom-decomposition-design.md
    section 2.4 for the exact stream shape). Stopping iteration early (GeneratorExit, e.g. the
    client disconnected) makes no further `ask` calls -- nothing after the current `yield` runs."""
    lib = lib or load_library()
    run_id = hashlib.sha256(f"{text}|{who}|{sorted(models)}|{budget}".encode()).hexdigest()[:12]
    base_state = f"Idea: {text}" + (f"\n\nWho this is for: {who}" if who else "")
    yield {"t": "start", "run_id": run_id, "library_sha256": lib["sha256"], "models": models,
           "budget": budget, "space": SPACE, "base_state_chars": len(base_state)}

    spent, fresh_calls, cached_calls = 0, 0, 0
    seq_counter = itertools.count(1)

    def do_call(state, questions, node_id):
        nonlocal spent, fresh_calls, cached_calls
        seq = next(seq_counter)
        per_model, errors, latency_ms, cached, item = call_all_models(state, questions, models, ask)
        spent += 1
        if cached:
            cached_calls += 1
        else:
            fresh_calls += 1
        return seq, per_model, errors, latency_ms, cached, item

    # 1. Frame: domain, audience, 10 profile probes, depth estimate, scope -- one call, 14 questions.
    fq = frame_questions(lib)
    seq, per_model, errors, latency_ms, cached, item = do_call(base_state, fq, "__frame__")
    yield {"t": "call", "seq": seq, "node": "__frame__", "n_questions": len(fq), "body": {"state": base_state, "questions": fq}}
    domain_v, audience_v = combine_choice(per_model, "domain"), combine_choice(per_model, "audience")
    profile_v = {p["id"]: combine_noul(per_model, f"profile::{p['id']}") for p in lib["profile_probes"]}
    profile_means = {k: v["mean"] for k, v in profile_v.items()}
    depth_v, scope_v = combine_score(per_model, "depth_estimate"), combine_noul(per_model, "scope")
    trusted = choice_trust(domain_v) and choice_trust(audience_v)
    enrich = lib["domain_enrichment"].get(domain_v["choice"]) if (domain_v["choice"] and trusted) else None
    if enrich:
        enriched_state = (base_state +
            f"\n\nThis is a {domain_v['choice']} idea, for {audience_v['choice']}."
            f" Known from similar {domain_v['choice']} ideas: pain points often include "
            f"{'; '.join(lib['pain_points'][i] for i in enrich['likely_pain_points'])}. Delights often include "
            f"{'; '.join(lib['delights'][i] for i in enrich['likely_delights'])}."
            f" The riskiest stage is usually: {lib['customer_journey'][enrich['riskiest_journey_stage']]}")
    else:
        enriched_state = base_state
    yield {"t": "frame", "seq": seq, "domain": {**domain_v, "trusted": choice_trust(domain_v)},
           "audience": {**audience_v, "trusted": choice_trust(audience_v)}, "profile": profile_v,
           "depth": depth_v, "scope": scope_v,
           "enrichment": {"applied": bool(enrich), "domain": domain_v["choice"] if enrich else None},
           "latency_ms": latency_ms, "cached": cached, "errors": errors}

    # 2. Control (doesn't count against budget): same 21 category questions on a fixed, generic
    # blank idea, so the page can show lift = how much of a category's score the user's actual
    # text caused, not just the raw (compressed) relevance number.
    spent_before_control = spent
    cq = category_questions(lib)
    control_per_model, control_errors, _, control_cached, _ = call_all_models(CONTROL_INTAKE, cq, models, ask)
    spent = spent_before_control  # explicitly not counted -- see docstring and design doc section 2.1
    if control_cached:
        cached_calls += 0  # a fully-cached control call is free either way; nothing to attribute
    control_gap = {cid: combine_noul(control_per_model, cid)["mean"] for cid in cq}
    yield {"t": "control", "seq": 0, "categories": control_gap, "cached": control_cached, "errors": control_errors}

    # 3. Categories: all 21 at once, shape-guaranteed + budget-ranked selection -- verbatim
    # mechanism from foundry/layered_walk.py's classify_root.
    seq, per_model, errors, latency_ms, cached, item = do_call(enriched_state, cq, "__categories__")
    yield {"t": "call", "seq": seq, "node": "__categories__", "n_questions": len(cq), "body": {"state": enriched_state, "questions": cq}}

    flat_models = []
    for m in models:
        vals = [per_model[m][cid]["noul"] for cid in cq if m in per_model and (per_model[m].get(cid) or {}).get("noul") is not None]
        if len(vals) >= 2 and (max(vals) - min(vals)) < FLAT_RANGE:
            flat_models.append(m)

    by_shape = {}
    cat_by_id = {c["id"]: c for c in lib["categories"]}
    items = {}
    for cid in cq:
        gap_v = combine_noul(per_model, cid)
        lift_mean = (gap_v["mean"] - control_gap[cid]) if (gap_v["mean"] is not None and control_gap.get(cid) is not None) else None
        boost = profile_boost(cid, profile_means, lib)
        composite = W_GAP * (gap_v["mean"] or 0) + W_PROFILE * min(boost, 1.0)
        items[cid] = {"gap": gap_v, "lift": lift_mean, "boost": boost, "composite": composite}
        by_shape.setdefault(cat_by_id[cid]["shape"] or "(untagged)", []).append(cid)

    guaranteed_ids = set()
    for shape, ids in by_shape.items():
        ranked = sorted(ids, key=lambda i: -items[i]["composite"])
        guaranteed_ids.update(ranked[:SHAPE_TOPK])

    seeds = []  # (priority, category_id)
    for cid, it in items.items():
        it["guaranteed"] = cid in guaranteed_ids
        priority = it["composite"] + (GUARANTEED_BONUS if it["guaranteed"] else 0.0)
        seeds.append((priority, cid))
    seeds.sort(key=lambda s: -s[0])
    for rank, (priority, cid) in enumerate(seeds, start=1):
        items[cid]["queue_rank"] = rank

    yield {"t": "categories", "seq": seq, "items": items, "flat_models": flat_models,
           "latency_ms": latency_ms, "cached": cached, "errors": errors}

    # 4. Drain one shared max-priority queue -- budget is the only real cutoff, no fixed top-k at
    # any level. Verbatim mechanism from foundry/layered_walk.py's run_walk/process_node.
    counter = itertools.count()
    heap = []
    for priority, cid in seeds:
        heapq.heappush(heap, (-priority, next(counter), cid, None, []))  # (neg-priority, tiebreak, id, parent_id, breadcrumb)

    consecutive_no_answer = 0
    reason = "exhausted"
    visited_leaves = 0
    frontier = []

    while heap:
        if spent >= budget:
            reason = "budget"
            break
        _, _, node_id, parent_id, breadcrumb = heapq.heappop(heap)
        node = cat_by_id.get(node_id)
        is_category = node is not None
        if is_category:
            node_text, children = node["text"], node["children"]
        else:
            # a leaf id -- find it under its parent category
            parent = cat_by_id[parent_id]
            node = next(c for c in parent["children"] if c["id"] == node_id)
            node_text, children = node["text"], []

        state = enriched_state + ("\n\nGaps already identified for this idea (confirmed NOT yet true, i.e. real, unaddressed gaps so far): " + "; ".join(breadcrumb) if breadcrumb else "")

        if children or is_category and not children:
            # category node (may have zero children in a malformed library entry -- still a category, not a leaf)
            cqs = child_questions(node_text, children)
            if not cqs:
                yield {"t": "node", "seq": 0, "id": node_id, "kind": "category", "children": {}, "errors": {}, "status": "no_children"}
                continue
            seq, per_model_n, errors_n, latency_n, cached_n, item_n = do_call(state, cqs, node_id)
            yield {"t": "call", "seq": seq, "node": node_id, "kind": "category", "n_questions": len(cqs), "body": {"state": state, "questions": cqs}}
            child_results = {}
            any_answer = False
            for c in children:
                v = combine_noul(per_model_n, f"child::{c['id']}")
                pushed = v["mean"] is not None and v["mean"] >= CHILD_MIN_SANITY
                child_results[c["id"]] = {"rel": v, "pushed": pushed}
                if v["mean"] is not None:
                    any_answer = True
                if pushed:
                    heapq.heappush(heap, (-v["mean"], next(counter), c["id"], node_id, breadcrumb + [node_text]))
                else:
                    frontier.append((0.0, c["id"], node_id))
            consecutive_no_answer = 0 if any_answer else consecutive_no_answer + 1
            yield {"t": "node", "seq": seq, "id": node_id, "kind": "category", "children": child_results,
                   "latency_ms": latency_n, "cached": cached_n, "errors": errors_n}
        else:
            leaf_state = state + " Specifically, not yet true: " + node_text + "\n\nWork item: make this requirement true for this idea."
            lqs = leaf_questions(node_text)
            seq, per_model_n, errors_n, latency_n, cached_n, item_n = do_call(leaf_state, lqs, node_id)
            yield {"t": "call", "seq": seq, "node": node_id, "kind": "leaf", "parent": parent_id, "n_questions": len(lqs), "body": {"state": leaf_state, "questions": lqs}}
            gate_v, risk_v, complexity_v = combine_noul(per_model_n, "gate"), combine_score(per_model_n, "risk"), combine_score(per_model_n, "complexity")
            phase_v, dependency_v = combine_choice(per_model_n, "phase"), combine_choice(per_model_n, "dependency")
            answers = {"gate": gate_v, "risk": risk_v, "complexity": complexity_v, "phase": phase_v, "dependency": dependency_v}
            any_answer = any(v.get("mean") is not None or v.get("choice") is not None for v in answers.values())
            consecutive_no_answer = 0 if any_answer else consecutive_no_answer + 1
            split = [k for k, v in answers.items() if (noul_split(v) if k in ("gate", "risk", "complexity") else choice_split(v))]
            status = "no_answer" if not any_answer else "ok"
            if any_answer:
                visited_leaves += 1
            yield {"t": "node", "seq": seq, "id": node_id, "kind": "leaf", "parent": parent_id,
                   "answers": answers, "split": split, "status": status,
                   "latency_ms": latency_n, "cached": cached_n, "errors": errors_n}

        if consecutive_no_answer >= 3:
            reason = "all_failed"
            break
    else:
        reason = "exhausted" if not heap else reason

    frontier_out = [{"id": nid, "kind": "leaf" if pid else "category", "priority": p}
                     for p, nid, pid in sorted(frontier, key=lambda x: -x[0])[:20]]
    # also include whatever's still on the heap, unvisited
    remaining = sorted(heap)
    for neg_p, _, nid, pid, _ in remaining[:20]:
        frontier_out.append({"id": nid, "kind": "leaf" if pid else "category", "priority": -neg_p})

    yield {"t": "end", "spent": spent, "budget": budget, "fresh_calls": fresh_calls,
           "cached_calls": cached_calls, "reason": reason, "frontier": frontier_out}


# ---------- CLI ----------

def _cli_ask(server_mod):
    def ask(model, item):
        return server_mod.one_item(model, server_mod.BACKENDS[model], item)
    return ask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-file")
    ap.add_argument("--intake", help="a foundry/ideas/<id>.json file -- reads its idea+customer fields")
    ap.add_argument("--who", default="")
    ap.add_argument("--models", required=True, help="comma-separated backend ids, e.g. semif,kev-4b,so1")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.intake:
        data = json.loads(Path(a.intake).read_text())
        text, who = data["idea"], data.get("customer", a.who)
    elif a.text_file:
        text, who = Path(a.text_file).read_text().strip(), a.who
    else:
        sys.exit("need --text-file or --intake")
    text = text[:MAX_TEXT]

    models = [m.strip() for m in a.models.split(",") if m.strip()]

    sys.path.insert(0, str(ROOT / "demo"))
    import server  # noqa: E402 -- CLI-only; the live server path never imports this module the other way

    for m in models:
        cfg = server.BACKENDS.get(m)
        if not cfg:
            sys.exit(f"unknown backend {m}")

    ask = _cli_ask(server)
    out_path = Path(a.out) if a.out else (ROOT / "data" / "probe-runs-v2" / "_custom_decompose" / f"{hashlib.sha256(text.encode()).hexdigest()[:10]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for ev in walk(text, who, models, a.budget, ask):
            f.write(json.dumps(ev) + "\n")
            if ev["t"] == "node":
                print(f"  [{ev['id']}] {ev['kind']}" + (f" -- {ev['status']}" if ev.get("status") else ""))
            elif ev["t"] == "end":
                print(f"\nspent {ev['spent']}/{ev['budget']} ({ev['fresh_calls']} fresh, {ev['cached_calls']} cached), reason={ev['reason']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
