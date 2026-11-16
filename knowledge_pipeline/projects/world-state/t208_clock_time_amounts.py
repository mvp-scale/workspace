"""T208 (step 15): measure a clock-time exclusion for the Fact finder's amounts, in memory, before editing facts_lib.py or stated_facts.py. Loads facts_lib.py source, applies the patch (skip a number that overlaps a clock-time span), runs current and patched facts_for on the 200 golden reference articles and 300 queue articles, and reports every difference.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t208_clock_time_amounts.py -> runs/pulse/t208/t208_clock_time_amounts.json"""
import json, re, sys, sqlite3, pathlib, types, collections
sys.path.insert(0, "."); import facts_lib as BASE
OUT = pathlib.Path("runs/pulse/t208"); OUT.mkdir(parents=True, exist_ok=True)
src = open("facts_lib.py").read()
CLOCK_DEF = '''CLOCK = re.compile(r"\\b(?:[01]?\\d|2[0-3]):[0-5]\\d(?::[0-5]\\d)?\\s?(?:(?:[ap]\\.?m\\.?(?=\\W|$))\\s?)?(?:(?:EST|EDT|CST|CDT|MST|MDT|PST|PDT|GMT|UTC|BST|CET|ET|PT)\\b)|\\b(?:[01]?\\d|2[0-3]):[0-5]\\d(?::[0-5]\\d)?\\s?[ap]\\.?m\\.?(?=\\W|$)|(?<=\\bat )(?:[01]?\\d|2[0-3]):[0-5]\\d\\b|\\b(?:1[0-2]|0?[1-9])\\s?[ap]\\.?m\\.?(?=\\W|$)|\\b(?:[01]\\d|2[0-3])[0-5]\\d\\s?(?:GMT|UTC)\\b", re.I)\n'''
a = src.index("YEAR = re.compile"); src2 = src[:a] + CLOCK_DEF + src[a:]
old = "        if any(a_ < e and s < b_ for a_, b_ in dspans): continue\n"; assert old in src2
src2 = src2.replace(old, "        if any(a_ < e and s < b_ for a_, b_ in dspans + cspans): continue\n", 1)
old2 = "    dspans = [(x[0], x[1]) for x in spots if x[2] == \"date\"]\n"; assert old2 in src2
src2 = src2.replace(old2, old2 + "    cspans = [m.span() for m in CLOCK.finditer(text)]\n", 1)
PATCH = types.ModuleType("facts_patched"); PATCH.__dict__["__name__"] = "facts_patched"; exec(compile(src2, "facts_patched.py", "exec"), PATCH.__dict__)
arts = []
for l in open("runs/pulse/golden/articles.jsonl"): g = json.loads(l); arts.append(("golden", g["title"], g["body"], g.get("date")))
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
for t, b, p in db.execute("select title, body, published from items where body is not null and length(body) > 800 order by id limit 300"): arts.append(("queue", t or "", b, (p or "")[:10] or None))
key = lambda f: (f["kind"], f["s"], f["e"], f["text"], f.get("status"), json.dumps(f.get("value"), default=str))
res = {"articles": len(arts), "articles_changed": 0, "golden_changed": 0, "removed_amounts": 0, "other_differences": 0, "examples": [], "added": 0}; ex = []
for set_, t, b, d in arts:
    text = re.sub(r"\s+", " ", (t or "") + ". " + b)[:12000]; anchor = (d + "T00:00:00Z") if d else None
    old = {key(f): f for f in BASE.facts_for(text, anchor)[0]}; new = {key(f): f for f in PATCH.facts_for(text, anchor)[0]}
    rem = [old[k] for k in old if k not in new]; add = [new[k] for k in new if k not in old]
    if rem or add:
        res["articles_changed"] += 1; res["golden_changed"] += set_ == "golden"; res["added"] += len(add)
        for f in rem:
            if f["kind"] == "amount": res["removed_amounts"] += 1; ex.append({"set": set_, "removed": f["text"].strip(), "context": text[max(0, f["s"] - 25):f["e"] + 25]})
            else: res["other_differences"] += 1
res["examples"] = ex[:40]; res["all_removed_contexts_clock_like"] = sum(1 for x in ex if re.search(r"\d\s?(?:[ap]\.?m\.?|GMT|UTC|EST|EDT|PST|PDT|CST|CDT|ET|PT)\b|\d:\d\d", x["context"], re.I))
json.dump(res, open(OUT / "t208_clock_time_amounts.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "examples"})); [print(" ", x["set"], "|", x["removed"], "|", x["context"]) for x in ex[:25]]
