"""Simulation: run one article through the BitMob pipeline (analyze2) by hand and see each tool's output, time and measured score.
Throwaway test bench, CPU only, no hosted calls, no GPU. Not part of the console.
Run: /workspace/models/embed-zs/.venv/bin/python simulation/server.py   (from knowledge_pipeline)  then open http://localhost:18770/
GET /api/articles -> dropdown list; GET /api/article?id=... ; POST /api/run {title, body, date, sparse} -> gate-by-gate read (G0 normalize, G1 spans, G2 facts, G3 cascade, decider, journal record, engine map); GET /api/heads -> measured scores per head."""
import json, os, random, re, sqlite3, sys, pathlib, time, hashlib, collections
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = pathlib.Path(__file__).resolve().parent; WS = HERE.parent / "projects" / "world-state"; os.chdir(WS); sys.path.insert(0, str(WS))
import analyze2 as A2, facts_lib as FL, span_rules as SR
import numpy as np
from expert1_runtime import ExpertS
PORT = int(os.environ.get("SIM_PORT", 18770)); E = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json"))
AN = {False: A2.Analyzer(E.S, FT, threads=8), True: A2.Analyzer(E.S, FT, threads=8, sparse="runs/expert1/sparse_heads_v2.pkl")}
ART = {}
for i, l in enumerate(open("runs/pulse/golden/articles.jsonl")):
    g = json.loads(l); ART["g%d" % i] = {"group": "Golden set", "title": g["title"], "body": g["body"], "date": g.get("date")}
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = db.execute("select id, title, body, published from items where body is not null and length(body) > 600").fetchall(); random.Random(7).shuffle(rows)
for r in rows[:30]: ART["q%s" % r[0]] = {"group": "Queue sample", "title": r[1] or "", "body": r[2], "date": (r[3] or "")[:10] or None}
def heads():
    ht = json.load(open("runs/pulse/t151/head_table.json"))["rows"]; hc = json.load(open("runs/pulse/head_coverage.json"))
    return {"table": [{k: r.get(k) for k in ("head", "score_now", "admission_marker", "barrier", "cpu_reader_can_replace_teacher")} for r in ht],
            "coverage": {k: {"answered": v["model_answered"].get("value"), "accuracy": v["model_accuracy"].get("value"), "answered_src": v["model_answered"].get("src"), "accuracy_src": v["model_accuracy"].get("src")} for k, v in hc.items()}}

ENGINE_MAP = [  # which engine question family each field feeds: from newsreader/bitmob/reader/engine_reader.py (D-0037) docstring; this bench does not call the engine
 ["story_type", "Story type", "gate questions g|happened, g|announced, g|opinion, g|forecast (type head)"],
 ["topic", "Topic (two guesses)", "placement: choice 'c' over the domains and y|<domain> (topic head)"],
 ["condition", "Condition, direction, size", "condition keys a|<dial>|<dir> (52 keys); expected impact and severity go to Clef today"],
 ["size", "Stated amounts", "evidence for size and severity answers; not an engine key by itself"]]
import pickle, datetime
import spacy
NLP = spacy.load("en_core_web_sm")
from sentence_transformers import SentenceTransformer
PLACE = pickle.load(open("runs/pulse/t200/place_student.pkl", "rb")); PLACE_ENC = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); PLACE_ENC.max_seq_length = 128
_tiers = json.load(open("runs/pulse/t230/capability_tiers.json")); CAP_REC = {tuple(x.split(" ", 1)) for x in _tiers["recurring_pairs"] if " " in x and x not in ("injure other", "speak condition", "update inbox")}
CAP_CAND = {(r["predicate"], r["object"]) for r in map(json.loads, open("runs/pulse/t222/capability_candidates.jsonl"))}   # 371 cross-Area pairs (two tiers: recurring in both periods, candidate otherwise)
TOPIC2DOM = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; HC = json.load(open("runs/pulse/head_coverage.json"))

MONTHS = "January February March April May June July August September October November December".split()
def clean_input(title, body, date):
    raw = (body or "").replace("\r", ""); lines = [l.strip() for l in raw.split("\n")]; t = (title or "").strip(); d = date or None; dsrc = "given" if date else None; kept = []; dropped = []
    for l in lines:
        if not l: continue
        if re.match(r"^TITLE:", l, re.I): t = t or re.sub(r"^TITLE:\s*", "", l, flags=re.I); continue
        if re.match(r"^DATE:", l, re.I):
            m = re.search(r"(%s)\s+(\d{1,2}),\s+(\d{4})" % "|".join(MONTHS), l)
            if m and not d: d = datetime.date(int(m.group(3)), MONTHS.index(m.group(1)) + 1, int(m.group(2))).isoformat(); dsrc = "DATE line"
            continue
        l = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", l); l = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", l).strip()
        if len(l.split()) < 6 or re.fullmatch(r"[=\-_*#\s]+", l): dropped.append(l[:50]); continue
        l = l.lstrip("•*- ").strip(); kept.append(l if l[-1] in ".!?\"”’)" else l + ".")
    return t, "\n".join(kept), d, {"lines_in": len([l for l in lines if l]), "lines_kept": len(kept), "dropped_examples": [x for x in dropped if x][:6], "date_source": dsrc}
import scan_gate as SG
TIMEPART = {"AM", "PM", "EST", "EDT", "GMT", "UTC", "ET", "PST", "BST"} | set(MONTHS)
def is_timepart(a): return (a.get("noun") or "") in TIMEPART
def claims_layer(text, facts, anchor):
    """Sentence-by-sentence evidence from the EXISTING tools: Scan (scan_gate.scan: spot classes and sentence spans), the Fact finder (triples) and the spaCy parse; spaCy NER only as a cross-check (it is disabled in analyze2)."""
    t0 = time.perf_counter(); spots, sents = SG.scan(text, anchor); doc = NLP(text); cnt = collections.Counter(sp[2] for sp in spots)
    ners = collections.Counter(e.label_ for e in doc.ents); parse = collections.Counter()
    for tok in doc:
        if tok.tag_ == "MD": parse["modals"] += 1
        if tok.dep_ == "nsubjpass": parse["passive"] += 1
        if tok.pos_ == "VERB": parse["past_verbs" if "Past" in tok.morph.get("Tense") else ("present_verbs" if "Pres" in tok.morph.get("Tense") else "other_verbs")] += 1
    parse["sentences"] = len(list(doc.sents)); out = []
    for a, b in sents:
        st = text[a:b].strip()
        if len(st.split()) < 6: continue
        inn = [sp for sp in spots if a <= sp[0] < b]; by = collections.defaultdict(list)
        for sp in inn: by[sp[2]].append(sp)
        figs = list(dict.fromkeys(text[sp[0]:sp[1]].strip() for c in ("money", "percent", "quantity") for sp in by.get(c, [])))
        ents = list(dict.fromkeys(text[sp[0]:sp[1]].strip() for sp in by.get("entity", [])))[:6]
        dates = list(dict.fromkeys(text[sp[0]:sp[1]].strip() for sp in by.get("date", [])))[:3]
        who = None
        for sp in by.get("attribution", []):
            w = text[sp[0]:sp[1]].lower()
            if w == "according to": m = re.match(r"([^,.;]{3,70})", text[sp[1]:sp[1] + 80].strip()); who = m.group(1).strip() if m else who
            else:
                prev = [e for e in by.get("entity", []) if e[1] <= sp[0] and sp[0] - e[1] <= 3]
                if prev: who = text[prev[-1][0]:prev[-1][1]].strip()
            if who: break
        cues = [c for c in ("quote", "attribution", "modal", "negation", "change", "event") if by.get(c)]
        fac = "reported" if (by.get("attribution") or by.get("quote")) else ("predicted" if by.get("modal") else "asserted")
        trip = ["%s %s %s" % tuple(f["value"]) for f in facts if f["kind"] == "triple" and a <= f["s"] < b and isinstance(f.get("value"), list) and len(f["value"]) == 3 and f["value"][0] and f["value"][2]][:2]
        score = (1 if figs else 0) + (1 if ents else 0) + (1 if dates else 0) + (1 if who else 0) + (1 if trip else 0)
        out.append({"sentence": st[:260], "factuality": fac, "negated": bool(by.get("negation")), "source": who, "cues": cues, "figures": figs[:6], "entities": ents, "dates": dates, "claims": trip, "evidence_score": score, "span": [a, b]})
    return out, (time.perf_counter() - t0) * 1000, cnt, parse, ners

def pc(p): return int(round(float(p) * 100))
def top(names, p, k): o = np.argsort(-p)[:k]; return [{"name": str(names[int(i)]), "pct": pc(p[i])} for i in o]
def run_article(d):
    sparse = bool(d.get("sparse")); X = AN[sparse]; t0c = time.perf_counter(); title, body, date, cl = clean_input(d.get("title"), d.get("body"), d.get("date")); title = re.sub(r"\s+", " ", title).strip(); clean_ms = (time.perf_counter() - t0c) * 1000
    res = X.analyze(title, body, date); T = res["ms"]; text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; ds = (date + "T00:00:00Z") if date else None; S = E.S; ev = res["evidence"]; f = res["fields"]
    spans = SR.spans(text, ds); facts = FL.facts_for(text, ds)[0] if ev["parse_ran"] else []; kinds = collections.Counter(x["kind"] for x in facts)
    claims, claims_ms, scan_cnt, parse_cnt, ner_cnt = claims_layer(text, facts, date)
    tr = [(f["value"][1], f["value"][2]) for f in facts if f["kind"] == "triple" and isinstance(f.get("value"), list) and len(f["value"]) == 3 and f["value"][1] and f["value"][2]]
    cap_rec = sorted({"%s %s" % p for p in tr if p in CAP_REC}); cap_cand = sorted({"%s %s" % p for p in tr if p in CAP_CAND and p not in CAP_REC})
    # Area (49 topics) and Domain (17, rolled up by a fixed map)
    _dw = []; _dr = 0; _dt = max(1, len(re.sub(r"\s+", " ", body)))
    if ev["encoder_skipped"]:
        H = X.sparse; ptv = X._sparse_proba("topic", text); tn = [str(c) for c in H["topic_model"].classes_]; psv = X._sparse_proba("story", text); sn = [str(c) for c in H["story_model"].classes_]; basis = "BitMob Domain sparse (the v6b network was skipped)"
    else: ptv, psv, nw = X.reader.read(title, body); tn, sn = S["topic_cl"], S["story_cl"]; _dw = X.reader.windows(title, body); _dr = sum(len(w) for w in _dw); basis = "BitMob Domain v6b, %d windows of %d word pieces = %d%% of the body text (at most %d windows; text after that is not read)" % (nw, X.reader.max_pieces, min(100, round(100 * _dr / _dt)), X.reader.cap)
    dom = collections.defaultdict(float)
    for n, p in zip(tn, ptv): dom[(TOPIC2DOM.get(n) or ["unmapped"])[0]] += float(p)
    dl = sorted(dom.items(), key=lambda kv: -kv[1])[:4]
    t1 = time.perf_counter(); v = PLACE_ENC.encode(["query: " + (title + ". " + body)[:1500]], normalize_embeddings=True, show_progress_bar=False); pp = PLACE["model"].predict_proba(v)[0]; place_ms = (time.perf_counter() - t1) * 1000
    pl = top(PLACE["classes"], pp, 3); place_ok = float(pp.max()) >= PLACE["line"]
    t2 = time.perf_counter(); pulse = E.read(title + ". " + body[:1200]); pulse_ms = (time.perf_counter() - t2) * 1000
    cond = pulse.get("condition"); cpres = pulse.get("condition_present", {})
    topic_ok = f["topic"]["answer"] is not None; story_ok = f["story_type"]["answer"] is not None
    area_unsure = None if topic_ok else "below the confidence line, so the pipeline defers it"
    # in-depth story card
    names = collections.OrderedDict()
    for x in facts:
        if x["kind"] == "name": r = names.setdefault(x["text"].strip(), {"name": x["text"].strip(), "n": 0, "roles": collections.Counter()}); r["n"] += 1; r["roles"][x.get("role") or "?"] += 1
    ents = sorted(names.values(), key=lambda r: -r["n"])[:12]; ents = [{"name": r["name"], "mentions": r["n"], "roles": ", ".join(k for k, _ in r["roles"].most_common(2))} for r in ents]
    seen = set(); acts = []
    for x in facts:
        if x["kind"] == "triple" and isinstance(x.get("value"), list) and len(x["value"]) == 3:
            k = tuple(x["value"])
            if k not in seen: seen.add(k); acts.append({"subject": k[0], "verb": k[1], "object": k[2], "status": x.get("status"), "span": [x["s"], x["e"]]})
    allnums = [{"text": x["text"].strip(), "unit": x.get("unit") or "", "noun": x.get("noun") or "", "verb": x.get("verb") or "", "status": x.get("status"), "timepart": is_timepart(x)} for x in facts if x["kind"] == "amount"]
    nums = sorted([n for n in allnums if not n["timepart"]], key=lambda n: (n["unit"] == "", n["unit"] not in ("%", "$")))[:30]; timeparts = [n for n in allnums if n["timepart"]][:10]
    dates = [{"text": x["text"].strip(), "date": x.get("value"), "status": x.get("status")} for x in facts if x["kind"] == "date"][:8]
    times = [{"kind": x["kind"], "text": x["text"].strip()} for x in spans if x["kind"] not in ("number_word",)][:10]
    story = {"headline": title, "words": len(text.split()),
        "domain": {"top": [{"name": k, "pct": pc(v)} for k, v in dl], "how": "rolled up from the Area probabilities through a fixed 49-to-17 map (specs/topic_to_iptc_v1.json); there is no separate Domain model", "answered": topic_ok, "basis": basis},
        "area": {"top": top(tn, ptv, 5), "answered": topic_ok, "note": area_unsure, "basis": basis},
        "region": {"top": pl, "answered": place_ok, "line_pct": pc(PLACE["line"]), "note": None if place_ok else "below the confidence line, so the pipeline defers it"},
        "type": {"top": top(sn, psv, 4), "answered": story_ok},
        "condition": {"present": cpres.get("answer"), "present_pct": pc(cpres.get("confidence", 0)) if cpres else None, "which": cond.get("answer") if cond and cond.get("status") == "answered" else None, "which_pct": pc(cond["confidence"]) if cond else None, "direction": cond.get("direction") if cond else None, "size": cond.get("size") if cond else None, "status": cpres.get("status")},
        "entities": ents, "actions": acts[:14], "numbers": nums, "timeparts": timeparts, "dates": dates, "times": times}
    # every BitMob model, distinguished
    hm = HC["Domain (topic)"]; mh = lambda k: HC["Domain (topic)"].get(k, {}).get("value")
    models = [
     {"name": "BitMob Solver (the whole chain, tools first then models)", "status": "runs", "ran": True, "ms": round(T["total_ms"], 1), "output": "this page is one run of it: Fact finder, span rules, then the models below, then the Decider", "tested": "the Decider keeps only admitted fields; its rules are checked in Lean", "src": "ledger L1057"},
     {"name": "BitMob Domain v6b (22.6M network): topic head, shown as Area and Domain", "status": "runs, partly proven", "ran": True, "ms": round(T["reader_ms"], 1) if not ev["encoder_skipped"] else 0, "output": "Area %s %d%%; Domain %s %d%%" % (story["area"]["top"][0]["name"], story["area"]["top"][0]["pct"], story["domain"]["top"][0]["name"], story["domain"]["top"][0]["pct"]),
      "tested": "Agrees with the Sonnet labeller on %d%% of the sealed set (Area, best two guesses). Against human labels (MN-DS, 1,600 fresh articles, Area rolled up to Domain, lenient match): right on the first guess %d%% of the time, within two guesses %d%%; the bar is 80%%." % (pc(HC["Domain (topic)"]["model_accuracy"]["value"]), pc(json.load(open("runs/pulse/anchor_mnds_fresh_v6b-student.json"))["top1_lenient_rate"]), pc(mh("model_accuracy_human") or 0)), "src": "runs/pulse/end2end_v6b-student_sealed.json; anchor_mnds_fresh_v6b-student.json; head_table.json"},
     {"name": "BitMob Function (story type), served by BitMob Domain v6b", "status": "working", "ran": True, "ms": 0, "output": "%s %d%%" % (story["type"]["top"][0]["name"], story["type"]["top"][0]["pct"]), "tested": "agrees with the Sonnet labeller on %d%% of the sealed set; against human CheckThat opinion-or-fact labels the three-encoder student answers 57%% of reads at the tolerance, the single student 35%%" % pc(HC["Function (story type)"]["model_accuracy"]["value"]), "src": "end2end_v6b-student_sealed.json; t179/t184_combined_encoders_selective.json"},
     {"name": "BitMob Domain sparse (keyword model)", "status": "working, candidate front step", "ran": sparse, "ms": None, "output": ("answered both heads, encoder skipped" if ev["encoder_skipped"] else "not confident on both, passed to the encoder") if sparse else "off for this run", "tested": "not wired into production; saves the encoder time when both heads are confident", "src": "runs/expert1/sparse_heads_v2.pkl"},
     {"name": "BitMob Condition (with direction and size), served by BitMob Domain v6b", "status": "runs, output unreliable", "ran": True, "ms": round(pulse_ms, 1), "output": ("condition " + ", ".join(cond["answer"]) + " (%d%%), direction %s, size %s" % (pc(cond["confidence"]), cond.get("direction"), cond.get("size"))) if story["condition"]["which"] else ("no condition present (%d%% sure)" % story["condition"]["present_pct"] if cpres.get("answer") is False and cpres.get("status") == "answered" else "unsure"), "tested": "agrees with Clef (the engine's own reader) at AUROC 0.82; that is agreement, not truth, so the head is not admitted", "src": "head_table.json (Condition present)"},
     {"name": "Place student (region, 8 options): experiment, no BitMob name yet", "status": "experiment, saved today", "ran": True, "ms": round(place_ms, 1), "output": "%s %d%%%s" % (pl[0]["name"], pl[0]["pct"], "" if place_ok else " (below the " + str(pc(PLACE["line"])) + "% line: deferred)"), "tested": "answers 63% of reads at 95% agreement with Jev; on the stories it answers it matches a text-derived place judge 91% of the time, same as Jev. The judge reads the same text, so it is a proxy", "src": "runs/pulse/t182/t182_selective_place.json; t199/t199_place_vs_judge.json; t200/place_student.pkl"},
     {"name": "BitMob Function, sentence-level experiment (opinion or fact)", "status": "experiment, not loaded here", "ran": False, "ms": None, "output": "not run on this page", "tested": "answers 57% of reads at tolerance against Jev, fitted on 51,000 sentences; full replacement fails", "src": "runs/pulse/head_coverage.json"},
     {"name": "Factuality (happened or not): no BitMob name yet", "status": "not passing", "ran": False, "ms": None, "output": "teacher only", "tested": "CPU student 61 to 64% balanced accuracy against a bar of 80%; the teacher (Jev) stays", "src": "head_table.json"},
     {"name": "Time (recent): no BitMob name yet", "status": "no judge, stopped", "ran": False, "ms": None, "output": "none", "tested": "strict publish-date truth gives AUC 0.607; no trustworthy judge", "src": "head_table.json"},
     {"name": "BitMob Area (name only)", "status": "not built", "ran": False, "ms": None, "output": "the Area shown above is BitMob Domain v6b's topic head, the stand-in", "tested": "no separate Area model or outside judge for the 49 Areas", "src": "ledger L1057"},
     {"name": "BitMob Novelty", "status": "weak judge", "ran": False, "ms": None, "output": "none", "tested": "ignores the area list as worded (AUROC 0.51); not usable as pass or fail", "src": "head_table.json"},
     {"name": "BitMob Capability", "status": "extractor and two-tier list, no model, no outside truth", "ran": ev["parse_ran"], "ms": None, "output": "%d recurring, %d candidate%s" % (len(cap_rec), len(cap_cand), (": " + ", ".join((cap_rec + cap_cand)[:4])) if (cap_rec or cap_cand) else " (no listed verb-object pair in this story)"), "tested": "matches the story's triples against 371 cross-Area verb-object pairs; only 23 recur in both halves of the corpus by date (the other 348 are candidates); stable across publishers, no outside judge", "src": "runs/pulse/t230/capability_tiers.json"},
     {"name": "Fact finder: triples, names, amounts (BitMob Solver tool, not a model)", "status": "tool, no bar set", "ran": ev["parse_ran"], "ms": round(T["solver_ms"], 1), "output": "%d triples, %d names, %d amounts" % (kinds.get("triple", 0), kinds.get("name", 0), kinds.get("amount", 0)), "tested": "F1 0.402 on CaRB, recall 0.31; each triple is checked against the text", "src": "head_table.json (Claims)"}]
    RT = {"BitMob Solver (the whole chain, tools first then models)": ("yes", "the chain runs end to end; each part is only as trusted as its row below"),
          "BitMob Area (name only)": ("no model", "the 49 Areas come from the Domain v6b topic head; no outside judge for them"),
          "BitMob Domain v6b (22.6M network): topic head, shown as Area and Domain": ("yes", "partly proven: 68% right on the first guess vs human labels, 80% within two; bar is 80%"),
          "BitMob Function (story type), served by BitMob Domain v6b": ("yes", "proven only against the labeller (Sonnet); human opinion-or-fact labels cover part of it"),
          "BitMob Domain sparse (keyword model)": ("yes, if ticked", "not proven for production; a speed-up in front of the encoder"),
          "BitMob Condition (with direction and size), served by BitMob Domain v6b": ("yes", "UNPROVEN and it rarely fires: present on 12 of 230 sample articles and 0 of 20 business ones, and it says none present (95% sure) on a plain falling-stock, delayed-orders story I wrote as a test. Treat it as not working until a judge exists"),
          "Place student (region, 8 options): experiment, no BitMob name yet": ("yes", "proxy only: matches Jev and a text-based judge, no human truth"),
          "BitMob Function, sentence-level experiment (opinion or fact)": ("not on this page", "partly proven: answers 57% of reads at the tolerance, the rest go to the teacher"),
          "Factuality (happened or not): no BitMob name yet": ("no passing model", "the CPU student fails its bar (61 to 64% vs 80%); the teacher answers"),
          "Time (recent): no BitMob name yet": ("no model", "no judge to train or check one against"),
          "BitMob Novelty": ("no model that works", "the test judge is too weak to use"),
          "BitMob Capability": ("yes, as a list match", "no model; a match against a list of 23 recurring and 348 candidate verb-object pairs; no outside truth exists, so it cannot be called right or wrong"),
          "Fact finder: triples, names, amounts (BitMob Solver tool, not a model)": ("yes (a tool)", "scores F1 0.40 on a public test; no bar set")}
    for m in models: m["runs"], m["trust"] = RT[m["name"]]
    top1 = lambda key: story[key]["top"][0] if story[key]["top"] else {"name": "", "pct": 0}
    cw = story["condition"]; cout = (", ".join(cw["which"]) + " (%d%%), %s, size %s" % (cw["which_pct"], cw["direction"], cw["size"])) if cw["which"] else ("none present (%d%% sure)" % cw["present_pct"] if cw["status"] == "answered" and cw["present"] is False else "unsure")
    sparse_out = ("answered, v6b skipped" if ev["encoder_skipped"] else "unsure, passed to v6b") if sparse else "not ticked"
    table = [
     {"name": "BitMob Domain", "on": "ON", "output": "%s %d%%" % (top1("domain")["name"], top1("domain")["pct"]), "passes": "No", "why": "68% right on first guess, 80% in two; bar is 80%", "ms": round(T["reader_ms"], 1) if not ev["encoder_skipped"] else 0},
     {"name": "BitMob Area", "on": "ON", "output": "%s %d%%" % (top1("area")["name"], top1("area")["pct"]), "passes": "Not tested", "why": "49 areas have no human-labelled test set", "ms": None},
     {"name": "BitMob Function (story type)", "on": "ON", "output": "%s %d%%" % (top1("type")["name"], top1("type")["pct"]), "passes": "Not tested", "why": "agrees with the Sonnet labeller 92%; no human test on this output", "ms": None},
     {"name": "BitMob Condition", "on": "ON", "output": cout, "passes": "No", "why": "says none on business news: 0 of 20 fire; only checked against Clef", "ms": round(pulse_ms, 1)},
     {"name": "BitMob Domain sparse", "on": "ON" if sparse else "OFF", "output": sparse_out, "passes": "Not tested", "why": "optional speed-up; tick the box to turn it on", "ms": None},
     {"name": "Place (no BitMob name yet)", "on": "ON", "output": "%s %d%%%s" % (story["region"]["top"][0]["name"], story["region"]["top"][0]["pct"], "" if place_ok else " (below its line)"), "passes": "Not tested", "why": "matches Jev 95% when it answers; no human test", "ms": round(place_ms, 1)},
     {"name": "BitMob Function, sentence level", "on": "OFF", "output": "—", "passes": "No", "why": "exists but not loaded here; answers only 57% of reads inside tolerance", "ms": None},
     {"name": "Factuality, whole-story model (no BitMob name yet)", "on": "OFF", "output": "—", "passes": "No", "why": "CPU student 61 to 64% vs bar 80%; the teacher Jev does it. Per-claim factuality (reported, asserted, predicted, denied) comes from BitMob tools rule cues in section 2, untested", "ms": None},
     {"name": "Time, story-level 'recent' model (no BitMob name yet)", "on": "OFF", "output": "—", "passes": "No", "why": "no model; no truth to check one. Dates and time spans in the text come from BitMob tools (section 2)", "ms": None},
     {"name": "BitMob Novelty", "on": "OFF", "output": "—", "passes": "No", "why": "not built; the test judge is too weak to use", "ms": None},
     {"name": "BitMob Capability", "on": "ON", "output": "%d recurring, %d candidate" % (len(cap_rec), len(cap_cand)), "passes": "Not tested", "why": "list match, no model; 23 pairs recur across two periods, no outside truth", "ms": None}]
    t_s = time.perf_counter(); SG.scan(text, date); scan_ms = (time.perf_counter() - t_s) * 1000
    stc = collections.Counter(x.get("status") for x in facts); fr = sum(1 for c in claims if c["figures"]); rep = sum(1 for c in claims if c["factuality"] == "reported")
    tools = [
     {"step": "URL parser", "in_out": "not applicable: pasted text has no URL", "ms": 0, "wired": "harvest only (section words)"},
     {"step": "Metadata", "in_out": "date %s%s; headline %d characters" % (date or "none", " (from the " + cl["date_source"] + ")" if cl["date_source"] and cl["date_source"] != "given" else "", len(title)), "ms": 0, "wired": "harvest only (date)"},
     {"step": "Clean", "in_out": "%d of %d lines kept (dropped nav, image names, short fragments)" % (cl["lines_kept"], cl["lines_in"]), "ms": round(clean_ms, 1), "wired": "bench only (analyze2 expects clean text)"},
     {"step": "Windows", "in_out": ("%d windows of 64 word pieces" % ev["windows"]) if not ev["encoder_skipped"] else "skipped: sparse model answered", "ms": 0, "wired": "analyze2"},
     {"step": "Scan (11 spot classes)", "in_out": ", ".join("%d %s" % (v, k) for k, v in scan_cnt.most_common()) or "nothing", "ms": round(scan_ms, 1), "wired": "analyze2 (inside the Fact finder)"},
     {"step": "spaCy parse (NER off)", "in_out": "%d sentences, %d past and %d present verbs, %d passive, %d modals" % (parse_cnt["sentences"], parse_cnt["past_verbs"], parse_cnt["present_verbs"], parse_cnt["passive"], parse_cnt["modals"]), "ms": None, "wired": "analyze2 (inside the Fact finder)"},
     {"step": "Fact finder", "in_out": "%d triples, %d names, %d amounts, %d dates" % (kinds.get("triple", 0), kinds.get("name", 0), kinds.get("amount", 0), kinds.get("date", 0)), "ms": round(T["solver_ms"], 1), "wired": "analyze2"},
     {"step": "Validator", "in_out": "%d stated, %d unbound (text cannot back it) of %d facts" % (stc.get("stated", 0), stc.get("unbound", 0), len(facts)), "ms": 0, "wired": "analyze2 (checks inside each fact)"},
     {"step": "Word lists", "in_out": "speech verbs, event words, quote marks: counted inside Scan (attribution, event, quote above)", "ms": 0, "wired": "analyze2 (counts not saved)"},
     {"step": "spaCy NER (cross-check)", "in_out": ", ".join("%d %s" % (v, k) for k, v in ner_cnt.most_common(6)), "ms": None, "wired": "NOT wired: disabled in analyze2; shown here as a cross-check only"},
     {"step": "Span rules", "in_out": "%d relative-time, number-word, age, duration spans" % len(spans), "ms": round(T["span_rules_ms"], 1), "wired": "analyze2"},
     {"step": "Sentence evidence table", "in_out": "%d sentences; %d carry figures; %d reported or quoted" % (len(claims), sum(1 for c in claims if c["figures"]), sum(1 for c in claims if c["factuality"] == "reported")), "ms": round(claims_ms, 1), "wired": "bench view built from the Scan, Fact finder and parse output above; not in analyze2, not tested"},
     {"step": "Decider", "in_out": "%d fields decided" % len(f), "ms": round(T["decider_ms"], 2), "wired": "analyze2 (Lean-checked rules)"}]
    abst = [m for m in ("area", "region", "type") if not story[m]["answered"]]
    use = [
     {"step": "G3 to journal", "built": "previewed only: this bench writes nothing", "what": "%d labels would be appended with their confidence and source; %d are abstentions, kept as 'unknown' instead of guessed." % (len(f) + len([k for k in pulse if isinstance(pulse[k], dict)]), len(abst) + sum(1 for k in ("change", "size", "traits") if f[k]["answer"] is None))},
     {"step": "G4 align (identity, dedup, contradictions)", "built": "not built", "what": "would take %d named mentions as candidate entities and %d subject-verb-object triples as candidate links, each with its text span as evidence, and merge them with what earlier stories said." % (len(ents), len(acts))},
     {"step": "G5 ontology", "built": "not built", "what": ("Area %s is a seeded Area, so the story attaches to it" % story["area"]["top"][0]["name"]) if topic_ok else "the Area head is unsure, so the story is held as uncertain and counts toward a novelty check, not forced into an Area."},
     {"step": "Macro Pulse tally", "built": "not built as a live tally", "what": ("+1 story under Domain %s, Area %s" % (story["domain"]["top"][0]["name"], story["area"]["top"][0]["name"]) if topic_ok else "no Area to count") + ((", condition " + ", ".join(cond["answer"]) + " " + str(cond.get("direction")) + ", size " + str(cond.get("size"))) if story["condition"]["which"] else "") + (", region " + pl[0]["name"] if place_ok else "") + "."},
     {"step": "Teacher routing", "built": "rule exists; the bench does not call a teacher", "what": ("Deferred to the teacher (Jev, or local Clef): " + ", ".join(abst) + ".") if abst else "Nothing deferred on the heads that ran; the not-built heads (time, novelty, capability, factuality) still go to the teacher."}]
    _full = len(re.sub(r"\s+", " ", title + ". " + body)); _pl = len(title + ". " + body)
    _pct = lambda r, t: min(100, round(100 * r / max(1, t)))
    COVER = {"article_chars": _full, "rows": [
        ({"model": "BitMob Domain v6b: Area, Domain, story type, Condition", "read": _dr, "total": _dt, "pct": _pct(_dr, _dt), "rule": "%d of at most %d windows of %d word pieces, headline repeated in each; body text after the last window is not read (body characters shown)" % (len(_dw), X.reader.cap, X.reader.max_pieces)} if not ev["encoder_skipped"] else
         {"model": "BitMob Domain sparse keyword model (the encoder was skipped)", "read": min(12000, _full), "total": _full, "pct": _pct(min(12000, _full), _full), "rule": "cleaned text up to 12,000 characters"}),
        {"model": "BitMob tools: Fact finder, span rules, Capability match", "read": min(12000, _full), "total": _full, "pct": _pct(min(12000, _full), _full), "rule": "cleaned text up to 12,000 characters"},
        {"model": "Place student (region)", "read": min(1500, _pl), "total": _pl, "pct": _pct(min(1500, _pl), _pl), "rule": "first 1,500 characters of title plus body"}]}
    COVER["warn"] = ("Not every model read the whole article: " + "; ".join("%s read %d%%" % (r["model"].split(":")[0].split(" (")[0], r["pct"]) for r in COVER["rows"] if r["pct"] < 100) + ". Text after each cut is not used by that model.") if any(r["pct"] < 100 for r in COVER["rows"]) else ""
    return {"coverage": COVER, "ms": T, "story": story, "models": models, "table": table, "tools": tools, "claims": claims, "clean": cl, "claims_ms": round(claims_ms, 1), "use": use, "engine_map": ENGINE_MAP, "text": text, "g0": {"characters": len(text), "words": len(text.split()), "sha1": hashlib.sha1(text.encode()).hexdigest()[:16], "date": date},
            "spans": [{"s": x["s"], "e": x["e"], "k": x["kind"]} for x in spans], "facts": [{"s": x["s"], "e": x["e"], "k": x["kind"]} for x in facts if x["kind"] in ("amount", "date", "name", "triple")], "pulse_ms": round(pulse_ms, 1), "place_ms": round(place_ms, 1)}

def badge(r):
    st = r["story"]; c = st["condition"]; top = lambda k: (st[k]["top"][0] if st[k]["top"] else {"name": "", "pct": 0})
    return {"area": st["area"]["answered"], "area_name": top("area")["name"], "area_pct": top("area")["pct"], "domain": top("domain")["name"], "domain_pct": top("domain")["pct"],
            "type": st["type"]["answered"], "type_name": top("type")["name"], "type_pct": top("type")["pct"],
            "cond": c["status"] == "answered", "cond_present": bool(c["which"]), "cond_name": ", ".join(c["which"]) if c["which"] else ("none" if c["status"] == "answered" else ""),
            "region": st["region"]["answered"], "region_name": top("region")["name"], "region_pct": top("region")["pct"], "triples": len(st["actions"]), "amounts": len(st["numbers"]), "names": len(st["entities"])}
import threading
def fill_badges():
    for k, v in list(ART.items()):
        try: v["badge"] = badge(run_article({"title": v["title"], "body": v["body"], "date": v.get("date")}))
        except Exception as e: v["badge"] = None
    print("badges ready", flush=True)
class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode(); self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p, _, q = self.path.partition("?")
        if p in ("/", "/index.html"): return self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/api/articles": return self.send(200, [{"id": k, "group": v["group"], "title": v["title"][:110], "words": len(v["body"].split()), "badge": v.get("badge")} for k, v in ART.items()])
        if p == "/api/article": a = ART.get(q.replace("id=", "")); return self.send(200 if a else 404, a or {"error": "no such article"})
        if p == "/api/heads": return self.send(200, heads())
        self.send(404, {"error": "not found"})
    def do_POST(self):
        if self.path != "/api/run": return self.send(404, {"error": "not found"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"); t, b = (d.get("title") or "").strip(), (d.get("body") or "").strip()
        if not b: return self.send(400, {"error": "body is empty"})
        try: self.send(200, run_article(d))
        except Exception as e: self.send(500, {"error": repr(e)})
    def log_message(self, *a): pass
if __name__ == "__main__": fill_badges(); print("simulation on http://localhost:%d/ (%d articles)" % (PORT, len(ART)), flush=True); ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
