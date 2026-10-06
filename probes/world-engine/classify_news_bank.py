"""Step 2 of the news bank: pick about 450 real headlines (round-robin across feeds so no outlet dominates), add the hand-written funny ones from demo/ticker.json,
then have the local model read each headline's country (choice over the top-100 table plus 'global') and topic (choice over the 14 domains). Resumable: answers are cached
per headline in /workspace/data/news/classified.jsonl. Output: /workspace/data/news/bank.json, items {x, c (ISO2 or WORLD), t (topic), src, kind, p_c, p_t}.
Run from this folder with the engine's python (needs the Winnow server on :8091): python classify_news_bank.py"""
import csv, json, os, random, collections, datetime, hashlib, sys
sys.path.insert(0, "/workspace/probes/persona"); import classify as C; O = C.O
import rules as RU      # WE_RULES picks the topic list; a non-v1 ruleset gets its own cache and bank files (classified_<rules>.jsonl, bank_<rules>.json) so the v1 ones are never overwritten
SUF = "" if RU.IS_V1 else "_" + os.path.basename(RU.R)
RAW, CACHE, OUT = "/workspace/data/news/raw_headlines.json", f"/workspace/data/news/classified{SUF}.jsonl", f"/workspace/data/news/bank{SUF}.json"
WBC = json.load(open("/workspace/probes/world-engine/data/sources_raw/wb_countries.json"))[1]
iso2 = {x["id"]: x["iso2Code"] for x in WBC}; region_of = {x["id"]: x["region"]["value"] for x in WBC}      # the server allows 2-64 options per question, so country is asked within a world region
region_of.setdefault("TWN", "East Asia & Pacific"); iso2.setdefault("TWN", "TW")      # Taiwan is in the UN table but not in the World Bank country list
top = list(csv.DictReader(open("/workspace/probes/world-engine/data/countries_top100.csv"))); crit = {r["iso3"]: r["name"] for r in top}
REG = sorted({region_of[r["iso3"]] for r in top}); in_region = {g: {r["iso3"]: r["name"] for r in top if region_of[r["iso3"]] == g} for g in REG}
for g in REG: in_region[g]["OTHER_HERE"] = "A different country in this part of the world, or no single country"
TOPIC = {"economy_housing": "ECONOMY", "work_labour": "WORK", "energy_resources": "ENERGY", "environment_climate": "CLIMATE", "health": "HEALTH", "safety_crime": "CRIME", "conflict_security": "CONFLICT",
         "government_law": "LAW", "international_migration": "DIPLOMACY", "society_identity": "SOCIETY", "culture_leisure": "CULTURE", "technology_science": "TECH", "education": "SCHOOL", "business_corporate": "BUSINESS", "other": "OTHER"}
raw = json.load(open(RAW)); rng = random.Random(7)
by = collections.defaultdict(list)
for i in raw: by[i["src"]].append(i)
for v in by.values(): rng.shuffle(v)
quota = {"news": 300, "tech": 90, "satire": 60}; picked = []; got = collections.Counter()
while any(by.values()) and any(got[k] < quota[k] for k in quota):
    for s in list(by):
        if by[s]:
            it = by[s].pop()
            if got[it["kind"]] < quota[it["kind"]]: picked.append(it); got[it["kind"]] += 1
done = {}
if os.path.exists(CACHE):
    for l in open(CACHE): r = json.loads(l); done[r["x"]] = r
today = datetime.date.today().isoformat(); n = 0
with open(CACHE, "a") as f:
    for it in picked:
        if it["x"] in done: continue
        st = f"News item (published {today}; today is {today}):\n{it['x']}."
        a = O.call(st, {"g": {"type": "choice", "instructions": "Which part of the world is this story mainly about?", "criteria": dict({g: g for g in REG}, GLOBAL="The whole world, or no single part")},
                        "t": {"type": "choice", "instructions": "Which area is this story mainly about?", "criteria": {d["id"]: d["definition"] for d in C.DOMAINS}}})
        g, t = a["g"]["choice"], a["t"]["choice"]; pg, pt = a["g"]["probabilities"], a["t"]["probabilities"]; c, pc = "WORLD", float(pg[g])
        if g != "GLOBAL":
            b = O.call(st, {"c": {"type": "choice", "instructions": "Which country is this story mainly about?", "criteria": in_region[g]}}); c = b["c"]["choice"]; pc = float(b["c"]["probabilities"][c]) * float(pg[g])
            c = "WORLD" if c == "OTHER_HERE" else c
        r = dict(it, cc=c, c=("WORLD" if c == "WORLD" else iso2.get(c, c[:2])), t=(TOPIC.get(t, "OTHER") if RU.IS_V1 else t), p_c=round(pc, 3), p_t=round(float(pt[t]), 3)); done[it["x"]] = r; f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush(); n += 1
        if n % 25 == 0: print(n, "classified", flush=True)
bank = [done[i["x"]] for i in picked if i["x"] in done]
for g in json.load(open("/workspace/demo/ticker.json")):
    t = g["t"]
    if not RU.IS_V1:      # our own lines carry v1 tags; under another ruleset the model places them in that ruleset's topics
        t = O.call(f"News item (published {today}; today is {today}):\n{g['x']}.", {"t": {"type": "choice", "instructions": "Which area is this story mainly about?", "criteria": {d["id"]: d["definition"] for d in C.DOMAINS}}})["t"]["choice"]
    bank.append({"x": g["x"], "c": g["c"], "t": t, "src": "written by us", "kind": "generated"})
rng.shuffle(bank); json.dump(bank, open(OUT, "w"), indent=0, ensure_ascii=False)
print(len(bank), "in the bank:", dict(collections.Counter(b["kind"] for b in bank)), "| WORLD-tagged real:", sum(1 for b in bank if b["kind"] != "generated" and b["c"] == "WORLD"))
