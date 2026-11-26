"""claims v1 (T158, G2): add-only rules on top of spo_chains.extract (nothing in spo_chains.py, facts_lib.py or raw-units.py claims_v0 is changed). One claim = subject, predicate, object plus attributes, with negation, modality and attribution kept.
Rules, each switchable (OPTS) so dev can measure them one at a time:
  parser   the lg parse (en_core_web_lg 3.8.0, MIT, NER excluded: 37 ms for a 680-word article) instead of sm
  expand_o the object is the whole noun phrase subtree (its modifiers and its of/in/over phrases), not just the noun chunk; conjuncts, relative clauses and clauses stay out
  expand_s the same for the subject
  attrs    a prepositional phrase never becomes the object when the verb has a direct object or a measure: it becomes an attribute (time, place, cause or other), 'dropped 10% under Trump' = enrollment | dropped | 10%, cause/other: under Trump
  speaker  a speech verb's speaker is the attribution (said_by), not the subject of the clause's claims; the speech triple keeps the speaker as subject and the clause as object
  passive  a passive with no agent keeps the patient as subject ('the municipality | was renamed | Jones'), not an empty subject
  dedupe   a bare 'X said' with no object is dropped when the same verb has its clause claim
  copula   'X is in/at/from Y' (AUX with a prepositional complement) is a claim
Import: V1.extract(text, nlp) -> [{"s","p","o","attrs","neg","modal","attrib","passive","rule"}]."""
import re, collections
import spo_chains as S
import lexicons as LX
OPTS = {"expand_o": True, "expand_s": True, "attrs": True, "speaker": True, "copula": True, "clause": True, "xcomp": True, "measure": True, "attrs_move": False, "passive": True, "dedupe": True, "measure_move": True, "antecedent": True, "slots": True}
SKIP_O = {"relcl", "acl", "appos", "conj", "cc", "ccomp", "advcl", "punct", "mark", "dep", "parataxis"}
SKIP_S = SKIP_O | {"prep"}
def span_text(tok, skip):
    keep = [tok]; stack = [tok]
    while stack:
        t = stack.pop()
        for c in t.children:
            if c.dep_ in skip: continue
            keep.append(c); stack.append(c)
    lo = min(x.i for x in keep); hi = max(x.i for x in keep)
    return tok.doc[lo:hi + 1].text
def prep_kind(o):
    if o is None: return "other"
    if o.ent_type_ in ("DATE", "TIME"): return "time"
    if o.ent_type_ in ("GPE", "LOC", "FAC"): return "place"
    return "other"
SUBORD_MARK = {"after", "before", "following", "amid", "despite", "over", "since"}
def _outside_subordinate(v, sub):
    """headline guard (T158 who-did-it fix): 'Gulf nations on alert after U.S. strikes Iranian island' has no finite verb before 'after', so the parser gives 'strikes' two subjects. A subject that stands BEFORE the verb's own subordinator (after/before/amid/...) while another subject of the same verb stands AFTER it is outside the subordinate clause and is not this verb's subject."""
    marks = [m.i for m in v.children if m.dep_ == "mark" and m.lower_ in SUBORD_MARK]
    if not marks or v.dep_ != "ROOT": return False
    m = min(marks)
    return sub.i < m and any(c.dep_ in ("nsubj", "nsubjpass") and c.i > m for c in v.children)
def extract(text, nlp, opts=None):
    o_ = {**OPTS, **(opts or {})}; doc = nlp(text); T = S.extract(nlp, [doc]); out = []
    for t in T:
        s = doc[t["s_i"]] if t["s_i"] is not None else None; o = doc[t["o_i"]] if t["o_i"] is not None else None; v = doc[t["v_i"]]
        if s is not None and _outside_subordinate(v, s): continue
        s_text = t["s"]; o_text = t["o"]; p = t["p"]; attrs = []; rule = []; s_short = t["s"]
        if o_.get("expand_s") and s is not None and not t["s_pronoun"] and s.pos_ in ("NOUN", "PROPN", "NUM"):
            s_text = span_text(s, SKIP_S); rule.append("expand_s")
        if t["s_pronoun"] and s is not None and s.pos_ in ("PROPN", "NOUN"):   # 'US' (the country) lower-cases to the pronoun 'us': a proper noun is never a pronoun to resolve (T158 who-did-it fix)
            t = {**t, "s_pronoun": False}
        if o_.get("antecedent") and t["s_pronoun"] and s is not None:   # who-did-it (T158 fix round 1): a pronoun subject inside a reported clause ('The coalition said IT intercepted ...') is the governing clause's subject, grounded in this sentence; never the nearest NER mention of an earlier sentence (the claims v0 resolver did that: 'it' -> Houthi)
            ant = _clause_antecedent(v, s)
            if ant is not None: s_text = span_text(ant, SKIP_S) if ant.pos_ in ("NOUN", "PROPN", "NUM") else ant.text; s_short = s_text; rule.append("clause_antecedent"); t = {**t, "s": s_text, "s_pronoun": False}
        if o is not None and not t.get("appositive"):
            if o_.get("expand_o") and o.pos_ in ("NOUN", "PROPN", "NUM", "PRON"):
                o_text = span_text(o, SKIP_O); rule.append("expand_o")
        if o_.get("passive") and t["passive"] and s is None:
            ps = [c for c in v.children if c.dep_ == "nsubjpass"]
            if ps:
                s = ps[0]; s_text = span_text(s, SKIP_S) if s.pos_ in ("NOUN", "PROPN", "NUM") else s.text; rule.append("passive")
                if o is not None and o.i == s.i: o = None; o_text = None
        out.append({"s": s_text, "s_short": s_short if s_text == t["s"] or t["s"] else s_text, "p": p, "o": o_text, "attrs": attrs, "neg": t["neg"], "modal": t["modal"], "attrib": t["attrib"], "passive": t["passive"], "said_by": t["said_by"], "rule": rule, "v_i": t["v_i"], "s_i": s.i if s is not None else None, "prep": t["prep"], "o_pos": o.pos_ if o is not None else None})
    if o_.get("copula") or o_.get("clause") or o_.get("xcomp"): out += _extra(doc, out, o_)
    if o_.get("dedupe"):   # a bare 'X said' (no object) is dropped when the same verb has its clause claim
        cv = {x["v_i"] for x in out if "clause" in x["rule"]}; out = [x for x in out if not (x["o"] is None and x.get("v_i") in cv and "clause" not in x["rule"])]
    if o_.get("measure"): out += _measure(doc, out, o_)
    if o_.get("attrs"): out = _attrs(doc, out, o_)
    if o_.get("slots", True): _attach_slots(doc, out)
    for x in out:
        x["v_span"] = [doc[x["v_i"]].idx, doc[x["v_i"]].idx + len(doc[x["v_i"]].text)] if x.get("v_i") is not None else None
        for k in ("v_i", "s_i", "prep", "o_pos"): x.pop(k, None)
    return out

def _clause_antecedent(v, pron):
    """the nominal subject of the clause that governs v when v is (a conjunct of) a ccomp/advcl clause; None when there is none or it is itself a pronoun (then the resolver keeps its job)"""
    h = v; hops = 0
    while h.dep_ == "conj" and hops < 3: h = h.head; hops += 1
    if h.dep_ not in ("ccomp", "advcl") or h.head is h: return None
    g = h.head
    for c in g.children:
        if c.dep_ in ("nsubj", "nsubjpass") and c.pos_ in ("NOUN", "PROPN") and c.i < h.i: return c
    return None
def _subj_text(sub, v, o_):
    """subject text of a claim built outside the base extractor (clause, xcomp, copula, measure): the phrase, or for a pronoun the governing clause's subject (same rule as in extract)"""
    if o_.get("antecedent") and sub.pos_ == "PRON" and sub.lower_ in ("it", "he", "she", "they"):
        ant = _clause_antecedent(v, sub)
        if ant is not None: return span_text(ant, SKIP_S) if ant.pos_ in ("NOUN", "PROPN", "NUM") else ant.text
    return span_text(sub, SKIP_S) if sub.pos_ in ("NOUN", "PROPN", "NUM") else sub.text
def _clause_text(c):
    keep = [x for x in c.subtree if not (x.dep_ == "punct" and x.i in (c.left_edge.i, c.right_edge.i))]; return c.doc[c.left_edge.i:c.right_edge.i + 1].text.strip(" ,;")
def _extra(doc, out, o_):
    """claims the base misses: a reported or complement clause as the object (X said/thinks that CLAUSE, speaker kept in attrib for speech verbs), a to-infinitive complement (X plans to DO), a copula with a prepositional complement (X was in Y)"""
    add = []; have = {(x["p"], x["v_i"]) for x in out if "v_i" in x}
    for v in doc:
        if v.pos_ not in ("VERB", "AUX"): continue
        subs = [x for x in S._subjects(v) if not _outside_subordinate(v, x)]
        if not subs: continue
        sT = _subj_text(subs[0], v, o_)
        neg = any(c.dep_ == "neg" for c in v.children); modal = [c.lower_ for c in v.children if c.dep_ == "aux" and (c.tag_ == "MD" or c.lower_ in S.MODALS)]
        vt = " ".join([c.text for c in v.children if c.dep_ in ("aux", "auxpass", "neg", "prt") and c.i < v.i] + [v.text])
        if o_.get("clause"):
            for c in v.children:
                if c.dep_ == "ccomp":
                    mk = [m.text for m in c.children if m.dep_ == "mark" and m.i < c.i]
                    add.append({"s": sT, "s_short": sT, "p": (vt + " " + " ".join(mk)).strip(), "o": _clause_text(c), "attrs": [], "neg": neg, "modal": modal, "attrib": sT if v.lemma_ in S.SPEECH else None, "passive": False, "said_by": None, "rule": ["clause"], "v_i": v.i})
        if o_.get("xcomp"):
            for c in v.children:
                if c.dep_ == "xcomp" and c.pos_ == "VERB" and any(m.dep_ == "aux" and m.lower_ == "to" for m in c.children):
                    add.append({"s": sT, "s_short": sT, "p": vt + " to", "o": doc[[m for m in c.children if m.dep_ == "aux" and m.lower_ == "to"][0].i + 1:c.right_edge.i + 1].text, "attrs": [], "neg": neg, "modal": modal, "attrib": None, "passive": False, "said_by": None, "rule": ["xcomp"], "v_i": v.i})
        if o_.get("copula") and v.lemma_ == "be" and v.pos_ in ("AUX", "VERB"):
            for c in v.children:
                if c.dep_ == "prep":
                    for po in c.children:
                        if po.dep_ == "pobj": add.append({"s": sT, "s_short": sT, "p": vt + " " + c.text, "o": span_text(po, SKIP_O), "attrs": [], "neg": neg, "modal": modal, "attrib": None, "passive": False, "said_by": None, "rule": ["copula"], "v_i": v.i})
    seen = {(x["s"], x["p"], x["o"]) for x in out}
    return [a for a in add if (a["s"], a["p"], a["o"]) not in seen]

_MEASURE_ENT = {"PERCENT", "MONEY", "QUANTITY", "CARDINAL"}
def _measure(doc, out, o_=None):
    """'dropped 10%' : a numeric npadvmod/dobj measure of the verb is its object (the amount), so a later 'under Trump' stays an attribute"""
    add = []; have = {(x["v_i"], x.get("s_i")) for x in out if x.get("v_i") is not None and x.get("prep") is None and x["o"]}
    for v in doc:
        if v.pos_ != "VERB": continue
        for c in v.children:
            if c.dep_ == "npadvmod" and (c.ent_type_ in _MEASURE_ENT or any(x.pos_ == "NUM" for x in c.children) or c.pos_ == "NUM") and c.ent_type_ not in ("DATE", "TIME"):
                subs = [x for x in S._subjects(v) if not _outside_subordinate(v, x)]
                if not subs: continue
                sT = _subj_text(subs[0], v, o_ or {})
                if (v.i, subs[0].i) in have: continue
                vt = " ".join([x.text for x in v.children if x.dep_ in ("aux", "auxpass", "neg", "prt") and x.i < v.i] + [v.text])
                add.append({"s": sT, "s_short": sT, "p": vt, "o": span_text(c, SKIP_O), "attrs": [], "neg": any(x.dep_ == "neg" for x in v.children), "modal": [x.lower_ for x in v.children if x.dep_ == "aux" and x.tag_ == "MD"], "attrib": None, "passive": False, "said_by": None, "rule": ["measure"], "v_i": v.i, "s_i": subs[0].i, "prep": None, "o_pos": "NUM"})
    return add
def _attrs(doc, out, o_):
    """a prepositional phrase never becomes the object when the same verb and subject already have a direct object or measure: it is attached to that claim as an attribute (kind time, place or other). attrs_move drops the separate prep claim, else both are kept (the prep claim is flagged demoted); measure_move drops it only when the direct claim is a measure ('dropped 10% | under Trump'), the known page failure"""
    direct = {}
    for x in out:
        if x.get("v_i") is not None and x.get("prep") is None and x["o"] and "copula" not in x["rule"] and "clause" not in x["rule"]: direct.setdefault((x["v_i"], x.get("s_i")), []).append(x)
    keep = []
    for x in out:
        k = (x.get("v_i"), x.get("s_i"))
        if x.get("prep") and k in direct:
            for d in direct[k]:
                d["attrs"].append({"prep": x["prep"], "text": x["o"], "kind": prep_kind(doc[x["v_i"]]) if False else "other"})
            if o_.get("attrs_move") or (o_.get("measure_move") and any("measure" in d["rule"] for d in direct[k])): continue
            x["demoted"] = True   # kept for recall, but its object comes from a prepositional phrase: show it as an attribute of the direct claim
        keep.append(x)
    return keep

# ---- attribution slots (T158 round 3, ledger L2962 / design 7.3): who said it, which verb of saying, and the reported content as the fact ----
# A slot rides on the claim of the CONTENT verb (claim["slot"]); the claim's own subject / predicate / object (the fact key) is untouched. Outcome class of the content: hit (struck, damaged, destroyed), attack (targeted, attacked, fired at: claimed, no outcome), blocked (intercepted, repelled, shot down, thwarted), none (no damage, did not report any damage, a denial of a hit or attack).
# the words are data (lexicons.json, playbook 00.1 round E); KP_LEXICONS=off leaves every class empty
HIT_V = LX.words("attack.hit_verbs"); ATTACK_V = LX.words("attack.attack_verbs"); BLOCK_V = LX.words("attack.block_verbs")
BLOCK_PHRASAL = LX.pairs("attack.block_phrasal"); BLOCK_IF_INCOMING = LX.words("attack.block_if_incoming_object")
DENY_V = LX.words("attack.deny_verbs"); SELF_REPORT_V = LX.words("attack.self_report_verbs")
DMG_N = LX.words("attack.damage_nouns"); INCOMING_N = LX.words("attack.incoming_nouns"); DENIED_N = LX.words("attack.denied_object_nouns")
SLOT_SPEECH = S.SPEECH | {"insist", "maintain", "claim", "assert", "contend", "tell"}
def _chars(doc, lo, hi): return [doc[lo].idx, doc[hi].idx + len(doc[hi].text)]
def _sub_chars(tok, skip):
    keep = [tok]; stack = [tok]
    while stack:
        t = stack.pop()
        for c in t.children:
            if c.dep_ in skip: continue
            keep.append(c); stack.append(c)
    return _chars(tok.doc, min(x.i for x in keep), max(x.i for x in keep))
def _has_no_damage(v):
    """'caused no damage', 'did not report any damage', 'reported no casualties': a damage noun under a negated verb or a determiner 'no'"""
    neg = any(c.dep_ == "neg" for c in v.children)
    for d in v.children:
        if d.dep_ in ("dobj", "obj", "attr") and d.lemma_.lower() in DMG_N:
            if neg or any(c.dep_ == "det" and c.lower_ in ("no", "any") and (neg or c.lower_ == "no") for c in d.children): return True
    return False
def _verb_class(v):
    """-> (class or None, negated). hit / attack / blocked / none by the verb lemma, its object and its negation"""
    lem = v.lemma_.lower(); neg = any(c.dep_ == "neg" for c in v.children)
    objs = [c for c in v.children if c.dep_ in ("dobj", "obj")]; otext = " ".join(span_text(o, SKIP_O).lower() for o in objs)
    if _has_no_damage(v): return "none", True
    if lem in BLOCK_V or any((lem, c.lower_) in BLOCK_PHRASAL for c in v.children if c.dep_ == "prt"):
        return (None, True) if neg else ("blocked", False)
    if lem in BLOCK_IF_INCOMING and any(w.rstrip("s") in INCOMING_N for w in re.findall(r"[a-z]+", otext)) : return (None, True) if neg else ("blocked", False)
    if lem in HIT_V: return ("none", True) if neg else ("hit", False)
    if lem in ATTACK_V: return ("none", True) if neg else ("attack", False)
    return None, neg
TARGET_PREP = {"in", "at", "on", "over", "near", "against", "toward", "towards", "to", "across", "inside", "within", "into"}
def _target_spans(h, cls):
    """char spans where the target of a reported outcome is named: the object phrase and the place prepositional phrases (in / at / on / over / near / against ...) of the content verb for hit / attack; those prepositional phrases only for blocked / none (the object there is the attacker: 'repelled Iranian air attacks'; 'from Iran' is the source, never the target)"""
    out = []
    for c in h.children:
        if c.dep_ in ("dobj", "obj") and cls in ("hit", "attack"): out.append(_sub_chars(c, SKIP_O - {"conj"}))
        elif c.dep_ == "prep" and c.lower_ in TARGET_PREP and not any(x.ent_type_ in ("DATE", "TIME") for x in c.subtree): out.append(_sub_chars(c, {"relcl", "acl", "punct"}))
        elif c.dep_ in ("dobj", "obj") and cls == "none":
            for p in c.children:
                if p.dep_ == "prep" and p.lower_ in TARGET_PREP: out.append(_sub_chars(p, {"relcl", "acl", "punct"}))
    return out
def _speaker_list(toks):
    out = []
    for s in toks:
        pron = s.pos_ == "PRON" and s.lower_ in ("it", "he", "she", "they", "we", "who", "which", "that")
        out.append({"text": None if pron else span_text(s, SKIP_S), "span": None if pron else _sub_chars(s, SKIP_S)})
    return out
def _slots(doc):
    out = []; seen = set()
    def add(sl):
        k = (sl["kind"], sl["verb_i"], tuple(tuple(x["span"] or ()) for x in sl["speakers"]), sl["cls"])
        if k not in seen: seen.add(k); out.append(sl)
    for v in doc:
        if v.pos_ not in ("VERB", "AUX"): continue
        lem = v.lemma_.lower()
        if lem in SLOT_SPEECH or lem in DENY_V:
            spk = [x for x in S._subjects(v) if not _outside_subordinate(v, x)] if not any(c.dep_ == "nsubjpass" for c in v.children) else []
            for c in [c for c in v.children if c.dep_ == "ccomp"]:
                for h in [c] + [x for x in c.conjuncts if x.pos_ in ("VERB", "AUX")]:
                    cls, neg = _verb_class(h); den = lem in DENY_V
                    if den: cls = "none" if cls in ("hit", "attack", "blocked") or cls is None else cls; neg = True
                    if cls is None: continue
                    add({"kind": "said", "say": v.lemma_.lower(), "say_text": v.text, "speakers": _speaker_list(spk) or [{"text": None, "span": None}], "cls": cls, "denial": den, "content_span": _sub_chars(c, {"punct"}), "target_spans": _target_spans(h, cls), "self_target": cls in ("blocked", "none"), "sent_targets": cls == "none", "verb_i": h.i})
            if lem in DENY_V:
                for d in [c for c in v.children if c.dep_ in ("dobj", "obj")]:
                    if d.lemma_.lower() in DENIED_N:
                        add({"kind": "said", "say": lem, "say_text": v.text, "speakers": _speaker_list(spk) or [{"text": None, "span": None}], "cls": "none", "denial": True, "content_span": _sub_chars(d, {"punct"}), "target_spans": [], "self_target": True, "sent_targets": True, "verb_i": v.i})
        if lem in SELF_REPORT_V and _has_no_damage(v):
            spk = [x for x in S._subjects(v) if not _outside_subordinate(v, x)]
            if spk: add({"kind": "self", "say": lem, "say_text": v.text, "speakers": _speaker_list(spk), "cls": "none", "denial": False, "content_span": _sub_chars(v, {"punct", "advcl", "relcl", "conj", "cc"}), "target_spans": [], "self_target": True, "sent_targets": True, "verb_i": v.i})
    for t in doc:   # 'according to X' gives X as the speaker of the clause it modifies, unless that clause already has its own speaker
        if t.lower_ == "according" and t.i + 1 < len(doc) and doc[t.i + 1].lower_ == "to":
            h = t.head
            if h.pos_ not in ("VERB", "AUX") or h.lemma_.lower() in SLOT_SPEECH: continue
            pobj = [x for c in doc[t.i + 1].children for x in ([c] if c.dep_ == "pobj" else [])]
            if not pobj: continue
            cls, neg = _verb_class(h)
            if cls is None: continue
            add({"kind": "according_to", "say": "according to", "say_text": "according to", "speakers": [{"text": doc.text[sp[0]:sp[1]], "span": sp} for sp in (_sub_chars(x, {"punct"}) for x in pobj)], "cls": cls, "denial": False, "content_span": _sub_chars(h, {"punct", "prep"} if False else {"punct"}), "target_spans": _target_spans(h, cls), "self_target": False, "sent_targets": False, "verb_i": h.i})
    said = {x["verb_i"] for x in out if x["kind"] == "said"}
    return [x for x in out if not (x["kind"] == "self" and x["verb_i"] in said)]
def _attach_slots(doc, out):
    sl = _slots(doc)
    for s in sl:
        for x in out:
            if x.get("v_i") == s["verb_i"]: x.setdefault("slots", []).append({k: v for k, v in s.items() if k != "verb_i"})
def slot_summary(claims):
    """compact counts for the trace stage: claims carrying a slot, slots by outcome class, slots whose speaker text is missing"""
    sl = [s for c in claims for s in (c.get("slots") or [])]; cnt = collections.Counter(s["cls"] for s in sl)
    return {"claims_with_slot": sum(1 for c in claims if c.get("slots")), "slots": len(sl), "by_class": dict(sorted(cnt.items())), "speaker_unresolved_text": sum(1 for s in sl if not any(x["text"] for x in s["speakers"]))}
