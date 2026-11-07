"""G1 scanner module (moved out of gates_v2.py so the G3 experiment can import it): one regex alternation pass producing [start, end, class(, resolved)] spots."""
import re
import size_quantity as SQ
# ------------------------------------------------------------------ G1 scanner
NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"; MAG = r"(?:\s?(?:thousand|million|billion|trillion|bn)\b)?"
UNITS = "|".join(u for c, u in SQ.UNITS if c != "percent")
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
EVENT = r"(?:kill|arrest|detain|announc|sign|ban|clos|open|rais|surg|plung|jump|drop|declin|increas|strik|struck|block|suspend|cancel|resign|elect|vot|approv|reject|launch|attack|protest|march|rall|clash|fir|stol|hack|breach|flood|burn|destroy|damag|collaps|evacuat|displac|infect|confirm|declar|warn|demand|condemn|shrink|grow|slash|hik|freez|seiz|storm|cut|hit|fell|rose|fall|rise)(?:e|ed|es|ing|s|d)?"
PAT = [("quote", r"[“\"][^”\"]{12,300}[”\"]"), ("money", r"(?:US\$|\$|€|£)\s?(?:%s)%s|(?:%s)%s\s?(?:dollars|euros|pounds|yuan|rupees|yen)\b" % (NUM, MAG, NUM, MAG)), ("percent", r"(?:%s)\s?(?:%%|per ?cent\b|percent\b)" % NUM),
       ("quantity", r"(?:%s)%s(?:%s)" % (NUM, MAG, UNITS)), ("date", r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|yesterday|today|tomorrow|(?:last|this|next) (?:week|month|year))\b|\b%s\s+\d{1,2}(?:st|nd|rd|th)?\b(?!,?\s*\d{4})|\b%s\s+\d{4}\b" % (MONTH, MONTH)),
       ("attribution", r"\b(?:said|says|told|according to|reported|warned|claimed|stated|added|noted)\b"), ("negation", r"\b(?:not|no|never|denied|without|despite|fail(?:ed|s)?)\b|n’t|n't"),
       ("modal", r"\b(?:could|may|might|will|would|expected to|plans? to|set to|likely|vow(?:ed|s)? to)\b"), ("change", r"\b(?:rise|rising|rose|fall|falling|fell|surge[sd]?|soar(?:ed|ing)?|plunge[sd]?|drop(?:ped|s)?|jump(?:ed|s)?|increase[sd]?|decline[sd]?|record|worst|highest|lowest)\b"),
       ("event", r"\b" + EVENT + r"\b"), ("entity", r"(?!(?:On|In|At|By|From|Between|During|After|Before|Since|Until|Over|Under|For|With|As|The|A|An|But|And|When|While|If|It|He|She|They|This|That|These|Those|There|Here|Now|Then|According)\b)[A-Z][\w’'-]+(?:\s+(?:of|the|de|and|for|al|bin)\s+[A-Z][\w’'-]+|\s+[A-Z][\w’'-]+)*")]
SCAN = re.compile("|".join(f"(?P<{n}>{p})" for n, p in PAT))
MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}; WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
def resolve(text, anchor):
    import datetime
    ad = datetime.date.fromisoformat(anchor[:10]); t = text.lower()
    if t in WD: return (ad - datetime.timedelta(days=(ad.weekday() - WD.index(t)) % 7)).isoformat()
    if t in ("yesterday", "today", "tomorrow"): return (ad + datetime.timedelta(days={"yesterday": -1, "today": 0, "tomorrow": 1}[t])).isoformat()
    m = re.match(r"(last|this|next) (week|month|year)", t)
    if m: return f"{m.group(1)} {m.group(2)} relative to {ad.isoformat()}"
    m = re.match(MONTH.lower() + r"\s+(\d{4})$", t)
    if m: return f"{m.group(1)}-{MON[t[:3]]:02d}"
    m = re.match(MONTH.lower() + r"\s+(\d{1,2})", t)
    if m:
        try:
            d = datetime.date(ad.year, MON[t[:3]], int(m.group(1)))
            return (d.replace(year=ad.year - 1) if d > ad + datetime.timedelta(days=30) else d).isoformat()
        except ValueError: return None
    return None
STARTER = set("The A An In On At As But And For With After Before When While If It He She They This That These Those There Here Now Then Our We You His Her Their Its According".split())
def scan(body, anchor):
    spots = []
    for m in SCAN.finditer(body):
        c = m.lastgroup; s, e = m.span()
        if c == "entity":
            single = " " not in m.group(0); first = s == 0 or body[max(0, s - 2):s] in (". ", "! ", "? ") or body[s - 1:s] in ("“", '"')
            if single and first and m.group(0) in STARTER: continue
            if single and m.group(0) in STARTER: continue
        spots.append([s, e, c] + ([resolve(m.group(0), anchor)] if c == "date" and anchor else []))
    sents = [(m.start(), m.end()) for m in re.finditer(r"[^\n]+?(?:(?<=[.!?])(?=\s+[A-Z0-9\"“‘'])|(?<=[.!?][”\"’])(?=\s)|$)", body)]
    return spots, [(a, b) for a, b in sents if body[a:b].strip()]
