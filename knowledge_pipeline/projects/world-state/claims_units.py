"""claims v1 as claim UNITS, a shared importable module (T172, owner yes L2870): the page (simulation/raw-units.py) and the live-trace chain (live_trace_v4.py) import this one file. Rules live in claims_v1.py (claims-v1.py is a loader shim for the scripts that still load the kebab-case name).
Code moved verbatim from simulation/raw-units.py (triple_spans, the claims v1 hook); the only change is that the extraction is a function of its own (extract_claims) so the chain can run it once and hand the result to the hook.
RAW_CLAIMS_V1=0 restores the v0 path exactly (the hook returns at once).
  extract_claims(text)                        -> the v1 claims worth keeping (has a verb span, a subject or object, a predicate); parses with en_core_web_lg (parser on, NER excluded), loaded once
  claims_v1(units, text, sents, stats, ...)   add-only unit builder, run BEFORE claims_v0 so its pronoun resolver also sees these claims; pass claims= to skip the parse
  triple_spans(text, a, b, v, sents)          the verb, subject and object spans of one triple
  summary(claims)                             compact counts for a trace stage"""
import os, re, time, bisect, threading, collections
import claims_v1 as V1
CLAIMS_V1_LABEL = "claims v1 (lg dependency rules: full phrases, passive, clause, measure, attributes), CaRB test F1 0.557 in-house scorer vs 0.136 for the v0 path (T158)"
_C1 = {"nlp": None}; _C1_LOCK = threading.Lock()
def triple_spans(text, a, b, v, sents):
    """The fact's own [a, b) is the verb token (surface form, so the verb span is verbatim even when v[1] is a lemma). Subject: last case-insensitive hit of v[0] before the verb inside the same sentence; object: first hit of v[2] after the verb there;
    either falls back to the nearest hit anywhere in the sentence. A role whose string is not in the sentence is left out."""
    sa, sb = 0, len(text)
    for x, y in sents:
        if x <= a < y: sa, sb = x, y; break
    low = text.lower(); out = [{"role": "verb", "s": a, "e": b}]
    def find(w, before):
        w = (w or "").strip().lower()
        if not w: return None
        i = low.rfind(w, sa, a) if before else low.find(w, b, sb)
        if i < 0: i = low.find(w, sa, sb)
        return None if i < 0 else {"s": i, "e": i + len(w)}
    for role, w, before in (("subject", v[0], True), ("object", v[2], False)):
        r = find(w, before)
        if r: out.append({"role": role, **r})
    return sorted(out, key=lambda x: x["s"])
def claims_nlp():
    with _C1_LOCK:
        if _C1["nlp"] is None:
            import spacy
            _C1["nlp"] = spacy.load("en_core_web_lg", exclude=["ner"])
    return _C1["nlp"]
def extract_claims(text):
    """one parse per article -> the v1 claims with a verb span, a subject or object and a predicate (what the hook turns into units)."""
    nlp = claims_nlp()
    return [c for c in V1.extract(text, nlp) if c.get("v_span") and (c["s"] or c["o"]) and c["p"]]
def claims_v1(units, text, sents, stats, topic, place, claims=None):
    """add-only, run BEFORE claims_v0 so its pronoun resolver also sees these claims. Parses the article once with en_core_web_lg (parser on, NER excluded, CPU; about 40 ms for 680 words), builds claims with claims_v1.py, and replaces each v0 triple or partial claim that has the same verb span with the v1 claim (kept in the unit as v0_value). Subject = the short name (merge key unchanged in kind); the full phrase is in subject_full; the object (value) is the full phrase. Prepositional-phrase objects that sit beside a direct object are flagged demoted and listed as attrs of the direct claim."""
    if os.environ.get("RAW_CLAIMS_V1", "1") == "0": return
    sstarts = [a for a, b in sents]; sidx = lambda pos: max(0, bisect.bisect_right(sstarts, pos) - 1); t0 = time.perf_counter()
    cl = extract_claims(text) if claims is None else claims; new = []
    for c in cl:
        vs, ve = c["v_span"]; si = sidx(vs); subj = c["s_short"] or c["s"]; both = bool(c["s"] and c["o"])
        u = {"unit": None, "sent_text": (text[sents[si][0]:sents[si][1]].strip()[:300] if si < len(sents) else None), "type": "triple" if both else "partial_claim", "subject": subj or None, "predicate": c["p"], "value": c["o"] or None, "sentence": si, "id": None, "spans": triple_spans(text, vs, ve, [subj, c["p"], c["o"]], sents),
             "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place, "src": "claims v1", "subject_full": c["s"], "negated": c["neg"], "modal": c["modal"], "attributed_to": c["attrib"] or c.get("said_by"), "passive": c["passive"], "attrs": c["attrs"], "demoted": bool(c.get("demoted")), "rule": c["rule"]}
        if "clause_antecedent" in c["rule"]: u["subject_surface"] = "pronoun"; u["agent_how"] = "clause antecedent (subject of the governing clause, same sentence)"
        if not both: u["missing"] = "subject" if not c["s"] else "object"
        new.append(u)
    vkeys = {(x["s"], x["e"]) for u in new for x in u["spans"] if x["role"] == "verb"}; old = len(units)
    units[:] = [u for u in units if not (u["type"] in ("triple", "partial_claim") and any(x["role"] == "verb" and (x["s"], x["e"]) in vkeys for x in (u.get("spans") or [])))] + new
    stats["claims_v1"] = len(new); stats["superseded_v0"] = old - (len(units) - len(new)); stats["claims_v1_ms"] = round((time.perf_counter() - t0) * 1000, 1)
def summary(claims):
    """compact counts for the trace stage: claims, with both sides, partial, negated, modal, attributed, by rule"""
    both = sum(1 for c in claims if c["s"] and c["o"]); rules = collections.Counter(r for c in claims for r in (c.get("rule") or []))
    return {"claims": len(claims), "both_sides": both, "partial": len(claims) - both, "negated": sum(1 for c in claims if c.get("neg")), "modal": sum(1 for c in claims if c.get("modal")), "attributed": sum(1 for c in claims if c.get("attrib") or c.get("said_by")), "by_rule": dict(sorted(rules.items()))}
