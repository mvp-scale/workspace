#!/usr/bin/env python3
"""Decompose and loop: score every model on the reference requirements tree
(probes/decompose/tree_ref.json) with a typed battery per node, then turn each leaf's risk
judgement into a Monte Carlo forecast of where the plan is likely to hit trouble, and check that
forecast against the leaf's real, held-out status (done / in_progress / blocked / not_started) --
not shown to the model.

One call per node per model (the node's whole battery in one request, like the other structures).
Local models only; the hosted backend is refused here. Writes the fully scored tree to
data/probe-runs-v2/_decompose/tree_scored.json, which server.py's /api/decompose-tree reads
directly (this structure is small enough that there's no separate per-item JSONL log; re-running
overwrites the file with all requested models included).

  python3 probes/lab_decompose.py --models kev-4b semif so1 laya verdict
  python3 probes/lab_decompose.py --models kev-4b semif so1 laya verdict --tree probes/decompose/tree_ref_edge.json --out data/probe-runs-v2/_decompose/tree_scored_edge.json

The 'true class' used for the schedule/budget forecast validation is whichever the tree
provides: 'critical_path' (bool, per node) if present, else status == 'blocked'.
"""
import argparse, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402

REF = ROOT / "probes" / "decompose" / "tree_ref.json"
OUT = ROOT / "data" / "probe-runs-v2" / "_decompose" / "tree_scored.json"
LEVELS5 = ["very low", "low", "medium", "high", "very high"]


def battery(node, dep_options):
    """Every node gets 'atomic' -- that is the classifier the loop steps on: a group should score
    low, a true leaf should score high. Only root/group also get 'covers'. Only leaves get the
    forecast questions: schedule risk (still called 'risk' in the record, worded as delay/rework)
    and a separate, directly-asked budget risk, plus complexity/parallel/dependency."""
    q = {"atomic": {"type": "noul", "instructions": node["text"] + "\n\nQuestion: is this a single, atomic unit of work that should be executed as one piece, not split into smaller pieces?",
                     "criteria": {"true": "A single indivisible unit of work.", "false": "Really a group of smaller pieces of work."}}}
    if node["kind"] in ("root", "group"):
        q["covers"] = {"type": "noul", "instructions": node["text"] + "\n\nQuestion: do the listed child items, taken together, fully cover what this requirement needs? Answer no if something the requirement calls for is missing, or not yet actually delivered by the children as things stand today.",
                        "criteria": {"true": "The children, taken together, fully cover the requirement as it stands today.", "false": "Something the requirement needs is missing from the children, or not yet actually delivered by them."}}
        return q
    q.update({
        "risk": {"type": "score", "instructions": node["text"] + "\n\nQuestion: if this item is left undone or wrong, how likely is it to make the overall plan run behind schedule (delay or rework)?",
                 "criteria": [f"{l} risk of schedule delay or rework" for l in LEVELS5]},
        "budget": {"type": "score", "instructions": node["text"] + "\n\nQuestion: if this item is left undone or wrong, how likely is it to make the overall plan cost more than planned (extra effort, compute or external spend)?",
                   "criteria": [f"{l} risk of running over budget" for l in LEVELS5]},
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
    par = (answers.get("parallel") or {}).get("noul")
    if par is not None:
        g["parallel_p"] = par; g["parallel_correct"] = (par >= 0.5) == node["parallel_ref"]
    risk = (answers.get("risk") or {}).get("score")
    if risk is not None:
        g["risk_0to1"] = risk / (len(LEVELS5) - 1)
        g["risk_abs_error"] = abs(g["risk_0to1"] - node["risk_ref"])
    budget = (answers.get("budget") or {}).get("score")
    if budget is not None:
        g["budget_0to1"] = budget / (len(LEVELS5) - 1)
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
        q = battery(node, ref["dep_options"])
        r = server.call(model, cfg, {"state": node["text"], "model": "jev-latest", "questions": q}, whole=True)
        if "error" in r:
            scored.append({**node, "error": r["error"]}); continue
        answers = r.get("answers") or {}
        scored.append({**node, "answers": answers, "grade": grade(node, answers)})
    return scored


def forecast_dim(scored_nodes, grade_key, seed, draws=4000):
    """Monte Carlo for one forecast dimension (schedule or budget): sample each leaf's 'causes
    trouble' outcome as a coin flip at the model's own score for that dimension, OR the flips up
    the tree (documented simplification: treats leaves as independent; the plan's own caveat is
    that real correlation between atoms isn't handled here)."""
    rnd = random.Random(seed)
    by_id = {n["id"]: n for n in scored_nodes}
    children = {}
    for n in scored_nodes:
        children.setdefault(n["parent"], []).append(n["id"])
    leaf_p = {n["id"]: n["grade"][grade_key] for n in scored_nodes if n["kind"] == "leaf" and "grade" in n and grade_key in n["grade"]}
    p_trouble = {}
    def sim(nid):
        if nid in p_trouble:
            return p_trouble[nid]
        node = by_id[nid]
        if node["kind"] == "leaf":
            p = leaf_p.get(nid, 0.0)
        else:
            kids = children.get(nid, [])
            hit = 0
            for _ in range(draws):
                if any(rnd.random() < sim(k) for k in kids):
                    hit += 1
            p = hit / draws if kids else 0.0
        p_trouble[nid] = p
        return p
    for n in scored_nodes:
        sim(n["id"])
    return p_trouble


def validate_dim(scored_nodes, p_trouble, grade_key, true_fn):
    """Illustrative only: with so few true-class leaves there is no statistical power here, just
    a check that the direction isn't obviously backwards."""
    leaves = [n for n in scored_nodes if n["kind"] == "leaf" and grade_key in n.get("grade", {})]
    hot = [n for n in leaves if true_fn(n)]
    other = [n for n in leaves if not true_fn(n)]
    if not hot or not other:
        return None
    wins = sum(1 for b in hot for o in other if p_trouble[b["id"]] > p_trouble[o["id"]])
    ties = sum(1 for b in hot for o in other if p_trouble[b["id"]] == p_trouble[o["id"]])
    total = len(hot) * len(other)
    auc = (wins + 0.5 * ties) / total
    return {"n_blocked": len(hot), "n_other": len(other), "auc": round(auc, 3),
            "mean_blocked": round(sum(p_trouble[b["id"]] for b in hot) / len(hot), 3),
            "mean_other": round(sum(p_trouble[o["id"]] for o in other) / len(other), 3)}


def simulate_loop(scored_nodes, threshold=0.6, max_depth=6):
    """The actual loop: starting at root, walk down; at each node ask the model's own live
    'atomic' judgement (already scored, not re-asked). If atomic_p >= threshold, stop here --
    that node becomes a pseudo-atomic stopping point for this model, whether or not the reference
    tree goes deeper. Otherwise expand into its real children (the planner's split is fixed and
    hand-authored; only the stop/continue decision is the model's own). Caps at max_depth as a
    safety valve for a model that never says yes (e.g. one that answers 'not atomic' to nearly
    everything -- see the write-up)."""
    by_id = {n["id"]: n for n in scored_nodes}
    children = {}
    for n in scored_nodes:
        children.setdefault(n["parent"], []).append(n["id"])
    stops, premature, path = [], [], []
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tree", type=Path, default=REF)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    ref = json.loads(a.tree.read_text())
    has_critical_path = any("critical_path" in n for n in ref["nodes"])
    true_fn = (lambda n: bool(n.get("critical_path"))) if has_critical_path else (lambda n: n.get("status") == "blocked")
    out = {"generated_from": str(a.tree), "pitch": ref.get("pitch"), "models": {}}
    for model in a.models:
        cfg = server.BACKENDS[model]
        if cfg.get("hosted"):
            print(f"skipping {model}: hosted model runs only through the UI"); continue
        print(f"scoring {model} ({len(ref['nodes'])} nodes)...")
        scored = score_model(model, cfg, ref)
        sched_p = forecast_dim(scored, "risk_0to1", seed=20260922)
        budget_p = forecast_dim(scored, "budget_0to1", seed=20260923)
        sched_val = validate_dim(scored, sched_p, "risk_0to1", true_fn)
        budget_val = validate_dim(scored, budget_p, "budget_0to1", true_fn)
        loop = simulate_loop(scored)
        sensitivity = sorted((n for n in scored if n["kind"] == "leaf" and "grade" in n and "risk_0to1" in n["grade"]),
                              key=lambda n: n["grade"]["risk_0to1"], reverse=True)[:5]
        n_ok = sum(1 for n in scored if "error" not in n)
        out["models"][model] = {"nodes": scored, "forecast_schedule": sched_p, "forecast_budget": budget_p,
                                 "validate_schedule": sched_val, "validate_budget": budget_val, "loop": loop,
                                 "top_risk": [{"id": n["id"], "title": n["title"], "risk": round(n["grade"]["risk_0to1"], 2)} for n in sensitivity],
                                 "n_ok": n_ok, "n_failed": len(scored) - n_ok}
        print(f"  {n_ok}/{len(scored)} nodes answered; loop stopped at {loop['n_stops']} pseudo-atomic points, avg depth {loop['avg_depth']}, "
              f"{len(loop['premature'])} premature (called a group atomic)"
              + (f"; schedule AUC {sched_val['auc']}, budget AUC {budget_val['auc']}" if sched_val and budget_val else ""))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
