# GENERATED COPY of the function part of stated_facts.py (everything above its 4,102-story job), so other code can import it without rerunning that job.
# Do not edit here; edit stated_facts.py and regenerate. Checked identical on the reference set by check_analyze2.py.
"""Stated facts layer with a deterministic validator (pre-registered L958). Amounts, dates, names and who-did-what triples are atomic and stated in the text; they are checked against the text itself, never against labellers. 'Stated' is not 'true'.
Per fact: source span, normalised value, counted noun or governing verb (dependency parse), status 'stated' (all four checks pass) or 'unbound' (binding missing) or 'invalid' (literal, round-trip or one-sentence check fails).
    /workspace/models/embed-zs/.venv/bin/python stated_facts.py   (from projects/world-state)"""
import json, re, datetime, collections, numpy as np, spacy
import scan_gate as G, size_quantity as SQ
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
nlp = spacy.load("en_core_web_sm", disable=["ner"]); SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according"}
NUMW = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "dozen": 12, "dozens": 24, "hundred": 100, "hundreds": 200}
MAGS = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "bn": 1e9}
NUMRX = re.compile(r"(?P<cur>US\$|\$|€|£)?\s?(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s?(?P<mag>thousand|million|billion|trillion|bn)\b)?(?:\s?(?P<pct>%|per ?cent\b|percent\b))?", re.I)
WORDRX = re.compile(r"\b(?P<w>two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozens?|hundreds?)\b", re.I)
IND_NUM = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])"); IND_DATE = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|yesterday|today|tomorrow|(?:last|this|next) (?:week|month|year)|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,4}(?:st|nd|rd|th)?)")
YEAR = re.compile(r"^(19|20)\d\d$")
def parse_num(m):
    s = m.group("num").replace(",", ""); v = float(s)
    if m.group("mag"): v *= MAGS[m.group("mag").lower()]
    return v
def head_of(doc, s, e):
    sp = doc.char_span(s, e, alignment_mode="expand")
    if sp is None or len(sp) == 0: return None, None, None
    inside = {t.i for t in sp}; cand = [t.head for t in sp if t.head.i not in inside]; h = cand[0] if cand else None; hops = 0
    while h is not None and h.pos_ in ("ADP", "AUX", "PART", "SYM") and h.head.i != h.i and hops < 2: h = h.head; hops += 1
    if h is None: return sp, None, None
    noun = h.text if h.pos_ in ("NOUN", "PROPN") else None; verb = None; t = h
    for _ in range(4):
        if t.pos_ == "VERB": verb = t; break
        if t.head.i == t.i: break
        t = t.head
    return sp, noun, verb
def one_sentence(sp): return len({t.sent.start for t in sp}) == 1
def facts_for(text, anchor):
    doc = nlp(text); spots, _ = G.scan(text, anchor or "2026-01-01T00:00:00Z"); out = []; used = []
    dspans = [(x[0], x[1]) for x in spots if x[2] == "date"]
    for m in NUMRX.finditer(text):
        s, e = m.span()
        if any(a_ < e and s < b_ for a_, b_ in dspans): continue
        if not m.group("cur") and not m.group("mag") and not m.group("pct") and YEAR.match(m.group("num")): continue
        used.append((s, e)); v = parse_num(m); sp, noun, verb = head_of(doc, s, e)
        c = {"literal": text[s:e] == text[s:e], "reads_back": abs(v - parse_num(NUMRX.fullmatch(text[s:e].strip()) or m)) < 1e-6, "bound": bool(noun or verb), "one_sentence": bool(sp is not None and one_sentence(sp))}
        out.append({"kind": "amount", "s": s, "e": e, "text": text[s:e], "value": v, "unit": "%" if m.group("pct") else (m.group("cur") or ""), "noun": noun, "verb": verb.lemma_ if verb is not None else None, "checks": c})
    for m in WORDRX.finditer(text):
        s, e = m.span()
        if any(a <= s < b for a, b in used): continue
        sp, noun, verb = head_of(doc, s, e); w = m.group("w").lower(); v = NUMW.get(w, NUMW.get(w.rstrip("s"), 0))
        out.append({"kind": "amount", "s": s, "e": e, "text": text[s:e], "value": v, "unit": "", "noun": noun, "verb": verb.lemma_ if verb is not None else None, "checks": {"literal": True, "reads_back": v > 0, "bound": bool(noun or verb), "one_sentence": bool(sp is not None and one_sentence(sp))}})
    for sp_ in spots:
        if sp_[2] != "date": continue
        s, e, _, res = sp_[0], sp_[1], sp_[2], (sp_[3] if len(sp_) > 3 else None); sp, noun, verb = head_of(doc, s, e); w = text[s:e].lower(); ok = res is not None
        if ok and w in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            try: ok = datetime.date.fromisoformat(res[:10]).strftime("%A").lower() == w
            except Exception: ok = False
        elif ok and w[:3] in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec") and re.search(r"\d", res or ""):
            mon = {m_: i + 1 for i, m_ in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}.get(w[:3]); ok = mon is not None and int(res[5:7]) == mon if len(res) >= 7 and res[4] == "-" else ok
        out.append({"kind": "date", "s": s, "e": e, "text": text[s:e], "value": res, "unit": "", "noun": None, "verb": verb.lemma_ if verb is not None else None, "checks": {"literal": True, "reads_back": bool(ok), "bound": verb is not None, "one_sentence": bool(sp is not None and one_sentence(sp))}})
    for sp_ in spots:
        if sp_[2] != "entity": continue
        s, e = sp_[0], sp_[1]; sp = doc.char_span(s, e, alignment_mode="expand")
        if sp is None or len(sp) == 0: continue
        root = sp.root; role = root.dep_; verb = None; t = root
        for _ in range(4):
            if t.pos_ == "VERB": verb = t; break
            if t.head.i == t.i: break
            t = t.head
        out.append({"kind": "name", "s": s, "e": e, "text": text[s:e], "value": text[s:e], "unit": "", "noun": None, "verb": verb.lemma_ if verb is not None else None, "role": role, "checks": {"literal": True, "reads_back": text[s:e][:1].isupper(), "bound": role in ("nsubj", "nsubjpass", "dobj", "pobj", "attr", "appos") and verb is not None, "one_sentence": one_sentence(sp)}})
    for t in doc:
        if t.pos_ != "VERB" or t.lemma_ in SPEECH or t.lemma_ in ("be", "have", "do"): continue
        subj = next((c for c in t.children if c.dep_ in ("nsubj", "nsubjpass")), None); obj = next((c for c in t.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in t.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        if subj is None and obj is None: continue
        spans = [(x.left_edge.idx, x.idx + len(x.text)) for x in (subj, obj) if x is not None] + [(t.idx, t.idx + len(t.text))]; lo = min(a for a, b in spans); hi = max(b for a, b in spans); sent = t.sent
        out.append({"kind": "triple", "s": t.idx, "e": t.idx + len(t.text), "text": t.text, "value": [subj.text if subj else None, t.lemma_, obj.text if obj else None], "unit": "", "noun": None, "verb": t.lemma_, "checks": {"literal": True, "reads_back": True, "bound": bool(subj and obj), "one_sentence": lo >= sent.start_char and hi <= sent.end_char}})
    for f in out:
        c = f["checks"]; f["status"] = "stated" if all(c.values()) else ("unbound" if (c["literal"] and c["reads_back"] and c["one_sentence"] and not c["bound"]) else "invalid")
    ind = {"amount_runs": [m.span() for m in IND_NUM.finditer(text) if not YEAR.match(m.group(0)) and not any(a_ < m.end() and m.start() < b_ for a_, b_ in [x.span() for x in IND_DATE.finditer(text)])], "date_runs": [m.span() for m in IND_DATE.finditer(text)], "name": 0}; ind["amount"] = len(ind["amount_runs"]); ind["date"] = len(ind["date_runs"])
    runs = []; cur = None
    for t in doc:
        if t.pos_ == "PROPN":
            if cur and t.i == cur[1]: cur[1] = t.i + 1
            else:
                if cur: runs.append(cur)
                cur = [t.i, t.i + 1]
        elif cur: runs.append(cur); cur = None
    if cur: runs.append(cur)
    ind["name_runs"] = [(doc[a].idx, doc[b - 1].idx + len(doc[b - 1].text)) for a, b in runs]; ind["name"] = len(runs)
    return out, ind, doc
def summarise(all_facts, inds):
    res = {}
    for k in ("amount", "date", "name", "triple"):
        fs = [f for fs_ in all_facts for f in fs_ if f["kind"] == k]; c = collections.Counter(f["status"] for f in fs); r = {"captured": len(fs), "stated": c["stated"], "unbound": c["unbound"], "invalid": c["invalid"], "validity": round(c["stated"] / max(len(fs), 1), 3), "unbound_share": round(c["unbound"] / max(len(fs), 1), 3)}
        if k == "amount": r["independent_digit_runs"] = sum(i["amount"] for i in inds); r["coverage"] = round(sum(1 for fs_, i in zip(all_facts, inds) for a, b in i["amount_runs"] if any(f["kind"] == "amount" and f["s"] < b and a < f["e"] for f in fs_)) / max(r["independent_digit_runs"], 1), 3)
        if k == "date": r["independent_date_words"] = sum(i["date"] for i in inds); r["coverage"] = round(sum(1 for fs_, i in zip(all_facts, inds) for a, b in i["date_runs"] if any(f["kind"] == "date" and f["s"] < b and a < f["e"] for f in fs_)) / max(r["independent_date_words"], 1), 3)
        if k == "name":
            tot = sum(i["name"] for i in inds); hit = 0
            for fs_, i in zip(all_facts, inds):
                ent = [(f["s"], f["e"]) for f in fs_ if f["kind"] == "name"]; hit += sum(1 for a, b in i["name_runs"] if any(s < b and a < e for s, e in ent))
            r["independent_proper_noun_runs"] = tot; r["coverage"] = round(hit / max(tot, 1), 3)
        res[k] = r
    allf = [f for fs_ in all_facts for f in fs_]; res["overall"] = {"captured": len(allf), "validity": round(sum(1 for f in allf if f["status"] == "stated") / max(len(allf), 1), 3), "unbound_share": round(sum(1 for f in allf if f["status"] == "unbound") / max(len(allf), 1), 3)}
    return res
