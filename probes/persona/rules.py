"""Loads rules/*.csv and checks them. The engine, classifier and personas should read from here, never from hard-coded lists."""
import csv
from collections import defaultdict
R = "/workspace/probes/persona/rules"
def load(name): return list(csv.DictReader(open(f"{R}/{name}.csv")))
def validate():
    dials = {r["id"]: r for r in load("dials")}; els = {r["id"]: r for r in load("elements")}; decs = {r["id"] for r in load("decisions")}
    grid, wts, attrs = load("grid"), load("decision_weights"), load("dial_attributes"); q = load("element_questions"); issues = []
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
    ph = {r["dial_id"] for r in load("impact_phrases")}; cond = {d for d in dials if dials[d]["kind"] == "condition"}
    if cond - ph: issues.append(f"impact_phrases: condition dials without phrases: {sorted(cond - ph)}")
    rnames = {r["name"] for r in load("resources")}
    for d in doms:
        for x in [v for v in d.get("resources", "").split("; ") if v and v != "none"]:
            if x not in rnames: issues.append(f"domains: {d['id']} names an unknown resource {x}")
    if {r["decision_id"] for r in load("decision_phrases")} != decs: issues.append("decision_phrases: needs exactly one row per decision")
    mw = {m["mode"]: float(m["weight"]) for m in load("impact_modes")}
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
