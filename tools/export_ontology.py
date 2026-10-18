"""Export the World engine's complete ontology as one shareable JSON file: every rule table in full (all rows, all columns), the place and people
tables, the full question battery word for word, the rules that live in code (thresholds, spread through places, decay), and a derived graph view.
Reads probes/persona/<WE_RULES, default rules_v2> and probes/world-engine/data; settlement types and audiences come from the running engine's
/graph when it answers (they are built at start-up). Writes exports/world-engine-ontology-<ruleset>.json.
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
# ---- complete: every table in full, the question battery, the rules in code
def table(path): return [{k: num(v) if v not in ("", None) else None for k, v in r.items()} for r in csv.DictReader(open(path, encoding="utf-8"))]
rule_tables = {f[:-4]: table(os.path.join(R, f)) for f in sorted(os.listdir(R)) if f.endswith(".csv")}
v1 = os.path.join(ROOT, "probes/persona/rules")
for f in ("type_weights.csv",):                      # tables the ruleset does not have; the engine falls back to v1's copy
    if f[:-4] not in rule_tables and os.path.exists(os.path.join(v1, f)): rule_tables[f[:-4]] = table(os.path.join(v1, f)); rule_tables[f[:-4] + "__note"] = "from probes/persona/rules (v1): " + RULESET + " has no copy, so the engine uses this one"
DATA = os.path.join(ROOT, "probes/world-engine/data")
place_tables = {f[:-4]: table(os.path.join(DATA, f)) for f in ("countries_world100.csv", "factors.csv", "segment_exposure.csv")}
questions, constants = None, {}
try:
    os.environ.setdefault("WE_RULES", RULESET); sys.path.insert(0, os.path.join(ROOT, "probes/world-engine")); import classify as C
    questions = {k: C.QS[k] for k in sorted(C.QS)}
    constants["reading"] = {"attribute_min": C.ATTR_MIN, "yes": C.YES, "expected_min": C.EXPECT_MIN, "expected_top": C.EXPECT_TOP,
                            "rule": "a condition moves when, for one direction only, an attribute's two wordings average >= attribute_min; both directions = conflict (no move)"}
except Exception as e: questions = f"not exported: {type(e).__name__}: {e}"
constants["places"] = {"chain": "world -> each country -> its metro, town and rural parts", "world_to_country_gain": 0.6, "world_to_country_gate": 0.003,
                       "country_to_settlement_gain": "1 + 0.1 x noise per condition, clipped to 0.7..1.3 (fixed seed 1234)", "lag_ticks": 1, "gate": 0.002, "noise_sigma": 0.05,
                       "anchor": "each country starts at its d_<condition> columns; the world is the population-weighted mean", "settlement_types": ["metro", "town", "rural"]}
constants["time"] = {"decay_per_tick": "0.5 ** (1 / half_life_ticks) per condition (conditions table)", "condition_ties": "a tie adds strength x amount to the target condition at the same place one tick later; at most 3 tie hops in a row"}
constants["feed"] = {"feed_scale": 0.5, "feed_cap": 0.4, "article_words_read": 1200, "people": 300000}
doc["complete"] = {"rule_tables": rule_tables, "place_and_people_tables": place_tables, "questions": questions, "rules_in_code": constants,
                   "where": {"rules": f"probes/persona/{RULESET}/*.csv", "places": "probes/world-engine/data/*.csv", "questions": "probes/world-engine/classify.py (from dial_attributes.csv + probes/persona/world_model.py GENRE, SCOPE + classify.EXTRA)",
                             "code": "probes/world-engine/engine.py, engine2.py (spread, decay), world_pop.py (people), world_service2.py (feed)"}}
doc["meta"]["sections"] = "graph view (topics ... links) is derived for reading; 'complete' holds every table in full and the rules in code"
doc["counts"] = {k: len(doc[k]) for k in ("topics", "conditions", "person_states", "decisions", "resources")} | {"countries": len(countries), "audiences": len(audiences or []), "settlement_types": len(settles or [])} | {f"links.{k}": len(v) for k, v in doc["links"].items()}
doc["counts"]["rule_tables"] = len([k for k in doc["complete"]["rule_tables"] if not k.endswith("__note")]); doc["counts"]["questions"] = len(questions) if isinstance(questions, dict) else 0
os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(OUT, f"{os.path.getsize(OUT) / 1024:.0f} KB"); print(json.dumps(doc["counts"], indent=0))
