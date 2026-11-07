"""Turn extraction records into training labels, one line per label: head, label, strength, rule, evidence. Nothing is judged here; strength says how the tool got it.
proved = the text states it and the Fact finder's checks passed; rule = a written rule fired; weak = a rule fired on a guess (e.g. largest city).
    /workspace/models/embed-zs/.venv/bin/python make_training_set.py   -> runs/harvest/train_labels.jsonl, train_labels_summary.json"""
import json, collections
out = []; add = lambda row, head, label, strength, rule, ev: out.append({"row": row, "head": head, "label": label, "strength": strength, "rule": rule, "evidence": ev})
R = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]
for r in R:
    row = r["row"]; t = r["text"]
    if r["domain_label"]: add(row, "domain", r["domain_label"]["label"], "rule", "url_section", r["domain_label"]["evidence"])
    if r["function"]["opinion_section"]: add(row, "function", "opinion", "rule", "url_section", r["source"]["section"])
    for a, b, tag in r["function"]["sentences"]:
        if tag != "unknown": add(row, "function", tag, "rule", "factuality-rules-v1", [a, b])
    for i in r["conditions"]["items"]: add(row, "conditions", i["condition"] + ("-negated" if i["negated"] else ""), "rule", "change-lexicon-v0", i["span"])
    for p in r["places"]["items"]:
        if p["country"]: add(row, "place", p["country"], "weak" if p["how"] in ("city, largest", "city, publisher country") else "rule", "geonames+alias-v0:" + p["how"], p["span"])
    for a in r["facts"]["amounts"]: add(row, "size", "stated amount", "proved", "fact-finder", a)
    for d in r["facts"]["dates"]: add(row, "date", "stated date", "proved", "fact-finder", d)
    for e_ in r["entities"]["items"]: add(row, "entity", e_[1], "rule", "spacy-ner-v0", [e_[2], e_[3]])
    if r["reader"]: add(row, "reader_topic", r["reader"]["topic_top2"][0], "weak", "bitmob-reader-v6b", r["reader"]["story_p"])
with open("runs/harvest/train_labels.jsonl", "w") as w:
    for o in out: w.write(json.dumps(o) + "\n")
S = {}
for h in sorted({o["head"] for o in out}):
    L = [o for o in out if o["head"] == h]; cls = collections.Counter(o["label"] for o in L); st = collections.Counter(o["strength"] for o in L)
    S[h] = {"labels": len(L), "articles": len({o["row"] for o in L}), "classes": len(cls), "min_class": min(cls.values()), "classes_ge60": sum(v >= 60 for v in cls.values()), "strength": dict(st), "top": cls.most_common(5)}
json.dump({"articles": len(R), "heads": S}, open("runs/harvest/train_labels_summary.json", "w"), indent=1)
for h, v in S.items(): print(h, v["labels"], "labels,", v["articles"], "articles,", v["classes"], "classes,", v["classes_ge60"], "with >=60;", v["strength"])
