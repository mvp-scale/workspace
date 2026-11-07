"""Rule binder prototype (no spaCy, no model): decides the 'bound' check of stated_facts.py for amounts and dates.
Deterministic: rule sentence split, regex tokens, closed word lists. Meant as a spec for a later Rust port.
  bind(text, s, e, kind) -> {"bound": bool, "noun": str|None, "verb": str|None, "one_sentence": bool}
Fact spans (s, e) come from the same regexes stated_facts.py already uses (NUMRX / WORDRX / scan_gate); only the binding step is replaced.
Status: stated = bound and one_sentence; unbound = one_sentence but not bound; invalid = span crosses a sentence break."""
import re

TOK = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*|\d+(?:,\d{3})*(?:\.\d+)?|[^\sA-Za-z\d]")
ABBR = {"mr", "mrs", "ms", "dr", "st", "inc", "corp", "ltd", "co", "no", "vs", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "gen", "sen", "rep", "gov", "lt", "col", "sgt", "prof", "jr", "sr", "u.s", "a.m", "p.m", "e.g", "i.e", "etc", "approx", "ca", "al"}
def split_sentences(text):
    """Return [(start, end)]. Break after . ! ? (plus closing quote/bracket) followed by space and a capital, digit or opening quote, unless the word before the dot is an abbreviation or one capital letter."""
    out = []; start = 0
    for m in re.finditer(r"[.!?][\"”’)\]]*\s+(?=[A-Z0-9\"“‘'(])", text):
        k = m.start(); w = re.search(r"([A-Za-z.]+)$", text[max(0, k - 12):k]); w = w.group(1).lower() if w else ""
        if text[k] == "." and (w in ABBR or (len(w) == 1 and w.isalpha()) or re.search(r"\b[A-Z]$", text[max(0, k - 2):k])): continue
        if text[k] == "." and re.match(r"\d", text[k - 1:k]) and re.match(r"\d", text[m.end():m.end() + 1]) and False: continue
        out.append((start, m.end())); start = m.end()
    out.append((start, len(text)))
    return [(a, b) for a, b in out if b > a]

DET = set("the a an this that these those my your his her its our their some any each every no all both either neither".split())
PREP = set("of in on at by for from with to into onto over under about after before during since until till through across between among against toward towards within without per via than as like near off up down out upon around behind beyond despite amid".split())
CONJ = set("and or but nor so yet because although though while whereas if unless whether when where which who whom whose what that than then".split())
PRON = set("i you he she it we they me him them us who whom what which there here one".split())
BE = set("is are was were be been being am 's ’s".split())
AUX = BE | set("do does did will would can could may might shall should must".split())
HAVE = set("has have had having".split())
ADV = set("also only just still even now then very too quite almost nearly roughly about approximately around over under at least most more less than up to some an estimated nearly alone already again ever not n't never currently recently reportedly allegedly further early late soon far well together".split())
MODS = set("new more other another additional extra further total major big large small little few many several various last next first second third top single entire whole same only average estimated least most young old average official total fresh long short high low".split())
IRREG = set("start starts die dies attend attends look looks ask asks operate operates hike spit run write rule rules consume predict believe believes happen happens become becomes remain call calls allow allows provide provides continue continues expect help helps meet meets open opens close closes win play plays move moves live lives work works vote votes leave pass passes rely agree agrees lead decline declines increase increases decrease drop drops climb climbs jump jumps surge surges slip slips tumble fall hurt hurts kill kills die injure injures arrest arrests charge charges accuse accuses sentence sentences visit visits meet announce announces launch launches sign signs appear appears seem seems stay stays follow follows offer offers hit sit sits wait waits ship ships grant grants hold return returns carry carries rank bring said says say told tell tells took take takes taken made make makes got get gets gave give gives given went go goes gone saw see sees seen found find finds led lead leads left leave leaves held hold holds paid pay pays sold sell sells won win wins lost lose loses set sets put cut cuts hit hits ran run runs came come comes began begin begins begun shot shoot rose rise rises risen fell fall falls fallen grew grow grows grown spent spend spends built build builds sent send sends kept keep keeps brought bring brings thought think thinks know knows knew known show shows shown cost costs earn earns reach reaches report reports include includes remain remains expect expects reflect reflects add adds mean means need needs want wants use uses face faces see sees receive receives record records post posts rank ranks total totals number numbers range ranges reveal reveals demand demands approve approves raise raises claim claims seek seeks buy buys beat beats lack lacks owe owes weigh weighs earned stood stand stands drew draw draws wrote write writes tied tie ties".split())
NOT_VERB = set("hundred thousand bed red shed sacred need seed speed feed bleed breed weed indeed hundred kindred wicked naked sunday monday friday evening morning building king thing ring spring string wing bring sing during nothing something anything everything ceiling feeling meaning beginning opening saving savings earnings findings holding holdings housing funding warning killing shooting bombing bearing training warming ceasing".split()) - {"bring", "need"}
ING_NOUN = set("morning evening building king thing ring spring string wing sing during nothing something anything everything ceiling feeling meaning beginning opening saving savings earnings findings holding holdings housing funding warning killing shooting bombing training warming".split())
def is_verb(w):
    lw = w.lower()
    if lw in AUX or lw in PREP or lw in CONJ or lw in DET or lw in PRON: return False
    if lw in IRREG or lw in HAVE: return True
    if lw in NOT_VERB: return False
    if lw.endswith("ed") and len(lw) > 4: return True
    if lw.endswith("ing") and len(lw) > 5 and lw not in ING_NOUN: return True
    return False
def is_noun(w):
    """Lowercase or capitalised content word that is none of: function word, verb, adverb (-ly), modifier."""
    lw = w.lower()
    if not w[:1].isalpha(): return False
    if lw in DET or lw in PREP or lw in CONJ or lw in PRON or lw in AUX or lw in HAVE or lw in ADV or lw in MODS: return False
    if lw.endswith("ly") and len(lw) > 4: return False
    if is_verb(w) and not lw.endswith("ing"): return False
    return True

def tokens(text, a, b): return [(m.group(0), a + m.start(), a + m.end()) for m in TOK.finditer(text[a:b])]

def bind(text, s, e, kind, sents=None):
    sents = sents or split_sentences(text)
    hit = [(a, b) for a, b in sents if a <= s < b]
    sa, sb = hit[0] if hit else (0, len(text))
    one = e <= sb or (e - sb) <= 0 or text[sb:e].strip() == ""
    toks = tokens(text, sa, sb); inside = [i for i, t in enumerate(toks) if t[1] < e and s < t[2]]
    if not inside: return {"bound": False, "noun": None, "verb": None, "one_sentence": one}
    i0, i1 = inside[0], inside[-1]
    if kind == "amount": noun, verb = _amount(toks, i0, i1, text)
    else: noun, verb = _date(toks, i0, i1, text)
    return {"bound": bool(noun or verb), "noun": noun, "verb": verb, "one_sentence": one}

def _has_verb(toks, i0, i1):
    return next((t[0].lower() for k, t in enumerate(toks) if is_verb(t[0]) and not (i0 <= k <= i1)), None)

def _amount(toks, i0, i1, text):
    n = len(toks)
    # 1) glued to punctuation or a digit before it, or followed by ':' + digit: citation marker, clock time, score, id -> not a counted quantity
    prev = toks[i0 - 1] if i0 > 0 else None
    if prev is not None and toks[i0][1] - prev[2] == 0 and not prev[0][:1].isalpha() and prev[0] not in ('"', "“", "‘", "'", "$", "(", "€", "£") : return None, None
    if prev is not None and toks[i0][1] - prev[2] == 0 and prev[0][:1].isdigit(): return None, None
    if i1 + 2 < n and toks[i1 + 1][0] == ":" and toks[i1 + 2][0][:1].isdigit() and toks[i1 + 1][1] == toks[i1][2]: return None, None
    # 2) a counted noun after the number (skipping modifiers); hyphen compounds count: "four-lane", "14-year-old"
    j = i1 + 1
    if j < n and toks[j][0] == "-" and toks[j][1] == toks[i1][2]:
        j += 1
        if j < n and toks[j][0][:1].isalpha(): return toks[j][0], None
    j = i1 + 1; skipped = 0
    while j < n and skipped < 3 and (toks[j][0].lower() in MODS or (toks[j][0].lower().endswith("ly") and len(toks[j][0]) > 4)):
        j += 1; skipped += 1
    if j < n and toks[j][0][:1].isalpha() and is_noun(toks[j][0]): return toks[j][0], None
    # 3) predicate: a be/aux form right before the number and no noun after -> nothing to hang it on
    k = i0 - 1
    while k >= 0 and toks[k][0].lower() in (ADV | MODS) - {"at", "to", "now", "also", "currently", "still"}: k -= 1
    if k >= 0 and (toks[k][0].lower() in BE or toks[k][0].lower() in AUX): return None, None
    # 4) otherwise it hangs on the clause verb if the sentence has one
    v = _has_verb(toks, i0, i1)
    return (None, v) if v else (None, None)

def _date(toks, i0, i1, text):
    """Default bound (the date hangs on the clause verb). Unbound when the date is only a modifier or a label:
    followed by 's or an attached capitalised word (Sunday Telegraph), directly after 'the', directly after a bare day number (12 August 2019),
    or when the sentence holds no verb-like word at all (dateline, caption)."""
    n = len(toks); lo = toks[i0][0].lower()
    if i1 + 1 < n and toks[i1 + 1][1] - toks[i1][2] <= 1 and toks[i1 + 1][0][:1].isupper(): return None, None
    if i0 > 0 and toks[i0 - 1][0].lower() == "the": return None, None
    if i0 > 0 and re.fullmatch(r"\d{1,2}", toks[i0 - 1][0]) and lo[:3] in MONTHS: return None, None
    for k, t in enumerate(toks):
        if is_verb(t[0]) and not (i0 <= k <= i1): return None, t[0].lower()
    return None, None
MONTHS = set("jan feb mar apr may jun jul aug sep oct nov dec".split())

def status(bound, one):
    return "stated" if bound and one else ("unbound" if one else "invalid")
