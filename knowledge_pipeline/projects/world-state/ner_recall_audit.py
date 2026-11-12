"""Recall audit for the date and amount extractors. Second extractor = spaCy en_core_web_sm NER (DATE; MONEY, PERCENT, QUANTITY, CARDINAL). Reads only the disagreements: spans the NER found that our tools did not overlap.
    /workspace/models/embed-zs/.venv/bin/python ner_recall_audit.py [N] -> runs/harvest/recall_audit.json"""
import json, re, sys, collections, spacy
import scan_gate as G, facts_lib as FL, span_rules as SR, random
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400; MODE = sys.argv[2] if len(sys.argv) > 2 else 'union'; samples = collections.defaultdict(list)
nlp = spacy.load("en_core_web_sm")
R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]
shape = lambda s: re.sub(r"[a-z]+", "a", re.sub(r"\d+", "9", s.strip()))[:30]
miss = {"date": collections.Counter(), "amount": collections.Counter()}; ex = {"date": collections.defaultdict(list), "amount": collections.defaultdict(list)}; tot = collections.Counter(); hit = collections.Counter()
for r in R:
    date = (r["date"] or "")[:10] or None; text = re.sub(r"\s+", " ", (r["title"] or "") + ". " + (r["text"] or ""))[:12000]; anchor = date + "T00:00:00Z" if date else None
    facts = FL.facts_for(text, anchor)[0]; d = nlp(text)
    new = SR.spans(text, anchor); newd = [(x["s"], x["e"]) for x in new if x["kind"] not in ("number_word",)]; newa = [(x["s"], x["e"]) for x in new if x["kind"] in ("number_word", "duration")]
    ours = {"date": [(f["s"], f["e"]) for f in facts if f["kind"] == "date"], "amount": [(f["s"], f["e"]) for f in facts if f["kind"] == "amount"]}
    if MODE == "union": ours["date"] += newd; ours["amount"] += newa
    for x in new: samples[x["kind"]].append((x["text"], text[max(0, x["s"] - 40):x["e"] + 40].replace("\n", " "), x["value"]))
    for e in d.ents:
        k = "date" if e.label_ == "DATE" else ("amount" if e.label_ in ("MONEY", "PERCENT", "QUANTITY", "CARDINAL") else None)
        if not k: continue
        tot[k] += 1
        if any(a < e.end_char and e.start_char < b for a, b in ours[k]): hit[k] += 1
        else:
            key = (e.label_, shape(e.text)); miss[k][key] += 1
            if len(ex[k][key]) < 4: ex[k][key].append(e.text)
out = {"articles": len(R), "ner_spans": dict(tot), "overlapped_by_ours": dict(hit), "recall_vs_ner": {k: round(hit[k] / tot[k], 3) for k in tot},
       "top_missed": {k: [[list(key), c, ex[k][key]] for key, c in miss[k].most_common(40)] for k in miss}}
random.seed(7); out["new_span_counts"] = {k: len(v) for k, v in samples.items()}; out["new_span_samples"] = {k: random.sample(v, min(6, len(v))) for k, v in samples.items()}
json.dump(out, open("runs/harvest/recall_audit_%s.json" % MODE, "w"), indent=1)
print(out["ner_spans"], out["recall_vs_ner"])
for k in miss:
    print("==", k)
    for key, c in miss[k].most_common(25): print(c, key, ex[k][key])
