"""T101: engine shadow run for story type. The engine reads a story into fact, forecast, opinion or unclear from Clef's stored gate probabilities (probes/world-engine/classify.py type_weight: fact when happened or announced is 0.5 or more, opinion under 0.5 and forecast under 0.5; forecast at 0.5 or more; opinion at 0.5 or more; else unclear). This reads the same stories with the registered CPU reader (v6b-student, field story_type) on title plus the first two sentences, and counts agreement with the engine's type over every story (a skipped story is a miss). Clef is a system reference: agreement is not accuracy. Nothing is changed in the engine.
    OUT=<folder> NP=<max stories> /workspace/models/embed-zs/.venv/bin/python -u t101_engine_shadow.py -> <OUT>/t101_engine_shadow.json"""
import os, sys, json, re, pathlib, collections
sys.path.insert(0, "."); from expert1_runtime import ExpertS
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t101")); OUT.mkdir(parents=True, exist_ok=True); NP = int(os.environ.get("NP", 0))
def engine_type(P):
    h, a, o, f = P["g|happened"], P["g|announced"], P["g|opinion"], P["g|forecast"]
    if (h >= .5 or a >= .5) and o < .5 and f < .5: return "fact"
    if f >= .5: return "forecast"
    if o >= .5: return "opinion"
    return "unclear"
seen = {}; src = pathlib.Path("/workspace/data/newsreader/labels")
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open(src / fn):
        r = json.loads(l)
        if r["id"] not in seen and "g|happened" in r.get("P", {}): seen[r["id"]] = r
rows = list(seen.values())
if os.environ.get("SEED"):
    import random
    random.Random(int(os.environ["SEED"])).shuffle(rows)
if NP: rows = rows[:NP]
def reader_text(r):
    body = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); body = re.sub(r"^Published\s*", "", body); sents = re.split(r"(?<=[.!?])\s+", body)
    return (r["title"].strip() + ". " + " ".join(sents[:2])).strip()
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); conf = collections.Counter(); eng = collections.Counter(); rd = collections.Counter(); agree = ans = 0
for r in rows:
    t = engine_type(r["P"]); eng[t] += 1; o = e.read(reader_text(r))["story_type"]
    if o.get("status") == "answered": ans += 1; rd[o["answer"]] += 1; conf[(t, o["answer"])] += 1; agree += (o["answer"] == t)
    else: rd["(unanswered)"] += 1; conf[(t, "(unanswered)")] += 1
n = len(rows); always = max(eng.values()) / n
res = {"stories": n, "answered": ans, "answered_share": round(ans / n, 4), "agreement_all": round(agree / n, 4), "agreement_of_answered": round(agree / max(ans, 1), 4), "engine_type_counts": dict(eng), "reader_counts": dict(rd), "always_most_common_engine_type": round(always, 4), "confusion_engine_to_reader": {f"{a}->{b}": v for (a, b), v in sorted(conf.items(), key=lambda kv: -kv[1])},
       "note": "Reference is Clef's stored gate through the engine's own type rule, so this is agreement with the engine as it runs today, not accuracy. Reader sees title plus first two sentences; the engine reads title plus up to 1200 words."}
json.dump(res, open(OUT / "t101_engine_shadow.json", "w"), indent=1); print(json.dumps(res, indent=1))
