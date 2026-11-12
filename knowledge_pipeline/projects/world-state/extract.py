"""extract: one record per article, written once, read by every head and by the training-set builder (owner direction 2026-11-07; extends analyze2's tools, does not replace them).
Each item carries the tool, version and evidence span that produced it. Tools: source and links, span rules (dates, years, durations, ages, number words), boilerplate strip, scan spots, spaCy parse (sentence factuality, change-with-direction), spaCy entity types, places linked to GeoNames with an alias table, the Fact finder, the URL section, the BitMob Domain (v6b) (main process).
    /workspace/models/embed-zs/.venv/bin/python extract.py [N]   -> runs/harvest/extract.jsonl, extract_topic_probs.npy"""
import json, re, sys, time, collections
from multiprocessing import Pool
from urllib.parse import urlparse
V = "extract-v1"
LINK = re.compile(r"https?://[^\s<>\")\]]+|\bwww\.[^\s<>\")\]]+", re.I)
ALIAS = {"U.S.": "US", "US": "US", "U.S": "US", "USA": "US", "United States": "US", "America": "US", "UK": "GB", "U.K.": "GB", "Britain": "GB", "Great Britain": "GB", "United Kingdom": "GB", "England": "GB", "Scotland": "GB", "Wales": "GB", "Northern Ireland": "GB",
         "UAE": "AE", "Russia": "RU", "South Korea": "KR", "North Korea": "KP", "Korea": "KR", "Ivory Coast": "CI", "Czech Republic": "CZ", "Burma": "MM", "Congo": "CD", "Taiwan": "TW", "Hong Kong": "HK", "Vietnam": "VN", "Iran": "IR", "Syria": "SY", "Venezuela": "VE", "Bolivia": "BO", "Tanzania": "TZ", "Palestine": "PS", "Gaza": "PS", "West Bank": "PS",
         "Va.": "US", "Ariz.": "US", "Fla.": "US", "N.J.": "US", "D.C.": "US", "DC": "US", "Calif.": "US", "Mass.": "US", "Pa.": "US", "Tenn.": "US", "Ga.": "US", "Mich.": "US", "Wash.": "US", "Ore.": "US", "Colo.": "US", "Conn.": "US", "Ill.": "US", "Ind.": "US", "Minn.": "US", "Mo.": "US", "N.Y.": "US", "N.C.": "US", "Ohio": "US", "Okla.": "US", "Tex.": "US", "Wis.": "US", "Wash": "US", "White House": "US", "Washington": "US", "Capitol Hill": "US"}
TLD = {"uk": "GB", "au": "AU", "ca": "CA", "in": "IN", "nz": "NZ", "za": "ZA", "sg": "SG", "pk": "PK", "ng": "NG", "ie": "IE", "ke": "KE", "my": "MY", "ph": "PH", "hk": "HK", "tw": "TW", "jp": "JP", "de": "DE", "fr": "FR"}
SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according", "claim", "allege", "insist", "suggest", "argue", "reveal", "confirm", "deny", "explain"}
DECIDE = {"approve", "rule", "vote", "decide", "sentence", "ban", "sign", "appoint", "elect", "reject", "pass", "order", "convict", "acquit", "fire", "hire", "name", "resign", "veto"}
REQUEST = {"urge", "call", "ask", "demand", "request", "plead", "appeal", "beg", "invite"}
PLAN = {"plan", "intend", "schedule", "propose", "aim", "vow", "pledge", "promise", "set"}; PRED = {"expect", "predict", "forecast", "project", "estimate", "fear", "likely", "anticipate"}
COND = {"rising": ("up", "rise increase grow surge jump climb soar spike boost gain hike double triple"), "falling": ("down", "fall drop decline decrease plunge slump shrink cut reduce slash tumble ease dip slide plummet halve"),
        "delayed": ("none", "delay postpone defer stall"), "disrupted": ("none", "disrupt halt suspend cancel shut block interrupt strand ground"), "expanded": ("up", "expand extend widen broaden")}
LEX = {w: (c, d) for c, (d, ws) in COND.items() for w in ws.split()}
def init():
    global nlp, ctry, city, adm, BP, FL, G, HV, SR
    import spacy, scan_gate as G, facts_lib as FL, harvest as HV, span_rules as SR
    nlp = spacy.load("en_core_web_sm"); ctry = {}; city = collections.defaultdict(dict); adm = collections.defaultdict(set); gd = "/workspace/data/geo/"
    for l in open(gd + "countryInfo.txt", encoding="utf-8"):
        if l[0] != "#": f = l.rstrip("\n").split("\t"); ctry[f[4]] = f[0]
    for l in open(gd + "cities15000.txt", encoding="utf-8"):
        f = l.split("\t")
        for nm in (f[1], f[2]): city[nm][f[8]] = max(city[nm].get(f[8], 0), int(f[14] or 0))
    for l in open(gd + "admin1CodesASCII.txt", encoding="utf-8"):
        f = l.rstrip("\n").split("\t"); adm[f[1]].add(f[0].split(".")[0]); adm[f[2]].add(f[0].split(".")[0])
    BP = json.load(open("runs/harvest/boilerplate.json"))["domains"]
def place_country(name, dom, explicit):
    n = re.sub(r"^the ", "", name.strip(), flags=re.I)
    if n in ALIAS: return ALIAS[n], "alias"
    if n in ctry: return ctry[n], "country name"
    if n in adm and len(adm[n]) == 1: return next(iter(adm[n])), "region name"
    cs = city.get(n) or {}
    if not cs and n in adm: cs = {c: 0 for c in adm[n]}
    if not cs: return None, None
    if len(cs) == 1: return next(iter(cs)), "city, one country"
    hit = [c for c in cs if c in explicit]
    if hit: return hit[0], "city, country named in article"
    tl = TLD.get(dom.rsplit(".", 1)[-1]); 
    if tl in cs: return tl, "city, publisher country"
    return max(cs, key=cs.get), "city, largest"
def work(r):
    t0 = time.perf_counter(); dom = r["domain"] or ""; bad = set(BP.get(dom, [])); raw = (r["text"] or ""); lines = raw.split("\n"); kept = [l for l in lines if re.sub(r"\s+", " ", l).strip() not in bad]; removed = len(lines) - len(kept)
    body = re.sub(r"\s+", " ", " ".join(kept)).strip()[:12000]; title = re.sub(r"\s+", " ", r["title"] or ""); text = title + ". " + body; date = (r["date"] or "")[:10] or None
    segs = [s.lower() for s in urlparse(r["url"] or "").path.split("/") if s]; sw = next((s for s in segs[:-1] if s in HV.SEC or s in HV.FN), None)
    rec = {"v": V, "row": r["row"], "source": {"url": r["url"], "domain": dom, "date": date, "description": r["description"], "links_in_text": LINK.findall(raw)[:20], "section": sw, "tool": "source-v0"}, "clean": {"boilerplate_lines_removed": removed, "chars": len(text), "tool": "boilerplate-v0"}, "text": text}
    d = nlp(text); sents = list(d.sents); fx = []; ch = []; sc = collections.Counter()
    for s in sents:
        toks = [t for t in s]; lem = {t.lemma_.lower() for t in toks}; low = s.text.lower(); root = s.root
        rootneg = any(c.dep_ == "neg" for c in root.children); modal = {t.lower_ for t in toks if t.tag_ == "MD"}; past = root.tag_ in ("VBD", "VBN"); subj = any(c.dep_ in ("nsubj", "nsubjpass") for c in root.children)
        if s.text.strip().endswith("?"): tag = "question"
        elif lem & SPEECH or "according to" in low: tag = "reported"
        elif rootneg and root.pos_ in ("VERB", "AUX"): tag = "denied"
        elif root.lemma_.lower() in REQUEST and root.pos_ == "VERB" or "should" in modal or "must" in modal or (root.dep_ == "ROOT" and root.tag_ == "VB" and root.i == s.start and not subj): tag = "request"
        elif root.lemma_.lower() in DECIDE and past and subj: tag = "decision"
        elif modal & {"will", "shall", "'ll"} or (lem & PLAN and "to" in low): tag = "planned"
        elif modal & {"may", "might", "could", "would"} or lem & PRED: tag = "predicted"
        elif root.pos_ in ("VERB", "AUX"): tag = "asserted"
        else: tag = "unknown"
        sc[tag] += 1; fx.append([s.start_char, s.end_char, tag])
        for t in toks:
            lm = t.lemma_.lower()
            if lm in LEX and (t.pos_ == "VERB" or t.pos_ == "NOUN"):
                thing = None
                for c in t.children:
                    if c.dep_ in ("nsubj", "nsubjpass", "dobj"): thing = c
                    elif c.dep_ == "prep" and c.lower_ in ("in", "of"): thing = next((g for g in c.children if g.dep_ == "pobj"), thing)
                if thing is not None: ch.append({"condition": LEX[lm][0], "direction": LEX[lm][1], "word": t.text, "thing": thing.lemma_.lower(), "span": [t.idx, t.idx + len(t.text)], "negated": any(c.dep_ == "neg" for c in t.children)})
    rec["function"] = {"sentences": fx, "counts": dict(sc), "opinion_section": sw in ("opinion", "opinions", "editorial", "comment", "commentary", "blog", "blogs"), "tool": "factuality-rules-v1"}
    rec["conditions"] = {"items": ch[:20], "tool": "change-lexicon-v0"}
    ents = [(x.text.strip(), x.label_, x.start_char, x.end_char) for x in d.ents]; rec["entities"] = {"counts": dict(collections.Counter(e[1] for e in ents)), "items": [[a, b, c, e_] for a, b, c, e_ in ents if b in ("ORG", "PERSON", "NORP", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW")][:30], "tool": "spacy-ner-v0"}
    pl = [e for e in ents if e[1] in ("GPE", "LOC", "FAC")]; explicit = {ALIAS[re.sub(r"^the ", "", p[0], flags=re.I)] if re.sub(r"^the ", "", p[0], flags=re.I) in ALIAS else ctry.get(re.sub(r"^the ", "", p[0], flags=re.I)) for p in pl} - {None}; out = []
    for nm, lab, a, b in pl:
        c, how = place_country(nm, dom, explicit); out.append({"text": nm, "country": c, "how": how, "span": [a, b]})
    rec["places"] = {"items": out[:30], "countries": dict(collections.Counter(p["country"] for p in out if p["country"])), "tool": "geonames+alias-v0"}
    sp, _ = G.scan(body, date + "T00:00:00Z" if date else None); rec["scan"] = {"counts": dict(collections.Counter(x[2] for x in sp)), "tool": "scan_gate"}
    try: f = FL.facts_for(text, date + "T00:00:00Z" if date else None)[0]
    except Exception: f = []
    rec["facts"] = {"counts": dict(collections.Counter(x["kind"] + "_" + x["status"] for x in f)), "amounts": [x["text"] for x in f if x["kind"] == "amount" and x["status"] == "stated"][:8], "dates": [x["text"] for x in f if x["kind"] == "date" and x["status"] == "stated"][:5], "tool": "fact-finder"}
    ms_ = SR.spans(text, date + "T00:00:00Z" if date else None); rec["more_spans"] = {"counts": dict(collections.Counter(x["kind"] for x in ms_)), "items": [[x["kind"], x["s"], x["e"], x["value"]] for x in ms_ if x["kind"] != "number_word" or x["value"] is not None][:60], "tool": "span-rules-v0"}
    rec["domain_label"] = ({"label": HV.SEC[sw], "tool": "url_section", "evidence": sw} if sw in HV.SEC else None); rec["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return rec
if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000; R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]; t0 = time.time()
    with Pool(16, initializer=init) as P: out = P.map(work, R, chunksize=10)
    wall = time.time() - t0; print("tools pass", len(out), "articles in", round(wall), "s =", round(len(out) / wall, 1), "per second")
    import numpy as np; sys.path.insert(0, "."); import analyze2 as A2; from expert1_runtime import ExpertS
    e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); S = e.S; X = A2.Analyzer(S, json.load(open("runs/pulse/field_table.json")), threads=8); vecs = []; t1 = time.time()
    for rec, r in zip(out, R):
        pt, ps, nw = X.reader.read(r["title"] or "", rec["text"][len(r["title"] or "") + 2:]); rec["reader"] = {"topic_top2": [S["topic_cl"][k] for k in np.argsort(-pt)[:2]], "story_type": S["story_cl"][int(ps.argmax())], "story_p": round(float(ps.max()), 3), "windows": nw, "tool": "bitmob-reader-v6b"}
        vecs.append(pt.astype(np.float16))
    np.save("runs/harvest/extract_topic_probs.npy", np.array(vecs)); print("reader pass", round(time.time() - t1), "s")
    with open("runs/harvest/extract.jsonl", "w") as w:
        for rec in out: w.write(json.dumps(rec) + "\n")
    json.dump({"articles": len(out), "tools_seconds": round(wall, 1), "per_second_no_reader": round(len(out) / wall, 2)}, open("runs/harvest/extract_run.json", "w"))
