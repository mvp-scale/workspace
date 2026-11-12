"""T140 (free CPU): are Jev's evidence sentences the ones that carry stated facts? For each dial the engine read, Jev chose an evidence sentence (call 2). span_rules.spans (regex dates, years, durations, ages, number words; no model) finds stated-fact spans. Compare the share of chosen sentences with at least one span with the share of all sentences in the same stories (chance), split by Jev's evidence-exists probability. Validator evidence for the decider's STATED_FACT path, independent of Jev.
    /workspace/models/embed-zs/.venv/bin/python t140_evidence_check.py (from projects/world-state) -> runs/pulse/t140/t140_evidence_check.json"""
import os, sys, json, re, pathlib, random
sys.path.insert(0, "."); import span_rules as SR
os.environ["NE"] = "0"; os.environ["NL"] = "0"; os.environ["NM"] = "0"
src = open("t135_full_read.py").read().split("S = sample(); T0")[0]
import types; sys.path.insert(0, "/workspace/probes/world-engine"); os.environ.setdefault("WE_RULES", "rules_v2"); ns = {"__name__": "t135defs"}; exec(compile(src, "t135defs", "exec"), ns); build_state = ns["build_state"]
OUT = pathlib.Path("runs/pulse/t140"); OUT.mkdir(parents=True, exist_ok=True)
text = {}
for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["text"])
for l in open("/workspace/data/newsreader/labels/t135_ls_sample.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["body"])
for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"): r = json.loads(l); text[r["id"]] = (r["text"].split(". ")[0][:200], r["text"])
rows = [json.loads(l) for l in open("/workspace/data/newsreader/labels/full-read-100.jsonl")]; rows = [r for r in rows if "error" not in r]
has = lambda s: len(SR.spans(s)) > 0
ev_has = []; chance_has = []; by_p = {"hi": [], "lo": []}; n_dials = 0
for r in rows:
    title, body = text[r["id"]]; st, off = build_state(title, body, r.get("published")); sents = st["sentences"]
    if not r["fired"]: continue
    chance_has += [has(s) for s in sents.values()]
    for k in r["fired"]:
        d = k[5:]; ev = r["answers_call2"].get(f"{d}__evidence_sentence"); ee = r["answers_call2"].get(f"{d}__evidence_exists")
        if not ev or ev["choice"] not in sents: continue
        h = has(sents[ev["choice"]]); ev_has.append(h); n_dials += 1; by_p["hi" if ee and ee["noul"] >= 0.5 else "lo"].append(h)
rate = lambda l: round(sum(l) / max(len(l), 1), 4)
res = {"chosen_with_span_k": sum(ev_has), "chosen_n": len(ev_has), "stories_with_fired_dials": sum(1 for r in rows if r["fired"]), "evidence_sentences_checked": n_dials, "share_of_chosen_sentences_with_a_stated_fact_span": rate(ev_has), "share_of_all_sentences_with_a_span_chance": rate(chance_has), "chosen_when_evidence_exists_p_at_least_0.5": {"n": len(by_p["hi"]), "share": rate(by_p["hi"])}, "chosen_when_evidence_exists_p_below_0.5": {"n": len(by_p["lo"]), "share": rate(by_p["lo"])},
       "note": "span_rules finds dates, years, durations, ages and number words with plain regex; many dials (unrest, trust) are not numeric, so a low share is expected there. Evidence for validating evidence sentences, not an accuracy figure."}
json.dump(res, open(OUT / "t140_evidence_check.json", "w"), indent=1); print(json.dumps(res, indent=1))
