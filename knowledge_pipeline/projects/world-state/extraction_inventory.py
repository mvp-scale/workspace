"""Extraction inventory: run every extractor we have on the same 300 real articles and record what each one pulls out, how often, how fast, and whether harvest.py / analyze2.py use it.
Writes runs/harvest/inventory.json. Nothing here labels anything.
    /workspace/models/embed-zs/.venv/bin/python extraction_inventory.py   (from projects/world-state)"""
import json, re, time, random, statistics, collections, sys
from urllib.parse import urlparse
import spacy, numpy as np
sys.path.insert(0, "."); import scan_gate as G, facts_lib as FL, analyze2 as A2, harvest as HV
from expert1_runtime import ExpertS
R = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(R); R = R[:300]
nlp = spacy.load("en_core_web_sm"); nlp_p = spacy.load("en_core_web_sm", disable=["ner"])
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); S = e.S; X = A2.Analyzer(S, json.load(open("runs/pulse/field_table.json")), threads=8)
body = lambda r: re.sub(r"\s+", " ", r["text"])[:12000]; full = lambda r: re.sub(r"\s+", " ", (r["title"] or "") + ". " + r["text"])[:12000]
def t_url(r): s = [x for x in urlparse(r["url"]).path.split("/") if x]; return {"path_segments": len(s), "section_words": [w for w in s[:-1] if w.lower() in HV.SEC or w.lower() in HV.FN], "slug_words": len(re.findall(r"[a-z]+", s[-1].lower())) if s else 0, "date_in_path": bool(re.search(r"/(19|20)\d\d/", r["url"]))}
def t_meta(r): return {"publisher": r["domain"], "published": (r["date"] or "")[:10], "description_chars": len(r["description"] or ""), "title_words": len((r["title"] or "").split())}
def t_scan(r): sp, se = G.scan(body(r), (r["date"] or "")[:10] + "T00:00:00Z" if r["date"] else None); c = collections.Counter(x[2] for x in sp); return {"sentences": len(se), **c}
def t_parse(r):
    d = nlp_p(full(r)); pos = collections.Counter(t.pos_ for t in d); dep = collections.Counter(t.dep_ for t in d); tag = collections.Counter(t.tag_ for t in d)
    return {"tokens": len(d), "sentences": len(list(d.sents)), "noun_chunks": len(list(d.noun_chunks)), **{"pos_" + k: v for k, v in pos.items()}, "passive": dep.get("nsubjpass", 0), "past_verbs": tag.get("VBD", 0), "present_verbs": tag.get("VBZ", 0) + tag.get("VBP", 0), "modals": tag.get("MD", 0), "root_verbs": [t.lemma_ for t in d if t.dep_ == "ROOT" and t.pos_ == "VERB"][:12]}
def t_ner(r): d = nlp(full(r)); return dict(collections.Counter(x.label_ for x in d.ents))
def t_facts(r): f = FL.facts_for(full(r), (r["date"] or "")[:10] + "T00:00:00Z" if r["date"] else None)[0]; return dict(collections.Counter(x["kind"] + "_" + x["status"] for x in f))
def t_reader(r): pt, ps, nw = X.reader.read(r["title"] or "", body(r)); return {"windows": nw, "topic_top2": [S["topic_cl"][k] for k in np.argsort(-pt)[:2]], "story_type": S["story_cl"][int(ps.argmax())], "story_p": round(float(ps.max()), 3)}
def t_lex(r): t = full(r).lower(); return {"event_words": len(re.findall(G.EVENT, t)), "speech_verbs": sum(len(re.findall(r"\b" + w + r"\w*", t)) for w in FL.SPEECH), "question_marks": t.count("?"), "quote_marks": t.count("“") + t.count("\"") // 2}
TOOLS = [("URL parser", "path, section words, slug, date in path", t_url, "harvest.py (section words only)"), ("Metadata", "publisher, publish date, description, title", t_meta, "harvest.py (date)"), ("Scan (regex)", "11 spot classes with spans, sentence spans, resolved dates", t_scan, "analyze2.py (via Fact finder)"),
         ("spaCy parse (NER off)", "tokens, sentences, parts of speech, dependencies, tense, modals, passive, noun chunks, root verbs", t_parse, "Fact finder only (not saved per article)"), ("spaCy NER", "entity types: PERSON, ORG, GPE, DATE, MONEY, ...", t_ner, "not used (disabled)"),
         ("Fact finder", "amounts, dates, names, who-did-what, each stated / unbound / invalid", t_facts, "analyze2.py, harvest.py"), ("BitMob Domain (v6b, 22.6M)", "per-window embedding, topic and story-type probabilities", t_reader, "analyze2.py"), ("Word lists", "event words, speech verbs, question and quote marks", t_lex, "scan_gate.py inside the Fact finder (counts not saved)")]
out = []; ex = next(r for r in R if 1100 < len(r["text"]) < 1700 and r["date"] and r["description"] and len((r["title"] or "").split()) > 5)
for name, what, fn, wired in TOOLS:
    ms = []; keys = collections.Counter(); hit = 0; tot = collections.defaultdict(float)
    for r in R:
        t = time.perf_counter(); o = fn(r); ms.append((time.perf_counter() - t) * 1000)
        if any(v for k, v in o.items() if not isinstance(v, (str, list)) or v): hit += 1
        for k, v in o.items():
            keys[k] += 1
            if isinstance(v, (int, float)) and not isinstance(v, bool): tot[k] += v
    out.append({"tool": name, "extracts": what, "wired": wired, "median_ms": round(statistics.median(ms), 2), "articles": len(R), "fields_seen": len(keys), "mean_per_article": {k: round(v / len(R), 2) for k, v in sorted(tot.items(), key=lambda x: -x[1])[:14]}, "example": fn(ex)})
vec = int(X.reader.sess.run(None, {"input_ids": np.ones((1, 8), dtype=np.int64), "attention_mask": np.ones((1, 8), dtype=np.int64)})[0].shape[-1])
json.dump({"articles": len(R), "embedding_dim": vec, "rust": "decider only (rust_pulse/src: decider.rs 25 lines, main.rs 12 lines)", "example_title": ex["title"], "example_chars": len(ex["text"]), "tools": out}, open("runs/harvest/inventory.json", "w"), indent=1)
for o in out: print(o["tool"], o["median_ms"], "ms", o["fields_seen"], "fields", list(o["mean_per_article"].items())[:5])
