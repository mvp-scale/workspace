"""T203 (next_steps 12): spaCy NER as a BitMob tool for Place. For each of the 1,600 queue stories with a Jev place_region label, take the GPE and LOC entities spaCy NER finds in title + first 3,000 body characters, look each up in the same country, short-form and large-city name table as the regex judge (t167), and apply the same rule (at least 2 mentions, one country at 60% or more). Reports how many stories NER decides, and how often its region equals Jev's, next to the regex judge on the same stories. Prediction in card T148-F.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -u t203_ner_place.py -> runs/pulse/t203/t203_ner_place.json"""
import json, re, sqlite3, collections, pathlib, runpy, time, spacy
OUT = pathlib.Path("runs/pulse/t203"); OUT.mkdir(parents=True, exist_ok=True)
g = runpy.run_path("t167_place_judge.py"); names, region, rows = g["names"], g["region"], g["rows"]
nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"]); db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
res_rows = []; t0 = time.time(); typed = collections.Counter(); amb_hits = 0
for r in rows:
    q = db.execute("select title, body from items where id=?", (r["id"],)).fetchone(); txt = ((q[0] or "") + ". " + q[1])[:3000]
    cnt = collections.Counter()
    for e in nlp(txt).ents:
        if e.label_ in ("GPE", "LOC"):
            typed[e.label_] += 1; k = e.text.lower().strip()
            if k.startswith("the "): k = k[4:]
            if k in names: cnt[names[k]] += 1
            elif k in ("georgia", "jordan", "chad", "guinea", "niger", "mali"): amb_hits += 1
    tot = sum(cnt.values()); ner_truth = None
    if tot >= 2:
        cc, n = cnt.most_common(1)[0]
        if n / tot >= 0.6: ner_truth = region(cc)
    res_rows.append({"id": r["id"], "jev": r["jev"], "regex": r["truth"], "ner": ner_truth})
n = len(res_rows); nd = [r for r in res_rows if r["ner"]]; rd = [r for r in res_rows if r["regex"]]; both = [r for r in res_rows if r["ner"] and r["regex"]]
acc = lambda L, k: round(sum(r[k] == r["jev"] for r in L) / max(len(L), 1), 3)
res = {"stories": n, "ner_decides": len(nd), "ner_decide_share": round(len(nd) / n, 3), "ner_accuracy_vs_jev": acc(nd, "ner"), "regex_decides": len(rd), "regex_decide_share": round(len(rd) / n, 3), "regex_accuracy_vs_jev": acc(rd, "regex"),
       "both_decide": len(both), "ner_vs_jev_on_both": acc(both, "ner"), "regex_vs_jev_on_both": acc(both, "regex"), "ner_equals_regex_on_both": round(sum(r["ner"] == r["regex"] for r in both) / max(len(both), 1), 3),
       "either_decides_share": round(sum(1 for r in res_rows if r["ner"] or r["regex"]) / n, 3), "typed_entities": dict(typed), "ambiguous_name_hits_skipped": amb_hits, "seconds": round(time.time() - t0)}
json.dump(res, open(OUT / "t203_ner_place.json", "w"), indent=1); print(json.dumps(res))
