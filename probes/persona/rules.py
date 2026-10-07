"""Loads rules/*.csv and checks them. The engine, classifier and personas should read from here, never from hard-coded lists."""
import csv, os
from collections import defaultdict
# WE_RULES picks the ontology: "rules" (default, v1) or "rules_v2" (a folder name under persona/, or an absolute path). This is the ONE place it is read; every loader goes through load().
BASE = "/workspace/probes/persona"; RULES = os.environ.get("WE_RULES", "rules").strip() or "rules"
R = RULES if os.path.isabs(RULES) else f"{BASE}/{RULES}"; V1 = f"{BASE}/rules"; IS_V1 = os.path.abspath(R) == os.path.abspath(V1)
SHARED = ("impact_levels", "impact_modes", "type_weights")      # tables keyed by size level, mode or story type (not by ontology ids): a ruleset without its own copy uses v1's
def exists(name): return os.path.exists(f"{R}/{name}.csv")
def load(name):
    p = f"{R}/{name}.csv"
    if not os.path.exists(p) and name in SHARED: p = f"{V1}/{name}.csv"
    return list(csv.DictReader(open(p)))
def load_opt(name):
    """Like load(), but a table the active ruleset does not have (yet) is an empty list, so a half-built ruleset still boots."""
    return load(name) if exists(name) or name in SHARED else []
SOWHAT = ("sowhat_frames", "sowhat_lexicon", "sowhat_templates")      # the So-what tables (frames, words, sentence templates); a ruleset without them (v1) has no story beats
def sowhat_tables(rules=None):
    """The three So-what tables of the active ruleset (or of the folder `rules`) as lists of rows; every one is [] when the ruleset has no So-what tables."""
    d = R if rules is None else (rules if os.path.isabs(rules) else f"{BASE}/{rules}")
    return {n[7:]: (list(csv.DictReader(open(f"{d}/{n}.csv"))) if os.path.exists(f"{d}/{n}.csv") else []) for n in SOWHAT}
SOWHAT2 = ("frames", "hooks", "templates", "lexicon")      # v2 tables: sowhat2_<name>.csv (spec/so-what-v2-contract.md)
def sowhat_version(rules=None):
    """2 when the active ruleset (or folder `rules`) has sowhat2_frames.csv, 1 when it has the v1 So-what tables, else 0."""
    d = R if rules is None else (rules if os.path.isabs(rules) else f"{BASE}/{rules}")
    return 2 if os.path.exists(f"{d}/sowhat2_frames.csv") else 1 if os.path.exists(f"{d}/sowhat_frames.csv") else 0
def sowhat2_tables(rules=None):
    """The So-what v2 tables as lists of rows, plus `lexicon_v1` (sowhat_lexicon.csv: conditions, places, audiences, who bands, read by the v2 composer); {} when the ruleset has no v2 tables."""
    if sowhat_version(rules) != 2: return {}
    d = R if rules is None else (rules if os.path.isabs(rules) else f"{BASE}/{rules}")
    rd = lambda n: list(csv.DictReader(open(f"{d}/{n}.csv"))) if os.path.exists(f"{d}/{n}.csv") else []
    return {**{n: rd(f"sowhat2_{n}") for n in SOWHAT2}, "lexicon_v1": rd("sowhat_lexicon")}
def sowhat_serve(rules=None):
    """What GET /sowhat sends: the v2 tables (version 2) when the ruleset has them, else the v1 tables (version 1), else empty (version 1, available false)."""
    t2 = sowhat2_tables(rules)
    if t2: return {"version": 2, "available": bool(t2["frames"]), **t2}
    t = sowhat_tables(rules); return {"version": 1, "available": bool(t["frames"]), **t}
def _up_means(text):
    t = (text or "").strip().lower()
    return t if t in ("strain", "build") else "strain" if t.endswith("(bad)") else "build" if "(good" in t else "neutral"
def dial_resources():
    """Each condition and the resource it is a level of: dial_resources.csv if the ruleset has one (v1), else derived from dials.csv `resource_id` and `up_means` (v2: '(bad)' = strain, '(good...)' = build, '(neutral)' = neutral)."""
    if exists("dial_resources"): return load("dial_resources")
    return [{"dial_id": r["id"], "resource_id": r["resource_id"], "role": "level_of", "up_means": _up_means(r.get("up_means")), "why": "", "status": "derived"} for r in load("dials") if r.get("resource_id")]
def topic_resources():
    """topic id -> resource ids, joined by id. Derived from each topic's conditions' resource_id (first appearance order) when the ruleset links conditions to resources (dials.csv resource_id, or v1's dial_resources.csv);
    the domains `resources` column is only used when there is no condition link at all (it is matched to resource ids, and to names for the old v1 column)."""
    res = load("resources"); ids = {r["id"] for r in res}; byname = {r["name"].lower(): r["id"] for r in res}; d2r = {r["dial_id"]: r["resource_id"] for r in dial_resources()}; out = {}
    derive = any(r.get("resource_id") for r in load("dials"))
    for d in load("domains"):
        if derive: out[d["id"]] = list(dict.fromkeys(d2r[x] for x in (v for v in d.get("dials", "").split("; ") if v) if x in d2r))
        else: out[d["id"]] = list(dict.fromkeys(byname.get(x.lower(), x) for x in (v for v in d.get("resources", "").split("; ") if v and v != "none") if x in ids or x.lower() in byname))
    return out
def validate():
    dials = {r["id"]: r for r in load("dials")}; els = {r["id"]: r for r in load("elements")}; decs = {r["id"] for r in load("decisions")}
    grid, wts, attrs = load("grid"), load("decision_weights"), load_opt("dial_attributes"); q = load_opt("element_questions"); issues = []
    for g in grid:
        if g["dial_id"] not in dials: issues.append(f"grid: unknown dial {g['dial_id']}")
        if g["element_id"] not in els: issues.append(f"grid: unknown element {g['element_id']}")
        if not g["why"].strip(): issues.append(f"grid: no reason for {g['element_id']} <- {g['dial_id']}")
    for x in wts:
        if x["decision_id"] not in decs or x["element_id"] not in els: issues.append(f"weights: unknown id {x}")
    per_dial, per_el = defaultdict(list), defaultdict(list)
    for g in grid: per_dial[g["dial_id"]].append(g["element_id"]); per_el[g["element_id"]].append(g["dial_id"])
    flags = {"identity-like cells (dial and element are the same construct)": [f"{g['element_id']} <- {g['dial_id']} ({g['strength']})" for g in grid if "identity" in g["status"]],
             "dials touching fewer than 2 elements (computed or media dials excepted)": [d for d in dials if dials[d]["kind"] == "condition" and len(per_dial[d]) < 2],
             "dials touching more than 4 elements": [d for d in dials if len(per_dial[d]) > 4],
             "elements no dial reaches (they act only through decision weights; fine for fixed traits)": [e for e in els if not per_el[e]],
             "decisions driven by fewer than 4 elements": [d for d in decs if sum(1 for x in wts if x["decision_id"] == d) < 4],
             "dials still without attributes": sorted({a["dial_id"] for a in attrs if a["attribute"] == "todo"}),
             "elements with fewer questions written than the target": [f"{e} ({sum(1 for r in q if r['element_id'] == e)} of {els[e]['n_questions_target']})" for e in els if int(els[e]["n_questions_target"]) > sum(1 for r in q if r["element_id"] == e)],
             "cells marked contested or weak (hold at zero until data)": [f"{g['element_id']} <- {g['dial_id']}" for g in grid if "contested" in g["status"] or "weak" in g["status"]]}
    doms = load("domains"); ids = [d["id"] for d in doms]
    if len(ids) != len(set(ids)): issues.append("domains: duplicate id")
    if "other" not in ids: issues.append("domains: the 'other' review bucket is missing")
    for d in doms:
        if not d["definition"].strip() or not d["status"].strip(): issues.append(f"domains: {d['id']} needs a definition and a status")
    for d in doms:
        for x in [v for v in d.get("dials", "").split("; ") if v]:
            if x not in dials: issues.append(f"domains: {d['id']} names an unknown dial {x}")
    ph = {r["dial_id"] for r in load_opt("impact_phrases")}; cond = {d for d in dials if dials[d]["kind"] == "condition"}
    if cond - ph: issues.append(f"impact_phrases: condition dials without phrases: {sorted(cond - ph)}")
    rnames = {r["name"] for r in load("resources")} | {r["id"] for r in load("resources")}
    for d in doms:
        for x in [v for v in d.get("resources", "").split("; ") if v and v != "none"]:
            if x not in rnames: issues.append(f"domains: {d['id']} names an unknown resource {x}")
    if exists("decision_phrases") and {r["decision_id"] for r in load("decision_phrases")} != decs: issues.append("decision_phrases: needs exactly one row per decision")
    # resource links (rules/dial_resources, element_resources, decision_resources, decision_stakes): every condition, person state and decision reaches a resource, every resource is reached
    import os
    if os.path.exists(f"{R}/dial_resources.csv"):
        res = {r["id"] for r in load("resources")}; dr, er, xr, ks = load("dial_resources"), load("element_resources"), load("decision_resources"), load("decision_stakes")
        for name, rows, key, ids in (("dial_resources", dr, "dial_id", set(dials)), ("element_resources", er, "element_id", set(els)), ("decision_resources", xr, "decision_id", decs)):
            for x in rows:
                if x[key] not in ids: issues.append(f"{name}: unknown id {x[key]}")
                if x["resource_id"] not in res: issues.append(f"{name}: unknown resource {x['resource_id']}")
                if not x["why"].strip() or x["status"] != "guess": issues.append(f"{name}: {x[key]} -> {x['resource_id']} needs a why and status guess")
            miss = sorted(ids - {x[key] for x in rows})
            if miss: issues.append(f"{name}: no resource reached from {miss}")
        for name, rows, w in (("element_resources", er, "weight"), ("decision_resources", xr, "weight")):
            for x in rows:
                if x[w] not in ("0.2", "0.5", "0.8"): issues.append(f"{name}: weight must be 0.2, 0.5 or 0.8 ({x})")
        if any(x["direction"] not in ("draw", "build") for x in xr): issues.append("decision_resources: direction must be draw or build")
        if any(x["up_means"] not in ("strain", "build") for x in dr + er): issues.append("dial/element_resources: up_means must be strain or build")
        if any(x["role"] != "level_of" for x in dr) or len({x["dial_id"] for x in dr}) != len(dr): issues.append("dial_resources: each condition must be a level of exactly one resource")
        if {x["decision_id"] for x in ks} != decs or any(not 1 <= int(x["stakes"]) <= 5 for x in ks): issues.append("decision_stakes: one row per decision, stakes 1..5")
        unreached = sorted(res - {x["resource_id"] for x in dr + er + xr})
        if unreached: issues.append(f"resources: not reached by any condition, state or decision: {unreached}")
    for t in load_opt("dial_ties"):
        if t["from_dial"] not in dials or t["to_dial"] not in dials: issues.append(f"dial_ties: unknown condition in {t['from_dial']} -> {t['to_dial']}")
        elif t["from_dial"] == t["to_dial"] or not 0 < abs(float(t["strength"])) < 1: issues.append(f"dial_ties: {t['from_dial']} -> {t['to_dial']} must be a different condition and |strength| between 0 and 1")
    mw = {m["mode"]: float(m["weight"]) for m in load("impact_modes")}
    lv = [(r["id"], float(r["multiplier"])) for r in load("impact_levels")]
    if dict(lv).get("notable") != 1.0: issues.append("impact_levels: 'notable' must stay 1.0 so ordinary stories keep their old numbers")
    if [m for _, m in lv] != sorted(m for _, m in lv): issues.append("impact_levels: multipliers must rise from minor to extreme")
    if mw.get("reported") != 1.0: issues.append("impact_modes: 'reported' must stay 1.0 so reported stories keep their old numbers")
    tws = {t["type"]: float(t["weight"]) for t in load("type_weights")}
    if tws.get("fact") != 1.0: issues.append("type_weights: 'fact' must stay 1.0 so counted stories keep their old numbers")
    if any(not 0 <= v <= 1 for v in tws.values()): issues.append("type_weights: weights must be between 0 and 1")
    return {"dials": len(dials), "elements": len(els), "grid_cells_nonzero": len(grid), "grid_size": f"{len(els)} x {len(dials)}", "decisions": len(decs), "decision_weights": len(wts), "issues": issues, "flags": flags}
if __name__ == "__main__":
    r = validate()
    print(f"{r['elements']} elements x {r['dials']} dials; {r['grid_cells_nonzero']} filled grid cells of {r['elements']*r['dials']}; {r['decisions']} decisions with {r['decision_weights']} weights")
    print("hard errors:", r["issues"] or "none")
    for k, v in r["flags"].items(): print(f"- {k}: {v if v else 'none'}")
