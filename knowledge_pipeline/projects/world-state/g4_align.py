"""G4/G5 v1, unmeasured. Knowledge alignment (playbook sections 1, 2, 8, 18) on top of raw-units: observation -> entity identity -> assertion -> vertical (IPTC) and horizontal links.
Shared importable module (T172, owner yes L2870; code moved verbatim from simulation/g4-align.py, which is now a loader shim): the page (simulation/raw-units.py) and the live-trace chain (live_trace_v4.py) import this one file. Nothing in the decider / lean is edited. CPU only, no hosted calls.
Three additions for the chain, each defaulting to the old behaviour: align(..., contradictions=False) skips the contradiction edges; rec["g4"]["contradictions_ms"] times them; a state object may carry g4_durable / g4_dir to place or disable the store (the page uses the env G4_DURABLE / G4_DURABLE_DIR as before).
One store (Store) holds everything; each edge carries `via` (its relation source) and evidence spans, so the three views on the page (flat table, relation map, hierarchical graph) are derived from the same data.
  Observation: every kept unit stays an observation tied to its span (rec["units"], untouched). Bare numbers and dates are never graph nodes: they attach to assertions as attributes.
  Entity identity: in-article alias clusters (surname, acronym incl. article country, head-noun containment, pronoun-resolved mentions, demonyms and places -> iso:XX), across articles an exact name/alias match in the same type (same name in another type = "unsure" flag).
  Assertion key: (subject identity, predicate lemma, object identity or normalised object head). Evidence is counted per independent publisher; journal copies/republished items do not count.
  Vertical: iptc_path + how in {exact, wordnet, sentence, article-topic}; places also get a geo path country -> region.
  Horizontal via: hierarchy, assertion, attribution, causal cue v0, co-occurrence, temporal, spatial, change, capability, similar v0 (unmeasured), story."""
import re, bisect, time, hashlib, collections, itertools, datetime, os, json, pathlib
LABEL = "G4/G5 v1, unmeasured"
IDENT_RULES = os.environ.get("G4_IDENT_RULES", "v2")   # T174 identity fix (item IDENTITY, wave 1). "v2" (default) = the four merge guards below, tagged "ident-v2"; G4_IDENT_RULES=v1 restores the earlier merges exactly.
PLACE_MODS = set("the of republic people's peoples kingdom state states federal democratic islamic united north south east west northern southern eastern western central new greater upper lower".split())
DEFAULT_DIR = str(pathlib.Path(__file__).resolve().parent.parent.parent / "runs" / "g4")   # knowledge_pipeline/runs/g4: where simulation/g4-align.py put it (simulation/../runs/g4)
TITLES = {"dr", "mr", "mrs", "ms", "miss", "prof", "professor", "sir", "dame", "mp", "senator", "president", "minister", "mayor", "judge"}
SKIPW = {"of", "the", "and", "for", "in", "on"}
GENERIC = set("what who that which it this he she they i we you one some there things thing lot way time times part none other others number-of me him her them us who whom place kind type day week month year list change article request end".split())
NERMAP = {"PERSON": "person", "ORG": "org", "GPE": "place", "LOC": "place", "FAC": "place", "NORP": "group", "LANGUAGE": "group", "PRODUCT": "product", "WORK_OF_ART": "product", "EVENT": "event", "LAW": "law"}
# --- N4: Few-NERD v1 fine types -> G4 types (the type determines the coarse type, so alias merges stay within it) ---
def fn_type(fine):
    c = fine.split("-")[0]
    return {"person": "person", "organization": "org", "location": "place", "building": "facility", "event": "event", "product": "product", "art": "work"}.get(c) or (
        "disease" if fine == "other-disease" else "substance" if fine in ("other-medical", "other-chemicalthing", "other-biologything") else "group" if fine == "other-language" else "law" if fine == "other-law" else "other")
HEALTH_PATH = {"disease": "health > disease and condition", "substance": "health > health treatment and procedure"}   # fallback when the term is not placed exactly
# --- end N4 ---
NONENT = {"DATE", "TIME", "CARDINAL", "MONEY", "PERCENT", "QUANTITY", "ORDINAL"}
PRON_P = {"he", "she"}
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
MON3 = {k[:3]: v for k, v in MONTHS.items()}
WDAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
UP = set("rise jump grow climb surge soar increase hike lift rocket".split()); DOWN = set("fall drop decline plunge slump decrease slide dip shrink tumble".split())
FWD = ["led to", "leads to", "lead to", "leading to", "as a result", "resulting in", "results in", "result in", "so that", "which means"]
BACK = ["because of", "because", "due to", "driven by", "caused by", "thanks to", "owing to", "as a consequence of", "after"]
CUE_RX = re.compile(r"\b(" + "|".join(re.escape(c) for c in sorted(FWD + BACK, key=lambda x: -len(x))) + r")\b", re.I)
VIAS = ["hierarchy", "assertion", "attribution", "causal cue v0", "co-occurrence", "temporal", "spatial", "change", "capability", "similar v0, unmeasured", "story"]
def nrm(s):
    s = re.sub(r"['’]s?\b", "", str(s or "")).lower(); s = re.sub(r"[^\w\s]", " ", s); w = [x for x in s.split() if x]
    while w and (w[0] in TITLES or w[0] == "the"): w = w[1:]
    return " ".join(w)
def stem(w):
    if len(w) > 4 and w.endswith("ies"): return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")): return w[:-1]
    return w
def cnorm(phrase):
    w = nrm(phrase).split()
    if w: w[-1] = stem(w[-1])
    return " ".join(w)
def initials(toks): return "".join(t[0] for t in toks if t not in SKIPW)
def h(s): return hashlib.md5(s.encode()).hexdigest()[:10]
def mid(a, b): return (a + b) // 2
class Store:
    def __init__(self):
        self.ent = {}; self.alias = {}; self.asr = {}; self.edges = {}; self.nodes = {}; self.arts = {}; self.roots = {}; self.vec = []; self.ms = []; self.curve = []
        self.canon_ent = collections.defaultdict(set)   # normalised canonical name -> entity ids (all types), for the "same name, unsure" flag
    # --- durable store (plan step 1, add-only): append-only JSONL, one line per article holding the entries that changed; load replays the lines in order ---
    SECTIONS = ("ent", "asr", "edges", "nodes", "arts", "roots", "alias", "canon_ent")
    @staticmethod
    def _enc(v):
        if isinstance(v, dict): return {"__d": [[Store._enc(k), Store._enc(x)] for k, x in v.items()]}
        if isinstance(v, (set, frozenset)): return {"__s": sorted((Store._enc(x) for x in v), key=lambda y: json.dumps(y, sort_keys=True))}
        if isinstance(v, tuple): return {"__t": [Store._enc(x) for x in v]}
        if isinstance(v, list): return [Store._enc(x) for x in v]
        if hasattr(v, "tolist") and hasattr(v, "dtype"): return {"__a": v.tolist(), "dtype": str(v.dtype)}
        if isinstance(v, float) and v != v: return {"__nan": 1}
        return v
    @staticmethod
    def _dec(v):
        if isinstance(v, list): return [Store._dec(x) for x in v]
        if isinstance(v, dict):
            if "__d" in v: return {Store._dec(k): Store._dec(x) for k, x in v["__d"]}
            if "__s" in v: return {Store._dec(x) for x in v["__s"]}
            if "__t" in v: return tuple(Store._dec(x) for x in v["__t"])
            if "__a" in v:
                import numpy as np; return np.array(v["__a"], dtype=v["dtype"])
            if "__nan" in v: return float("nan")
        return v
    def attach(self, path):
        """attach a log file: load it when it exists, and save after every article from here on"""
        self.path = path; self._h = {}; self._vn = 0; self.loaded_lines = 0
        if os.path.exists(path):
            for l in open(path, encoding="utf-8"):
                if not l.strip(): continue
                r = json.loads(l); self.loaded_lines += 1
                for sec in self.SECTIONS:
                    tgt = getattr(self, sec)
                    for kj, vj in r.get(sec, []):
                        k = self._dec(kj); v = self._dec(vj)
                        if sec == "canon_ent": v = set(v); tgt[k] = v
                        else: tgt[k] = v
                        self._h[(sec, json.dumps(kj, sort_keys=True))] = hashlib.md5(json.dumps(vj, sort_keys=True).encode()).hexdigest()
                for x in r.get("vec", []): self.vec.append(self._dec(x))
                if r.get("curve"): self.curve.append(r["curve"])
            self._vn = len(self.vec)
        return self
    def save_article(self, art):
        """append one line with every entry that changed since the last save (new or edited); an unchanged store appends an empty-delta line only when the article is new"""
        if not getattr(self, "path", None): return
        line = {"art": art}; changed = 0
        for sec in self.SECTIONS:
            out = []
            for k, v in getattr(self, sec).items():
                kj = self._enc(k); vj = self._enc(v); hk = (sec, json.dumps(kj, sort_keys=True)); hv = hashlib.md5(json.dumps(vj, sort_keys=True).encode()).hexdigest()
                if self._h.get(hk) != hv: self._h[hk] = hv; out.append([kj, vj])
            if out: line[sec] = sorted(out, key=lambda x: json.dumps(x[0], sort_keys=True)); changed += len(out)
        if len(self.vec) > self._vn: line["vec"] = [self._enc(x) for x in self.vec[self._vn:]]; self._vn = len(self.vec)
        if self.curve: line["curve"] = self.curve[-1]
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f: f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
    def digest(self):
        """sha256 of the whole store content (no timings), the same for two replays of the same input"""
        body = {sec: sorted([json.dumps(self._enc(k), sort_keys=True), json.dumps(self._enc(v), sort_keys=True)] for k, v in getattr(self, sec).items()) for sec in self.SECTIONS}
        body["vec"] = [self._enc(x) for x in self.vec]; body["curve"] = self.curve
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    def counts(self): return {"entities": len(self.ent), "assertions": len(self.asr), "edges": len(self.edges), "articles": len(self.arts), "nodes": len(self.nodes), "vec": len(self.vec)}
    def stats(self):
        E = list(self.ent.values()); A = list(self.asr.values())
        how = lambda L: dict(collections.Counter((x.get("iptc") or {}).get("how") or "none" for x in L))
        withp = lambda L: sum(1 for x in L if (x.get("iptc") or {}).get("path"))
        ne = collections.Counter(e["via_edge"] for e in self.edges.values()) if False else collections.Counter(e["via"] for e in self.edges.values())
        return {"entities": len(E), "entities_with_iptc": withp(E), "entities_how": how(E), "assertions": len(A), "assertions_with_iptc": withp(A), "assertions_how": how(A), "edges_by_via": dict(ne), "articles": len(self.arts)}
def _span(s, e): return {"s": int(s), "e": int(e)}
def ctry_name(ch, iso):
    if not hasattr(ch, "_g4_inv"):
        inv = {}
        for k, v in ch.EX.ctry.items():
            if v not in inv or (len(k) < len(inv[v]) and k[0].isupper()): inv[v] = k
        ch._g4_inv = inv
    return ch._g4_inv.get(iso) or iso
NUMW = {w: i + 1 for i, w in enumerate("one two three four five six seven eight nine ten eleven twelve".split())}; NUMW.update(hundred=100, hundreds=100, thousand=1000, million=1e6, billion=1e9)
def parse_amount(u):
    v = str(u.get("value") or ""); m = re.search(r"-?\d[\d,]*\.?\d*", v); num = None
    if m:
        try: num = float(m.group(0).replace(",", ""))
        except Exception: pass
    else:
        for w in re.findall(r"[a-z]+", v.lower()):
            if w in NUMW: num = float(NUMW[w]); break
        if num is None: return None
    unit = u.get("unit")
    if "per cent" in v or "%" in v or "percent" in v: unit = "%"
    elif u.get("subject") and not unit: unit = u["subject"]
    return {"text": v, "value": num, "unit": unit}
def resolve_date(text, pub):
    """-> (iso or None, period or None, label). Month names alone take the latest such month not after the publish month (published 2026-11-20: October -> 2026-10)."""
    t = str(text or "").strip().lower(); y, mo = (int(pub[:4]), int(pub[5:7])) if pub and re.match(r"^\d{4}-\d{2}", pub) else (None, None)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", t)
    if m: return t, t[:7], datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%d %b %Y")
    m = re.match(r"^(.*?) relative to (\d{4}-\d{2}-\d{2})$", t)
    if m:
        w, base = m.group(1), m.group(2); d = datetime.date.fromisoformat(base)
        if w == "last year": return None, str(d.year - 1), "%d" % (d.year - 1)
        if w == "next month": n = d.month % 12 + 1; yy = d.year + (1 if d.month == 12 else 0); return None, "%d-%02d" % (yy, n), datetime.date(yy, n, 1).strftime("%b %Y")
        if w == "this week": iso = d.isocalendar(); return None, "%d-W%02d" % (iso[0], iso[1]), "week of " + base
        if w == "last month": n = (d.month - 2) % 12 + 1; yy = d.year - (1 if d.month == 1 else 0); return None, "%d-%02d" % (yy, n), datetime.date(yy, n, 1).strftime("%b %Y")
        return None, None, w
    if re.match(r"^\d{4}$", t): return None, t, t
    if t in MONTHS or t[:3] in MON3 and len(t) <= 9 and t in MONTHS:
        n = MONTHS[t]
        if y: yy = y if n <= mo else y - 1; return None, "%d-%02d" % (yy, n), datetime.date(yy, n, 1).strftime("%b %Y")
    return None, None, t
# --- contradictions (plan step 7, add-only; nothing above changed except the three marked lines in align) ---
# Rule: the same assertion key (subject + predicate + object identity) read with opposite polarity (positive vs negative evidence on one assertion), or two assertions with the same subject and object whose predicates are opposite directions (rise / fall, canonical since the change bundle),
# with evidence inside a time window, adds one edge via "contradiction" (label "contradicts"). Both assertions are kept; the edge carries the sources (article, publisher, independent) of each side. A polarity edge joins the two readings of one assertion, written "A:x#+" and "A:x#-".
# Not a contradiction: a different place, different resolved dates, or a prediction against an assertion (they are not about the same thing). No model, no file access; Store -> edges.
WINDOW_DAYS = 7; OPPOSITE = {"rise": "fall", "fall": "rise"}
def _day(S, art):
    d = (S.arts.get(art) or {}).get("day")
    try: return datetime.date.fromisoformat(d) if d else None
    except ValueError: return None
def _pair_ok(S, e1, e2, W):
    d1, d2 = _day(S, e1["art"]), _day(S, e2["art"])   # a day we do not know counts as inside the window (flagged in the note)
    if d1 and d2 and abs((d1 - d2).days) > W: return False
    a1, a2 = e1["attrs"], e2["attrs"]
    if a1.get("place") and a2.get("place") and a1["place"] != a2["place"]: return False
    t1 = {t.get("iso") or t.get("period") for t in a1.get("time", []) if t.get("iso") or t.get("period")}; t2 = {t.get("iso") or t.get("period") for t in a2.get("time", []) if t.get("iso") or t.get("period")}
    if t1 and t2 and not (t1 & t2): return False
    return (a1.get("modality") == "predicted") == (a2.get("modality") == "predicted")
def _sources(evs): return sorted(({"art": e["art"], "pub": e["pub"], "independent": e["independent"]} for e in evs), key=lambda x: x["art"])
def contradict_edges(S, aids, art, W=WINDOW_DAYS):
    """-> [edge dict] for the assertions in aids (claims only), against everything in the store. Pure: the caller merges them. Same input, same edges (sorted)."""
    out = {}; idx = None
    def put(a_, b_, kind, ea, eb, note):
        a_, b_, ea, eb = (a_, b_, ea, eb) if a_ <= b_ else (b_, a_, eb, ea)
        out[("contradiction", a_, b_, "contradicts")] = {"via": "contradiction", "a": a_, "b": b_, "label": "contradicts", "w": 1, "art": art, "spans": [], "sent": None, "note": note, "kind": kind, "window_days": W, "sources": {"a": _sources(ea), "b": _sources(eb)}}
    for aid in sorted(aids):
        r = S.asr.get(aid)
        if not r or r.get("kind") != "claim": continue
        pos = [e for e in r["evid"] if e["attrs"].get("polarity") != "negative"]; neg = [e for e in r["evid"] if e["attrs"].get("polarity") == "negative"]
        pr = [(p, n) for p in pos for n in neg if _pair_ok(S, p, n, W)]
        if pr: put(aid + "#+", aid + "#-", "polarity", list({id(p): p for p, _ in pr}.values()), list({id(n): n for _, n in pr}.values()), "same assertion read as true and as negated, inside %d days" % W)
        if r["pred"] in OPPOSITE:
            if idx is None:
                idx = collections.defaultdict(list)
                for y in S.asr.values():
                    if y.get("kind") == "claim": idx[(y["subj"], y["obj"], y["obj_text"])].append(y)
            for y in idx.get((r["subj"], r["obj"], r["obj_text"]), ()):
                if y["pred"] != OPPOSITE[r["pred"]]: continue
                px = [e for e in r["evid"] if e["attrs"].get("polarity") != "negative"]; py = [e for e in y["evid"] if e["attrs"].get("polarity") != "negative"]   # "did not fall" is not "rose"
                pr = [(p, q) for p in px for q in py if _pair_ok(S, p, q, W)]
                if pr: put(aid, y["id"], "direction", list({id(p): p for p, _ in pr}.values()), list({id(q): q for _, q in pr}.values()), "%s against %s, same subject and object, inside %d days" % (r["pred"], y["pred"], W))
    return [out[k] for k in sorted(out)]
def contradiction_counts(S):
    """C per assertion and per entity, derived from the contradiction edges in the store (nothing extra is stored): {"asr": {aid: n}, "ent": {eid: n}}. An entity's C counts each edge once over the assertions it is the subject or object of."""
    asr = collections.Counter(); ent = collections.defaultdict(set)
    for k, e in S.edges.items():
        if e["via"] != "contradiction": continue
        for x in {e["a"].split("#")[0], e["b"].split("#")[0]}:
            asr[x] += 1; r = S.asr.get(x)
            if r:
                for q in (r["subj"], r["obj"]):
                    if q: ent[q].add(k)
    return {"asr": dict(asr), "ent": {q: len(v) for q, v in ent.items()}}
# --- end contradictions ---
class Art:
    pass
def sent_index(sents):
    st = [a for a, b in sents]; return lambda pos: max(0, bisect.bisect_right(st, pos) - 1)
def align(rec, G, ch, contradictions=True):
    """add-only: reads rec (after merge_units), updates the store on G, sets rec["g4"]. Returns nothing. contradictions=False (the chain, flag off) leaves the contradiction edges out."""
    t0 = time.perf_counter(); S = getattr(G, "g4", None)
    if S is None:
        S = G.g4 = Store(); dur = getattr(G, "g4_durable", None)   # None: the env decides (the page); True / False: the chain says
        if (os.environ.get("G4_DURABLE", "1") != "0") if dur is None else dur:   # durable store: reload what an earlier process saved; G4_DURABLE=0 keeps the old in-memory behaviour
            S.attach(os.path.join(getattr(G, "g4_dir", None) or os.environ.get("G4_DURABLE_DIR") or DEFAULT_DIR, "store.jsonl"))
            if hasattr(G, "pulled"): G.pulled |= set(S.arts)
    if rec.get("state") != "traced": return
    text = rec["text"]; sents = rec["scan"]["sents"]; sidx = sent_index(sents); art = rec["id"]; pub = rec["publisher"]; pk = ch.pack
    spots = rec["scan"]["spots"]; units = rec["units"]; pubd = (rec.get("published") or "")[:10]; codes = rec["codes"]; l1 = codes.get("l1")
    story = rec.get("story") or {}; kind = story.get("kind"); of = (story.get("of") or {}).get("id"); root = S.roots.get(of, of) if of else art; S.roots[art] = root
    independent = kind not in ("copy", "republished")
    S.arts[art] = {"publisher": pub, "title": rec["title"], "root": root, "independent": independent, "kind": kind, "day": pubd or None}   # day: the contradiction window needs it (plan step 7)
    sent_txt = lambda i: text[sents[i][0]:sents[i][1]].strip()[:300] if 0 <= i < len(sents) else ""
    # ---- article topic path, placed terms per sentence (in-topic majority) ----
    topic_q = codes.get("node") or codes.get("l1")
    tpath = (pk.path(topic_q) if topic_q in pk.node else None); tq = topic_q if tpath else None
    placed = (rec["items"].get("mapping") or {}).get("placed") or []; bysent = collections.defaultdict(list)
    for p in placed:
        if p[6] and p[5]: bysent[sidx(p[0])].append(p[5])
    def sent_path(sis):
        c = collections.Counter(p for si in sis for p in bysent.get(si, []))
        return c.most_common(1)[0][0] if c else None
    path_q = {}
    def qcode_of(path):
        if path not in path_q:
            q = None
            for k in pk.node:
                pass
            path_q[path] = None
        return path_q[path]
    pq = getattr(ch, "_g4_pq", None)
    if pq is None: pq = ch._g4_pq = {}
    def to_q(path):   # IPTC path string -> qcode (label chain match), cached on the chain
        if path in pq: return pq[path]
        last = path.split(" > ")[-1]; best = None
        for q in pk.node:
            if pk.lab(q) == last and pk.path(q) == path: best = q; break
        pq[path] = best; return best
    def mkiptc(path, how, why=None):
        if not path: return None
        q = to_q(path); ch_ = pk.chain(q) if q else []
        return {"path": path, "node": q, "domain": path.split(" > ")[0], "how": how, "why": why}
    topic_iptc = lambda: mkiptc(tpath, "article-topic", "the article's landing topic")
    # ---- mentions ----
    M = []   # {s,e,sent,surface,type,ner,pron}
    def addm(s, e, ty, ner, surf=None, pron=None, src=None, unit=None, fine=None):
        M.append({"s": s, "e": e, "sent": sidx(s), "surface": surf if surf is not None else text[s:e], "type": ty, "ner": ner, "pron": pron, "src": src, "fine": fine, "coarse": fine.split("-")[0] if fine else None})   # N4: fine/coarse from Few-NERD v1
    dates = []   # (s, e, text, value)
    inv_place = {}
    for u in units:
        if u.get("filter") and not u["filter"]["kept"]: continue
        sp = [(x["s"], x["e"]) for x in (u.get("mentions") or u.get("spans") or [])] if u["type"] in ("name", "place", "date") else []
        if u["type"] == "name":
            ner = u.get("ner") or "UNTYPED"
            if ner == "DATE" or ner == "TIME":
                for a, b in sp: dates.append((a, b, text[a:b], u["subject"]))
                continue
            if ner in NONENT: continue
            fine = u.get("ner_fine")   # N4: Few-NERD v1 type wins over lg (DATE/TIME/numbers above stay lg)
            for a, b in sp: addm(a, b, fn_type(fine) if fine else NERMAP.get(ner, "unk"), ner, src="name", fine=fine)
        elif u["type"] == "place" and u.get("value") and (u.get("ner_coarse") or "location") in ("location", "building"):   # N4: a place-linker hit that Few-NERD types as org/person/other is not a country mention (Hollywood the industry is not iso:US)
            for a, b in sp: addm(a, b, "place", "GPE", src="place"); M[-1]["iso"] = u["value"]
        elif u["type"] == "date":
            for a, b in sp: dates.append((a, b, text[a:b], u["subject"]))
    # place-lookup identity for GPE/NORP names (country names, aliases, demonyms)
    if not hasattr(pk, "_lk"): pk.lookup_places("", ch.EX)
    lk = pk._lk[0]
    for m in M:
        if IDENT_RULES == "v2" and m.get("iso") and m.get("src") == "place":   # ident-v2 (e): a place-linker span that ends in a country name or demonym but starts with non-place words is a name of something else (Alternative for Germany, MTN Uganda, Two Danish, Latin America): it keeps no iso and stays untyped
            _w = m["surface"].strip().split()
            if len(_w) > 1 and m["surface"].strip() not in lk and _w[-1] in lk and not all(x.lower() in PLACE_MODS for x in _w[:-1]): m.pop("iso"); m["type"] = "unk"
        if m.get("iso"): continue
        t = re.sub(r"['’]s$", "", m["surface"].strip()); t = re.sub(r"^(the|more|many|some|most|all|other|several|few) ", "", t, flags=re.I)
        hit = lk.get(t) if m["type"] in ("place", "group", "unk", "org") else None
        if m.get("fine") and m["fine"] != "location-GPE" and m["type"] != "group": hit = None   # N4: only a Few-NERD location-GPE name can become a country/place id (no org/building/location-other -> iso)
        if not hit and m["type"] == "place" and len(t.split()) > 1 and (IDENT_RULES != "v2" or all(w.lower() in PLACE_MODS for w in t.split()[:-1])): hit = lk.get(t.split()[-1])   # ident-v2 (b): the last-word fallback needs a place-modifier prefix (West Africa, Republic of Korea), not an org or title (MTN Uganda, Alternative for Germany)
        if hit and (m["type"] in ("place", "group") or t.isupper()): m["iso"] = hit[0]; m["type"] = "place"
    # typing fix: all-caps surface that WordNet knows as a common noun/concept is a CONCEPT (AI = artificial intelligence), not ORG/PERSON
    def wn_concept(surface):
        w = surface.strip()
        if not (w.isupper() and 2 <= len(w) <= 5 and w.isalpha()): return None
        offs = pk.lem.get(w.lower()) or []; cands = [o for o in offs if not pk.inst.get(o)]
        if not cands: return None
        best = None
        for o in cands:
            for x in pk.syn[o][0]:
                if len(x.split()) > 1 and "".join(t[0] for t in x.split()) == w.lower() and (best is None or (pk.idx.get(pk.norm(x)) and not pk.idx.get(pk.norm(best[1])))): best = (o, x)
        if best is None: best = (cands[0], pk.syn[cands[0]][0][0])
        return best
    for m in M:
        if m["type"] in ("org", "person", "unk") and not m.get("iso"):
            c = wn_concept(m["surface"])
            if c: m["type"] = "concept"; m["wn"] = c[1]; m["off"] = c[0]
    # junk: untyped names are kept only when capitalised mid-sentence multiword or all-caps-free proper tokens; sentence-initial single words are dropped
    keep = []
    for m in M:
        if m["type"] == "unk":
            w = m["surface"].split(); sa = sents[m["sent"]][0]
            if not (len(w) >= 2 and m["s"] > sa + 2 and all(x[:1].isupper() for x in w)): continue
        keep.append(m)
    M = sorted(keep, key=lambda m: m["s"])
    # ---- in-article clustering ----
    clusters = []   # {type, canon, surfaces:set, toks, ms:[m]}
    def new_cluster(m):
        c = {"type": m["type"], "coarse": m.get("coarse"), "fine": m.get("fine"), "canon": m["surface"].strip(), "iso": m.get("iso"), "wn": m.get("wn"), "off": m.get("off"), "surf": collections.Counter(), "ms": []}; clusters.append(c); return c
    def add_to(c, m):
        c["ms"].append(m); c["surf"][m["surface"].strip()] += 1; n = lambda x: len(nrm(x).split())
        if m["type"] != "concept" and not c.get("iso") and n(m["surface"]) > n(c["canon"]): c["canon"] = m["surface"].strip()
    art_iso = (rec["stage_out"].get("place_linker", {}).get("out", {}).get("country") or {}).get("iso2")
    ctoks = lambda c: nrm(c["canon"]).split()
    def find(m, strict):
        nm = nrm(m["surface"]); tk = nm.split()
        for c in clusters:
            if c["type"] != m["type"]: continue
            if m.get("coarse") and c.get("coarse") and m["coarse"] != c["coarse"]: continue   # N4: alias merges stay within the coarse type
            if m.get("iso") and c.get("iso") == m["iso"]: return c
            if IDENT_RULES == "v2" and m.get("iso") and c.get("iso") and m["iso"] != c["iso"]: continue   # ident-v2 (a): two different countries are never one entity (Singapore inside "Singapore and Brazil")
            if m["type"] == "concept" and c.get("wn") == m.get("wn"): return c
            ct = ctoks(c)
            if nm == " ".join(ct): return c
            if m["type"] == "person" and len(tk) == 1 and ct and tk[0] == ct[-1]: return c
            if m["type"] == "person" and len(ct) == 1 and tk and ct[0] == tk[-1]: c["canon"] = m["surface"].strip(); return c
            if m["type"] in ("org", "unk", "group", "product", "event", "law", "place"):   # N4: place added so NSW closes on New South Wales (same type only)
                j = " ".join(ct)
                if not m["surface"].strip().isupper() or len(tk) > 1:
                    if (" " + nm + " ") in (" " + j + " ") or (" " + j + " ") in (" " + nm + " "):
                        if IDENT_RULES == "v2" and m["type"] in ("product", "place"):   # ident-v2 (c): a product or place name joins a longer name of its type only as its head noun (Times in New York Times, Central Africa in West and Central Africa), never as its leading part (Windows in Windows Fax and Scan, Google in Google Mobile Services, West in West and Central Africa)
                            sh, lg = (tk, ct) if len(tk) < len(ct) else (ct, tk)
                            if sh != lg and lg[-len(sh):] != sh: continue
                            if sh != lg and m["type"] == "place" and not all(x in PLACE_MODS or x == "and" for x in lg[:len(lg) - len(sh)]): continue   # a place joins a longer place name only when the extra words are place modifiers (West and Central Africa), not a title or a party (Alternative for Germany, Prince and Princess of Wales)
                        return c
                else:   # acronym: initials of the canonical name, with or without "of"; the article's country may close it (Reserve Bank + Australia)
                    a = nm.replace(" ", ""); ini = initials(ct)
                    if a == ini: m["how_alias"] = "acronym"; return c
                    if art_iso and a == ini + ctry_name(ch, art_iso)[0].lower() and len(ini) >= 2: m["how_alias"] = "acronym+country"; return c
        return None
    for m in sorted(M, key=lambda m: (-len(nrm(m["surface"]).split()), m["s"])):
        if m["type"] == "org" and m["surface"].strip().isupper() and len(nrm(m["surface"]).split()) == 1 and not m.get("iso"): continue   # acronyms last
        c = find(m, True) or new_cluster(m); add_to(c, m)
    for m in M:
        if m["type"] == "org" and m["surface"].strip().isupper() and len(nrm(m["surface"]).split()) == 1 and not m.get("iso"):
            c = find(m, True) or new_cluster(m); add_to(c, m)
    for c in clusters: c["surf"] = c["surf"]
    mcl = {}
    for c in clusters:
        for m in c["ms"]: mcl[(m["s"], m["e"])] = c
    def cluster_at(s, e):
        if (s, e) in mcl: return mcl[(s, e)]
        for (a, b), c in mcl.items():
            if a <= s and e <= b: return c
        return None
    # ---- vertical: iptc for concepts (structure_pack placement) ----
    pcache = {}
    def place_concept(term_words, sis):
        """exact IPTC label wins; WordNet hops only when in the article's topic or the sentences have no in-topic placed term; else the sentence majority."""
        cands = []; ws = [w for w in term_words if w]
        order = ([" ".join(ws)] if len(ws) > 1 else []) + ws[::-1]
        for pos, t in enumerate(dict.fromkeys(order)):
            k = (t, l1)
            if k not in pcache:
                pcache[k] = [(hop, q, via, (l1 and pk.chain(q)[0] == l1)) for hop, q, via in pk.place(t)[:6]]
            for hop, q, via, it in pcache[k]:
                if hop == "exact" and pk.norm(pk.lab(q)) != t: hop = "side"; via = via + " (part of the label '%s')" % pk.lab(q)
                cands.append(({"exact": 0, "side": 1, "up": 2}[hop], not it, pos, q, hop, via, it))
        sp_ = sent_path(sis)
        ex = [c for c in cands if c[4] == "exact"]
        if ex: c = min(ex, key=lambda c: (c[1], c[2])); return mkiptc(pk.path(c[3]), "exact", "IPTC label %s" % c[5])
        wn = [c for c in cands if c[6] or not sp_]
        if wn: c = min(wn, key=lambda c: (c[1], c[0], c[2])); return mkiptc(pk.path(c[3]), "wordnet", c[5])
        if sp_: return mkiptc(sp_, "sentence", "majority in-topic placed term in its sentence(s)")
        return topic_iptc()
    # ---- entity records (in-article), identity across articles ----
    def type_path(t): return {"person": "person", "org": "organisation", "place": "place", "group": "group of people", "concept": "concept", "product": "product", "event": "event", "law": "law", "unk": "name", "facility": "facility", "work": "work of art", "substance": "substance", "disease": "disease", "other": "other name"}.get(t, t)
    E = {}   # cluster idx -> record
    def ent_for(c):
        if "_e" in c: return c["_e"]
        sis = sorted({m["sent"] for m in c["ms"]}); ty = c["type"]
        if c.get("iso"): canon = ctry_name(ch, c["iso"]); eid = "iso:" + c["iso"]; nmn = nrm(canon)
        else:
            canon = c["wn"] if c.get("wn") else c["canon"]; nmn = nrm(canon) if ty != "concept" else cnorm(canon); eid = ty + ":" + nmn
        al = {nrm(x) for x in c["surf"]}; al.discard(""); al.add(nmn)
        toks = nmn.split(); gen = set()   # ident-v2 (d): the initials generated from a name are registered, but never used as a key to find an existing entity (Daily Mail / Daily Mirror, UT Austin / United Airlines both generate one initial string)
        if ty == "org" and len(toks) >= 2: gen.add(initials(toks).lower())
        if ty == "org" and art_iso and len(toks) >= 2: gen.add((initials(toks) + ctry_name(ch, art_iso)[0]).lower())
        al |= gen
        if c.get("iso"): al.update(nrm(x) for x in c["surf"])
        # across articles: exact canonical name or alias in the same type (iso ids are exact by construction)
        hit = None
        if not c.get("iso"):
            if eid in S.ent: hit = eid
            else:
                cand = {S.alias[(ty, a)] for a in al if (ty, a) in S.alias and not (IDENT_RULES == "v2" and a in gen and a not in {nrm(x) for x in c["surf"]} and a != nmn)}
                if len(cand) == 1: hit = next(iter(cand))
        if hit: eid = hit
        r = S.ent.get(eid); new = r is None
        if new:
            r = S.ent[eid] = {"id": eid, "type": ty, "canon": canon, "aliases": {}, "arts": {}, "evid": [], "unsure": [], "sents": 0, "iptc": None, "geo": None, "kind_note": None}
        if len(nrm(canon).split()) > len(nrm(r["canon"]).split()) and ty not in ("place", "concept"): r["canon"] = canon
        for x, n in c["surf"].items(): r["aliases"][x] = r["aliases"].get(x, 0) + n
        for x in c.get("pron", []): r.setdefault("pron", []).append(x) if x not in r.get("pron", []) else None
        for a in al:
            if IDENT_RULES == "v2" and a in gen and S.alias.get((ty, a), eid) != eid: continue   # ident-v2 (d): a generated initials string already owned by another entity stays with it
            S.alias[(ty, a)] = eid
        # same name in another type: flag, never merge
        for oid in S.canon_ent.get(nmn, ()):
            if oid != eid and S.ent[oid]["type"] != ty and oid not in r["unsure"]: r["unsure"].append(oid); S.ent[oid]["unsure"].append(eid) if eid not in S.ent[oid]["unsure"] else None
        S.canon_ent[nmn].add(eid)
        prior = len(r["arts"]); priorp = len(set(r["arts"].values())); r["arts"].setdefault(art, pub)
        ms = c["ms"]; ev = {"art": art, "pub": pub, "title": rec["title"], "sent": sent_txt(sis[0]) if sis else "", "spans": [_span(m["s"], m["e"]) for m in ms[:12]], "independent": independent, "sents": sis}
        if not any(x["art"] == art for x in r["evid"]): r["evid"].append(ev)
        # vertical
        if c.get("iso"):
            if not r["geo"]:
                reg = (rec["stage_out"].get("place_linker", {}).get("out") or {}).get("region") if c["iso"] == art_iso else None
                wnp = pk.place_chain(canon, None); part = (wnp or {}).get("part_of") or []
                r["geo"] = [x for x in [canon, reg or (part[0] if part else None)] if x]
        if c.get("wn"): ip = place_concept(c["wn"].split(), sis); ip["via_type"] = "wordnet concept: %s" % c["wn"]
        else: ip = None
        if ty in ("substance", "disease"):   # N4: Few-NERD other-medical / chemicalthing / biologything / disease -> IPTC health: exact node when the term is placed, else the health fallback
            if not (r["iptc"] and r["iptc"]["how"] == "exact"):
                ipx = place_concept(nmn.split(), sis)
                if not (ipx and ipx["how"] == "exact"): ipx = mkiptc(HEALTH_PATH[ty], "type-map", "Few-NERD type %s maps to IPTC health" % (c.get("fine") or ty))
                else: ipx["via_type"] = "Few-NERD %s, term placed exactly" % (c.get("fine") or ty)
                r["iptc"] = ipx
        elif not (r["iptc"] and r["iptc"]["how"] in ("exact", "wordnet")):
            if ty == "concept" and ip is None: ip = place_concept(nmn.split(), sis)
            if ty != "concept" or ip is None:
                sp_ = sent_path(sis); ip = mkiptc(sp_, "sentence", "type %s + majority in-topic placed term of its sentences" % ty) if sp_ else topic_iptc()
            if ip and not (r["iptc"] and r["iptc"]["how"] in ("sentence", "article-topic") and ip["how"] == "article-topic"): r["iptc"] = ip
        c["_e"] = (eid, new, prior, priorp); c["_r"] = r; c["_sis"] = sis; return c["_e"]
    for c in clusters: ent_for(c)
    # ---- helpers on sentence geometry ----
    vspan = lambda u: next(((x["s"], x["e"]) for x in u["spans"] if x["role"] == "verb"), None)
    amts = []
    for u in units:
        if u["type"] == "amount" and u.get("spans") and (not u.get("filter") or u["filter"]["kept"]):
            for sp in (u.get("mentions") or u["spans"])[:20]: amts.append((sp["s"], sp["e"], parse_amount(u)))
    amts = [x for x in amts if x[2]]
    amts = sorted({(a, b): (a, b, d) for a, b, d in amts}.values(), key=lambda x: x[0]); amts = [x for i, x in enumerate(amts) if not any(y[0] <= x[0] and x[1] <= y[1] and y is not x for y in amts)]
    dts = sorted({(a, b): (a, b, t, v) for a, b, t, v in dates}.values(), key=lambda x: x[0])
    for a, b, t, v in dts: pass
    def cleandates():
        out = []
        for a, b, t, v in dts:
            iso, per, lab_ = resolve_date(v if v and v != t else t, pubd)
            if per is None and t.lower() in MONTHS: iso, per, lab_ = resolve_date(t, pubd)
            if t.lower() in WDAYS and per is None and iso is None: pass
            out.append({"s": a, "e": b, "text": t, "iso": iso, "period": per, "label": lab_, "sent": sidx(a)})
        return out
    DT = cleandates()
    bund = (rec["items"].get("bundles") or [])
    negs = [s for s in spots if s[2] == "negation"]; mods = [s for s in spots if s[2] == "modal"]
    places = [m for m in M if m.get("iso")]
    ents_by_sent = collections.defaultdict(list)
    for c in clusters:
        for m in c["ms"]: ents_by_sent[m["sent"]].append((m["s"], m["e"], c))
    # ---- attribution units -> speaker clusters (a concept can't speak; pronoun re-pointed to the nearest earlier PERSON) ----
    def person_before(pos, back=4):
        best = None
        for c in clusters:
            if c["type"] != "person": continue
            for m in c["ms"]:
                if m["e"] <= pos and sidx(pos) - m["sent"] <= back and (best is None or m["e"] > best[0]): best = (m["e"], c)
        return best[1] if best else None
    ATT = []
    for u in units:
        if u["type"] != "attribution": continue
        sp = {x["role"]: x for x in u["spans"]}; sc = cluster_at(sp["speaker"]["s"], sp["speaker"]["e"]); how = "lg speaker"
        if u.get("resolved_from"): how = "pronoun %s -> %s" % (u["resolved_from"]["pronoun"], u["resolved_from"]["to"])
        if u.get("resolved_from") and sc is not None and sc["type"] != "concept": sc.setdefault("pron", []).append("%s -> %s" % (u["resolved_from"]["pronoun"], u["resolved_from"]["to"]))
        if sc is None or sc["type"] == "concept":
            vs = sp["verb"]["s"]; sa = sents[u["sentence"]][0]; pm = list(re.finditer(r"\b(he|she)\s*$", text[sa:vs], flags=re.I)); sc2 = None
            if u.get("resolved_from") or sc is not None: sc2 = person_before(sa + (pm[-1].start() if pm else 0) if pm else sp["speaker"]["s"])
            if sc2: sc = sc2; how = "re-pointed to the nearest earlier person (a concept cannot speak)"
            elif sc is not None and sc["type"] == "concept": continue
        if sc is not None and sc["type"] == "org" and re.search(r"\b(I|me|my|we|our|I'm|I've)\b", str(u["value"])):   # an org does not speak in the first person
            sc2 = person_before(sp["verb"]["s"])
            if sc2: sc = sc2; how = "first-person quote: re-pointed from an org to the nearest earlier person"
        if sc is None: continue
        ATT.append({"u": u, "c": sc, "clause": sp.get("clause"), "verb": sp["verb"], "how": how, "sent": u["sentence"]})
    # ---- assertions ----
    A = []   # in-article assertion dicts
    CUR_PRED = [None]
    def np_before(a, b, sa):
        """noun phrase ending at [a,b): up to 2 preceding lowercase non-stop alphabetic words (unemployment rate, mortgage repayments)."""
        i = a; words = []
        while len(words) < 2:
            m = re.search(r"([A-Za-z][A-Za-z\-]+)\s+$", text[sa:i])
            if not m or text[sa + m.start(1)] .isupper(): break
            w = m.group(1)
            if w.lower() in ch_stop(ch) or w.lower() in TITLES or (CUR_PRED[0] and w.lower().startswith(CUR_PRED[0][:4])): break
            words.insert(0, w.lower()); i = sa + m.start(1)
        return words, i
    def locate(word, sa, sb, a, b, before):
        pat = re.compile(r"\b" + re.escape(word) + r"s?\b", re.I)
        ms = [m for m in pat.finditer(text, sa, sb)]
        if not ms: return None
        if before: c_ = [m for m in ms if m.end() <= a]; return (c_[-1] if c_ else ms[0])
        c_ = [m for m in ms if m.start() >= b]; return (c_[0] if c_ else ms[-1])
    def role_entity(word, sa, sb, a, b, before, si):
        """-> dict(kind=entity|attr|none, cluster/concept words, span) for a triple subject/object string."""
        w = (word or "").strip(); lw = w.lower()
        if not w or lw in GENERIC: return None
        if re.fullmatch(r"[\d.,]+", lw) or lw in ("cent", "percent", "%", "years", "year", "months", "month", "weeks", "days", "hours", "times", "dollars", "mark"): return {"kind": "num"}
        if lw in MONTHS or lw in WDAYS: return {"kind": "date", "text": w}
        m = locate(w, sa, sb, a, b, before)
        if m is None: return {"kind": "concept", "words": [cnorm(w)], "span": None}
        s, e = m.start(), m.end()
        for (x, y, c) in ents_by_sent.get(si, []):   # a named mention that contains or ends with the head
            if x <= s and e <= y and c["type"] != "concept": return {"kind": "entity", "c": c, "span": (x, y)}
            if c["type"] in ("person", "org", "place", "unk") and x <= s and e <= y: return {"kind": "entity", "c": c, "span": (x, y)}
        for (x, y, c) in ents_by_sent.get(si, []):
            if y == s - 0 or (y <= s and s - y <= 1): pass
        c = cluster_at(s, e)
        if c is not None: return {"kind": "entity", "c": c, "span": (s, e)}
        words, i0 = np_before(s, e, sa)
        if text[max(sa, i0 - 4):i0].lower() == "the ":   # definite anaphora: 'the central bank' -> the one org in the article whose last token is that head noun
            oc = [c for c in clusters if c["type"] == "org" and ctoks(c) and ctoks(c)[-1] == stem(w.lower())]
            if len(oc) == 1: oc[0].setdefault("pron", []).append("the %s -> %s (definite, head noun)" % (" ".join(words + [w.lower()]), oc[0]["canon"])); return {"kind": "entity", "c": oc[0], "span": (i0, e)}
        if lw == "number":
            mm = re.match(r"\s+of\s+((?:[a-z]+\s+){0,1}[A-Za-z]+)", text[e:sb]);
            if mm: return {"kind": "concept", "words": ["number", "of"] + [x.lower() for x in mm.group(1).split()], "span": (i0, e + mm.end())}
        # a demonym in the phrase or the head itself (Australians) -> its place
        for (x, y, c) in ents_by_sent.get(si, []):
            if x >= i0 and y <= e and c.get("iso"): return {"kind": "entity", "c": c, "span": (x, y)}
        return {"kind": "concept", "words": words + [cnorm(w)], "span": (i0, e)}
    for u in units:
        if u["type"] != "triple" or (u.get("filter") and not u["filter"]["kept"] and not (u["filter"]["reason"] == "pronoun" and str(u["subject"]).strip().lower() in PRON_P)): continue
        si = u["sentence"]; v = vspan(u)
        if si is None or v is None: continue
        sa, sb = sents[si]; subj = str(u["subject"]).strip(); res = None; CUR_PRED[0] = str(u["predicate"]).lower()
        if subj.lower() in PRON_P and not u.get("resolved_from"):   # pronoun resolver v1: he/she -> nearest earlier PERSON within 4 sentences
            pc = person_before(v[0]);
            if pc: res = {"kind": "entity", "c": pc, "span": None, "pron": subj}; pc.setdefault("pron", []).append("%s -> %s (g4 resolver v1, within 4 sentences)" % (subj, pc["canon"]))
        elif u.get("resolved_from"):
            r0 = u["resolved_from"]; c0 = cluster_at(r0["span"]["s"], r0["span"]["e"])
            if c0 is not None and c0["type"] == "concept":
                pm = list(re.finditer(r"\b(he|she|they|it)\b", text[sa:v[0]], flags=re.I)); c1 = person_before(sa + pm[-1].start()) if pm else None
                if c1: res = {"kind": "entity", "c": c1, "span": None, "pron": u["subject_surface"]}
                else: continue
            elif c0 is not None: res = {"kind": "entity", "c": c0, "span": None, "pron": u.get("subject_surface")}
        if res is None: res = role_entity(subj, sa, sb, v[0], v[1], True, si)
        if not res or res["kind"] != "entity" and res["kind"] != "concept": continue
        ob = role_entity(str(u["value"]), sa, sb, v[0], v[1], False, si)
        A.append({"u": u, "si": si, "v": v, "subj": res, "obj": ob, "pred": str(u["predicate"]).lower()})
    # ownership of amounts / dates: those after the assertion's verb and before the next triple verb in the sentence
    by_sent_v = collections.defaultdict(list)
    for a in A: by_sent_v[a["si"]].append(a["v"][0])
    out_ents = {}; out_asr = {}; EDG = []
    def ref_ent(role):   # -> entity id, or concept entity id (created lazily)
        if role is None: return None
        if role["kind"] == "entity": return role["c"]["_e"][0]
        if role["kind"] == "concept":
            words = role["words"]; k = cnorm(" ".join(words)); eid = "concept:" + k
            r = S.ent.get(eid); sis = [role.get("si", 0)]
            if r is None:
                r = S.ent[eid] = {"id": eid, "type": "concept", "canon": k, "aliases": {}, "arts": {}, "evid": [], "unsure": [], "iptc": place_concept(k.split(), role.get("sis") or []), "geo": None}
                S.alias[("concept", k)] = eid
            r["aliases"][" ".join(words)] = r["aliases"].get(" ".join(words), 0) + 1; r["arts"].setdefault(art, pub)
            if not any(x["art"] == art for x in r["evid"]): r["evid"].append({"art": art, "pub": pub, "title": rec["title"], "sent": sent_txt(role.get("si", 0)), "spans": [_span(*role["span"])] if role.get("span") else [], "independent": independent, "sents": [role.get("si", 0)]})
            if not hasattr(role, "x"): pass
            return eid
    for a in A:
        for k in ("subj", "obj"):
            if a[k] and a[k]["kind"] == "concept": a[k]["si"] = a["si"]; a[k]["sis"] = [a["si"]]
    # canonical predicate and direction from change bundles (the bundle on the verb token, else the only bundle in the sentence)
    def bundle_for(a):
        v = a["v"]; sb_ = [b for b in bund if b["span"][0] < v[1] and v[0] < b["span"][1]]
        if sb_: return sb_[0], "on the verb"
        return None, None
    totals = collections.Counter()
    for a in A:
        u = a["u"]; si = a["si"]; v = a["v"]; sa, sb = sents[si]
        sid = ref_ent(a["subj"]); oid = ref_ent(a["obj"]) if a["obj"] and a["obj"]["kind"] in ("entity", "concept") else None
        pred = a["pred"]; bd, bwhy = bundle_for(a); direction = None
        if oid is None and not (a["obj"] and a["obj"]["kind"] in ("num", "date")) and not any(v[1] <= x[0] < sb for x in amts) and not any(d["sent"] == si and d["s"] >= v[1] for d in DT): continue
        if bd: direction = bd["direction"]; pred = "rise" if direction == "up" else ("fall" if direction == "down" else pred)
        elif pred in UP: pred = "rise"; direction = "up"
        elif pred in DOWN: pred = "fall"; direction = "down"
        nxt = min([x for x in by_sent_v[si] if x > v[0]] or [sb])
        am = [x for x in amts if v[1] <= x[0] < nxt and x[1] <= sb]
        if a["obj"] and a["obj"]["kind"] == "num" and not am: am = [x for x in amts if sa <= x[0] < sb and x[0] >= v[1]][:1]
        if bd and bd.get("size") and not am:
            sz = bd["size"]; am = [(sz["span"][0], sz["span"][1], {"text": sz["text"].strip(), "value": sz["value"], "unit": sz.get("unit") or None})]
        tm = [d for d in DT if d["sent"] == si and (d["s"] >= v[1] or a["obj"] and a["obj"]["kind"] == "date")] or [d for d in DT if d["sent"] == si]
        if a["obj"] and a["obj"]["kind"] == "date" and not tm: tm = []
        pl = [m for m in places if m["sent"] == si]; place = None; place_how = None
        if pl: place = pl[0]["iso"]; place_how = "same sentence"
        elif (rec["stage_out"].get("place_linker", {}).get("out") or {}).get("country"): place = art_iso; place_how = "article country (top place-linker country)"
        neg = [n for n in negs if v[0] - 40 <= n[0] <= v[1] + 15 and sa <= n[0] < sb]; mod = [n for n in mods if v[0] - 40 <= n[0] <= v[1] + 15 and sa <= n[0] < sb]
        spk = None
        for at in ATT:
            if at["clause"] and at["clause"]["s"] <= v[0] < at["clause"]["e"] + 1: spk = at; break
        so = rec["sentences"][si] if si < len(rec["sentences"]) else {}
        key = "%s | %s | %s" % (sid, pred, oid or (cnorm(str(u["value"])) if a["obj"] and a["obj"]["kind"] not in ("num", "date") else "-"))
        aid = "A:" + h(key)
        att = {"amount": [x[2] for x in am], "time": [{"text": d["text"], "label": d["label"], "iso": d["iso"], "period": d["period"]} for d in tm[:2]], "place": place, "place_how": place_how, "direction": direction, "direction_how": ("change bundle " + bwhy) if bd else ("verb lemma in the up/down list" if direction else None),
               "polarity": "negative" if neg else "positive", "modality": "predicted" if mod or so.get("factuality") == "predicted" else ("reported" if so.get("factuality") == "reported" else "asserted"), "speaker": spk["c"]["_e"][0] if spk else None, "speaker_how": spk["how"] if spk else None}
        if a["obj"] and a["obj"]["kind"] == "date" and not tm: att["time"] = [{"text": a["obj"]["text"], "label": a["obj"]["text"], "iso": None, "period": None}]
        spans = [_span(*v)]
        for k in ("subj", "obj"):
            if a[k] and a[k].get("span"): spans.append(_span(*a[k]["span"]))
        # vertical: the sentence's in-topic majority placed term, else the object/subject concept, else the article topic
        sp_ = sent_path([si]); ip = mkiptc(sp_, "sentence", "majority in-topic placed term in the assertion's sentence") if sp_ else topic_iptc()
        # an exact IPTC placement of the subject or object (not outside the article's topic) is the more specific path
        for rid in (oid, sid):
            r_ = S.ent.get(rid)
            if r_ and r_["iptc"] and r_["iptc"]["how"] == "exact" and r_["type"] == "concept" and (not l1 or pk.chain(r_["iptc"]["node"])[0] == l1 if r_["iptc"]["node"] else False): ip = {**r_["iptc"], "why": "exact IPTC label of its %s '%s'" % ("object" if rid == oid else "subject", r_["canon"])}; break
        r = S.asr.get(aid); new = r is None
        ev = {"art": art, "pub": pub, "title": rec["title"], "sent": sent_txt(si), "spans": spans, "independent": independent, "attrs": att, "sents": [si]}
        if new: r = S.asr[aid] = {"id": aid, "key": key, "subj": sid, "pred": pred, "obj": oid, "obj_text": None if oid else (cnorm(str(u["value"])) if a["obj"] and a["obj"]["kind"] not in ("num", "date") else None), "kind": "claim", "arts": {}, "evid": [], "iptc": ip, "attrs": att}
        prior = len(r["arts"]); priorp = len(set(S.arts[x]["publisher"] for x, ok in [(x, 1) for x in r["arts"]] if S.arts[x]["independent"]))
        if art not in r["arts"]: r["arts"][art] = pub; r["evid"].append(ev)
        r["iptc"] = r["iptc"] or ip
        out_asr[aid] = {"id": aid, "new": new, "prior": prior, "priorp": priorp, "si": si, "v": v, "att": att, "sid": sid, "oid": oid, "pred": pred, "surface": u["predicate"], "spk": spk["c"]["_e"][0] if spk else None}
        # attribution edges: speaker -> subject entity of the attributed claim
        a["aid"] = aid; a["sid"] = sid; a["oid"] = oid; a["att"] = att; a["spk"] = spk
    # attribution assertions (speaker said clause): one per attribution unit
    for at in ATT:
        u = at["u"]; si = at["sent"]; sp_ = sent_path([si]); ip = mkiptc(sp_, "sentence", "majority in-topic placed term in the quoted sentence") if sp_ else topic_iptc(); sid = at["c"]["_e"][0]
        clause = str(u["value"])[:200]; key = "%s | say | %s" % (sid, h(nrm(clause)[:80])); aid = "A:" + h(key)
        att = {"amount": [], "time": [], "place": None, "place_how": None, "direction": None, "polarity": "positive", "modality": "reported", "speaker": sid, "speaker_how": at["how"], "quote": clause}
        r = S.asr.get(aid); new = r is None
        ev = {"art": art, "pub": pub, "title": rec["title"], "sent": sent_txt(si), "spans": [_span(at["verb"]["s"], at["verb"]["e"])] + ([_span(at["clause"]["s"], at["clause"]["e"])] if at["clause"] else []), "independent": independent, "attrs": att, "sents": [si]}
        if new: r = S.asr[aid] = {"id": aid, "key": key, "subj": sid, "pred": "say", "obj": None, "obj_text": clause[:90], "kind": "attribution", "arts": {}, "evid": [], "iptc": ip, "attrs": att}
        prior = len(r["arts"]); priorp = len({S.arts[x]["publisher"] for x in r["arts"] if S.arts[x]["independent"]})
        if art not in r["arts"]: r["arts"][art] = pub; r["evid"].append(ev)
        out_asr[aid] = {"id": aid, "new": new, "prior": prior, "priorp": priorp, "si": si, "v": (at["verb"]["s"], at["verb"]["e"]), "att": att, "sid": sid, "oid": None, "pred": "say", "surface": u["predicate"], "spk": sid, "attr": True}
    # ---- edges ----
    ed = {}
    def edge(via, a_, b_, label, w=1, spans=None, sent=None, note=None):
        if a_ is None or b_ is None or a_ == b_: return
        k = (via, a_, b_, label)
        r = ed.get(k)
        if r is None: r = ed[k] = {"via": via, "a": a_, "b": b_, "label": label, "w": 0, "art": art, "spans": [], "sent": sent, "note": note}
        r["w"] += w
        if spans: r["spans"].extend(spans[:3])
    def tnode(ip):
        if not ip: return None, None
        q = ip.get("node") or ("P:" + ip["path"]); S.nodes[q] = {"id": q, "label": ip["path"].split(" > ")[-1], "path": ip["path"], "domain": ip["domain"]}
        d = "D:" + ip["domain"]; S.nodes[d] = {"id": d, "label": ip["domain"], "path": ip["domain"], "domain": ip["domain"]}; return q, d
    ENT_THIS = {}
    for c in clusters:
        eid = c["_e"][0]; ENT_THIS[eid] = c["_r"]
    for eid, r in list(S.ent.items()):
        if art in r["arts"]: ENT_THIS[eid] = r
    for eid, r in ENT_THIS.items():   # hierarchy: entity -> topic -> domain; place -> country -> region
        q, d = tnode(r["iptc"])
        if q: edge("hierarchy", eid, q, r["iptc"]["how"], 1, None, None, r["iptc"].get("why")); edge("hierarchy", q, d, "in domain", 1)
        if r.get("geo") and len(r["geo"]) > 1: gid = "G:" + r["geo"][1]; S.nodes[gid] = {"id": gid, "label": r["geo"][1], "path": " > ".join(r["geo"][::-1]), "domain": None}; edge("spatial", eid, gid, "part of", 1, None, None, "country -> region (WordNet / place linker)")
    for aid, o in out_asr.items():
        r = S.asr[aid]; q, d = tnode(r["iptc"])
        if q: edge("hierarchy", aid, q, r["iptc"]["how"], 1, None, o["si"], r["iptc"].get("why"))
        if o["sid"] and not o.get("attr"): edge("assertion", o["sid"], o["oid"], o["pred"], 1, [_span(*o["v"])], o["si"]) if o["oid"] else None
        if o.get("attr"): edge("attribution", o["sid"], aid, "said", 1, [_span(*o["v"])], o["si"])
        elif o["att"].get("speaker"): edge("attribution", o["att"]["speaker"], aid, "said", 1, [_span(*o["v"])], o["si"])
        pl = o["att"].get("place")
        if pl and not o.get("attr"): edge("spatial", aid, "iso:" + pl, "in", 1, None, o["si"], o["att"].get("place_how"))
        if o["att"].get("direction") and not o.get("attr"):
            evs = (rec.get("world") or {}).get("events") or []; l1l = str(codes.get("l1_label") or "").lower(); pick = next((e for e in evs if l1l and l1l.split()[0] in e["name"].lower()), None) or (max(evs, key=lambda e: e["talk"]) if evs else None)
            if pick: rid = "R:" + pick["resource"]; S.nodes[rid] = {"id": rid, "label": pick["name"], "path": "World state resource: " + pick["name"], "domain": None}; edge("change", aid, rid, o["att"]["direction"], 1, [_span(*o["v"])], o["si"], "resource chosen by the article's L1 topic name, else the top-talk resource (ledger_split)")
        for tm_ in o["att"]["time"]:
            if tm_.get("period"): pass
    # attribution edges of a speaker to the subject entity of attributed claims (so the relation map shows "X said about Y")
    for a in A:
        if a.get("spk") and a["sid"] and a["spk"]["c"]["_e"][0] != a["sid"]: edge("attribution", a["spk"]["c"]["_e"][0], a["sid"], "said about: " + a["pred"], 1, [_span(*a["v"])], a["si"])
    # co-occurrence (entities in the same sentence; weak, weighted by the number of sentences)
    for si, L in ents_by_sent.items():
        ids = sorted({c["_e"][0] for (_, _, c) in L if c["type"] != "unk"})
        if len(ids) > 8: ids = ids[:8]
        for x, y in itertools.combinations(ids, 2): edge("co-occurrence", x, y, "same sentence", 1, None, si)
    # causal cue v0
    asr_by_sent = collections.defaultdict(list)
    for aid, o in out_asr.items():
        if not o.get("attr"): asr_by_sent[o["si"]].append((o["v"][0], aid, o))
    def side_ids(si, lo, hi):
        ids = [x[1] for x in asr_by_sent.get(si, []) if lo <= x[0] < hi]
        if ids: return ids, "assertion"
        es = [c["_e"][0] for (x, y, c) in ents_by_sent.get(si, []) if lo <= x < hi and c["type"] != "unk"]
        return es, "entity"
    for si, (sa, sb) in enumerate(sents):
        for m in CUE_RX.finditer(text, sa, sb):
            cue = m.group(1).lower(); fwd = cue in FWD; cs, ce = m.start(), m.end(); cm = text.find(",", ce, sb); cm = sb if cm < 0 else cm
            if si > 0 and cs - sa < 3 and fwd:   # sentence-initial forward cue: the previous sentence's last assertion causes this sentence's first
                prev = asr_by_sent.get(si - 1, []); nxt = asr_by_sent.get(si, [])
                if prev and nxt: edge("causal cue v0", sorted(prev)[-1][1], sorted(nxt)[0][1], cue, 1, [_span(cs, ce)], si, "forward cue at the start of the sentence"); continue
            if fwd: left, lk = side_ids(si, sa, cs); right, rk = side_ids(si, ce, sb); cause, effect = left, right
            else:
                cause, ck = side_ids(si, ce, cm); effect, ek = side_ids(si, cm, sb) if cm < sb else (None, None)
                if not effect: effect, ek = side_ids(si, sa, cs)
            if cause and effect:
                c_, e_ = cause[0], effect[-1] if fwd else effect[0]
                if (c_ in out_asr) == (e_ in out_asr): edge("causal cue v0", c_, e_, cue, 1, [_span(cs, ce)], si, "cause -> effect from the cue word in the sentence")
    # temporal: assertions sharing a resolved period are chained; before/after from resolved dates
    per = collections.defaultdict(list)
    for aid, o in out_asr.items():
        for t_ in o["att"].get("time", []):
            if t_.get("period"): per[t_["period"]].append((o["v"][0], aid, t_))
    for p_, L in per.items():
        L = sorted(set((x[0], x[1]) for x in L))
        for (x, a1), (y, a2) in zip(L, L[1:]): edge("temporal", a1, a2, "same period " + p_, 1, None, None)
    dated = sorted([(t_["iso"], aid) for aid, o in out_asr.items() for t_ in o["att"].get("time", []) if t_.get("iso")])
    for (d1, a1), (d2, a2) in zip(dated, dated[1:]):
        if d1 < d2: edge("temporal", a1, a2, "before", 1, None, None, "%s before %s" % (d1, d2))
    # capability pairs -> matched assertions
    cap = (rec["stage_out"].get("capability_list") or {}).get("out") or {}
    for tier in ("recurring", "candidate"):
        for pair in cap.get(tier) or []:
            w = pair.split(); cid = "C:" + pair; S.nodes[cid] = {"id": cid, "label": pair, "path": "capability (%s)" % tier, "domain": None}
            for aid, o in out_asr.items():
                r = S.asr[aid]
                if r["pred"] == w[0] and w[-1] in (r.get("obj_text") or "") + " " + str(r["obj"] or ""): edge("capability", aid, cid, tier, 1, [_span(*o["v"])], o["si"])
    # story / source
    if of or kind in ("copy", "republished"):
        sid_ = "S:" + str(root); S.nodes[sid_] = {"id": sid_, "label": "story: " + (S.arts.get(root, {}).get("title") or rec["title"])[:60], "path": "same story (journal)", "domain": None}
        for aid in out_asr: edge("story", aid, sid_, kind or "story", 1)
    # similar v0 (unmeasured): bge sentence embeddings of assertion sentences, against earlier articles' assertions
    sim_n = 0
    try:
        keys = [(aid, o["si"]) for aid, o in out_asr.items() if not o.get("attr")]
        if keys:
            import numpy as np
            sens = [sent_txt(si) for _, si in keys]; V = ch.bge.encode(sens, normalize_embeddings=True, show_progress_bar=False)
            for (aid, si), vec in zip(keys, V):
                best = None
                for (pa, paid, pv) in S.vec:
                    if pa == art or paid == aid: continue
                    s_ = float(np.dot(pv, vec))
                    if s_ >= 0.86 and (best is None or s_ > best[0]): best = (s_, paid)
                if best: edge("similar v0, unmeasured", aid, best[1], "cos %.2f" % best[0], 1, None, si); sim_n += 1
            for (aid, si), vec in zip(keys, V): S.vec.append((art, aid, vec))
    except Exception as e: rec["g4_similar_error"] = repr(e)
    _tc = time.perf_counter()
    for r in (contradict_edges(S, list(out_asr), art) if contradictions else []): ed[(r["via"], r["a"], r["b"], r["label"])] = r   # plan step 7: both assertions stay, a 'contradicts' edge joins them
    _tc = round((time.perf_counter() - _tc) * 1000, 1)
    # merge this article's edges into the store; count articles per edge
    for k, r in ed.items():
        g = S.edges.get(k)
        if g is None: g = S.edges[k] = {**r, "arts": {art: pub}, "w": 0, "spans": []}
        else: g["arts"][art] = pub
        if r["via"] == "contradiction": g["sources"] = r["sources"]   # derived from the evidence, so it is replaced, not added
        g["w"] += r["w"]
    for c in clusters:
        for x in c.get("pron", []):
            if x not in c["_r"].setdefault("pron", []): c["_r"]["pron"].append(x)
    # ---- per-article payload ----
    def ent_out(eid):
        r = S.ent[eid]; arts = r["arts"]; ev = next(x for x in r["evid"] if x["art"] == art)
        pubs = {S.arts[a]["publisher"] for a in arts if S.arts[a]["independent"]}
        return {"id": eid, "type": r["type"], "canon": r["canon"], "aliases": sorted(r["aliases"], key=lambda x: -r["aliases"][x]), "pronouns": r.get("pron", [])[:8], "n_mentions": sum(r["aliases"].values()), "iptc": r["iptc"], "geo": r.get("geo"), "unsure": [{"id": u_, "type": S.ent[u_]["type"], "canon": S.ent[u_]["canon"]} for u_ in r["unsure"]], "articles": len(arts), "publishers": len(pubs), "evid_this": ev,
                "evid_all": [{"art": x["art"], "pub": x["pub"], "title": x["title"], "sent": x["sent"], "independent": x["independent"]} for x in r["evid"]], "new": len(arts) == 1}
    ents_out = [ent_out(eid) for eid in ENT_THIS if art in S.ent[eid]["arts"]]
    def asr_out(aid):
        r = S.asr[aid]; o = out_asr[aid]; arts = r["arts"]; pubs = {S.arts[a]["publisher"] for a in arts if S.arts[a]["independent"]}
        return {"id": aid, "kind": r["kind"], "subj": r["subj"], "pred": r["pred"], "surface": o["surface"], "obj": r["obj"], "obj_text": r["obj_text"], "attrs": o["att"], "iptc": r["iptc"], "articles": len(arts), "publishers": len(pubs), "new": o["new"], "prior_articles": o["prior"], "prior_publishers": o["priorp"],
                "same_story_merge": bool(o["prior"]) and any(S.arts[x]["root"] == root for x in arts if x != art),
                "evid_this": next(x for x in r["evid"] if x["art"] == art), "evid_all": [{"art": x["art"], "pub": x["pub"], "title": x["title"], "sent": x["sent"], "independent": x["independent"]} for x in r["evid"]]}
    asr_list = [asr_out(aid) for aid in out_asr]
    nodes = {}
    for k, r in ed.items():
        for n_ in (r["a"], r["b"]):
            if n_ in S.nodes: nodes[n_] = S.nodes[n_]
    # joins at IPTC-node level, store-wide
    joins = joins_of(S)
    ms = round((time.perf_counter() - t0) * 1000, 1); S.ms.append(ms)
    S.curve.append({"articles": len(S.arts), "entities": len(S.ent), "assertions": len(S.asr), "edges": len(S.edges)})
    S.save_article(art)   # durable store: append this article's changes (no-op when no file is attached)
    rec["g4"] = {"label": LABEL, "entities": ents_out, "assertions": asr_list, "edges": [{**r, "arts": None} for r in ed.values()], "nodes": nodes, "ms": ms, "contradictions_ms": _tc, "story": {"root": root, "independent": independent, "kind": kind}, "joins": joins[:12], "graph": {**S.stats(), "joins_nodes": len(joins), "curve": S.curve[-60:]}, "similar_edges": sim_n, "contradiction_edges": sum(1 for r in ed.values() if r["via"] == "contradiction"),
                 "mentions_unclustered": len(M) - sum(len(c["ms"]) for c in clusters), "alias_merges": sum(len(c["ms"]) - len({(m["surface"].strip()) for m in c["ms"]}) + 0 for c in clusters), "aliases_merged": sum(max(0, len(c["surf"]) - 1) for c in clusters)}
def ch_stop(ch):
    if not hasattr(ch, "_g4_stop"):
        from spacy.lang.en.stop_words import STOP_WORDS
        ch._g4_stop = set(STOP_WORDS)
    return ch._g4_stop
def joins_of(S):
    """IPTC-node level joins across articles: a node reached by items from >= 2 articles (entities and assertions). Returns [{node, path, articles, publishers, entities, assertions, pairs}] by size."""
    by = collections.defaultdict(lambda: {"arts": {}, "ents": set(), "asr": set()})
    for e in S.ent.values():
        ip = e.get("iptc")
        if ip and ip.get("path"):
            b = by[ip["path"]]; b["ents"].add(e["id"])
            for a_ in e["arts"]: b["arts"][a_] = S.arts[a_]["publisher"]
    for a in S.asr.values():
        ip = a.get("iptc")
        if ip and ip.get("path"):
            b = by[ip["path"]]; b["asr"].add(a["id"])
            for a_ in a["arts"]: b["arts"][a_] = S.arts[a_]["publisher"]
    out = []
    for p, b in by.items():
        if len(b["arts"]) >= 2:
            pubs = {S.arts[a_]["publisher"] for a_ in b["arts"] if S.arts[a_]["independent"]}
            out.append({"path": p, "node": to_node(S, p), "articles": len(b["arts"]), "publishers": len(pubs), "entities": len(b["ents"]), "assertions": len(b["asr"]), "items": sorted(b["ents"])[:8]})
    return sorted(out, key=lambda x: (-x["articles"], -x["entities"]))
def to_node(S, p):
    for k, n in S.nodes.items():
        if n.get("path") == p: return k
    return None
