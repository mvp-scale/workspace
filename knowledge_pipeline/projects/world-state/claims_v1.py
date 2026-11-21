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
import re
import spo_chains as S
OPTS = {"expand_o": True, "expand_s": True, "attrs": True, "speaker": True, "copula": True, "clause": True, "xcomp": True, "measure": True, "attrs_move": False, "passive": True, "dedupe": True, "measure_move": True}
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
def extract(text, nlp, opts=None):
    o_ = {**OPTS, **(opts or {})}; doc = nlp(text); T = S.extract(nlp, [doc]); out = []
    for t in T:
        s = doc[t["s_i"]] if t["s_i"] is not None else None; o = doc[t["o_i"]] if t["o_i"] is not None else None; v = doc[t["v_i"]]
        s_text = t["s"]; o_text = t["o"]; p = t["p"]; attrs = []; rule = []; s_short = t["s"]
        if o_.get("expand_s") and s is not None and not t["s_pronoun"] and s.pos_ in ("NOUN", "PROPN", "NUM"):
            s_text = span_text(s, SKIP_S); rule.append("expand_s")
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
    if o_.get("measure"): out += _measure(doc, out)
    if o_.get("attrs"): out = _attrs(doc, out, o_)
    for x in out:
        x["v_span"] = [doc[x["v_i"]].idx, doc[x["v_i"]].idx + len(doc[x["v_i"]].text)] if x.get("v_i") is not None else None
        for k in ("v_i", "s_i", "prep", "o_pos"): x.pop(k, None)
    return out

def _clause_text(c):
    keep = [x for x in c.subtree if not (x.dep_ == "punct" and x.i in (c.left_edge.i, c.right_edge.i))]; return c.doc[c.left_edge.i:c.right_edge.i + 1].text.strip(" ,;")
def _extra(doc, out, o_):
    """claims the base misses: a reported or complement clause as the object (X said/thinks that CLAUSE, speaker kept in attrib for speech verbs), a to-infinitive complement (X plans to DO), a copula with a prepositional complement (X was in Y)"""
    add = []; have = {(x["p"], x["v_i"]) for x in out if "v_i" in x}
    for v in doc:
        if v.pos_ not in ("VERB", "AUX"): continue
        subs = S._subjects(v)
        if not subs: continue
        sT = span_text(subs[0], SKIP_S) if subs[0].pos_ in ("NOUN", "PROPN", "NUM") else subs[0].text
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
def _measure(doc, out):
    """'dropped 10%' : a numeric npadvmod/dobj measure of the verb is its object (the amount), so a later 'under Trump' stays an attribute"""
    add = []; have = {(x["v_i"], x.get("s_i")) for x in out if x.get("v_i") is not None and x.get("prep") is None and x["o"]}
    for v in doc:
        if v.pos_ != "VERB": continue
        for c in v.children:
            if c.dep_ == "npadvmod" and (c.ent_type_ in _MEASURE_ENT or any(x.pos_ == "NUM" for x in c.children) or c.pos_ == "NUM") and c.ent_type_ not in ("DATE", "TIME"):
                subs = S._subjects(v)
                if not subs: continue
                sT = span_text(subs[0], SKIP_S) if subs[0].pos_ in ("NOUN", "PROPN", "NUM") else subs[0].text
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
