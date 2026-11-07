"""Track 1 (pre-registered L930): size as the quantity a sentence itself states. RULES stage of the playbook 00 cascade: extract number + unit class + counted noun from the first 600 characters (headline + short description); abstain when no quantity is stated.
    python3 size_quantity.py   (from projects/world-state)   -> runs/pulse/size_quantity.json, runs/pulse/size_quantity_sample.jsonl"""
import json, re, random, collections
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
W = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "dozen": 12, "dozens": 24, "hundreds": 200, "thousands": 2000}
NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|" + "|".join(W) + r")"
MAG = r"(?:\s?(?:thousand|million|billion|trillion|bn|m|k)\b)?"
UNITS = [
    ("percent", r"(?:%|\s?per ?cent\b|\s?percent\b)"),
    ("people", r"\s(?:people|persons|residents|civilians|children|workers|employees|staff|protesters|demonstrators|passengers|survivors|victims|migrants|refugees|families|households|homes|villagers|students|patients|soldiers|police|officers)\b"),
    ("casualty", r"\s(?:dead|deaths|killed|injured|wounded|missing|arrested|detained|displaced|evacuated|hospitalised|hospitalized|infected|fatalities|casualties)\b"),
    ("area", r"\s?(?:hectares|acres|sq(?:uare)? ?(?:km|kilomet\w+|miles?|metres|meters)|km2|km²|ha)\b"),
    ("length", r"\s?(?:km|kilomet\w+|miles?|metres|meters|feet|ft)\b"),
    ("mass", r"\s?(?:tonnes|tons|tonne|kg|kilograms?|pounds|lbs)\b"),
    ("volume", r"\s?(?:litres|liters|gallons|barrels|cubic (?:metres|meters)|m3|bbl)\b"),
    ("concentration", r"\s?(?:µg/m3|ug/m3|ppm|ppb|μg/m³|micrograms)\b"),
    ("jobs", r"\s(?:jobs|positions|roles|layoffs|redundancies)\b"),
    ("count_thing", r"\s(?:attacks|incidents|cases|records|breaches|fires|species|flights|outages|protests|strikes|shortages|plants|sites|companies|firms|banks|accounts|devices|systems|vehicles|buildings|schools|hospitals|villages|cities|countries|days|weeks|months|years|hours)\b"),
]
MONEY = re.compile(r"(?:US\$|\$|€|£|USD |EUR |GBP )\s?" + NUM + MAG + r"|" + NUM + MAG + r"\s?(?:dollars|euros|pounds|yuan|rupees|yen|usd|eur|gbp)\b", re.I)
AIQ = re.compile(r"(?:air quality index|aqi)(?: of| reached| hit| at)?\s?(\d{2,3})", re.I)
BAD_BEFORE = re.compile(r"(?:aged?|age of|since|in|by|from|until|before|after|of)\s$", re.I)
UNIT_RX = [(c, re.compile(r"(?<![\w.])(" + NUM + MAG + r")(" + u + r")", re.I)) for c, u in UNITS]
YEAR = re.compile(r"^(19|20)\d\d$")
def extract(text):
    t = re.sub(r"\s+", " ", text)[:600]; out = []
    for m in MONEY.finditer(t): out.append({"cls": "money", "span": m.group(0).strip(), "at": m.start()})
    for m in AIQ.finditer(t): out.append({"cls": "concentration", "span": m.group(0), "at": m.start()})
    for c, rx in UNIT_RX:
        for m in rx.finditer(t):
            num = m.group(1).strip()
            if YEAR.match(num) and c in ("count_thing",): continue
            after = t[m.end():m.end() + 12].lower()
            if c == "count_thing" and re.match(r"^(?: ago| old|-old|-year)", after): continue
            if c == "count_thing" and m.group(2).strip().lower() in ("days", "weeks", "months", "years", "hours") : continue   # durations are not the size of a condition
            out.append({"cls": c, "span": (num + m.group(2)).strip(), "at": m.start()})
    out.sort(key=lambda x: x["at"]); seen = set(); res = []
    for o in out:
        if o["at"] in seen: continue
        seen.add(o["at"]); res.append(o)
    return res
if __name__ == "__main__":
    S = {}
    for r in J("runs/label_store/labels.jsonl"):
        if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen" and r["kinds"]: S[r["item_id"]] = r["kinds"]
    pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
    for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
    ids = [i for i in S if i in pool]; per = collections.defaultdict(lambda: [0, 0]); cls = collections.Counter(); ex = {}
    for i in ids:
        q = extract(pool[i]); ex[i] = q
        for k in S[i]: per[k][0] += 1; per[k][1] += bool(q)
        for o in q[:1]: cls[o["cls"]] += 1
    n = len(ids); cov = sum(1 for i in ids if ex[i]) / n
    res = {"items_with_kind": n, "coverage_any": round(cov, 3), "first_quantity_class": dict(cls), "coverage_per_kind": {k: {"items": v[0], "coverage": round(v[1] / v[0], 3)} for k, v in sorted(per.items(), key=lambda kv: -kv[1][0])}}
    json.dump(res, open("runs/pulse/size_quantity.json", "w"), indent=1)
    rng = random.Random(11); pick = rng.sample([i for i in ids if ex[i]], 100)
    with open("runs/pulse/size_quantity_sample.jsonl", "w") as f:
        for n_, i in enumerate(pick):
            o = ex[i][0]; t = re.sub(r"\s+", " ", pool[i])[:600]; a = o["at"]
            f.write(json.dumps({"n": n_, "id": i, "kinds": S[i], "class": o["cls"], "span": o["span"], "context": t[max(0, a - 70):a + 90]}) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "coverage_per_kind"}), "\n", {k: v["coverage"] for k, v in list(res["coverage_per_kind"].items())[:16]})
