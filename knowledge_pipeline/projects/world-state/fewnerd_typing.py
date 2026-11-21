"""Few-NERD entity typing (T158-N4), a shared importable module (T172, owner yes L2870): the page (simulation/raw-units.py) and the live-trace chain (live_trace_v4.py) import this one file, so they run the same code.
Code moved verbatim from simulation/raw-units.py (the Few-NERD block); only the model path is now relative to this folder. Model: runs/pulse/names_fewnerd_v2/model (spaCy tok2vec+ner, 66 fine types, CC BY-SA 4.0 derivative), CPU.
  fn_nlp()                      the model, loaded once (thread-safe)
  fn_ents(text)                 one pass per article -> [(fine, s, e)]; coarse type = the prefix before '-'
  apply_fewnerd(units, ...)     add-only typing of name and place units, plus new name units for spans no unit covers (src fewnerd)
  summary(fents)                compact counts for a trace stage"""
import bisect, collections, pathlib, threading
HERE = pathlib.Path(__file__).resolve().parent
FN_LABEL = "entities v2 (Few-NERD v2, test F1 coarse 0.713 / fine 0.566)"
FN_MODEL = HERE / "runs" / "pulse" / "names_fewnerd_v2" / "model"   # T172 wave 1: v1 (coarse 0.6908 / fine 0.5372) -> v2 (coarse 0.7126 / fine 0.5657, runs/pulse/names_fewnerd_v2/test-scores-vs-v1.json); v1 stays on disk, point this path back to roll back
_FN = None; _FN_LOCK = threading.Lock()
def fn_nlp():
    """Few-NERD v2 (spaCy tok2vec+ner, 66 fine types), loaded once and cached; CPU."""
    global _FN
    with _FN_LOCK:
        if _FN is None:
            import spacy
            _FN = spacy.load(str(FN_MODEL))
    return _FN
def fn_ents(text):
    """one Few-NERD pass per article -> [(fine, s, e)]; coarse type = the prefix before '-'."""
    d = fn_nlp()(text); return [(e.label_, e.start_char, e.end_char) for e in d.ents]
def apply_fewnerd(units, text, fents, sstarts, sents, topic, place):
    """entities v2 (add-only, after apply_lg): every name unit gets ner_fine / ner_coarse from the best-overlapping Few-NERD span and keeps its lg label in ner_lg (cross-check); place units get ner_fine too;
    Few-NERD spans that overlap no name/date/amount/place unit become new name units (src fewnerd). lg stays the source for DATE/TIME and numbers."""
    ov = lambda a, b, x, y: min(b, y) - max(a, x)
    for u in units:
        if u["type"] in ("name", "place") and u.get("spans"):
            a, b = u["spans"][0]["s"], u["spans"][0]["e"]; best = max(((ov(a, b, x, y), l) for l, x, y in fents if x < b and a < y), default=None)
            if u["type"] == "name": u["ner_lg"] = u.get("ner")
            if best: u["ner_fine"] = best[1]; u["ner_coarse"] = best[1].split("-")[0]; u["ner_fine_src"] = "fewnerd"
    occ = [(sp["s"], sp["e"]) for u in units if u["type"] in ("name", "date", "amount", "place") for sp in (u["spans"] or [])[:1]]
    sidx = lambda pos: max(0, bisect.bisect_right(sstarts, pos) - 1); new = []
    for lab, a, b in fents:
        t = text[a:b].strip()
        if not t or any(ov(a, b, x, y) > 0 for x, y in occ): continue
        s = sidx(a); new.append({"unit": None, "sent_text": (text[sents[s][0]:sents[s][1]].strip()[:300] if s < len(sents) else None), "type": "name", "subject": t, "predicate": None, "value": None, "sentence": s, "id": None, "spans": [{"role": "name", "s": a, "e": b}], "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place, "src": "fewnerd", "ner": "UNTYPED", "ner_src": "fewnerd", "ner_lg": None, "ner_fine": lab, "ner_coarse": lab.split("-")[0], "ner_fine_src": "fewnerd"}); occ.append((a, b))
    units.extend(new); return len(new)
def summary(fents):
    """compact counts for the trace stage: mentions, by coarse type, by fine type (top 8)"""
    co = collections.Counter(l.split("-")[0] for l, _, _ in fents); fi = collections.Counter(l for l, _, _ in fents)
    return {"mentions": len(fents), "by_coarse": dict(sorted(co.items())), "top_fine": [[k, n] for k, n in sorted(fi.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]}
