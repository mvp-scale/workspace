"""Builds specs/world_state_v1.json from the ontology tables. Run: python3 -I make_spec.py"""
import csv, json
R = "/workspace/probes/persona/rules_v2/"
rd = lambda f: list(csv.DictReader(open(R + f + ".csv", encoding="utf-8")))
dials = [d for d in rd("dials") if d["kind"] == "condition"]; topics = rd("domains"); lev = rd("impact_levels"); ph = {r["dial_id"]: r for r in rd("impact_phrases")}
cond_ids = [d["id"] for d in dials]; topic_ids = [t["id"] for t in topics]
levels = [l["id"] for l in lev]
g = ["You read one short news item (a headline and a one or two sentence description) and describe what it says about the state of the world.",
     "Reply with the JSON object only. Fill four fields: topic, story_type, claim, conditions.",
     "topic: the single best topic id from the list below. Use 'other' only if nothing fits.",
     "story_type: 'fact' if the item reports something that happened or was announced; 'forecast' if mainly a prediction; 'opinion' if mainly commentary; 'unclear' otherwise.",
     "claim: the main claim of the item in one plain sentence of at most 25 words, using only what the item says.",
     "conditions: the conditions of a place that this item reports as moving, or gives a real reason to expect to move. A condition appears at most once. Use the condition ids below. direction 'up' means the condition rises as defined by its 'up' meaning; 'down' means it falls.",
     "level: how large the change is for the people affected: " + "; ".join(f"{l['id']} = {l['definition'].rstrip('.')}" for l in lev) + ".",
     "Be conservative. If the item does not clearly report or imply a change in a listed condition, leave conditions empty. Do not guess from background knowledge about the world. An item about a person, sport or entertainment with no effect on any condition has an empty list.",
     "", "TOPICS (id: meaning)"] + [f"{t['id']}: {t['name']} - {t['definition'].strip()}"[:170] for t in topics] + ["", "CONDITIONS (id: meaning | up = ... | down = ...)"] + \
    [f"{d['id']}: {d['definition'].strip()} | up = {ph.get(d['id'],{}).get('up','')} | down = {ph.get(d['id'],{}).get('down','')}"[:330] for d in dials]
schema = {"type": "object", "additionalProperties": False, "required": ["topic", "story_type", "claim", "conditions"], "properties": {
    "topic": {"type": "string", "enum": topic_ids}, "story_type": {"type": "string", "enum": ["fact", "forecast", "opinion", "unclear"]},
    "claim": {"type": "string", "maxLength": 220},
    "conditions": {"type": "array", "maxItems": 6, "items": {"type": "object", "additionalProperties": False, "required": ["condition", "direction", "level"],
        "properties": {"condition": {"type": "string", "enum": cond_ids}, "direction": {"type": "string", "enum": ["up", "down"]}, "level": {"type": "string", "enum": levels}}}}}}
ex = [("synthetic-1", "Harbor Council closes ferry terminal after storm. The council of the fictional town of Varnel said the old terminal will stay shut for months while the pier is rebuilt.",
       {"topic": "transport_infrastructure", "story_type": "fact", "claim": "A storm-damaged ferry terminal in Varnel will stay closed for months while the pier is rebuilt.", "conditions": [{"condition": "infrastructure_condition", "direction": "down", "level": "notable"}, {"condition": "disruption", "direction": "up", "level": "minor"}]}),
      ("synthetic-2", "Analyst predicts steady growth for the toy market. A commentator at the fictional firm Corvale says sales of wooden toys should keep rising next year.",
       {"topic": "consumer_retail", "story_type": "forecast", "claim": "An analyst expects wooden toy sales to keep rising next year.", "conditions": []}),
      ("synthetic-3", "Village band wins regional contest. The fictional Marlow Brass Band took first prize at the weekend festival in front of a large crowd.",
       {"topic": "culture_leisure", "story_type": "fact", "claim": "The Marlow Brass Band won first prize at a regional festival.", "conditions": []})]
spec = {"name": "world_state_v1", "prompt_version": "ws-v1", "model": "claude-haiku-5-5", "max_tokens": 450, "cap_usd": 5.0, "layers": ["TOPIC", "CONDITIONS"], "mode": "generate",
        "guideline": g, "input_template": "ITEM {id}\n<text>\n{text}\n</text>", "output_schema": schema,
        "examples": [{"input": {"id": i, "text": t}, "output": o} for i, t, o in ex]}
json.dump(spec, open("world_state_v1.json", "w"), indent=1, ensure_ascii=False)
print("conditions:", len(cond_ids), "topics:", len(topic_ids), "guideline chars:", sum(len(x) + 1 for x in g))
