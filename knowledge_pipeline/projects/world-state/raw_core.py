"""raw_core: the page's record builder as a SHARED IMPORTABLE MODULE (T172, owner yes L2870, design L2869). Code moved verbatim from simulation/raw-units.py; the page (raw-units.py) and the live-trace chain (live_trace_v4.py) import this one file, so they run the same code.
Contents: the unit builder (units_for), spaCy-lg entity typing (apply_lg), claims funnel v0 (claims_v0), the sentence table and item lists (sentence_table, extras), the optional saved heads, the record builder build_rec (everything run_one does after the live_trace stages),
the merge rule (filter_v0, identity, Graph, merge_units). Few-NERD typing is in fewnerd_typing.py, claims v1 in claims_units.py / claims_v1.py, G4 alignment in g4_align.py.
Behaviour is unchanged for the page. Changes for the chain, each defaulting to the old behaviour: Graph(dur_dir, durable, ledger) places or disables the durable node log and can skip the resource ledger; merge_units takes the graph (and the chain) as arguments;
build_rec(fewnerd=, claims=, pre=) can leave Few-NERD or claims v1 out and take their results from an earlier chain stage instead of running them again. No hosted calls, CPU only."""
import os, re, sys, json, time, bisect, threading, collections, unicodedata
import journal as JR
import ledger_split as LS
import g4_align as G4
from claims_units import triple_spans, claims_v1, CLAIMS_V1_LABEL
from fewnerd_typing import fn_nlp, fn_ents, apply_fewnerd, FN_LABEL
_CH = {"fn": None, "ch": None}
def set_chain(fn=None, ch=None):
    """the chain that identity() uses when none is passed: the page registers its lazy chain() function, the live-trace chain registers itself"""
    _CH["fn"] = fn; _CH["ch"] = ch
def current_chain(): return _CH["ch"] or (_CH["fn"]() if _CH["fn"] else None)
MERGE_LABEL = "merge rule v1 (type + entity identity), unmeasured"
_ARTICLES = {"a", "an", "the"}
def norm(s):   # possessive 's folded (Cuba's -> cuba)
    s = unicodedata.normalize("NFKD", str(s or "")).lower(); s = re.sub(r"['\u2019]s\b", "", s); s = re.sub(r"[^\w\s]", " ", s); w = [x for x in s.split() if x not in _ARTICLES]; return " ".join(w)
FILTER_LABEL = "filter v0.1 (original-case acronym check)"
from spacy.lang.en.stop_words import STOP_WORDS
PRONOUNS = set("i me my mine myself you your yours yourself he him his himself she her hers herself it its itself we us our ours ourselves they them their theirs themselves who whom whose which what that this these those there here".split())
def filter_v0(u):
    """filter v0 (first extraction round's baseline, not tuned): drop units with no span; subjects that are pronouns or spaCy stop words; amounts with no unit and no noun. Returns a reason code or None."""
    if not u["spans"]: return "no_span"
    n = norm(u["subject"]) if u["type"] not in ("place",) else ""
    raw = re.sub(r"[^A-Za-z]", "", str(u["subject"] or "")); acro = len(raw) >= 2 and raw.isupper()   # all-caps acronyms (US, UK, IT, WHO, EU) are names, not pronouns or stop words; checked on the original case
    if acro: n = ""
    if n and n in PRONOUNS: return "pronoun"
    if n and (n in STOP_WORDS or all(w in STOP_WORDS for w in n.split())): return "function_word"
    if u["type"] == "amount" and not (u.get("unit") or u["subject"]): return "amount_no_unit"
    return None
def identity(subj, ch=None):
    """entity identity for the merge key: country ISO2 when the surface is a country name, alias or demonym (Cuba, Cuba's, Cuban -> iso:CU), else the normalised name with the possessive folded."""
    t = re.sub(r"['\u2019]s$", "", str(subj or "").strip()); t = re.sub(r"^the ", "", t, flags=re.I); ch = ch or current_chain()
    if not hasattr(ch.pack, "_lk"): ch.pack.lookup_places("", ch.EX)
    hit = ch.pack._lk[0].get(t)
    return ("iso:" + hit[0]) if hit else norm(subj)
def _node_log(dur_dir=None, durable=None):
    """durable merge-index log (plan step 1): append-only JSONL beside the G4 store; None when G4_DURABLE=0 (durable=None: the env decides, as on the page; True / False: the chain says)"""
    if (os.environ.get("G4_DURABLE", "1") == "0") if durable is None else not durable: return None
    return os.path.join(dur_dir or os.environ.get("G4_DURABLE_DIR") or G4.DEFAULT_DIR, "raw-units-nodes.jsonl")
class Graph:
    def __init__(self, dur_dir=None, durable=None, ledger=True):
        self.lock = threading.Lock(); self.g4_dir = dur_dir; self.g4_durable = durable; self.with_ledger = ledger; self.reset(); self.load_durable()   # g4_dir / g4_durable: read by g4_align.align for its store
    def load_durable(self):
        p = _node_log(self.g4_dir, self.g4_durable)
        if not p or not os.path.exists(p): return
        for l in open(p, encoding="utf-8"):
            if not l.strip(): continue
            r = json.loads(l); self.merge(tuple(r["k"]), r["art"], r["pub"], r["label"], r["topic"], _replay=True); self.pulled.add(r["art"])
    def reset(self):
        self.nodes = {}; self.pulled = set(); self.batches = 0; self.jidx = JR.new_index(); self.seq = 0; self.seqmap = {}; self.g4 = None   # g4: G4/G5 v1 store, created lazily by g4-align
        if self.with_ledger: self.ledger = LS.Ledger(json.load(open(LS.SPEC)), "auto"); self.rnames = {r["id"]: (r["name"], r["group"]) for r in self.ledger.sp["resources"]}
    def merge(self, key, art, pub, label, topic=None, _replay=False):
        n0 = self.nodes.get(key); sig = (len(n0["arts"]), len(n0["topics"])) if n0 else None
        r = self._merge(key, art, pub, label, topic); n1 = self.nodes[key]; p = _node_log(self.g4_dir, self.g4_durable)
        if p and not _replay and sig != (len(n1["arts"]), len(n1["topics"])):   # something changed: append it (SAME ARTICLE with nothing new writes nothing)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a", encoding="utf-8") as f: f.write(json.dumps({"k": list(key), "art": art, "pub": pub, "label": label, "topic": topic}, sort_keys=True, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        return r
    def _merge(self, key, art, pub, label, topic=None):
        n = self.nodes.get(key)
        if n is None: self.nodes[key] = {"label": label, "arts": {art: pub}, "topics": {topic} if topic else set()}; return {"result": "NEW", "before": 0, "after": 1, "articles": [art], "publishers": [pub], "topic_nodes": sorted(self.nodes[key]["topics"])}
        if topic: n["topics"].add(topic)   # the topic node is a property of the node (the set seen), not part of the key
        if art in n["arts"]: return {"result": "SAME ARTICLE", "before": len(n["arts"]), "after": len(n["arts"]), "articles": list(n["arts"]), "publishers": sorted(set(n["arts"].values())), "topic_nodes": sorted(n["topics"])}
        b = len(n["arts"]); n["arts"][art] = pub; return {"result": "+EVIDENCE", "before": b, "after": b + 1, "articles": list(n["arts"]), "publishers": sorted(set(n["arts"].values())), "topic_nodes": sorted(n["topics"])}
def lab(ch, q): return ch.pack.lab(q) if q and q in ch.pack.node else None
def units_for(ch, line, text, stats=None):
    """units from the stage items: triples, names, amounts, dates (facts), places (place_linker), capability pairs (capability_list). Returns (units, topic, place)."""
    FL, SG = ch.FL, ch.SG; date = (line["published"] or "")[:10]; date = date if re.match(r"^\d{4}-\d{2}-\d{2}$", date) else None; ds = (date + "T00:00:00Z") if date else None
    kept, _ = FL.quarantine(FL.facts_for(text, ds)[0], text); _, sents = SG.scan(text, ds or "2026-01-01T00:00:00Z"); starts = [a for a, b in sents]
    sidx = lambda pos: max(0, bisect.bisect_right(starts, pos) - 1)
    st = {s["name"]: s for s in line["stages"]}; tl = (st.get("topic_landing") or {}).get("out") or {}; rr = tl.get("rerank") or {}
    topic = {"l1": rr.get("l1_code") or tl.get("l1_code"), "node": rr.get("node"), "p": rr.get("p"), "decision": tl.get("decision")}
    pl = (st.get("place_linker") or {}).get("out") or {}; place = (pl.get("top_countries") or [[None]])[0][0] or ((st.get("place_student") or {}).get("out") or {}).get("top1")
    U = []
    def add(typ, subj, val, s, sid=None, pred=None, spans=None, unit=None): U.append({"unit": unit, "sent_text": (text[sents[s][0]:sents[s][1]].strip()[:300] if s is not None and s < len(sents) else None), "type": typ, "subject": subj, "predicate": pred, "value": val, "sentence": s, "id": sid, "spans": spans or [], "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place})
    for f in kept:
        v = f.get("value"); k = f["kind"]; s = sidx(f["s"])
        if k == "triple" and stats is not None: stats["found"] = stats.get("found", 0) + 1
        if k == "triple" and isinstance(v, list) and len(v) == 3 and v[0] and v[2]: add("triple", v[0], v[2], s, pred=v[1], spans=triple_spans(text, f["s"], f["e"], v, sents))
        elif k == "triple" and isinstance(v, list) and len(v) == 3 and v[1] and (v[0] or v[2]):   # claims funnel v0: an unbound triple (one side missing) is kept as a partial claim, shown and never merged
            add("partial_claim", v[0] or None, v[2] or None, s, pred=v[1], spans=triple_spans(text, f["s"], f["e"], v, sents)); U[-1]["missing"] = "subject" if not v[0] else "object"; U[-1]["status"] = f.get("status")
        elif k == "triple" and stats is not None: stats["unusable"] = stats.get("unusable", 0) + 1
        elif k == "name": add("name", f["text"].strip(), None, s, spans=[{"role": "name", "s": f["s"], "e": f["e"]}])
        elif k == "amount": add("amount", (f.get("noun") or f.get("unit") or "").strip() or None, f["text"].strip(), s, pred=f.get("verb") or None, spans=[{"role": "amount", "s": f["s"], "e": f["e"]}], unit=f.get("unit") or None)
        elif k == "date": add("date", str(v) if v else f["text"].strip(), f["text"].strip(), s, spans=[{"role": "date", "s": f["s"], "e": f["e"]}])
    return U, topic, place
LG_LABEL = "entities v1 (spaCy lg), unmeasured vs outside truth"
LG_NAMES = {"PERSON", "ORG", "GPE", "NORP", "LOC", "FAC", "PRODUCT", "EVENT", "LAW", "WORK_OF_ART", "LANGUAGE"}
LG_DATES = {"DATE", "TIME"}; LG_AMTS = {"CARDINAL", "MONEY", "PERCENT", "QUANTITY"}
_LG = None; _LG_LOCK = threading.Lock()
def lg_nlp():
    """spaCy en_core_web_lg 3.8.0 (MIT), loaded once and cached; only tok2vec + ner run (no parser/tagger), CPU."""
    global _LG
    with _LG_LOCK:
        if _LG is None:
            import spacy
            _LG = spacy.load("en_core_web_lg", exclude=["parser", "lemmatizer", "tagger", "attribute_ruler", "senter"])
    return _LG
def lg_ents(text):
    """one lg pass per article -> [(label, s, e)] with the raw OntoNotes label."""
    d = lg_nlp()(text); return [(e.label_, e.start_char, e.end_char) for e in d.ents]
_NEXTW = re.compile(r"\s+([a-z][a-z\-]{2,})")
def apply_lg(units, text, ents, sstarts, sents, topic, place):
    """entities v1 (add-only): type every name unit with its lg label; lg names with no overlapping name unit become name units (src lg); lg DATE/TIME and CARDINAL/MONEY/PERCENT/QUANTITY become date/amount units when they overlap no existing unit. The place lookup is untouched."""
    ov = lambda a, b, x, y: min(b, y) - max(a, x)
    names = [u for u in units if u["type"] == "name" and u["spans"]]
    for u in names:
        a, b = u["spans"][0]["s"], u["spans"][0]["e"]; best = max(((ov(a, b, x, y), l) for l, x, y in ents if x < b and a < y), default=None)
        u["ner"] = best[1] if best else "UNTYPED"; u["ner_src"] = "lg" if best else "spot only, no lg label"
    nm_sp = [(u["spans"][0]["s"], u["spans"][0]["e"]) for u in names]
    occ = [(sp["s"], sp["e"]) for u in units if u["type"] in ("name", "date", "amount", "place") for sp in (u["spans"] or [])[:1]]
    sidx = lambda pos: max(0, bisect.bisect_right(sstarts, pos) - 1); new = []
    def mk(typ, subj, val, a, b, lab, unit=None):
        s = sidx(a); return {"unit": unit, "sent_text": (text[sents[s][0]:sents[s][1]].strip()[:300] if s < len(sents) else None), "type": typ, "subject": subj, "predicate": None, "value": val, "sentence": s, "id": None, "spans": [{"role": typ, "s": a, "e": b}], "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place, "src": "lg", "ner": lab, "ner_src": "lg"}
    for lab, a, b in ents:
        t = text[a:b].strip()
        if not t: continue
        if lab in LG_NAMES:
            if any(ov(a, b, x, y) > 0 for x, y in nm_sp): continue
            new.append(mk("name", t, None, a, b, lab)); nm_sp.append((a, b))
        elif lab in LG_DATES or lab in LG_AMTS:
            if any(ov(a, b, x, y) > 0 for x, y in occ): continue
            if lab in LG_DATES: new.append(mk("date", t, t, a, b, lab))
            else:
                m = _NEXTW.match(text, b); noun = m.group(1) if (m and lab in ("CARDINAL", "QUANTITY")) else None
                new.append(mk("amount", noun, t, a, b, lab, unit={"PERCENT": "%", "MONEY": "money", "QUANTITY": "quantity"}.get(lab)))
            occ.append((a, b))
    units.extend(new); return len(new)
CLAIMS_LABEL = "claims funnel v0 (partial claims kept, pronoun resolver v0, attribution claims), unmeasured"
_PRON = {"he", "she", "they", "it"}
def claims_v0(units, text, ents, sents, spots, stats, topic, place):
    """add-only. (1) pronoun resolver v0: a he/she/they/it subject of a triple takes the nearest preceding lg PERSON/ORG mention within 2 sentences (resolved_from marks it; no gender or number check). (2) attribution claims: each scan attribution spot with a PERSON/ORG speaker
    (lg mention before the verb in the sentence within 80 characters, else right after it within 30; 'according to X'; or a he/she/they resolved as above) becomes a claim speaker -> verb -> clause (the sentence's quote, else the rest of the sentence). Returns nothing; edits units and stats."""
    sstarts = [a for a, b in sents]; sidx = lambda pos: max(0, bisect.bisect_right(sstarts, pos) - 1)
    cand = sorted([(a, b, l) for l, a, b in ents if l in ("PERSON", "ORG")], key=lambda x: x[1])
    def resolve(pos, pron=None):
        best = None
        ok = {"it": ("ORG",), "he": ("PERSON",), "she": ("PERSON",)}.get((pron or "").lower())   # T158-C1 (add-only argument): 'it' never takes a PERSON ('It follows the loss' was resolved to David Bassanese), he/she never an ORG; 'they' keeps both; no pronoun given = old behaviour
        for a, b, l in cand:
            if b <= pos and sidx(pos) - sidx(a) <= 2 and (ok is None or l in ok): best = (a, b, l)
        return best
    stats["pronoun_subjects"] = stats["resolved"] = 0
    for u in units:
        if u["type"] != "triple" or str(u["subject"]).strip().lower() not in _PRON: continue
        g = {x["role"]: x for x in u["spans"]}; vs = g["verb"]["s"] if "verb" in g else None; stats["pronoun_subjects"] += 1
        if vs is None: continue
        sa = sents[u["sentence"]][0] if u["sentence"] is not None and u["sentence"] < len(sents) else 0
        ms = [m for m in re.finditer(r"\b%s\b" % re.escape(str(u["subject"]).strip()), text[sa:vs], flags=re.I)]
        if not ms: continue
        pos = sa + ms[-1].start(); r = resolve(pos, u["subject"])
        if r:
            u["subject_surface"] = u["subject"]; u["subject"] = text[r[0]:r[1]].strip(); u["resolved_from"] = {"pronoun": u["subject_surface"], "to": u["subject"], "ner": r[2], "span": {"s": r[0], "e": r[1]}, "sentences_back": sidx(pos) - sidx(r[0]), "label": CLAIMS_LABEL}; stats["resolved"] += 1
    spk = [(a, b, l) for l, a, b in ents if l in ("PERSON", "ORG")]; stats["attribution_spots"] = 0; stats["attribution"] = 0; done = set()
    quotes = [x for x in spots if x[2] == "quote"]
    for sp in spots:
        if sp[2] != "attribution": continue
        stats["attribution_spots"] += 1; vs, ve = sp[0], sp[1]; si = sidx(vs); sa, sb = sents[si] if si < len(sents) else (0, len(text)); word = text[vs:ve].lower(); who = None; res = None; clause = None
        if word == "according to":
            a_ = [x for x in spk if ve <= x[0] <= ve + 60 and x[1] <= sb]
            if a_:
                who = a_[0]; rest = text[who[1]:sb].lstrip(" ,;:"); clause = (rest, who[1] + (len(text[who[1]:sb]) - len(text[who[1]:sb].lstrip(" ,;:"))), sb)
        else:
            b_ = [x for x in spk if sa <= x[0] and x[1] <= vs and vs - x[1] <= 80]
            if b_: who = b_[-1]
            else:
                a_ = [x for x in spk if ve <= x[0] <= ve + 30 and x[1] <= sb]
                if a_: who = a_[0]
                else:
                    m = re.search(r"\b(he|she|they)\s*$", text[sa:vs], flags=re.I)
                    if m:
                        r = resolve(sa + m.start(), m.group(1))
                        if r: who = r; res = {"pronoun": m.group(1), "to": text[r[0]:r[1]].strip(), "ner": r[2], "span": {"s": r[0], "e": r[1]}, "sentences_back": sidx(sa + m.start()) - sidx(r[0]), "label": CLAIMS_LABEL}
        if not who: continue
        qs = [q for q in quotes if sa <= q[0] < sb]
        if qs: clause = (text[qs[0][0]:qs[0][1]], qs[0][0], qs[0][1])
        elif clause is None:
            if who[1] <= vs: a2, b2 = ve, sb
            else: a2, b2 = sa, vs
            seg = text[a2:b2]; lead = len(seg) - len(seg.lstrip(" ,;:")); seg = seg.lstrip(" ,;:"); seg = re.sub(r"^that\s+", "", seg); clause = (seg, a2 + lead, b2)
        ct, ca, cb = clause; ct = ct.strip()
        if len(ct) < 12 or (vs, ve) in done: continue
        done.add((vs, ve)); stats["attribution"] += 1
        u = {"unit": None, "sent_text": text[sa:sb].strip()[:300], "type": "attribution", "subject": text[who[0]:who[1]].strip(), "predicate": text[vs:ve], "value": ct[:200], "sentence": si, "id": None, "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place, "src": "attribution v0", "ner": who[2], "ner_src": "lg",
             "spans": [{"role": "speaker", "s": who[0], "e": who[1]}, {"role": "verb", "s": vs, "e": ve}, {"role": "clause", "s": ca, "e": min(cb, ca + 200)}]}
        if res: u["resolved_from"] = res
        units.append(u)
def sentence_table(text, spots, sents, units):
    """per-sentence rule cues (the server.py claims_layer cue rules, same logic, untested): reported (attribution or quote spot), predicted (modal), else asserted; negated; the claims whose verb falls in the sentence."""
    out = []
    for i, (a, b) in enumerate(sents):
        by = collections.defaultdict(list)
        for sp in spots:
            if a <= sp[0] < b: by[sp[2]].append(sp)
        out.append({"i": i, "span": [a, b], "factuality": "reported" if (by.get("attribution") or by.get("quote")) else ("predicted" if by.get("modal") else "asserted"), "negated": bool(by.get("negation")), "modal": bool(by.get("modal")),
                    "claims": sum(1 for u in units if u["type"] in ("triple", "partial_claim", "attribution") and u.get("sentence") == i), "words": len(text[a:b].split())})
    return out
HEAD_FILES = {"function_sentence": ["runs/pulse/t210/t210_function_head.pkl", "runs/pulse/t210"], "factuality_story": ["runs/pulse/t178/t178_factuality_student.pkl", "runs/pulse/t152_factuality_student.pkl"], "time": ["runs/pulse/t165/t165_time_head.pkl"], "novelty": ["runs/pulse/t169/t169_novelty_head.pkl"]}
HEAD_ROW = {"function_sentence": "Story type / Function", "factuality_story": "Factuality", "time": "Time (recent)", "novelty": "Novelty"}
HEAD_WHY = {"function_sentence": "t210_save_function_head.py was written but never run: runs/pulse/t210 does not exist and no function-head pickle exists anywhere; producing it means fitting 1,792-dim features on 51,000 sentences, which is training",
            "factuality_story": "t178_factuality_student.py writes only cross-validation scores (runs/pulse/t178/t178_factuality_student.json) and never saves a fitted model; the student scores 0.61 to 0.64 balanced accuracy against the 0.80 bar",
            "time": "t165_time_head.py writes only a score file (runs/pulse/t165/t165_time_head.json), no saved model; no trustworthy time judge exists (AUC 0.607)",
            "novelty": "t169_novelty_pilot.py and t169b write Jev-read pilot files only, no saved model; the as-worded test scores AUROC 0.51"}
RAW_HEADS = os.environ.get("RAW_HEADS", "0") == "1"   # T158-H1: add-only flag, default off. RAW_HEADS=1 loads the saved function and factuality heads (runs/pulse/function_head_v1, factuality_v1) if present
_SH = {"h": None, "err": None, "tried": False}
def saved_heads():
    if not RAW_HEADS: return None
    if not _SH["tried"]:
        _SH["tried"] = True
        try:
            import importlib.util; base = os.path.dirname(os.path.abspath(__file__)); sp = importlib.util.spec_from_file_location("saved_heads", os.path.join(base, "saved-heads.py")); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); _SH["h"] = m.SavedHeads()
        except Exception as e: _SH["err"] = repr(e)[:200]
    return _SH["h"]
def attach_heads(rec, text, sents):
    """RAW_HEADS=1 only: per-sentence function_p (P opinion, Jev-copy label) / function (opinion|fact|unsure) and factuality_p (P happened) added to rec["sentences"]; trust labels travel with them."""
    h = saved_heads()
    if h is None: return
    t = time.perf_counter(); texts = [text[a:b].strip() for a, b in sents]; o = h.score(texts)
    for row, i in zip(rec["sentences"], range(len(texts))):
        if "function_p" in o: row["function_p"] = round(o["function_p"][i], 3); row["function"] = o["function_answer"][i]
        if "factuality_p" in o: row["factuality_p"] = round(o["factuality_p"][i], 3)
    rec["heads_ms"] = round((time.perf_counter() - t) * 1000, 1); rec["heads_label"] = "saved CPU heads T158-H1: function head AUC 0.79 vs human gold on 300 CheckThat sentences (copies Jev, Jev 0.88); factuality head cross-validated bal acc 0.56-0.64 (below Jev 0.72, below the 0.80 bar), trained on event sentences only, so its value on other sentences is untested"
def heads_check(stage_out):
    """the four heads live_trace lists as not_attached: does a saved model exist on disk? Nothing is trained here; a saved model would be loaded in raw-units only if it loads in under 200 ms (none exists, so none is attached)."""
    base = os.path.dirname(os.path.abspath(__file__)); out = []
    for nm in ("function_sentence", "factuality_story", "time", "novelty"):
        found = [f for f in HEAD_FILES[nm] if os.path.isfile(os.path.join(base, f))]
        _on = bool(saved_heads()) and nm in ("function_sentence", "factuality_story")
        out.append({"stage": nm, "head_row": HEAD_ROW[nm], "attached": _on, "attach_note": ("per-sentence outputs in rec.sentences (RAW_HEADS=1)" if _on else (_SH["err"] if RAW_HEADS and _SH["err"] else None)), "saved_model_found": bool(found), "looked_for": HEAD_FILES[nm], "live_trace_why": (stage_out.get(nm) or {}).get("why"), "reason": HEAD_WHY[nm] if not found else "a saved file exists but raw-units has no loader for it yet"})
    return out
def extras(ch, text, full, spots, sents, line):
    """item-level lists the stages keep in `full` (live_trace is not edited): windows, scan dates, change bundles, independent runs, the landing top-3 with embedding scores, the structure-pack placement, held items; span_rules items are re-read with the stage's own call because `full` keeps only counts."""
    date = (line["published"] or "")[:10]; ds = (date + "T00:00:00Z") if re.match(r"^\d{4}-\d{2}-\d{2}$", date) else None
    sp = ch.SR.spans(text, ds); kept, held = ch.FL.quarantine(sp, text)
    g = lambda k: full.get(k) or {}
    tl = g("topic_landing"); pk = g("structure_pack"); art = tl.get("article") or []
    return {"label": "item lists from live_trace `full` (add-only)", "windows": g("windows").get("offsets_text"), "scan_dates": g("scan_dates").get("dates"), "span_rules": [{"kind": x["kind"], "s": x["s"], "e": x["e"], "text": x.get("text"), "value": x.get("value")} for x in kept], "span_held": g("span_rules").get("held"),
            "facts_held": g("facts").get("held"), "bundles": g("tags_bundles").get("bundles"), "independent": {k: g("independent_counter").get(k) for k in ("amount", "date", "name", "amount_runs", "date_runs")},
            "landing": {"top3": [{"code": a["qcode"], "label": a.get("label"), "score": a.get("score"), "path": a.get("path"), "definition": a.get("definition")} for a in art[:3]], "best": tl.get("best"), "vote": tl.get("vote"), "n_sent": tl.get("n_sent"), "rerank": tl.get("rerank"), "decision": tl.get("decision"), "how": "cosine of the article's sentence embeddings against the IPTC card embeddings (e5-small)"},
            "mapping": {"l1_code_used": pk.get("l1_code_used"), "n_terms": pk.get("n_terms"), "n_placed": pk.get("n_placed"), "in_topic": pk.get("in_topic"), "hops": pk.get("hops"), "unplaced_share": pk.get("unplaced_share"), "unplaced": pk.get("unplaced"), "placed": [[x["start"], x["end"], x["word"], x["hop"], x.get("via"), x.get("path"), x.get("in_topic")] for x in (pk.get("placed_spans") or [])]}}
_NERMAP = {"PERSON": "person", "ORG": "org", "GPE": "place", "LOC": "place", "FAC": "place", "NORP": "group"}
def ner_spans(ch, text):
    """spaCy NER (the pipe place_linker already enables) -> [(label, s, e)]; used only to tag name units."""
    with ch.EX.nlp.select_pipes(enable=["tok2vec", "ner"]): d = ch.EX.nlp(text)
    return [(_NERMAP.get(e.label_, e.label_.lower()), e.start_char, e.end_char) for e in d.ents]
def build_rec(ch, line, text, full, rec, fewnerd=True, claims=True, pre=None):
    """everything the page does with one traced article after the live_trace stages: units from the stage items and the fact finder, lg and Few-NERD typing, claims v1 and v0, the sentence table, the item lists, the codes and probabilities. rec carries id, publisher, title, published, text, stage_out, story;
    it is filled in place and returned. fewnerd / claims switch those two steps off; pre = {"fents": ..., "claims": ...} hands in what an earlier chain stage already computed (the same call on the same text, so the result is the same)."""
    pre = pre or {}; cstats = {}; units, topic, place = units_for(ch, line, text, cstats); _t = time.perf_counter(); ents = lg_ents(text); rec["lg_ms"] = round((time.perf_counter() - _t) * 1000, 1); st = {s["name"]: s for s in line["stages"]}
    # place units and capability units from the stage outputs (full keeps the items)
    plf = (full.get("place_linker") or {}).get("items") or []; sstarts = [a for a, b in ch.SG.scan(text, "2026-01-01T00:00:00Z")[1]]
    for it in plf:
        if it.get("country"): units.append({"type": "place", "subject": it["text"], "predicate": None, "value": it["country"], "sentence": max(0, bisect.bisect_right(sstarts, it["span"][0]) - 1), "id": it["country"], "spans": [{"role": "place", "s": it["span"][0], "e": it["span"][1]}], "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place})
    cf = full.get("capability_list") or {}
    for tier in ("recurring", "candidate"):
        for pair in cf.get(tier) or []: units.append({"type": "capability", "spans": [], "subject": pair, "predicate": tier, "value": None, "sentence": None, "id": None, "topic_l1": topic["l1"], "topic_node": topic["node"], "place": place})
    tl = (st.get("topic_landing") or {}).get("out") or {}; top3 = [x[0] for x in (tl.get("top3") or [])]
    _sents = ch.SG.scan(text, "2026-01-01T00:00:00Z")[1]; rec["lg_new_units"] = apply_lg(units, text, ents, sstarts, _sents, topic, place); rec["lg_label"] = LG_LABEL
    if fewnerd: _t = time.perf_counter(); _fe = pre["fents"] if "fents" in pre else fn_ents(text); rec["fn_new_units"] = apply_fewnerd(units, text, _fe, sstarts, _sents, topic, place); rec["fn_ms"] = round((time.perf_counter() - _t) * 1000, 1); rec["fn_label"] = FN_LABEL   # Few-NERD v1 (T158-N4)
    _t = time.perf_counter(); _d = (line["published"] or "")[:10]; _ds = (_d + "T00:00:00Z") if re.match(r"^\d{4}-\d{2}-\d{2}$", _d) else "2026-01-01T00:00:00Z"; spots_all, sents_all = ch.SG.scan(text, _ds)
    if claims: claims_v1(units, text, sents_all, cstats, topic, place, claims=pre.get("claims")); rec["claims_v1_label"] = CLAIMS_V1_LABEL
    claims_v0(units, text, ents, sents_all, spots_all, cstats, topic, place); rec["claims_stats"] = cstats; rec["scan"] = {"label": "scan spots (scan_gate.scan, the call the scan_dates stage makes)", "spots": [list(x) for x in spots_all], "sents": [list(x) for x in sents_all]}
    rec["sentences"] = sentence_table(text, spots_all, sents_all, units); attach_heads(rec, text, sents_all); rec["items"] = extras(ch, text, full, spots_all, sents_all, line); rec["heads_unattached"] = heads_check(rec["stage_out"]); rec["claims_label"] = CLAIMS_LABEL; rec["extras_ms"] = round((time.perf_counter() - _t) * 1000, 1)
    l2 = (((line.get("journal") or {}).get("ids") or {}).get("topic") or {}).get("l2")
    codes = {"l2": l2, "l2_label": lab(ch, l2), "l1": topic["l1"], "l1_label": lab(ch, topic["l1"]), "node": topic["node"], "node_label": lab(ch, topic["node"]), "top3": [{"code": c, "label": lab(ch, c)} for c in top3]}
    ar = (st.get("area_function") or {}).get("out") or {}; cd = (st.get("condition") or {}).get("out") or {}; ps = (st.get("place_student") or {}).get("out") or {}; pk = (st.get("structure_pack") or {}).get("out") or {}
    p = {"rerank_p": topic["p"], "landing_p": tl.get("landing_p"), "topic_decision": topic["decision"], "area_top": ar.get("topic"), "story_type_top": ar.get("story_type"), "condition_present_conf": cd.get("present_conf"), "condition_present": cd.get("present"), "condition_which": cd.get("which"), "condition_direction": cd.get("direction"), "place_student_top": ps.get("top"), "place_student_answered": ps.get("answered"), "place_linker_top": (st.get("place_linker") or {}).get("out", {}).get("top_countries")}
    rec.update(units=units, codes=codes, p=p, decider=line["decider"], stages=[{"name": s["name"], "state": s["state"], "n": s["n"], "ms": s["ms"]} for s in line["stages"]], gaps=line.get("gaps"))
    return rec
def mention_spans(u):
    """the surface spans one unit contributes to its key's mention list: the unit's own span (the verb span for a triple)."""
    sp = [x for x in (u.get("spans") or []) if x["role"] == "verb"] if u["type"] == "triple" else (u.get("spans") or [])[:1]
    return {(x["s"], x["e"]) for x in sp}
def merge_units(rec, batch=None, G=None, ch=None):
    """filter v0 first (dropped units carry a reason code and are not merged); then merge rule v0: key = (unit type, entity identity: country ISO2 for places and demonyms, else the normalised name with the possessive folded); the topic node is a property of the node; one evidence per article per key."""
    seen = {}; out = []
    claims = []
    for u in rec["units"]:
        u["filter"] = {"label": FILTER_LABEL, "kept": True, "reason": None}
        if u["type"] == "partial_claim": u["merge"] = {"result": "NO KEY", "why": "partial claim: shown, never merged"}; out.append(u); claims.append((u, "partial")); continue
        why = filter_v0(u)
        isc = u["type"] in ("triple", "attribution")
        if why: u["filter"].update(kept=False, reason=why); u["merge"] = {"result": "DROPPED"}; out.append(u); claims.append((u, "dropped: " + why)) if isc else None; continue
        subj = (u["id"] or "") if u["type"] == "place" else identity(u["subject"], ch); node = u["topic_node"] or u["topic_l1"]
        if u["type"] == "place" and subj: subj = "iso:" + subj
        if u["type"] == "triple" and norm(u["value"]): u["object_key"] = " | ".join(("object", identity(u["value"], ch)))
        if not subj: u["merge"] = {"result": "NO KEY", "why": "no subject"}; out.append(u); continue
        key = (u["type"], subj); u["key"] = " | ".join(key)
        if key in seen: seen[key]["_m"].update(mention_spans(u)); claims.append((u, "folded")) if isc else None; u["folded_into"] = seen[key]["key"]; continue
        seen[key] = u; u["_m"] = set(mention_spans(u)); prior = set(G.nodes[key]["arts"]) if key in G.nodes else set(); u["merge"] = G.merge(key, rec["id"], rec["publisher"], "%s %s" % (u["type"], u["subject"]), node)
        if u["merge"]["result"] == "+EVIDENCE": u["merge"]["scope"] = "same story" if (batch and prior & batch) else "other"
        if isc: claims.append((u, "merged"))
        out.append(u)
    for u in out:   # every mention of the key in this article; counting (evidence) stays one per key per article
        if "_m" in u: u["mentions"] = [{"s": a, "e": b} for a, b in sorted(u.pop("_m"))]; u["n_mentions"] = len(u["mentions"])
    rec["units"] = out
    cs = rec.get("claims_stats") or {}; ct = collections.Counter(f for _, f in claims); pk = ct["partial"]; kept_c = sum(v for k, v in ct.items() if k in ("merged", "folded"))
    rec["claims"] = [{"type": u["type"], "subject": u.get("subject"), "predicate": u.get("predicate"), "value": u.get("value"), "missing": u.get("missing"), "sentence": u.get("sentence"), "sent_text": u.get("sent_text"), "spans": u.get("spans"), "resolved_from": u.get("resolved_from"), "ner": u.get("ner"), "fate": f, "node": (u.get("key") if f in ("merged",) else u.get("folded_into")), "merge": (u.get("merge") or {}).get("result")} for u, f in claims]
    rec["claims_funnel"] = {"label": CLAIMS_LABEL, "found": cs.get("found", 0), "both_sides": sum(1 for u in out if u["type"] == "triple") + sum(1 for u, f in claims if u["type"] == "triple" and f == "folded"), "partial": pk, "unusable": cs.get("unusable", 0), "pronoun_subjects": cs.get("pronoun_subjects", 0), "resolved": cs.get("resolved", 0),
                            "attribution_spots": cs.get("attribution_spots", 0), "attribution": cs.get("attribution", 0), "dropped": sum(v for k, v in ct.items() if k.startswith("dropped")), "dropped_reasons": dict(collections.Counter(f[9:] for _, f in claims if f.startswith("dropped"))), "kept": kept_c, "folded": ct["folded"], "merged": ct["merged"], "shown": kept_c + pk}
