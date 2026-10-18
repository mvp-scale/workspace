"""Write exports/world-engine-ontology.yaml: every element with its name and what it moves next, left to right
(topic -> condition -> person state -> decision -> resource), plus places and story labels. No data tables.
Reads exports/world-engine-ontology-rules_v2.json and exports/world-engine-labels.json (run tools/export_ontology.py first). Run from /workspace."""
import json, re

J = json.load(open("exports/world-engine-ontology-rules_v2.json")); T = J["complete"]["rule_tables"]; L = json.load(open("exports/world-engine-labels.json"))
name = {k: {x["id"]: x["name"] for x in L[k]} for k in ("topics", "conditions", "person_states", "decisions", "resources")}
q = lambda s: ('"' + str(s).replace('"', "'") + '"') if re.search(r"[:#\[\]{},&*!|>'\"%@`]|^\s|\s$|^(yes|no|true|false|null)$", str(s), re.I) else str(s)
sg = lambda w: f"+{abs(w):g}" if w >= 0 else f"-{abs(w):g}"
o = ["# World engine ontology: what each element is, and what it moves next.",
     "# Read it left to right:  story -> topic -> condition -> person state -> decision -> resource",
     "#   topic:        what a story is about",
     "#   condition:    a level of the world that stories push up or down (each is the level of one resource)",
     "#   person state: how a person feels or is placed; conditions move it",
     "#   decision:     what a person might do; person states make it more or less likely",
     "#   resource:     what the world runs on; conditions and states depend on it, decisions draw on or build it",
     "# Signs: + raises, - lowers. Numbers are link strengths, hand-set guesses until fitted against outcomes.",
     "# Places: a story enters the world or a country, then spreads to that country's cities, towns and rural areas.",
     "# Generated from probes/persona/rules_v2 by tools/export_ontology_yaml.py; labels match the running engine.", "",
     "flow: [topics, conditions, person_states, decisions, resources]", ""]
o.append("topics:            # topic -> conditions it can move")
for t in T["domains"]:
    if t["id"] not in name["topics"]: continue
    ds = [d for d in (t.get("dials") or "").split("; ") if d]; o += [f"  {t['id']}:", f"    name: {q(t['name'])}", f"    moves: [{', '.join(ds)}]"]
o += ["", "conditions:        # condition -> person states it moves; other conditions it pushes; the resource it is a level of"]
for c in T["dials"]:
    o += [f"  {c['id']}:", f"    name: {q(c['name'])}"]
    ms = [g for g in T["grid"] if g["dial_id"] == c["id"]]
    if ms: o.append("    moves:"); o += [f"      {g['element_id']}: {sg(g['strength'])}" for g in ms]
    ts = [x for x in T["dial_ties"] if x["from_dial"] == c["id"]]
    if ts: o.append("    pushes:"); o += [f"      {x['to_dial']}: {sg(x['strength'])}" for x in ts]
    r = next((x for x in T["dial_resources"] if x["dial_id"] == c["id"]), None)
    if r: o.append(f"    level_of: {r['resource_id']}        # higher = {q(r['up_means'])}")
o += ["", "person_states:     # person state -> decisions it makes more (+) or less (-) likely; resources it depends on"]
for e in T["elements"]:
    o += [f"  {e['id']}:", f"    name: {q(e['name'])}"]
    ds = [w for w in T["decision_weights"] if w["element_id"] == e["id"]]
    if ds: o.append("    drives:"); o += [f"      {w['decision_id']}: {sg(w['weight'])}" for w in ds]
    rs = [x for x in T["element_resources"] if x["element_id"] == e["id"]]
    if rs: o.append("    depends_on: [" + ", ".join(x["resource_id"] for x in rs) + "]")
    if not ds and not rs: o.append("    # a trait: shapes people, moves no decision directly")
o += ["", "decisions:         # decision -> resources it draws on (uses up) or builds"]
for d in T["decisions"]:
    o += [f"  {d['id']}:", f"    name: {q(d['name'])}"]
    dr = [x for x in T["decision_resources"] if x["decision_id"] == d["id"] and x["direction"] == "draw"]; bu = [x for x in T["decision_resources"] if x["decision_id"] == d["id"] and x["direction"] == "build"]
    if dr: o.append("    draws_on: [" + ", ".join(x["resource_id"] for x in dr) + "]")
    if bu: o.append("    builds: [" + ", ".join(x["resource_id"] for x in bu) + "]")
o += ["", "resources:         # end of the chain: what the world runs on"]
for r in T["resources"]: o += [f"  {r['id']}: {q(r['name'])}"]
o += ["", "places:            # where a story lands and spreads", "  world: World", "  countries:        # " + str(len(L["countries"])) + ", by id"]
o += [f"    {c['id']}: {q(c['name'])}" for c in L["countries"]]
o += ["  settlement_types:  # each country splits into these", *[f"    {s['id']}: {q(s['name'])}" for s in L["settlement_types"]],
      "  audiences:        # groups of people with similar traits; they cut across countries and scale how much a story is felt", *[f"    a{a['id']}: {q(a['name'])}" for a in L["audiences"]],
      "", "story_labels:      # what the reader decides about each story before it moves anything",
      "  types: [" + ", ".join(x["id"] for x in L["story_types"]) + "]", "  scope: [" + ", ".join(x["id"] for x in L["story_scope"]) + "]",
      "  impact_levels: [" + ", ".join(x["id"] for x in L["impact_levels"]) + "]", "  impact_modes: [" + ", ".join(x["id"] for x in L["impact_modes"]) + "]"]
open("exports/world-engine-ontology.yaml", "w").write("\n".join(o) + "\n"); print("exports/world-engine-ontology.yaml:", len(o), "lines")
