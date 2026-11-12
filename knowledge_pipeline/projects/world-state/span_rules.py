"""Date, year, duration, age and number-word spans that scan_gate.py and facts_lib.py do not capture. Plain regex rules, no model. Each span: kind, s, e, text, value (normalised or None).
Found by the recall audit against spaCy NER (ner_recall_audit.py, runs/harvest/recall_audit.json). Existing tools are unchanged; callers take the union.
    spans(text, anchor_iso) -> list of dicts"""
import re, datetime
MN = "January February March April May June July August September October November December".split(); MAB = {m[:3].lower(): i + 1 for i, m in enumerate(MN)}; MAB["sept"] = 9
MON = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
UNITW = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(); TENW = "twenty thirty forty fifty sixty seventy eighty ninety".split()
WV = {w: i for i, w in enumerate(UNITW)}; WV.update({w: 20 + 10 * i for i, w in enumerate(TENW)})
NW = r"(?:(?:%s)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|%s)" % ("|".join(TENW), "|".join(UNITW))
SCALE = {"hundred": 100, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
UNIT = r"(?:day|week|month|year|hour|minute|decade|season|quarter|night)s?"; DUNIT = r"(?:day|week|month|year|hour|minute|decade|season)s?"
YEARS = r"(?:19|20)\d{2}"
WD = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
RX = [
    ("date_iso", re.compile(r"(?<![\d-])(%s)-(\d{2})-(\d{2})(?![\d-])" % YEARS)),
    ("date_dmy", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(%s)(?:,?\s+(%s))?\b" % (MON, YEARS))),
    ("date_mdy", re.compile(r"\b(%s)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(%s))?(?!\d|\s?(?:%%|per ?cent|percent))" % (MON, YEARS))),
    ("date_slash", re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")),
    ("month_year", re.compile(r"\b(%s)\s+(%s)\b" % (MON, YEARS))),
    ("decade", re.compile(r"\b(?:19|20)\d0s\b|(?<!\w)'\d0s\b")),
    ("year", re.compile(r"(?<![\w.,$£€%%/-])(%s)(?![\w%%/]|,\d|\.\d|\s?(?:%%|per ?cent|percent))" % YEARS)),
    ("month", re.compile(r"(?<![\w-])(?P<pre>(?i:in|since|until|by|during|last|next|this|early|late|mid-?|from|through|of|before|after|every) )?(?P<m>January|February|April|June|July|August|September|October|November|December|May|March)\b(?!\s+\d)")),
    ("relative", re.compile(r"\b(?:%s|(?:last|next|this|past|coming|previous) (?:%s|night|morning|afternoon|evening|weekend|quarter|decade|summer|winter|spring|fall|autumn|week|month|year)|(?:this|yesterday|tomorrow) (?:morning|afternoon|evening|night)|tonight|overnight|earlier this (?:week|month|year)|(?:today|yesterday|tomorrow)|(?:\d+|a|an|%s|several|few|couple of) %s ago)\b" % (WD, WD, NW, UNIT), re.I)),
    ("period", re.compile(r"\b(?:(?:the|this|last|next|each|every|early|late|mid|that) )?(?:(?:first|second|third|fourth|1st|2nd|3rd|4th) (?:quarter|half)|(?:weekends?|spring|summer|autumn|winter|Christmas|Easter|Thanksgiving|Ramadan|New Year(?:'s)?(?: Day| Eve)?|Black Friday|election day|(?:%s)s)|the (?:\d{1,2})(?:st|nd|rd|th))\b" % WD, re.I)),
    ("age", re.compile(r"\b(\d{1,3})[- ]years?[- ]old\b|\baged? (\d{1,3})\b(?!\s*(?:months?|weeks?|days?|hours?))", re.I)),
    ("duration", re.compile(r"\b(?:(?:about|around|nearly|almost|over|more than|less than|at least|roughly|another|past|last|next) )?(?:\d+|%s|a|an|several|few|couple of)[- ]%s(?![- ]old)\b" % (NW, DUNIT), re.I)),
    ("number_word", re.compile(r"\b(?:(?:%s|a|an)[- ](?:thirds?|fourths?|quarters?|halves|fifths?)|%s(?:[- ](?:hundred|thousand|million|billion|trillion))?|(?:a|an|one) (?:hundred|thousand|million|billion|trillion|dozen)|(?:hundreds|thousands|millions|billions|dozens|scores) of|half(?: a (?:million|billion|dozen))?|(?:a|one) (?:half|third|quarter)|(?:%s)[- ](?:thirds?|fourths?|quarters?|halves|fifths?))\b" % ("|".join(UNITW[1:12]), NW, "|".join(UNITW[2:12])), re.I)),
]
def _iso(y, m, d):
    try: return datetime.date(y, m, d).isoformat()
    except ValueError: return None
def _anchor_year(m, d, ad):
    try: x = datetime.date(ad.year, m, d)
    except ValueError: return None
    return (x.replace(year=ad.year - 1) if x > ad + datetime.timedelta(days=30) else x).isoformat()
def _word_value(t):
    t = t.lower().replace("-", " "); parts = t.split()
    if t.startswith("half a "): return 0.5 * SCALE.get(parts[2], 12 if parts[2] == "dozen" else None) if parts[2] in SCALE or parts[2] == "dozen" else None
    if t.startswith("half"): return 0.5
    if parts[0] in ("a", "an", "one") and len(parts) == 2 and parts[1] == "dozen": return 12
    total = 0; cur = 0
    for p in parts:
        p = p.rstrip("s") if p.rstrip("s") in SCALE else p
        if p in ("a", "an"): cur = 1
        elif p in WV: cur += WV[p]
        elif p in SCALE: total += (cur or 1) * SCALE[p]; cur = 0
        else: return None
    return total + cur
def spans(text, anchor=None):
    ad = datetime.date.fromisoformat(anchor[:10]) if anchor else None; out = []; taken = []
    def free(s, e): return not any(s < b and a < e for a, b in taken)
    for kind, rx in RX:
        for m in rx.finditer(text):
            s, e = m.span()
            if kind == "month":
                s = m.start("m")
                if m.group("m") in ("May", "March") and not m.group("pre"): continue
            if kind == "date_mdy" and m.group(1).lower() == "may" and not m.group(3) and not re.search(r"(?:in|on|since|until|by|during|from|through|of|before|after|last|next|this|early|late) $", text[max(0, s - 12):s], re.I) and not re.match(r"\s*(?:[,.;:)]|$)", text[e:e + 3]): continue
            if kind == "relative" and m.group(0).lower() in ("today", "yesterday", "tomorrow") and m.group(0)[0].isupper():
                prev = re.search(r"([A-Za-z]+)\W*$", text[max(0, s - 30):s]); sent_start = not text[:s].strip() or text[:s].rstrip().endswith((".", "!", "?", ":", '"', "“"))
                if prev and prev.group(1)[0].isupper() and not sent_start: continue
            if not free(s, e): continue
            v = None; g = m.groups()
            if kind == "date_iso": v = _iso(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "date_dmy":
                mo = MAB.get(g[1].lower().rstrip(".")[:4] if g[1].lower().startswith("sept") else g[1].lower()[:3]); v = _iso(int(g[2]), mo, int(g[0])) if g[2] else (_anchor_year(mo, int(g[0]), ad) if ad else None)
            elif kind == "date_mdy":
                mo = MAB.get("sept" if g[0].lower().startswith("sept") else g[0].lower()[:3]); v = _iso(int(g[2]), mo, int(g[1])) if g[2] else (_anchor_year(mo, int(g[1]), ad) if ad else None)
            elif kind == "date_slash":
                a, b, y = int(g[0]), int(g[1]), int(g[2]); y += 2000 if y < 100 else 0
                v = _iso(y, a, b) if b > 12 else (_iso(y, b, a) if a > 12 else None)
            elif kind == "month_year": v = f"{g[1]}-{MAB['sept' if g[0].lower().startswith('sept') else g[0].lower()[:3]]:02d}"
            elif kind == "year": v = g[0]
            elif kind == "month":
                nm = m.group("m"); mo = MN.index(nm) + 1 if nm in MN else None; v = f"{ad.year if ad else ''}-{mo:02d}" if mo and ad else None
            elif kind == "age": v = int(g[0] or g[1])
            elif kind == "duration":
                t = m.group(0).lower(); n = re.search(r"\d+|%s" % NW, t); v = {"n": int(n.group(0)) if n and n.group(0).isdigit() else (_word_value(n.group(0)) if n else (1 if re.search(r"\b(?:a|an)\b", t) else None)), "unit": re.search(UNIT, t).group(0).rstrip("s")}
            elif kind == "number_word":
                if m.group(0).lower() == "one": continue
                v = _word_value(m.group(0))
            elif kind == "relative" and m.group(0).lower().endswith("ago"):
                t = m.group(0).lower(); n = re.search(r"\d+|%s" % NW, t); v = {"ago": int(n.group(0)) if n and n.group(0).isdigit() else (_word_value(n.group(0)) if n else 1), "unit": re.search(UNIT, t).group(0).rstrip("s")}
            elif kind == "relative" and ad and re.fullmatch(r"(last|next) " + WD, m.group(0), re.I):
                w = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(m.group(0).split()[1].lower()); back = (ad.weekday() - w) % 7 or 7
                v = (ad - datetime.timedelta(days=back) if m.group(0).lower().startswith("last") else ad + datetime.timedelta(days=7 - back)).isoformat()
            elif kind == "relative" and ad and m.group(0).capitalize() in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
                w = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(m.group(0).lower()); v = (ad - datetime.timedelta(days=(ad.weekday() - w) % 7)).isoformat()
            out.append({"kind": kind, "s": s, "e": e, "text": text[s:e], "value": v}); taken.append((s, e))
    return sorted(out, key=lambda x: x["s"])
