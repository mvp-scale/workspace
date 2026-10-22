#!/usr/bin/env python3
"""Reference distribution for the World engine "hit counter" (demo/hits.py).
Writes data/bitmob-integration/hit_reference.json. Counts, not shares, so the page can compute its own bounds.
Set 1 (jev_testA): Jev labels on the frozen test set data/trainset/testA.jsonl (topic, country, target_keys, gate, P g|forecast).
Set 2 (clef_reads): stories the engine read with Clef (reader id starts with clef, or reader_kind llm) in data/world-engine/reads.jsonl; written only when >= 50 distinct stories exist.
Names are the engine's own display names: probes/persona/rules_v2/domains.csv (topics) and dials.csv (conditions). Run: python3 tools/hit_reference.py"""
import csv, json, datetime, collections
R = "/workspace/probes/persona/rules_v2"; OUT = "/workspace/data/bitmob-integration/hit_reference.json"
TOPIC = {r["id"]: r["name"] for r in csv.DictReader(open(f"{R}/domains.csv"))}
DIAL = {r["id"]: r["name"] for r in csv.DictReader(open(f"{R}/dials.csv"))}
def cond_name(d, dr): return f"{DIAL.get(d, d)} {dr}"
def type_of(h, a, o, f):      # same rule as classify.type_weight: a story is one of fact / forecast / opinion / unclear
    return "fact" if (h >= .5 or a >= .5) and o < .5 and f < .5 else "forecast" if f >= .5 else "opinion" if o >= .5 else "unclear"
def new(): return {"n": 0, "topic": collections.Counter(), "country": collections.Counter(), "cond": collections.Counter(), "no_reading": 0, "gate_closed": 0, "type": collections.Counter(), "stories_with_topic": 0}
def fin(s, src):
    return {"source": src, "n": s["n"], "stories_with_topic": s["stories_with_topic"], "topic": dict(s["topic"].most_common()), "country": dict(s["country"].most_common()), "cond": dict(s["cond"].most_common()), "no_reading": s["no_reading"], "gate_closed": s["gate_closed"], "type": dict(s["type"].most_common()), "expected": None}
j = new()
for l in open("/workspace/data/trainset/testA.jsonl"):
    r = json.loads(l); j["n"] += 1
    if r.get("topic"): j["topic"][TOPIC.get(r["topic"], r["topic"])] += 1; j["stories_with_topic"] += 1
    j["country"][r.get("country") or "global"] += 1
    keys = r.get("target_keys") or []
    for k in keys: d, dr = k.split("|")[:2]; j["cond"][cond_name(d, dr)] += 1
    j["no_reading"] += not keys; j["gate_closed"] += not r.get("gate_ok", True)
    g = r["gate"]; j["type"][type_of(g["happened"], g["announced"], g["opinion"], r["P"]["g|forecast"])] += 1
sets = {"jev_testA": fin(j, "Jev labels on the frozen test set (data/trainset/testA.jsonl); one topic per story; conditions = target_keys")}
c = new(); seen = set()
for l in open("/workspace/data/world-engine/reads.jsonl"):
    r = json.loads(l)
    if not (str(r.get("reader") or "").startswith("clef") or r.get("reader_kind") == "llm") or r["title"] in seen: continue
    seen.add(r["title"]); c["n"] += 1
    e = r.get("entry") or ""; c["country"][e.split(":")[1] if e.startswith("COUNTRY:") else "global"] += 1
    rd = [x for x in r.get("readings") or [] if x["direction"] != "conflict" and x.get("basis", "reported") == "reported"]
    for x in rd: c["cond"][cond_name(x["dial"], x["direction"])] += 1
    c["no_reading"] += not rd; c["gate_closed"] += not r.get("gate_ok", True)
    g = r["gate"]; c["type"][type_of(g["happened"], g["announced"], g["opinion"], r["P"]["g|forecast"])] += 1
if c["n"] >= 50:
    f = fin(c, "Stories the engine read with Clef (data/world-engine/reads.jsonl, distinct titles); topic not logged there"); f["topic"] = None; sets["clef_reads"] = f
json.dump({"made": datetime.datetime.now().isoformat(timespec="seconds"), "topic_names": TOPIC, "dial_names": DIAL, "sets": sets}, open(OUT, "w"), indent=1)
print({k: v["n"] for k, v in sets.items()}, "->", OUT)
