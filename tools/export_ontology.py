"""Export the World engine's full ontology as one shareable JSON file.
Reads the ruleset CSVs (probes/persona/rules_v2 by default, or WE_RULES) and the country table; adds settlement types and audiences from the
running engine's /graph when it answers (they are built at start-up). Writes exports/world-engine-ontology-<ruleset>.json.
Run: python3 tools/export_ontology.py [--no-engine]"""
import csv, json, os, sys, subprocess, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULESET = os.environ.get("WE_RULES", "rules_v2"); R = os.path.join(ROOT, "probes/persona", RULESET)
COUNTRIES = os.path.join(ROOT, "probes/world-engine/data/countries_world100.csv")
OUT = os.path.join(ROOT, "exports", f"world-engine-ontology-{RULESET}.json")


def rows(name):
    p = os.path.join(R, name + ".csv")
    return [{k: (v if v != "" else None) for k, v in r.items()} for r in csv.DictReader(open(p, encoding="utf-8"))] if os.path.exists(p) else []


def num(v):
    try: return float(v)
    except (TypeError, ValueError): return v


def links(name, a, b, keep):
    return [{"from": r[a], "to": r[b], **{k: num(r.get(k)) for k in keep if k in r}} for r in rows(name)]


topics = rows("domains")
topic_condition = [{"from": t["id"], "to": d} for t in topics for d in (t.get("dials") or "").split("; ") if d]
countries = [{k: num(r[k]) if k in ("pop_m", "median_age", "income_k", "urban") else r[k] for k in ("id", "iso2", "iso3", "region", "name", "pop_m", "median_age", "income_k", "urban")}
             for r in csv.DictReader(open(COUNTRIES, encoding="utf-8"))]
settles, audiences, engine = None, None, "not asked"
if "--no-engine" not in sys.argv:
    try:
        g = json.load(urllib.request.urlopen("http://127.0.0.1:8112/graph", timeout=20)); settles, audiences, engine = g["places"]["settles"], g["places"]["audiences"], "answered"
    except OSError: engine = "not running: settlement types and audiences left out"
try: commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
except OSError: commit = None

doc = {
    "meta": {"name": "World engine ontology", "ruleset": RULESET, "git_commit": commit, "generated": datetime.datetime.now().isoformat(timespec="seconds"), "engine": engine,
             "chain": "topic -> condition -> person state -> decision; conditions, person states and decisions each link to resources; conditions can drive other conditions",
             "status": "Draft. Every link strength and weight is a hand-set guess until it is fitted against outcomes (each row carries its own status).",
             "sources": {"countries": "UN World Population Prospects 2024 (CC BY 3.0 IGO) and World Bank World Development Indicators (CC BY 4.0); income_k = 0.6 x GDP per person PPP (our rule). Attribute both when sharing.",
                         "rules": "Written for this project (probes/persona/" + RULESET + ")."}},
    "counts": {},
    "topics": [{k: t[k] for k in ("id", "name", "definition", "kind", "status") if k in t} for t in topics],
    "conditions": [{**{k: r[k] for k in ("id", "name", "definition", "resource_id", "up_means", "status", "grounding_series")}, "half_life_ticks": num(r["half_life_ticks"])} for r in rows("dials")],
    "person_states": [{k: r[k] for k in ("id", "name", "kind", "definition", "status")} for r in rows("elements")],
    "decisions": [{**{k: r[k] for k in ("id", "name", "status")}, "opportunity_rate": num(r["opportunity_rate"]), "bias": num(r["bias"])} for r in rows("decisions")],
    "resources": [{k: r[k] for k in ("id", "name", "group", "definition", "status")} for r in rows("resources")],
    "places": {"countries": countries, "settlement_types": settles, "audiences": audiences},
    "links": {
        "topic_condition": topic_condition,
        "condition_state": links("grid", "dial_id", "element_id", ("strength", "why", "moderated_by", "status")),
        "state_decision": links("decision_weights", "element_id", "decision_id", ("weight", "why", "status")),
        "condition_condition": links("dial_ties", "from_dial", "to_dial", ("strength", "why", "status")),
        "condition_resource": links("dial_resources", "dial_id", "resource_id", ("role", "up_means", "why", "status")),
        "state_resource": links("element_resources", "element_id", "resource_id", ("weight", "up_means", "why", "status")),
        "decision_resource": links("decision_resources", "decision_id", "resource_id", ("direction", "weight", "why", "status")),
    },
    "decision_stakes": [{"decision": r["decision_id"], "stakes": num(r["stakes"]), "why": r["why"], "status": r["status"]} for r in rows("decision_stakes")],
}
doc["counts"] = {k: len(doc[k]) for k in ("topics", "conditions", "person_states", "decisions", "resources")} | {"countries": len(countries), "audiences": len(audiences or []), "settlement_types": len(settles or [])} | {f"links.{k}": len(v) for k, v in doc["links"].items()}
os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(OUT, f"{os.path.getsize(OUT) / 1024:.0f} KB"); print(json.dumps(doc["counts"], indent=0))
