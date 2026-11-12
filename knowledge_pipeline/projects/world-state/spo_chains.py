"""Subject-predicate-object triples and chains from a dependency parse (spaCy en_core_web_sm). Open IE practice: one triple per verb and per coordinated subject/object (CALM-style), passive voice flipped,
negation, modality and attribution kept as notes on the triple (MinIE-style), prepositional objects kept with their preposition, nested clauses linked ("X said that Y did Z").
Everything is read from the sentence: arguments and evidence are word for word. Pronouns are kept as written (no coreference).
    import spo_chains as S; S.extract(nlp, sentences) -> triples; S.chains(triples) -> chains"""
import re, collections
SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "argue", "insist", "suggest", "confirm", "deny", "explain", "allege", "declare", "write", "testify", "assert", "acknowledge", "predict"}
PLAN = {"plan", "expect", "intend", "aim", "vow", "hope", "want", "try", "seek", "threaten", "promise", "propose", "need", "refuse", "agree"}
MODALS = {"will", "would", "could", "may", "might", "can", "should", "must", "shall", "'ll", "ca"}
PRON = {"he", "she", "it", "they", "we", "i", "you", "who", "which", "that", "this", "these", "those", "there", "what", "him", "her", "them", "us", "me", "his", "their", "its", "our", "my", "your"}
DET = {"the", "a", "an", "this", "that", "these", "those", "his", "her", "its", "their", "our", "my", "your", "some", "any", "no"}
def _phrase(tok, chunks, ents):
    for e in ents:
        if e.start <= tok.i < e.end and e.label_ not in ("DATE", "TIME", "CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY"): return e.text
    c = chunks.get(tok.i)
    if c is not None:
        w = [t for t in c]
        while w and w[0].lower_ in DET: w = w[1:]
        return tok.doc[w[0].i:w[-1].i + 1].text if w else tok.text
    return tok.text
def _key(tok, text):
    if tok.pos_ == "PROPN" or tok.ent_type_ in ("PERSON", "ORG", "GPE", "LOC", "NORP", "FAC", "EVENT", "PRODUCT", "LAW"): return re.sub(r"\W+", " ", text.lower()).strip()
    return tok.lemma_.lower()
def _conj(tok):
    out = [tok]; stack = [tok]
    while stack:
        t = stack.pop()
        for c in t.children:
            if c.dep_ == "conj" and c.pos_ in ("NOUN", "PROPN", "PRON", "NUM"):
                lo, hi = sorted((c.i, t.i))
                if any(x.text in ("-", "–") for x in tok.doc[lo:hi + 1]) and hi - lo <= 2: continue
                out.append(c); stack.append(c)
    return out
def _subjects(v, depth=0):
    subs = [c for c in v.children if c.dep_ in ("nsubj", "nsubjpass", "csubj")]
    subs = [s for s in subs if s.lower_ not in ("who", "which", "that")] or ([v.head] if v.dep_ in ("relcl", "acl") and v.head.pos_ in ("NOUN", "PROPN", "PRON") else [])
    if not subs and v.dep_ in ("conj", "xcomp", "advcl", "ccomp") and depth < 3 and v.head.pos_ in ("VERB", "AUX"): subs = _subjects(v.head, depth + 1) if v.dep_ != "xcomp" or not [c for c in v.head.children if c.dep_ in ("dobj", "obj")] else [c for c in v.head.children if c.dep_ in ("dobj", "obj")]
    out = []
    for s in subs:
        if s.pos_ in ("NOUN", "PROPN", "PRON", "NUM"): out += _conj(s)
        else: out.append(s)
    ids = {t.i for t in out}
    return [s for s in out if re.search(r"\w", s.text) and s.dep_ != "compound" and not (s.i + 2 in ids and s.doc[s.i + 1].text in ("-", "–"))]
def extract(nlp, sentences):
    triples = []; tid = 0
    for si, text in enumerate(sentences):
        doc = text if hasattr(text, 'vocab') else nlp(text); text = doc.text; chunks = {t.i: c for c in doc.noun_chunks for t in c}; ents = list(doc.ents); by_tok = {}; sent_attrib = None
        for t in doc:
            if t.lower_ == "according" and t.dep_ in ("prep", "advmod"):
                for p in t.children:
                    if p.dep_ == "pcomp" or p.dep_ == "prep":
                        for o in p.children:
                            if o.dep_ == "pobj": sent_attrib = _phrase(o, chunks, ents)
        if text.strip().endswith("?"): continue  # a question states nothing
        verbs = [t for t in doc if (t.pos_ == "VERB") or (t.pos_ == "AUX" and t.dep_ == "ROOT" and any(c.dep_ in ("attr", "acomp") for c in t.children))]
        for v in verbs:
            subs = _subjects(v); passive = any(c.dep_ == "nsubjpass" for c in v.children) or any(c.dep_ == "auxpass" for c in v.children)
            objs = []; preps = []; agent = []
            for c in v.children:
                if c.dep_ in ("dobj", "obj", "attr", "oprd", "dative"): objs += _conj(c)
                elif c.dep_ == "agent":
                    for o in c.children:
                        if o.dep_ == "pobj": agent += _conj(o)
                elif c.dep_ == "prep" and c.lower_ not in ("according",):
                    for o in c.children:
                        if o.dep_ == "pobj": preps += [(c.lower_, x) for x in _conj(o)]
                elif c.dep_ == "acomp" and c.pos_ == "ADJ": objs.append(c)
            neg = any(c.dep_ == "neg" for c in v.children); modal = [c.lower_ for c in v.children if c.dep_ in ("aux",) and (c.tag_ == "MD" or c.lower_ in MODALS)]
            if v.dep_ in ("xcomp", "ccomp") and v.head.lemma_ in PLAN: modal.append(v.head.lemma_)
            attrib = sent_attrib; clause = [c for c in v.children if c.dep_ == "ccomp"]
            if passive:  # flip: the grammatical subject is the thing acted on
                acted = subs; subs = agent or []; objs = acted + objs; agent = []
            DIRADV = {"ahead", "back", "up", "down", "out", "off", "away", "over", "forward", "behind", "apart", "together", "along"}
            vtext = " ".join([c.text for c in v.children if c.dep_ in ("aux", "auxpass", "neg", "prt") and c.i < v.i] + [v.text] + [c.text for c in v.children if (c.dep_ == "prt" or (c.dep_ == "advmod" and c.lower_ in DIRADV)) and c.i > v.i])
            if not subs and not objs and not preps and not clause: continue
            if not subs: subs = [None]
            def is_time(o): return o.ent_type_ in ("DATE", "TIME") or o.lemma_.lower() in ("minute", "hour", "day", "week", "month", "year", "morning", "evening", "night", "afternoon", "weekend", "season", "quarter", "half", "time", "ago", "today", "yesterday", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
            when = [o for o in objs if is_time(o)] + [o for p, o in preps if is_time(o)]; objs = [o for o in objs if not is_time(o)]; preps = [(p, o) for p, o in preps if not is_time(o)]
            rels = [(o, "") for o in objs] + [(o, p) for p, o in preps] or [(None, "")]
            for s in subs:
                for o, prep in rels:
                    if s is None and o is None: continue
                    if s is not None and o is not None and s.i == o.i: continue
                    s_text = _phrase(s, chunks, ents) if s is not None else None; o_text = _phrase(o, chunks, ents) if o is not None else None
                    idx = [x.i for x in (s, o, v) if x is not None]; ev = doc[min(idx):max(idx) + 1].text
                    triples.append({"id": tid, "sent": si, "s_i": s.i if s is not None else None, "o_i": o.i if o is not None else None, "s": s_text, "s_key": _key(s, s_text) if s is not None else None, "s_pronoun": bool(s is not None and s.lower_ in PRON), "p": (vtext + (" " + prep if prep else "")).strip(), "p_lemma": v.lemma_.lower(), "prep": prep or None,
                                    "o": o_text, "o_key": _key(o, o_text) if o is not None else None, "o_pronoun": bool(o is not None and o.lower_ in PRON), "neg": neg, "modal": sorted(set(modal)), "attrib": attrib, "passive": passive, "evidence": ev, "contains": [], "said_by": None, "v_i": v.i, "sent_text": text, "when": [_phrase(x, chunks, ents) for x in when]})
                    tid += 1
        for t in doc:
            if t.dep_ == "appos" and t.pos_ in ("NOUN", "PROPN") and t.head.pos_ in ("NOUN", "PROPN"):
                triples.append({"id": tid, "sent": si, "s_i": t.head.i, "o_i": t.i, "s": _phrase(t.head, chunks, ents), "s_key": _key(t.head, _phrase(t.head, chunks, ents)), "s_pronoun": False, "p": "is", "p_lemma": "be", "prep": None, "o": _phrase(t, chunks, ents), "o_key": _key(t, _phrase(t, chunks, ents)), "o_pronoun": False, "neg": False, "modal": [], "attrib": sent_attrib, "passive": False, "evidence": doc[min(t.head.i, t.i):max(t.head.i, t.i) + 1].text, "contains": [], "said_by": None, "v_i": t.i, "sent_text": text, "when": [], "appositive": True}); tid += 1
        # nested clauses: "X said that [clause]" -> the clause's triples are inside the speech triple
        by_v = {}
        for t in triples:
            if t["sent"] == si: by_v.setdefault(t["v_i"], []).append(t)
        doc_v = {t.i: t for t in doc}
        for vi, ts in list(by_v.items()):
            v = doc_v[vi]
            for c in v.children:
                if c.dep_ == "ccomp" and c.i in by_v:
                    for t in ts:
                        t["contains"] += [x["id"] for x in by_v[c.i]]
                        if v.lemma_ in SPEECH:
                            for x in by_v[c.i]: x["said_by"] = t["s"]
    return triples
def merge_aliases(triples):
    """Within one article, a bare surname matches the full name that ends with it (McAuliffe -> Terry McAuliffe)."""
    keys = collections.Counter(k for t in triples for k in (t["s_key"], t["o_key"]) if k and " " in k); alias = {}
    for t in triples:
        for f in ("s_key", "o_key"):
            k = t[f]
            if not k or " " in k: continue
            longs = [x for x in keys if x.split()[-1] == k and len(x.split()) > 1]
            if len(longs) == 1: alias[k] = longs[0]
    for t in triples:
        for f in ("s_key", "o_key"):
            if t[f] in alias: t[f] = alias[t[f]]
    return alias
def chains(triples, window=2):
    """A chain links triple A to triple B when A's object is B's subject (same entity, within `window` sentences), or when B sits inside A as a reported clause."""
    byid = {t["id"]: t for t in triples}; nxt = collections.defaultdict(list)
    for a in triples:
        for b in triples:
            if a["id"] == b["id"]: continue
            if b["id"] in a["contains"]: nxt[a["id"]].append(b["id"])
            elif a["o_key"] and a["o_key"] == b["s_key"] and 0 <= b["sent"] - a["sent"] <= window and not a["s_pronoun"] and a["o_key"] not in PRON: nxt[a["id"]].append(b["id"])
    best = {}
    def longest(i, seen):
        if i in best and not seen: return best[i]
        r = [i]
        for j in nxt.get(i, []):
            if j in seen: continue
            c = [i] + longest(j, seen | {i})
            if len(c) > len(r): r = c
        return r
    out = []
    for i in nxt:
        c = longest(i, frozenset())
        if len(c) >= 2: out.append(c)
    out.sort(key=lambda c: -len(c)); used = set(); res = []
    for c in out:
        if used & set(c): continue
        res.append(c); used |= set(c)
    return res
