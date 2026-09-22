#!/usr/bin/env python3
"""Decompose and loop: score every model on a reference plan (probes/decompose/tree_ref*.json)
with a typed battery per node, then check what the models are actually worth as a second reader
of a hand-authored plan: do they catch a genuine, planted coverage gap; do they split the plan to
a workable level (the loop, driven by each model's own live 'atomic' judgement); do they pick out
the same schedule-critical items the planner's CPM pass did; where do they disagree with the
planner's own risk read.

There is no Monte Carlo forecast and no "confidence" number here (an earlier version had one; it
was removed on review -- multiplying together a few models' own subjective 0-4 Likert ratings and
calling the product a probability of meeting a launch date is dressed-up subjectivity, not a
forecast: see the write-up in demo/scenarios.html's "What this page does not measure" section).
The schedule verdict instead comes from a deterministic CPM pass over authored duration estimates
and predecessor edges, computed once in build_tree_edge.py and never touched by a model.

One call per node per model (the node's whole battery in one request, like the other structures).
Local models only; the hosted backend is refused here. Writes the fully scored tree to
data/probe-runs-v2/_decompose/tree_scored.json, which server.py's /api/decompose-tree reads
directly (this structure is small enough that there's no separate per-item JSONL log; re-running
overwrites the file with all requested models included).

  python3 probes/lab_decompose.py --models kev-4b semif so1 laya verdict --tree probes/decompose/tree_ref_edge.json --out data/probe-runs-v2/_decompose/tree_scored_edge.json
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402

REF = ROOT / "probes" / "decompose" / "tree_ref.json"
OUT = ROOT / "data" / "probe-runs-v2" / "_decompose" / "tree_scored.json"
LEVELS5 = ["very low", "low", "medium", "high", "very high"]
PHASE_CRITERIA = {
    "spike": "Finding something out -- a measurement, an experiment, a check against documentation. Nothing is built or decided yet.",
    "decide": "A choice between real options that a person has to make; no new information is being gathered.",
    "build": "Writing the actual implementation, once what to build is already known.",
    "validate": "Checking that something already built actually works, at realistic scale or against a real baseline.",
    "launch": "Getting a working, validated system into production: deploy, rollback, runbook.",
}


def battery(node, dep_options, phase_options):
    """Every node gets 'atomic' -- the classifier the loop steps on: a group should score low, a
    true leaf should score high. Only root/group also get 'covers'. Only leaves get: 'gate' (does
    a bad answer here change the architecture, not just the date -- graded against the authored
    gate flag), 'phase' (which SDLC phase this is -- graded against the authored phase), plus
    risk/complexity/parallel/dependency. 'risk' is asked but never graded against a reference (the
    reference would be equally subjective); it is used only for cross-model agreement."""
    q = {"atomic": {"type": "noul", "instructions": node["text"] + "\n\nQuestion: is this a single, atomic unit of work that should be executed as one piece, not split into smaller pieces?",
                     "criteria": {"true": "A single indivisible unit of work.", "false": "Really a group of smaller pieces of work."}}}
    if node["kind"] in ("root", "group"):
        q["covers"] = {"type": "noul", "instructions": node["text"] + "\n\nQuestion: do the listed child items, taken together, fully cover what this requirement needs? Answer no if something the requirement calls for is missing, or not yet actually delivered by the children as things stand today.",
                        "criteria": {"true": "The children, taken together, fully cover the requirement as it stands today.", "false": "Something the requirement needs is missing from the children, or not yet actually delivered by them."}}
        return q
    q.update({
        "gate": {"type": "noul", "instructions": node["text"] + "\n\nQuestion: if this item's answer comes back the opposite of what is currently assumed, does the overall architecture have to change shape -- not just take longer?",
                 "criteria": {"true": "A surprising answer here would force a redesign, not just a delay.", "false": "A surprising answer here would only cost time, not change the design."}},
        "phase": {"type": "choice", "instructions": node["text"] + "\n\nQuestion: which of these best describes this item?", "criteria": PHASE_CRITERIA},
        "risk": {"type": "score", "instructions": node["text"] + "\n\nQuestion: if this item is left undone or wrong, how likely is it to make the overall plan run behind schedule (delay or rework)?",
                 "criteria": [f"{l} risk of schedule delay or rework" for l in LEVELS5]},
        "complexity": {"type": "score", "instructions": node["text"] + "\n\nQuestion: how complex is this item to actually do?",
                       "criteria": [f"{l} complexity" for l in LEVELS5]},
        "parallel": {"type": "noul", "instructions": node["text"] + "\n\nQuestion: can this item be worked on in parallel with the other items in its group, without waiting for one of them to finish first?",
                     "criteria": {"true": "Can proceed independently of its siblings.", "false": "Has to wait on a sibling first."}},
        "dependency": {"type": "choice", "instructions": node["text"] + "\n\nQuestion: what mainly stands between this item and being done?",
                       "criteria": {"none": "Nothing external; it just needs to be built.", "needs-user-decision": "It is blocked on a decision only the user can make.",
                                    "needs-other-item": "It depends on another item in this plan finishing first.", "needs-external-check": "It depends on an external resource or check (e.g. data access) not yet confirmed."}},
    })
    return q


def grade(node, answers):
    g = {}
    a = (answers.get("atomic") or {}).get("noul")
    if a is not None:
        g["atomic_p"] = a
        if node["atomic_ref"] is not None:  # root has none
            g["atomic_correct"] = (a >= 0.5) == node["atomic_ref"]
    if node["kind"] in ("root", "group"):
        p = (answers.get("covers") or {}).get("noul")
        if p is not None and node["covers_ref"] is not None:
            g["covers_p"] = p
            g["covers_correct"] = (p >= 0.5) == node["covers_ref"]
        return g
    gate = (answers.get("gate") or {}).get("noul")
    if gate is not None:
        g["gate_p"] = gate; g["gate_correct"] = (gate >= 0.5) == bool(node.get("gate"))
    phase = answers.get("phase") or {}
    if phase.get("choice") is not None:
        g["phase_pred"] = phase["choice"]; g["phase_correct"] = phase["choice"] == node.get("phase")
    par = (answers.get("parallel") or {}).get("noul")
    if par is not None:
        g["parallel_p"] = par; g["parallel_correct"] = (par >= 0.5) == node["parallel_ref"]
    risk = (answers.get("risk") or {}).get("score")
    if risk is not None:
        g["risk_0to1"] = risk / (len(LEVELS5) - 1)  # never graded against a reference -- see module docstring
    comp = (answers.get("complexity") or {}).get("score")
    if comp is not None:
        g["complexity_0to1"] = comp / (len(LEVELS5) - 1)
        g["complexity_abs_error"] = abs(g["complexity_0to1"] - node["complexity_ref"])
    dep = answers.get("dependency") or {}
    if dep.get("choice") is not None:
        g["dependency_pred"] = dep["choice"]; g["dependency_correct"] = dep["choice"] == node["dependency_ref"]
    return g


def score_model(model, cfg, ref):
    nodes = ref["nodes"]
    scored = []
    for node in nodes:
        q = battery(node, ref["dep_options"], ref.get("phase_options", []))
        r = server.call(model, cfg, {"state": node["text"], "model": "jev-latest", "questions": q}, whole=True)
        if "error" in r:
            scored.append({**node, "error": r["error"]}); continue
        answers = r.get("answers") or {}
        scored.append({**node, "answers": answers, "grade": grade(node, answers)})
    return scored


def simulate_loop(scored_nodes, threshold=0.6, max_depth=6):
    """The actual loop: starting at root, walk down; at each node ask the model's own live
    'atomic' judgement (already scored, not re-asked). If atomic_p >= threshold, stop here --
    that node becomes a pseudo-atomic stopping point for this model, whether or not the reference
    tree goes deeper. Otherwise expand into its real children (the planner's split is fixed and
    hand-authored; only the stop/continue decision is the model's own). Caps at max_depth as a
    safety valve for a model that never says yes."""
    by_id = {n["id"]: n for n in scored_nodes}
    children = {}
    for n in scored_nodes:
        children.setdefault(n["parent"], []).append(n["id"])
    stops, premature = [], []
    def walk(nid, depth):
        node = by_id[nid]
        p = (node.get("grade") or {}).get("atomic_p")
        kids = children.get(nid, [])
        stop = (p is not None and p >= threshold) or not kids or depth >= max_depth
        if stop:
            stops.append({"id": nid, "title": node["title"], "depth": depth, "atomic_p": p, "kind": node["kind"], "is_real_leaf": node["kind"] == "leaf"})
            if node["kind"] != "leaf" and p is not None and p >= threshold:
                premature.append({"id": nid, "title": node["title"], "depth": depth, "atomic_p": p})
            return
        for k in kids:
            walk(k, depth + 1)
    walk("root", 0)
    depths = [s["depth"] for s in stops]
    return {"stops": stops, "premature": premature, "n_stops": len(stops),
            "avg_depth": round(sum(depths) / len(depths), 2) if depths else None,
            "max_depth_hit": sum(1 for s in stops if s["depth"] >= max_depth and not s["is_real_leaf"])}


def gate_pick(scored_nodes):
    """Does this model's own highest-risk leaf happen to be one of the planner's authored gates?
    A small, honest measure of whether the model's judgement lines up with the planner's -- not a
    claim that either is right."""
    leaves = [n for n in scored_nodes if n["kind"] == "leaf" and "grade" in n and "risk_0to1" in n["grade"]]
    if not leaves:
        return None
    top = max(leaves, key=lambda n: n["grade"]["risk_0to1"])
    return {"id": top["id"], "title": top["title"], "risk": round(top["grade"]["risk_0to1"], 2), "is_gate": bool(top.get("gate"))}


def pairwise_agreement(all_scored):
    """Share of leaf pairs that every pair of models ranks in the same relative order by 'risk'.
    Needs no ground truth (there isn't one for a subjective rating) -- it only measures whether
    the models agree with each other, which is itself information."""
    models = list(all_scored.keys())
    leaves_by_model = {m: {n["id"]: n["grade"]["risk_0to1"] for n in all_scored[m] if n["kind"] == "leaf" and "grade" in n and "risk_0to1" in n["grade"]} for m in models}
    common = set.intersection(*(set(v) for v in leaves_by_model.values())) if leaves_by_model else set()
    common = sorted(common)
    out = {}
    for i, m1 in enumerate(models):
        agree, total = 0, 0
        for m2 in models:
            if m2 == m1:
                continue
            for a in range(len(common)):
                for b in range(a + 1, len(common)):
                    x, y = common[a], common[b]
                    d1 = leaves_by_model[m1][x] - leaves_by_model[m1][y]
                    d2 = leaves_by_model[m2][x] - leaves_by_model[m2][y]
                    if d1 == 0 or d2 == 0:
                        continue
                    total += 1
                    if (d1 > 0) == (d2 > 0):
                        agree += 1
        out[m1] = round(agree / total, 3) if total else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tree", type=Path, default=REF)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    ref = json.loads(a.tree.read_text())
    out = {"generated_from": str(a.tree), "pitch": ref.get("pitch"), "schedule": ref.get("schedule"),
           "horizon_working_days": ref.get("horizon_working_days"), "days_per_week": ref.get("days_per_week"),
           "out_of_scope_v1": ref.get("out_of_scope_v1"), "models": {}}
    all_scored = {}
    for model in a.models:
        cfg = server.BACKENDS[model]
        if cfg.get("hosted"):
            print(f"skipping {model}: hosted model runs only through the UI"); continue
        print(f"scoring {model} ({len(ref['nodes'])} nodes)...")
        scored = score_model(model, cfg, ref)
        all_scored[model] = scored
        loop = simulate_loop(scored)
        pick = gate_pick(scored)
        n_ok = sum(1 for n in scored if "error" not in n)
        out["models"][model] = {"nodes": scored, "loop": loop, "gate_pick": pick, "n_ok": n_ok, "n_failed": len(scored) - n_ok}
        print(f"  {n_ok}/{len(scored)} nodes answered; loop stopped at {loop['n_stops']} pseudo-atomic points, avg depth {loop['avg_depth']}, "
              f"{len(loop['premature'])} premature"
              + (f"; top-risk pick '{pick['title']}' is{'' if pick['is_gate'] else ' NOT'} a gate" if pick else ""))
    agreement = pairwise_agreement(all_scored) if all_scored else {}
    for m in out["models"]:
        out["models"][m]["risk_agreement"] = agreement.get(m)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
