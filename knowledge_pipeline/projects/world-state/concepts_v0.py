"""concepts_v0: concept layer v0 (PROVISIONAL, unmeasured). Builds, from what the pipeline already wrote for one window, a graph of concept cards + typed links + a per-article triage,
and a time-boxed "deep pass" for one concept. Design: concept-delta-design.md sections 1.1-1.6 (card, relations, certainty, states, triage); owner zoom levels L0 street map / L1 card / L2 structure / L3 deep.
Inputs (read only, nothing is written, no network, no hosted model, no download): <trace>/slow_consolidate/knowledge.json + consolidated.json, <trace>/g4/store.jsonl (identity entities),
<trace>/chain.jsonl (article seq/title/publisher), /workspace/data/anchors/wikidata_cache (cache only), IPTC medtop.json + WordNet data.noun (local packs), probes/persona/rules_v2/resources.csv,
and, for the deep pass, the other windows under demo/mockups/structure-live/*/trace/slow_consolidate (history before this window).
Rules (all stated guesses): certainty = sum(decayed weight of independent owners) / (that + decayed contradiction support + 1); direction needs >= 2 independent owners reading up/down else null;
what_it_is only from a cached Wikidata hit (exact label), the IPTC definition of the node the facts landed on, or a WordNet gloss for a plain noun, never invented; links typed by predicate class rules, else 'related'.
Contract: GET /api/raw/concepts and /api/raw/deep (simulation/server.py -> raw-units.py concepts(), deep())."""
import os, re, sys, json, time, collections, bisect

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import wikidata_cache as WC
import lexicons as LX
STRUCT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "demo", "mockups", "structure-live"))
RES_CSV = "/workspace/probes/persona/rules_v2/resources.csv"; IPTC = "/workspace/data/ontology_src/iptc/medtop.json"; WN = "/workspace/data/ontology_src/wordnet/wordnet"
MIN_FACTS = 2; MIN_OWNERS_ACTIVE = 3; CONCEPT_MIN_FACTS = 3; CONCEPT_MIN_OWNERS = 2; BOX_S = 120.0
SPEECH = {"say", "tell", "report", "claim", "add", "state", "warn", "say in", "say that", "according", "note", "announce", "confirm", "deny", "describe", "write"}
CAUSE = {"cause", "lead to", "trigger", "spark", "result in", "prompt", "force", "drive", "provoke", "induce", "contribute to", "bring about", "set off"}
PART = {"belong to", "part of", "include", "contain", "member of", "comprise", "consist of", "host", "have", "own"}
ISA = {"be", "become", "be a", "serve as", "remain"}
OPPOSE = LX.words("relation.oppose_predicates")   # the words are data (lexicons.json, playbook 00.1 round E); KP_LEXICONS=off leaves every class empty
AGENT_KINDS = {"person", "org", "place"}
# v1 rules (all PROVISIONAL, rule-based, nothing invented: every field cites edge ids / a cached source)
CAUSE_VERBS = CAUSE | {"push", "fuel", "spark", "lead", "prompt", "trigger", "drive", "cause", "result", "contribute", "bring", "set off", "stoke", "heighten", "worsen"}
CAUSE_MARK = re.compile(r"\b(in response to|because of|because|as a result of|due to|owing to|triggered by|sparked by|prompted by|driven by|following|after|led to)\b", re.I)
CLAUSE_END = re.compile(r"[,;:()*\u2014\u2013]|\s(?:and|but|while|as|which|that|when|with|despite|amid)\s|\.(?:\s|$)", re.I)
KIN = LX.words("relation.kinetic_verbs")
GENERIC_SYN = 4; GENERIC_TAG = 3; GENERIC_DEPTH = 5; GENERIC_DF = 0.25   # stoplist rule: WordNet polysemy / SemCor tag count / hypernym depth, or share of area articles that use the head word
PROCESS_MIN_OWNERS = 3; PROCESS_MIN_EDGES = 4; TYPED_MIN_OWNERS = 2
_CACHE = {}; _RES = {}; _WN = {}; _IP = {}; _OW = {}; _PL = {}

# ---------------------------------------------------------------- loading
def _jl(p, default=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default
def _inner(x):
    ln = x.get("line") if isinstance(x, dict) else None
    if isinstance(ln, str):
        try: ln = json.loads(ln)
        except Exception: ln = None
    if not isinstance(ln, dict): ln = x if isinstance(x, dict) and "stages" in x else None
    return ln
def owners_map():
    if not _OW:
        d = _jl(os.path.join(HERE, "publisher-owners.json"), {}) or {}
        for r in d.get("publishers", []) if isinstance(d, dict) else []:
            if isinstance(r, dict) and r.get("publisher"): _OW[r["publisher"]] = r.get("owner") or r["publisher"]
    return _OW
def resources_csv():
    if not _RES:
        import csv
        try:
            for r in csv.DictReader(open(RES_CSV, encoding="utf-8")): _RES[r["id"]] = {"name": r.get("name"), "definition": r.get("definition"), "source": "resources.csv:" + r["id"]}
        except Exception: pass
    return _RES
def iptc_defs():
    if not _IP:
        cs = (_jl(IPTC, {}) or {}).get("conceptSet") or []
        for c in cs:
            df = c.get("definition"); df = (df.get("en-GB") or next(iter(df.values()), None)) if isinstance(df, dict) else df
            _IP[c.get("qcode")] = {"label": (c.get("prefLabel") or {}).get("en-GB"), "definition": df}
    return _IP
def wn_gloss(term):
    """first-sense gloss of a plain noun from the local WordNet pack (index.noun -> offset -> data.noun); None when absent"""
    if not _WN:
        idx = {}
        try:
            for l in open(WN + "/index.noun"):
                if l.startswith(" "): continue
                p = l.split(); idx[p[0]] = p
        except Exception: pass
        _WN["idx"] = idx
    p = _WN["idx"].get(term.lower().strip().replace(" ", "_"))
    if not p: return None
    try:
        n_ptr = int(p[3]); off = p[6 + n_ptr]
        with open(WN + "/data.noun", "rb") as f:
            f.seek(int(off)); line = f.readline().decode("utf-8", "replace")
        return {"text": line.split("|", 1)[1].strip().split(";")[0].strip(), "src": "wordnet:%s (first sense of '%s', not disambiguated by context)" % (off, term)}
    except Exception: return None
def wn_info(term):
    """(synset count, SemCor tagged-sense count, first-sense hypernym depth) of a noun from the local WordNet pack, or None when absent"""
    wn_gloss("war")
    p = _WN["idx"].get((term or "").lower().strip().replace(" ", "_"))
    if not p: return None
    try:
        n = int(p[2]); off = p[-n]; tag = int(p[-n - 1]); d = 0
        with open(WN + "/data.noun", "rb") as f:
            while d < 30:
                f.seek(int(off)); l = f.readline().decode("utf-8", "replace").split("|")[0].split(); wc = int(l[3], 16); i = 4 + 2 * wc; pc = int(l[i]); i += 1; h = None
                for k in range(pc):
                    sym, o = l[i + 4 * k], l[i + 4 * k + 1]
                    if sym in ("@", "@i"): h = o; break
                if not h: break
                off = h; d += 1
        return {"syn": n, "tag": tag, "depth": d}
    except Exception: return None
def generic_why(head, df):
    """why this head noun is generic (None when it is not): WordNet top-level / very frequent noun (many senses, often tagged, shallow in the hypernym tree) or a word that a large share of this area's articles use (IDF)"""
    w = wn_info(head); why = []
    if w:
        if w["syn"] >= GENERIC_SYN: why.append("%d WordNet senses" % w["syn"])
        if w["tag"] >= GENERIC_TAG: why.append("tagged %d times in SemCor" % w["tag"])
        if w["depth"] <= GENERIC_DEPTH: why.append("WordNet hypernym depth %d" % w["depth"])
    if df >= GENERIC_DF: why.append("used in %d%% of this area's articles" % round(100 * df))
    return "; ".join(why) or None
def load(td):
    td = os.path.abspath(td); k = td
    sc = os.path.join(td, "slow_consolidate"); sig = tuple(os.path.getmtime(os.path.join(sc, f)) if os.path.exists(os.path.join(sc, f)) else 0 for f in ("knowledge.json", "consolidated.json")) + (os.path.getmtime(os.path.join(td, "chain.jsonl")) if os.path.exists(os.path.join(td, "chain.jsonl")) else 0,)
    c = _CACHE.get(("load", k))
    if c and c["sig"] == sig: return c["D"]
    K = _jl(os.path.join(sc, "knowledge.json")); C = _jl(os.path.join(sc, "consolidated.json")) or {}
    arts = {}
    if os.path.exists(os.path.join(td, "chain.jsonl")):
        for l in open(os.path.join(td, "chain.jsonl"), encoding="utf-8"):
            try: ln = _inner(json.loads(l))
            except Exception: continue
            if ln and ln.get("id"): arts[ln["id"]] = {"seq": ln.get("seq"), "title": ln.get("title"), "pub": ln.get("source"), "day": (ln.get("published") or "")[:10]}
    store = os.path.join(td, "g4", "store.jsonl"); ents = {}
    if os.path.exists(store):
        try: ents = WC.read_entities([store])
        except Exception: ents = {}
    slow = {}
    if os.path.exists(os.path.join(td, "slow.jsonl")):
        for l in open(os.path.join(td, "slow.jsonl"), encoding="utf-8"):
            try: r = json.loads(l); slow[r.get("id")] = r
            except Exception: pass
    D = {"td": td, "K": K, "C": C, "arts": arts, "ents": ents, "slow": slow}
    _CACHE[("load", k)] = {"sig": sig, "D": D}; return D

# ---------------------------------------------------------------- identity
def _norm(s): return re.sub(r"\s+", " ", re.sub(r"['’]s\b", "", str(s or "")).lower()).strip()
def _label_of(cid, ents):
    e = ents.get(cid)
    if cid.startswith("process:"): return _PL.get(cid) or cid
    if cid.startswith("resource:"): return (resources_csv().get(cid[9:]) or {}).get("name") or cid[9:].replace("_", " ")
    if e:
        if cid.startswith("iso:"): return e.get("canon") or cid
        al = e.get("aliases") or {}
        if isinstance(al, dict) and al:
            best = max(al.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]; return best
        return e.get("canon") or cid.split(":", 1)[-1]
    return cid.split(":", 1)[-1] if ":" in cid else cid
def _kind(cid, ents):
    p = cid.split(":", 1)[0]
    return {"person": "person", "org": "org", "group": "org", "iso": "place", "place": "place", "facility": "place", "resource": "resource", "process": "process", "cap": "capability", "concept": "concept"}.get(p, "entity" if p in ("event", "work", "product", "disease", "substance", "other", "unk") else "concept")
NP_MAXTOK = 6; NP_MIN_ARTS = 2; NP_AMBIG_SYN = 5; NP_AMBIG_TAG = 3
NP_STOP = set('of in on to for with that who which what is are was were be been has have had will would could should may might not and or but at by from as into over under after before about during while when where this these those their his her its our your my it they he she we you them there than then so if'.split())
_DEMO = {}
def demonyms():
    if not _DEMO:
        try: _DEMO.update({k.lower(): v for k, v in json.load(open(os.path.join(HERE, "specs", "demonyms_wordnet_v0.json")))["map"].items()})
        except Exception: _DEMO["_"] = None
    return _DEMO
def make_canon(ents, edge_ids_seen):
    """concept: names that equal a typed entity's label (or one of its aliases) merge into that entity ('merge iso/concept names already handled' by G4; the leftover same-label concept: ids are merged here).
    Coverage rules (PROVISIONAL, T158 round 4; each one is tagged and counted, canon.rule(x) names it, canon.all(x) lists every concept a surface reaches):
      coord  a typed entity whose label is 'X and Y' with X and Y each the name of a typed entity is two entities (first conjunct is the primary id, both get the fact)
      np-name  a plain noun phrase of 2..%d words that contains the full name of a typed entity seen in >= %d articles (longest name wins) is a mention of that entity
      np-demonym  a plain noun phrase of 2..%d words that contains a country demonym (specs/demonyms_wordnet_v0.json, from WordNet pertainyms) is a mention of that country when the window has it"""  % (NP_MAXTOK, NP_MIN_ARTS, NP_MAXTOK)
    typed = {}; names = {}; demo = demonyms()
    for cid, e in ents.items():
        if cid.split(":", 1)[0] in ("concept", "resource", "cap"): continue
        nm = {_norm(e.get("canon"))} | {_norm(a) for a in (e.get("aliases") or {})}
        for n in nm:
            if n and n not in typed: typed[n] = cid
        if cid.split(":", 1)[0] in ("unk", "other"): continue
        for n in nm:
            tk = tuple(n.split())
            if not tk or (len(tk) == 1 and len(tk[0]) < 4) or "and" in tk or "&" in tk: continue
            if len(tk) == 1:   # a one-word name that is also a common English word (WordNet: >= 5 senses or tagged >= 3 times: turkey, player, division) is not read out of a phrase
                w = wn_info(tk[0])
                if w and (w["syn"] >= NP_AMBIG_SYN or w["tag"] >= NP_AMBIG_TAG): continue
            elif cid.split(":", 1)[0] in ("org", "group", "product", "event", "work", "facility") and all(wn_info(t) for t in tk): continue   # a multiword org name made only of common words (state government) is not a name
            if len(e.get("arts") or {}) >= NP_MIN_ARTS: names.setdefault(tk, cid)
    isos = {"iso:" + v: v for v in demo.values() if v}
    memo = {}
    def resolve(x):
        """-> (ids in order, rule tag or None)"""
        if not x: return [], None
        if x in memo: return memo[x]
        r = ([x], None)
        if not x.startswith("concept:"):
            lab = _norm((ents.get(x) or {}).get("canon") or x.split(":", 1)[-1])
            if " and " in " " + lab + " " and x.split(":", 1)[0] not in ("resource", "process", "cap", "iso"):
                halves = [h.strip() for h in re.split(r"\s+and\s+", lab) if h.strip()]
                ids = [typed.get(h) for h in halves]
                if len(halves) == 2 and all(ids) and ids[0] != ids[1] and x not in ids: r = (ids, "coord")
        else:
            low = _norm(x[8:]); typ = typed.get(low)
            if typ: r = ([typ], None)
            else:
                tk = low.split()
                if 2 <= len(tk) <= NP_MAXTOK:
                    hit = None
                    for L in range(len(tk), 0, -1):
                        for i in range(len(tk) - L + 1):
                            c = names.get(tuple(tk[i:i + L]))
                            if c and (L > 1 or i == 0) and not any(t in NP_STOP or t.isdigit() for t in tk[:i] + tk[i + L:]): hit = c; break   # a one-word name only leads the phrase (modi appeal), never sits inside it after a given name or title (penelope brady, coach chelsea)   # the rest of the phrase has no function word or number: a noun phrase, not a clause
                        if hit: break
                    if hit: r = ([hit], "np-name")
                    else:
                        for t in tk:
                            iso = demo.get(t)
                            if iso and "iso:" + iso in ents: r = (["iso:" + iso], "np-demonym"); break
        memo[x] = r; return r
    def canon(x):
        ids, _ = resolve(x); return ids[0] if ids else None
    canon.all = lambda x: resolve(x)[0]; canon.rule = lambda x: resolve(x)[1]
    return canon
def link_rel(pred, a_kind, b_kind):
    p = (pred or "").lower().strip()
    if p in ISA: return "is_a"
    if p in PART: return "part_of"
    if p in CAUSE: return "causes"
    if p in OPPOSE and a_kind in AGENT_KINDS and b_kind in AGENT_KINDS: return "opposes"
    return "related"

# ---------------------------------------------------------------- card slots v1 (role / did / because / allies / opponents / effect / disputed / new), PROVISIONAL, rule-based, every item cites edge ids
MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
def fmt_days(days):
    ds = sorted(d for d in days if d and re.match(r"\d{4}-\d\d-\d\d", d))
    if not ds: return None
    f = lambda d: "%s %d" % (MONTH[int(d[5:7]) - 1], int(d[8:10]))
    return f(ds[0]) if ds[0] == ds[-1] else ("%s-%d" % (f(ds[0]), int(ds[-1][8:10])) if ds[0][5:7] == ds[-1][5:7] else "%s-%s" % (f(ds[0]), f(ds[-1])))
def sureness(owners, cert, disputed=False):
    """word for the certainty: disputed / established (>= 3 independent owners, cert >= 0.6) / reported (>= 2 owners) / single source"""
    if disputed: return "disputed"
    if owners >= 3 and cert >= 0.6: return "established"
    return "reported" if owners >= 2 else "single source"
SUBSPLIT = re.compile(r"(?<=[.!?\u201d\"])\s+(?=[A-Z\u201c\"#*])|\s*#{1,3}\s+|\s\*+(?=[A-Za-z])|\*+\s+")
def _subs(sent):
    """the sentence split at headline / paragraph / sentence boundaries; every piece is a substring of the fragment sentence"""
    return [x.strip() for x in SUBSPLIT.split(sent or "") if x and len(x.split()) >= 4]
def best_sub(sent, nre=None):
    """the piece of a fragment sentence that carries the concept (its name) when given, else the first full-length piece; always a substring of the sentence"""
    ps = _subs(sent) or [sent]
    if nre:
        for x in ps:
            if nre.search(x): return x
    return ps[0]
def _sents(e): return [f for f in (e.get("fragments") or []) if f.get("sent")]
def _names(cid, ents):
    e = ents.get(cid) or {}; ns = {_label_of(cid, ents)} | {a for a in (e.get("aliases") or {})} | ({e["canon"]} if e.get("canon") else set())
    return sorted({n for n in ns if n and len(n) >= 2 and re.search(r"[A-Za-z]", n)}, key=lambda n: -len(n))
def _name_re(names):
    if not names: return None
    return re.compile("|".join((r"\b%s\b" if len(n) <= 3 else r"\b%s") % re.escape(n) for n in names), re.I)
def _has_letters(x): return bool(x and len(re.findall(r"[A-Za-z]", str(x))) >= 3)
def edge_owners(e): return {o for o, w, d in _own_of(e)}

def _directions(cid, fe, EB, canon, ents, MS=()):
    """[{object, label, dir, certainty, owners, edge_ids, sentence}]: up/down read on facts where this concept is the subject; object = the fact's object (a concept / resource id) or null when the fact has none; independent owners per (object, dir)"""
    g = {}
    for eid, role in fe.items():
        if role != "subject": continue
        e = EB[eid]
        for f in e.get("fragments") or []:
            dd = f.get("direction") or (e.get("attrs") or {}).get("direction")
            if dd not in ("up", "down"): continue
            o = canon(e.get("obj")); lab = _label_of(o, ents) if o else (e.get("obj_text") or None)
            if not _has_letters(lab): o, lab = None, None
            x = g.setdefault((o, dd), {"object": o, "label": lab, "dir": dd, "ow": {}, "edge_ids": [], "sentence": None, "pub": None, "pred": e.get("pred")})
            _add_ow(x["ow"], owners_map().get(f.get("pub"), f.get("pub")), _w(e))
            if eid not in x["edge_ids"]: x["edge_ids"].append(eid)
            if not x["sentence"] and f.get("sent"): x["sentence"] = best_sub(f["sent"], _name_re(_names(cid, ents))); x["pub"] = f.get("pub")
    out = []
    for x in g.values():
        if x["object"] and x["object"].startswith("concept:") and x["object"] not in MS and len(x["ow"]) < 2: continue   # a one-owner free-text object is not a concept of the graph: left out of the card
        sup = _sup(x["ow"]); disp = any(y["object"] == x["object"] and y["dir"] != x["dir"] for y in g.values())
        out.append({"object": x["object"], "label": x["label"], "dir": x["dir"], "certainty": _cert(sup, 1.0 if disp else 0.0), "owners": len(x["ow"]), "edge_ids": x["edge_ids"][:6], "sentence": x["sentence"], "pub": x["pub"], "pred": x["pred"], "rule": "rule-based: fragment direction read (direction_v1) on a fact whose subject is this concept"})
    out.sort(key=lambda d: (d["object"] is None, -d["owners"], -len(d["edge_ids"]), d["label"] or "", d["dir"]))
    return out[:12]
def _drivers(cid, fe, EB, canon, ents, links, nre, kind):
    """causes of this concept: (1) a causal-verb fact whose object is this concept (subject = driver), (2) typed 'causes' links, (3) 'because / after / in response to / following ...' clauses quoted from the sentences of its facts"""
    out = []; seen = set()
    for eid, role in fe.items():
        e = EB[eid]
        if e.get("kind") != "assertion": continue
        pr = (e.get("pred") or "").lower(); first = pr.split()[0] if pr else ""
        if canon(e.get("obj")) == cid and (pr in CAUSE_VERBS or first in CAUSE_VERBS):
            sd = canon(e.get("anchor") or e.get("subj")); fr = (_sents(e) or [{}])[0]
            if fr.get("sent"): fr = {**fr, "sent": best_sub(fr["sent"], nre)}
            if sd and sd != cid and fr.get("sent"):
                k = ("v", sd); 
                if k in seen: continue
                seen.add(k); out.append({"concept": sd, "label": _label_of(sd, ents), "rel": "causes", "certainty": _cert(sum(w for o, w, d in _own_of(e)), 0.0), "edge_ids": [eid], "text": "%s %s %s" % (_label_of(sd, ents), pr, _label_of(cid, ents)), "sentence": fr["sent"], "pub": fr.get("pub"), "day": fr.get("day"), "marker": pr, "rule": "rule-based: causal predicate '%s' with this concept as object" % pr, "_o": len(edge_owners(e))})
    for l in links:
        if l["b"] == cid and l["rel"] == "causes" and ("v", l["a"]) not in seen:
            e = EB.get(l["edge_ids"][0]) if l["edge_ids"] else None; fr = (_sents(e) or [{}])[0] if e else {}
            if fr.get("sent"): fr = {**fr, "sent": best_sub(fr["sent"], nre)}
            if fr.get("sent"): seen.add(("v", l["a"])); out.append({"concept": l["a"], "label": _label_of(l["a"], ents), "rel": "causes", "certainty": l["certainty"], "edge_ids": l["edge_ids"][:6], "text": "%s causes %s" % (_label_of(l["a"], ents), _label_of(cid, ents)), "sentence": fr["sent"], "pub": fr.get("pub"), "day": fr.get("day"), "marker": "causes", "rule": "rule-based: typed causes link", "_o": l["owners"]})
    if nre:
        for eid, role in fe.items():
            e = EB[eid]
            if e.get("kind") != "assertion": continue
            for f, sent in [(f, x) for f in _sents(e) for x in _subs(f["sent"])]:
                m0 = nre.search(sent)
                if not m0: continue
                for m in CAUSE_MARK.finditer(sent):
                    if m.start() < m0.start(): continue
                    rest = sent[m.end():]; cut = CLAUSE_END.search(rest); clause = (rest[:cut.start()] if cut else rest).strip(" \"'\u201c\u201d\u2018\u2019")
                    ws = clause.split()
                    if len(ws) < 2 or len(ws) > 18 or not re.search(r"[A-Za-z]{3}", clause): continue
                    clause = re.sub(r"\s+[-\u2013\u2014]\s+\w+$", "", clause).strip()
                    if len(clause.split()) < 2 or nre.search(clause): continue   # a clause that names the concept itself is its own action, not its cause
                    tk = set(re.findall(r"[a-z]{3,}", clause.lower())); dup = next((o for o in out if o["marker"] not in ("causes",) and o.get("_tk") and len(tk & o["_tk"]) >= 0.7 * min(len(tk), len(o["_tk"]))), None)
                    if dup is not None:
                        if eid not in dup["edge_ids"]: dup["edge_ids"].append(eid); dup["_o"] += len(edge_owners(e))
                        continue
                    seen.add(("c", clause.lower()))
                    lc = None
                    for x in sorted(F_LABELS(links, ents), key=lambda t: -len(t[1])):
                        if x[0] != cid and len(x[1]) >= 3 and re.search(r"\b%s" % re.escape(x[1]), clause, re.I): lc = x[0]; break
                    out.append({"concept": lc, "label": clause, "rel": "causes", "certainty": _cert(sum(w for o, w, d in _own_of(e)), 0.0), "edge_ids": [eid], "text": "%s %s" % (m.group(0).lower(), clause), "sentence": sent, "pub": f.get("pub"), "day": f.get("day"), "marker": m.group(0).lower(), "rule": "rule-based: '%s' clause quoted from a fact sentence" % m.group(0).lower(), "_o": len(edge_owners(e)), "_tk": tk})
                    break
    out.sort(key=lambda d: (0 if d["rule"].startswith("rule-based: causal") or d["rule"].endswith("link") else 1, -d["_o"], d["text"]))
    for d in out:
        d.pop("_o", None); d.pop("_tk", None)
    return out[:5]
def F_LABELS(links, ents):
    ids = {l["a"] for l in links} | {l["b"] for l in links}
    return [(i, _label_of(i, ents)) for i in ids if not i.startswith("resource:")]
SPEECH_ROLE = SPEECH | {"say", "tell", "report"}
MEDIATE = {"mediate", "broker", "negotiate", "talk", "call", "urge", "propose", "host", "facilitate"}
def _card_extra(cid, kind, fe, EB, canon, ents, links, MS, cf, nre, directions, ow):
    """role / did / allies / opponents / sources / effect / disputed (PROVISIONAL, every item cites edge ids)"""
    ex = {"role": None, "did": [], "allies": [], "opponents": [], "sources": [], "effect": [], "disputed": []}
    if kind in ("resource", "process"): return ex
    out_k = in_k = sp = md = 0; ids_o = []; ids_i = []; acts = {}
    for eid, role in fe.items():
        e = EB[eid]
        if e.get("kind") != "assertion": continue
        pr = (e.get("pred") or "").lower(); first = pr.split()[0] if pr else ""
        if role == "subject":
            if first in KIN: out_k += 1; ids_o.append(eid)
            if first in SPEECH or pr in SPEECH: sp += 1
            if first in MEDIATE: md += 1
            if first not in SPEECH and pr not in SPEECH and first not in ("be", "have", "become", "say"):
                o = canon(e.get("obj")); lab = _label_of(o, ents) if o else None
                if _has_letters(lab) and not (o or "").startswith("resource:"):
                    a = acts.setdefault(pr, {"objs": {}, "eids": [], "days": set(), "ow": set(), "sent": None, "pub": None}); a["objs"].setdefault(lab, set()).update(edge_owners(e)); a["eids"].append(eid); a["ow"] |= edge_owners(e)
                    for f in e.get("fragments") or []:
                        if f.get("day"): a["days"].add(f["day"])
                    if not a["sent"] and _sents(e): a["sent"] = best_sub(_sents(e)[0]["sent"], nre); a["pub"] = _sents(e)[0].get("pub")
        elif role == "object" and first in KIN: in_k += 1; ids_i.append(eid)
    if out_k >= 2 and out_k >= 1.5 * in_k: ex["role"] = {"label": "attacker", "edge_ids": ids_o[:6], "basis": "%d kinetic-family facts as subject vs %d as object" % (out_k, in_k)}
    elif in_k >= 2 and in_k >= 1.5 * out_k: ex["role"] = {"label": "target", "edge_ids": ids_i[:6], "basis": "%d kinetic-family facts as object vs %d as subject" % (in_k, out_k)}
    elif out_k >= 2 and in_k >= 2: ex["role"] = {"label": "party to the exchange", "edge_ids": (ids_o + ids_i)[:6], "basis": "%d kinetic-family facts as subject, %d as object" % (out_k, in_k)}
    elif md >= 2: ex["role"] = {"label": "mediator", "edge_ids": [], "basis": "%d mediation-family facts as subject" % md}
    elif sp >= 3 and out_k == 0 and in_k == 0: ex["role"] = {"label": "reporter", "edge_ids": [], "basis": "%d speech facts as subject" % sp}
    for pr, a in sorted(acts.items(), key=lambda kv: (-len(kv[1]["ow"]), -len(kv[1]["eids"]), kv[0]))[:3]:
        objs = sorted(a["objs"].items(), key=lambda kv: (-len(kv[1]), kv[0]))[:4]
        ex["did"].append({"verb": pr, "objects": [o for o, _ in objs], "days": fmt_days(a["days"]), "outlets": len(a["ow"]), "edge_ids": a["eids"][:6], "sentence": a["sent"], "pub": a["pub"], "text": "%s %s" % (pr, ", ".join(o for o, _ in objs)) + ((", " + fmt_days(a["days"])) if fmt_days(a["days"]) else ""), "rule": "rule-based: verb + object concepts + date range + outlet count of facts with this concept as subject"})
    # allies / opponents / sources from typed links and '-backed' patterns
    spk = {}; rel = {}
    for l in links:
        if l["rel"] in ("affects_resource",) or cid not in (l["a"], l["b"]): continue
        o = l["b"] if l["a"] == cid else l["a"]
        if o.startswith(("resource:", "process:")) or _kind(o, ents) not in AGENT_KINDS: continue
        x = rel.setdefault(o, {"opp": [], "ally": [], "preds": set(), "ow": 0}); x["preds"] |= set(l.get("preds") or []); x["ow"] = max(x["ow"], l["owners"])
        if l["rel"] == "opposes": x["opp"] += l["edge_ids"]
        elif l["rel"] == "part_of": x["ally"] += l["edge_ids"]
    for eid, role in fe.items():
        e = EB[eid]
        if e.get("kind") != "assertion" or not nre: continue
        o = canon(e.get("obj")) if role == "subject" else canon(e.get("anchor") or e.get("subj"))
        if not o or o == cid or o.startswith(("resource:", "process:")) or _kind(o, ents) not in AGENT_KINDS: continue
        for f in _sents(e):
            if re.search(r"(%s)[\w]*[- ](backed|aligned|allied)|\ballies?\b.{0,40}(%s)" % (nre.pattern, nre.pattern), f["sent"], re.I):
                x = rel.setdefault(o, {"opp": [], "ally": [], "preds": set(), "ow": 1}); x["ally"].append(eid); x["pattern"] = f["sent"]; break
    for o, x in sorted(rel.items(), key=lambda kv: (-len(set(kv[1]["opp"]) | set(kv[1]["ally"])), kv[0])):
        only_speech = x["preds"] and all((p or "").split(" ")[0] in SPEECH or p in SPEECH for p in x["preds"]) and not x["opp"] and not x["ally"]
        it = {"concept": o, "label": _label_of(o, ents), "n": len(set(x["opp"]) | set(x["ally"])), "edge_ids": sorted(set(x["ally"] or x["opp"]))[:6]}
        if only_speech or (_kind(o, ents) == "person" and not x["opp"] and not x["ally"]): ex["sources"].append({k: it[k] for k in ("concept", "label")}); continue
        if x["ally"] and len(x["ally"]) >= len(x["opp"]): ex["allies"].append({**it, "edge_ids": sorted(set(x["ally"]))[:6], "note": x.get("pattern")})
        elif x["opp"]: ex["opponents"].append({**it, "edge_ids": sorted(set(x["opp"]))[:6]})
    if nre:
        have = {a["concept"] for a in ex["allies"]}; pat = re.compile(r"(?:%s)\w*[- ](?:backed|aligned|allied)\s+(?:armed\s+|militant\s+)?(?:group\s+)?((?:the\s+)?[A-Z][\w'\u2019]+(?:\s[A-Z][\w'\u2019]+)?)" % nre.pattern)
        for eid, role in fe.items():
            e = EB[eid]
            if e.get("kind") != "assertion": continue
            for f in _sents(e):
                for m in pat.finditer(f["sent"]):
                    cap = re.sub(r"^the\s+", "", m.group(1), flags=re.I).strip(); cm = next((i for i in sorted(MS, key=lambda i: -len(_label_of(i, ents))) if i != cid and not i.startswith(("resource:", "process:")) and _kind(i, ents) in AGENT_KINDS | {"entity"} and cap.lower() in _norm(_label_of(i, ents))), None)
                    if cm in have or any(a["label"].lower() == cap.lower() for a in ex["allies"]): continue
                    have.add(cm); ex["allies"].append({"concept": cm, "label": _label_of(cm, ents) if cm else cap, "n": 1, "edge_ids": [eid], "note": best_sub(f["sent"], nre), "rule": "rule-based: 'X-backed / aligned / allied' pattern in a fact sentence"})
    ex["allies"] = ex["allies"][:6]; ex["opponents"] = sorted(ex["opponents"], key=lambda r: -r["n"])[:6]; ex["sources"] = ex["sources"][:4]
    ex["effect"] = [d for d in directions if d["object"]][:4]
    for c in cf[:3]:
        eids = [x for x in (c["a"], c["b"]) if x in EB]; ss = []
        for x in eids:
            e = EB[x]; fs = _sents(e)
            if c["kind"] == "polarity":
                for pol in ("positive", "negative"):
                    f = next((f for f in fs if f.get("polarity") == pol), None)
                    if f: ss.append({"stance": pol, "sentence": best_sub(f["sent"], nre), "pub": f.get("pub"), "edge_id": x})
            elif fs: ss.append({"stance": None, "sentence": best_sub(fs[0]["sent"], nre), "pub": fs[0].get("pub"), "edge_id": x})
        if ss: ex["disputed"].append({"kind": c["kind"], "edge_ids": eids or [c["a"]], "reads": ss[:2], "src": c["src"]})
    return ex

# ---------------------------------------------------------------- process concepts
def find_processes(A, canon, F, ents):
    """recurring event clusters: kinetic-family predicates (strike / target / attack / intercept / repel ...) between typed actors that each have >= 2 facts; actors joined by such an edge form one cluster;
    a cluster is a 'process' when >= PROCESS_MIN_OWNERS independent owners read it and it has >= PROCESS_MIN_EDGES edges. Label = most oriented initiator + most oriented target + most frequent predicate (never invented prose)."""
    par = {}
    def fd(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    E = []
    for e in A:
        pr = (e.get("pred") or "").lower().split()
        if not pr or pr[0] not in KIN: continue
        a = canon(e.get("anchor") or e.get("subj")); b = canon(e.get("obj"))
        if not a or not b or a == b or _kind(a, ents) not in AGENT_KINDS or _kind(b, ents) not in AGENT_KINDS or len(F.get(a, ())) < 2 or len(F.get(b, ())) < 2: continue
        E.append((e, a, b)); par[fd(a)] = fd(b)
    comps = collections.defaultdict(list)
    for e, a, b in E: comps[fd(a)].append((e, a, b))
    out = {}
    for root, es in comps.items():
        ow = set(); out_n = collections.Counter(); in_n = collections.Counter(); preds = collections.Counter(); per = collections.defaultdict(list)
        for e, a, b in es:
            for o, w, d in _own_of(e): ow.add(o)
            out_n[a] += 1; in_n[b] += 1; preds[(e.get("pred") or "").lower().split()[0]] += 1; per[a].append(e["id"]); per[b].append(e["id"])
        if len(ow) < PROCESS_MIN_OWNERS or len(es) < PROCESS_MIN_EDGES: continue
        actors = sorted(set(out_n) | set(in_n))
        A_ = max(actors, key=lambda x: (out_n[x] - in_n[x], out_n[x], x)); B_ = max([x for x in actors if x != A_], key=lambda x: (in_n[x] - out_n[x], in_n[x], x))
        pr = preds.most_common(1)[0][0]; plural = pr if pr.endswith("s") else pr + "s"
        pid = "process:" + __import__("hashlib").sha1("|".join(actors).encode()).hexdigest()[:8]
        lab = "%s\u2013%s %s" % (_label_of(A_, ents), _label_of(B_, ents), plural) + (" (+%d actors)" % (len(actors) - 2) if len(actors) > 2 else "")
        _PL[pid] = lab
        out[pid] = {"label": lab, "edge_ids": sorted({e["id"] for e, a, b in es}), "actors": {x: {"role": "initiator" if out_n[x] >= in_n[x] else "target", "out": out_n[x], "in": in_n[x], "edge_ids": sorted(set(per[x]))} for x in actors},
                    "preds": dict(preds), "owners": len(ow), "sides": [A_, B_]}
    return out

# ---------------------------------------------------------------- build
def _w(e): return float(((e.get("decay") or {}).get("weight")) or 0.5)
def _own_of(e):
    """[(owner, decayed weight, day)] one per independent source of the edge (owner-level independence, as consolidate.independence)"""
    out = []
    for s in ((e.get("independent") or {}).get("sources") or []):
        out.append((s.get("owner") or owners_map().get(s.get("pub")) or s.get("pub"), _w(e), s.get("day")))
    if not out:
        for p in e.get("publishers") or []: out.append((owners_map().get(p, p), _w(e), (e.get("days") or [None])[-1]))
    return out
def _cert(sup_for, sup_against): return round(sup_for / (sup_for + sup_against + 1.0), 3)
def _sup(owner_weights): return sum(owner_weights.values())
def _add_ow(d, owner, w): d[owner] = max(d.get(owner, 0.0), w)
def _frag_seq(D, f): return (D["arts"].get(f.get("art")) or {}).get("seq")
def _clip(s, n=240): s = re.sub(r"\s+", " ", str(s or "")).strip(); return s if len(s) <= n else s[:n - 1] + "…"

ROLE_PERSON = {}
def wn_is_a(term, target_off):
    """True when the first noun sense of term has the synset at target_off among its hypernym ancestors (local WordNet)"""
    wn_gloss("war"); p = _WN["idx"].get((term or "").lower().strip().replace(" ", "_"))
    if not p: return False
    try:
        n = int(p[2]); off = p[-n]; d = 0
        with open(WN + "/data.noun", "rb") as f:
            while d < 30:
                if off == target_off: return True
                f.seek(int(off)); l = f.readline().decode("utf-8", "replace").split("|")[0].split(); wc = int(l[3], 16); i = 4 + 2 * wc; pc = int(l[i]); i += 1; h = None
                for k in range(pc):
                    if l[i + 4 * k] in ("@", "@i"): h = l[i + 4 * k + 1]; break
                if not h: return False
                off = h; d += 1
    except Exception: return False
    return False
def is_role_noun(head):
    """a head word whose first WordNet sense is a person or a group of people (commuter, resident, official, soldier, couple); None offsets are looked up from the first sense of 'person' and 'group'"""
    if head in ROLE_PERSON: return ROLE_PERSON[head]
    wn_gloss("war")
    if "_t" not in ROLE_PERSON:
        def first(w):
            p = _WN["idx"].get(w); return p[-int(p[2])] if p else None
        ROLE_PERSON["_t"] = (first("person"), first("group"))
    t1, t2 = ROLE_PERSON["_t"]; r = bool(head and len(head) >= 4 and ((t1 and wn_is_a(head, t1)) or (t2 and wn_is_a(head, t2)))); ROLE_PERSON[head] = r; return r
ROLE = {}
def role_noun_to_process(A, canon, PROC, F, EB, ents):
    """R4: a fact whose subject is a plain role noun (a person or group word by WordNet, no typed entity) and whose predicate is in the kinetic family attaches to the process concept that has that predicate AND shares an article with the fact. Returns {edge id: process id}. ROLE (module state, rebuilt each call) feeds triage."""
    ROLE.clear(); out = {}
    parts = {pid: {f.get("art") for eid in pr["edge_ids"] for f in EB[eid].get("fragments") or []} for pid, pr in PROC.items()}
    for e in A:
        sub = e.get("anchor") or e.get("subj")
        if not sub or not str(sub).startswith("concept:") or canon(sub) != sub: continue
        pr = (e.get("pred") or "").lower().split()
        if not pr or pr[0] not in KIN: continue
        w = _norm(sub[8:]).split()
        if not w or not is_role_noun(w[-1]): continue
        arts = {f.get("art") for f in e.get("fragments") or []}
        c = [pid for pid, p in PROC.items() if pr[0] in p["preds"] and parts[pid] & arts]
        if not c: continue
        pid = max(c, key=lambda q: (len(parts[q] & arts), q)); F[pid].setdefault(e["id"], "mention"); out[e["id"]] = pid; ROLE.setdefault(e["id"], []).append(pid)
    return out

def build(td, area=None):
    D = load(td); K, C, arts, ents = D["K"], D["C"], D["arts"], D["ents"]
    if not isinstance(K, dict) or not C: return {"exists": False, "why": "this window has no slow_consolidate/knowledge.json + consolidated.json"}
    canon = make_canon(ents, None); kedges = K.get("edges") or {}
    A = [e for e in C.get("edges") or [] if e.get("kind") == "assertion"]; R = [e for e in C.get("edges") or [] if e.get("kind") == "resource"]
    # per concept: facts (edges anchored on or pointing at it), owner weights, articles
    F = collections.defaultdict(dict)   # cid -> {edge id: role}
    for e in A:
        s = canon(e.get("anchor") or e.get("subj")); o = canon(e.get("obj"))
        if s: F[s][e["id"]] = "subject" if not canon.rule(e.get("anchor") or e.get("subj")) else "mention"
        if o and o != s: F[o].setdefault(e["id"], "object" if not canon.rule(e.get("obj")) else "mention")
        for x in canon.all(e.get("anchor") or e.get("subj"))[1:] + canon.all(e.get("obj"))[1:]:   # coord: the other conjunct of 'X and Y' carries the fact too (role mention)
            if x != s: F[x].setdefault(e["id"], "mention")
    EB = {e["id"]: e for e in A}
    for e in R: F[e["subj"]][e["id"]] = "resource"; EB[e["id"]] = e
    PROC = find_processes(A, canon, F, ents)
    for pid, pr in PROC.items():
        for eid in pr["edge_ids"]: F[pid][eid] = "process"
    ROLE_ATT = role_noun_to_process(A, canon, PROC, F, EB, ents)
    meta = {}
    for cid, fe in F.items():
        ow = {}; seqs = []; days = set();
        for eid in fe:
            e = EB[eid]
            for o, w, d in _own_of(e) if e.get("kind") != "resource" else [(owners_map().get(p, p), _w(e), (e.get("days") or [None])[-1]) for p in e.get("publishers") or []]: _add_ow(ow, o, w)
            for f in e.get("fragments") or []:
                sq = _frag_seq(D, f)
                if sq is not None: seqs.append(sq)
                if f.get("day"): days.add(f["day"])
        meta[cid] = {"owners": ow, "seqs": seqs, "days": days}
    # membership: typed entities and resources with >= MIN_FACTS facts; plain nouns only with real recurrence
    art_words = collections.defaultdict(set)
    for e in A:
        for f in e.get("fragments") or []:
            if f.get("sent"): art_words[f.get("art")] |= set(re.findall(r"[a-z]+", f["sent"].lower()))
    n_art = max(1, len(art_words)); dropped = []
    members = []; QN = {}
    for cid, fe in F.items():
        k = _kind(cid, ents); n = len(fe); no = len(meta[cid]["owners"])
        if cid.startswith("resource:"):
            if n >= MIN_FACTS: members.append(cid); QN[cid] = (MIN_FACTS, 0)
        elif cid in PROC:
            if no >= PROCESS_MIN_OWNERS: members.append(cid); QN[cid] = (0, PROCESS_MIN_OWNERS)
        elif k == "concept":
            if n >= CONCEPT_MIN_FACTS and no >= CONCEPT_MIN_OWNERS:
                label = _label_of(cid, ents); words = re.findall(r"[A-Za-z]+", label); head = words[-1].lower() if words else ""
                wd = WC.resolve(label); named = bool(wd and wd.get("description") and _norm(wd.get("label")) == _norm(label) and any(ch.isupper() for ch in label))
                df = sum(1 for ws in art_words.values() if head in ws) / n_art; gw = generic_why(head, df) if head else "no alphabetic head word"
                if len(head) < 3: gw = gw or "head word shorter than 3 letters"
                if named: members.append(cid); QN[cid] = (CONCEPT_MIN_FACTS, CONCEPT_MIN_OWNERS)
                elif no >= 3 and not gw: members.append(cid); QN[cid] = (CONCEPT_MIN_FACTS, 3)
                else: dropped.append({"id": cid, "label": label, "owners": no, "facts": n, "why": gw or "fewer than 3 independent owners (plain noun, not a resource, not an identity-linked entity, no cached Wikidata hit)"})
        elif n >= MIN_FACTS: members.append(cid); QN[cid] = (MIN_FACTS, 0)
        elif k in ("person", "org", "place", "entity") and no >= TYPED_MIN_OWNERS: members.append(cid); QN[cid] = (1, TYPED_MIN_OWNERS)   # R3: a typed named entity read by >= 2 independent owners (publishers; a copy by the same owner is not a second article) is a concept even with one distinct fact
    MS = set(members)
    # contradictions: knowledge.json contested pairs + own polarity / direction reversals on the same key
    conflicts = []   # {a, b, kind, art_later, concept}
    for p in K.get("contested") or []:
        conflicts.append({"a": p.get("a"), "b": p.get("b"), "kind": p.get("kind"), "later_edge": (p.get("later") or {}).get("edge"), "src": "knowledge.contested"})
    for e in A:
        pols = collections.defaultdict(set)
        for f in e.get("fragments") or []: pols[f.get("polarity")].add(f.get("art"))
        if pols.get("positive") and pols.get("negative"): conflicts.append({"a": e["id"], "b": e["id"], "kind": "polarity", "later_edge": e["id"], "src": "own: same key read positive and negative"})
    conf_by_concept = collections.defaultdict(list)
    for c in conflicts:
        for eid in (c["a"], c["b"]):
            e = EB.get(eid)
            if e:
                for x in (canon(e.get("anchor") or e.get("subj")), canon(e.get("obj"))):
                    if x in MS and c not in conf_by_concept[x]: conf_by_concept[x].append(c)
    # links
    L = {}
    for e in A:
        a = canon(e.get("subj")); b = canon(e.get("obj"))
        if not a or not b or a == b or a not in MS or b not in MS: continue
        rel = link_rel(e.get("pred"), _kind(a, ents), _kind(b, ents)); key = (a, b, rel); l = L.setdefault(key, {"a": a, "b": b, "rel": rel, "edge_ids": [], "ow": {}, "dir": collections.Counter(), "preds": collections.Counter()})
        l["edge_ids"].append(e["id"]); l["preds"][e.get("pred")] += 1
        for o, w, d in _own_of(e): _add_ow(l["ow"], o, w)
        if (e.get("attrs") or {}).get("direction") in ("up", "down"): l["dir"][e["attrs"]["direction"]] += 1
    for pid, pr in PROC.items():
        if pid not in MS: continue
        for x, v in pr["actors"].items():
            if x not in MS or len(v["edge_ids"]) < 2: continue
            ow = {}
            for eid in v["edge_ids"]:
                for o, w, d in _own_of(EB[eid]): _add_ow(ow, o, w)
            L[(x, pid, "part_of")] = {"a": x, "b": pid, "rel": "part_of", "edge_ids": v["edge_ids"], "ow": ow, "dir": collections.Counter(), "preds": collections.Counter({"%s %s" % (v["role"], k): n for k, n in pr["preds"].items()}), "note": "PROVISIONAL process membership: %s in %d of the cluster's %d kinetic-family edges (out %d, in %d)" % (v["role"], len(v["edge_ids"]), len(pr["edge_ids"]), v["out"], v["in"]), "role": v["role"]}
    # affects_resource: a concept and a resource read in the same articles (>= 2 shared articles and >= 2 shared owners); top 2 resources per concept; co-occurrence, labelled so in 'note'
    res_arts = {}
    for e in R:
        if e["subj"] in MS: res_arts.setdefault(e["subj"], {"arts": set(), "eids": [], "ow": {}}); x = res_arts[e["subj"]]; x["eids"].append(e["id"]); x["arts"] |= {f.get("art") for f in e.get("fragments") or []}
    cart = collections.defaultdict(lambda: collections.defaultdict(set))   # concept -> art -> edge ids
    for cid in MS:
        if cid.startswith("resource:"): continue
        for eid, role in F[cid].items():
            if role == "subject":
                for f in EB[eid].get("fragments") or []: cart[cid][f.get("art")].add(eid)
    for cid in MS:
        if cid.startswith("resource:") or _kind(cid, ents) == "concept": continue
        cand = []
        for rid, x in res_arts.items():
            sh = set(cart[cid]) & x["arts"]
            if len(sh) < 2: continue
            ow = {}
            for a in sh: _add_ow(ow, (arts.get(a) or {}).get("pub") and owners_map().get(arts[a]["pub"], arts[a]["pub"]) or a, 0.8)
            if len(ow) >= 2: cand.append((len(sh), rid, sh, ow))
        for n, rid, sh, ow in sorted(cand, key=lambda t: (-t[0], t[1]))[:2]:
            eids = sorted({eid for a in sh for eid in cart[cid][a]})[:6] + res_arts[rid]["eids"][:3]
            L[(cid, rid, "affects_resource")] = {"a": cid, "b": rid, "rel": "affects_resource", "edge_ids": eids, "ow": ow, "dir": collections.Counter(), "preds": collections.Counter({"co-read in %d articles" % n: 1}), "note": "PROVISIONAL co-occurrence: the concept and the resource are read in the same %d articles; a typed effect (draws/adds/damages) is not read" % n}
    links = []
    for l in L.values():
        sup = _sup(l["ow"]); ag = 0.0
        for c in conf_by_concept.get(l["a"], []):
            if set(l["edge_ids"]) & {c["a"], c["b"]}: ag += 1.0
        d = None
        if l["dir"]["up"] + l["dir"]["down"] >= 2: d = "up" if l["dir"]["up"] > l["dir"]["down"] else "down" if l["dir"]["down"] > l["dir"]["up"] else "flat"
        links.append({"a": l["a"], "b": l["b"], "rel": l["rel"], "direction": d, "certainty": _cert(sup, ag), "owners": len(l["ow"]), "edge_ids": sorted(set(l["edge_ids"]))[:12], "n": len(set(l["edge_ids"])), "preds": [p for p, _ in l["preds"].most_common(3)], **({"note": l["note"]} if l.get("note") else {}), **({"role": l["role"]} if l.get("role") else {})})
    links.sort(key=lambda x: (-x["owners"], -x["n"], x["a"], x["b"]))
    # cards
    last_day = max([d for m in meta.values() for d in m["days"]] or [""])
    out = []
    for cid in sorted(MS, key=lambda c: (-len(F[c]), c)):
        m = meta[cid]; label = _label_of(cid, ents); kind = _kind(cid, ents); fe = F[cid]
        ow = m["owners"]; sup = _sup(ow); cf = conf_by_concept.get(cid, [])
        ag = sum(1.0 for _ in cf)
        # direction: independent owners that read up / down on facts anchored on this concept
        up, dn = {}, {}
        for eid, role in fe.items():
            if role != "subject": continue
            e = EB[eid]
            for f in e.get("fragments") or []:
                dd = f.get("direction"); o = owners_map().get(f.get("pub"), f.get("pub"))
                if dd == "up": _add_ow(up, o, _w(e))
                elif dd == "down": _add_ow(dn, o, _w(e))
        nread = len(set(up) | set(dn)); direction = None; dir_edges = [eid for eid, role in fe.items() if role == "subject" and any(f.get("direction") in ("up", "down") for f in EB[eid].get("fragments") or [])]
        if nread >= 2: direction = "up" if sum(up.values()) > sum(dn.values()) else "down" if sum(dn.values()) > sum(up.values()) else "flat"
        # what it is: only a cited source
        wi = None
        if cid.startswith("resource:"):
            r = resources_csv().get(cid[9:]); wi = {"text": r["definition"], "src": r["source"]} if r and r.get("definition") else None
        elif cid in PROC:
            pr = PROC[cid]; wi = {"text": "Recurring exchange of %s between %d actors (%s), read by %d independent owners in %d facts." % (", ".join("%s x%d" % (k, n) for k, n in sorted(pr["preds"].items(), key=lambda kv: -kv[1])[:3]), len(pr["actors"]), ", ".join(_label_of(x, ents) for x in sorted(pr["actors"])[:5]), pr["owners"], len(pr["edge_ids"])), "src": "derived:process cluster of %d kinetic-family edges (%s...)" % (len(pr["edge_ids"]), ",".join(pr["edge_ids"][:3]))}
        else:
            e0 = ents.get(cid) or {}; names = [label] + [a for a, _ in sorted((e0.get("aliases") or {}).items(), key=lambda kv: -kv[1])[:6]] + ([e0.get("canon")] if e0.get("canon") else [])
            seen = set()
            for nme in names:
                if not nme or nme.lower() in seen: continue
                seen.add(nme.lower()); r = WC.resolve(nme)
                if r and r.get("description") and _norm(r.get("label")) == _norm(nme):
                    wi = {"text": r["description"], "src": "wikidata:%s (cached top hit of %d for '%s', exact label)" % (r["qid"], r.get("n_hits") or 1, nme)}; break
            if not wi and kind == "concept" and len(label.split()) <= 2:
                g = wn_gloss(label.split()[-1] if len(label.split()) > 1 else label)
                wi = g
        # state
        indep_each_side = bool(cf) and len(ow) >= 2
        days = sorted(m["days"]); recent = bool(days) and days[-1] >= last_day[:8] + "%02d" % max(1, int(last_day[8:10]) - 1) if last_day else False
        if cf and indep_each_side: state = "contested"
        elif wi is None and len(ow) < 2: state = "gap"
        elif len(ow) >= MIN_OWNERS_ACTIVE: state = "active" if recent else "settled"
        else: state = "emerging"
        resources = [{"resource": l["b"], "direction": l["direction"], "edge_ids": l["edge_ids"][:6]} for l in links if l["a"] == cid and l["rel"] == "affects_resource"]
        rel_n = collections.defaultdict(lambda: {"n": 0, "cert": 0.0, "rel": "related"})
        for l in links:
            if l["rel"] in ("affects_resource",): continue
            other = l["b"] if l["a"] == cid else l["a"] if l["b"] == cid else None
            if other is None: continue
            x = rel_n[other]; x["n"] += l["n"]; x["cert"] = max(x["cert"], l["certainty"]);
            if l["rel"] != "related" or x["rel"] == "related": x["rel"] = l["rel"]
        related = [{"concept": o, "rel": x["rel"], "n": x["n"], "certainty": x["cert"]} for o, x in sorted(rel_n.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:8]]
        nre = _name_re(_names(cid, ents)) if kind not in ("resource", "process") else None
        directions = _directions(cid, fe, EB, canon, ents, MS) if kind not in ("resource", "process") else []
        sc = None
        if direction is not None and any(d["dir"] != direction for d in directions):
            tot = collections.Counter()
            for d in directions: tot[d["dir"]] += d["owners"]
            hi = max(tot.values()); lo = min(tot.values()) if len(tot) > 1 else 0
            if lo * 2 > hi: direction = None   # up on some objects, down on others: the scalar would mislead
        drivers = _drivers(cid, fe, EB, canon, ents, links, nre, kind) if kind not in ("resource", "process") else []
        extra = _card_extra(cid, kind, fe, EB, canon, ents, links, MS, cf, nre, directions, ow)
        gaps = []
        if wi is None: gaps.append("what_it_is: no Wikidata hit, IPTC node or WordNet gloss in the local caches")
        if direction is None: gaps.append("direction: %d independent owner(s) read up/down, 2 needed%s" % (nread, "; ambiguous across objects" if directions else ""))
        if not drivers: gaps.append("drivers: no causal read (causes) with this concept as the object")
        if not resources: gaps.append("resources: no resource read in the same articles")
        if len(ow) < 2: gaps.append("one owner only")
        dobj = [d for d in directions if d["object"]]
        sf = {"what_it_is": "today" if wi else "cant", "direction": "today" if any(d["owners"] >= 2 for d in dobj) else ("partly" if directions else "cant"),
              "drivers": "today" if any(d["certainty"] >= .5 for d in drivers) else ("partly" if drivers else "cant"), "resources": "today" if resources else "cant",
              "related": "today" if any(r["n"] >= 2 for r in related) else ("partly" if related else "cant")}
        eids = sorted(fe)
        out.append({"id": cid, "label": label, "kind": kind, "depth": "L1", "state": state, "certainty": _cert(sup, ag), "direction": direction, "owners": len(ow), "facts": len(fe),
                    "first_seq": min(m["seqs"]) if m["seqs"] else None, "last_seq": max(m["seqs"]) if m["seqs"] else None,
                    "card": {"what_it_is": wi, "drivers": drivers, "resources": resources, "related": related, "gaps": gaps, **extra}, "slot_fill": sf, "directions": directions, "certainty_word": sureness(len(ow), _cert(sup, ag), bool(cf) and len(ow) >= 2), "edge_ids": eids[:200], "dir_edge_ids": dir_edges[:10], "conflicts": [c["src"] for c in cf][:3]})
    focus = out[0]["id"] if out else None
    # focus = the area's main concept: most facts among entities (not resource, not plain noun) when any
    ent_first = [c for c in out if c["kind"] not in ("resource",)]; focus = (ent_first[0]["id"] if ent_first else focus)
    tri, qseq = triage(D, canon, A, EB, MS, F, links, conflicts, QN)
    for c in out: c["in_graph_from_seq"] = qseq.get(c["id"])
    last = {}
    for t in tri:
        if t.get("change_text"):
            for c_, ch in (t.get("concept_changes") or {}).items(): last.setdefault(c_, []).append({"seq": t["seq"], "art": t["art"], "change_text": ch["text"], "change_kind": ch["kind"], "pub": ch["pub"], "edge_ids": ch["edge_ids"]})   # v2 touch rule: only a fact where the concept is subject or object
    for c in out:
        c["card"]["new"] = sorted(last.get(c["id"], []), key=lambda r: -r["seq"])[:3]
    dc = {k[2]: v["r"]["depth"] for k, v in _CACHE.items() if k[0] == "deep" and k[1] == os.path.abspath(td)}
    for c in out:
        if c["id"] in dc: c["depth"] = dc[c["id"]]
    return {"exists": True, "area": area, "as_of": K.get("as_of"), "n_articles": K.get("articles"), "concepts": out, "links": [{k: v for k, v in l.items() if k not in ("preds",)} for l in links], "triage": tri, "focus": focus, "dropped": sorted(dropped, key=lambda d: (-d["facts"], d["id"])),
            "provisional": True, "rules": "PROVISIONAL v0: certainty = decayed independent-owner support / (support + contradictions + 1); states per design 1.5 (single window: 'settled' = >= 3 owners, nothing new in the last day of the window); triage replays articles in seq order"}

# ---------------------------------------------------------------- triage
# v2 (PROVISIONAL, rule-based): 'known' needs EVERY fact of the article to be a repeat (same slot, owner already counted) on a concept that was in the graph BEFORE this article (incremental membership);
# a fact anchored on no graph concept is shown as new (new_concept, 'unmapped'); any new slot / identity / pair downgrades known; amount, status and negation differences on the same subject+predicate family are conflict candidates.
UNITS = LX.seq("amount.units")   # count units (data, file order kept); the scale units stay here
NUM_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(%|per\s?cent|percent|million|billion|thousand|trillion|k\b" + "".join("|" + re.escape(u) for u in UNITS) + r")?", re.I)
SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
def _amounts(text):
    """the set of (value, unit) amounts in a text: number + unit normalised (percent, million = x1e6, ...); {} when none"""
    out = set()
    for m in NUM_RE.finditer(str(text or "")):
        try: v = float(m.group(1).replace(",", ""))
        except Exception: continue
        u = (m.group(2) or "").lower().replace(" ", "")
        if u in SCALE: v *= SCALE[u]; u = ""
        u = "pct" if u in ("%", "percent", "percent") or u.startswith("per") else u
        if 1900 <= v <= 2100 and not u: continue   # a year is not an amount
        out.add((round(v, 2), u))
    return frozenset(out)
def _strip_amount(text): return _norm(NUM_RE.sub(" ", str(text or "")))
STATUS_GROUPS = LX.groups("change.status_groups")
STATUS_OBJ = LX.groups("change.status_objects")
def _neg_split(pred):
    p = _norm(pred); n = False
    for pre in ("not ", "no longer ", "never ", "fail to ", "fails to ", "failed to ", "did not ", "does not ", "do not ", "cannot "):
        if p.startswith(pre): p = p[len(pre):]; n = True; break
    if re.search(r"n't\b", p): p = re.sub(r"n't\b", "", p).strip(); n = True
    return p.strip(), n
def _status_of(pred):
    """(group index, +1 / -1) when the predicate head is a status word with an opposite, else None"""
    ws = _norm(pred).split(); h = ws[-1] if ws else ""; h0 = ws[0] if ws else ""
    for gi, (pos, neg) in enumerate(STATUS_GROUPS):
        for w in (h0, h):
            if w in pos: return gi, 1
            if w in neg: return gi, -1
    return None
def _obj_status(obj):
    ws = set(_norm(obj).split())
    for gi, (pos, neg) in enumerate(STATUS_OBJ):
        if ws & pos: return gi, 1
        if ws & neg: return gi, -1
    return None
def _qualify(D, MS, F, EB, order, QN):
    """incremental membership: the replay position (index in seq order) at which each final concept first met its own membership rule (facts / independent owners read up to that article)"""
    pos_of = {aid: i for i, (aid, _) in enumerate(order)}; qpos = {}
    for cid in MS:
        if cid.startswith("resource:"): qpos[cid] = -1; continue
        qn = (QN or {}).get(cid, (MIN_FACTS, 0)); nf, no = qn[0], qn[1]; na = qn[2] if len(qn) > 2 else 0; rows = []
        for eid in F.get(cid, {}):
            e = EB.get(eid)
            if not e or e.get("kind") == "resource": continue
            for f in e.get("fragments") or []:
                if f.get("art") in pos_of: rows.append((pos_of[f["art"]], eid, owners_map().get(f.get("pub"), f.get("pub")), f["art"]))
        rows.sort(); es = set(); os_ = set(); as_ = set(); q = None
        for p, eid, ow, ar in rows:
            es.add(eid); os_.add(ow); as_.add(ar)
            if len(es) >= nf and len(os_) >= no and len(as_) >= na: q = p; break
        qpos[cid] = q if q is not None else (rows[-1][0] if rows else -1)
    return pos_of, qpos
def triage(D, canon, A, EB, MS, F, links, conflicts, QN=None):
    arts = D["arts"]; order = sorted(arts.items(), key=lambda kv: (kv[1]["seq"] if kv[1]["seq"] is not None else 1e9)); pos_of, qpos = _qualify(D, MS, F, EB, order, QN)
    qsorted = sorted(qpos.values())
    occ = collections.defaultdict(list)   # art -> [(edge, fragment)]
    for e in A:
        for f in e.get("fragments") or []:
            if f.get("art") in arts: occ[f["art"]].append((e, f))
    later_conf = {c.get("later_edge"): c for c in conflicts}; first_pos = {}
    for aid_, lst in occ.items():
        for e_, f_ in lst: first_pos[e_["id"]] = min(first_pos.get(e_["id"], 10 ** 9), pos_of[aid_])
    seen_key = {}; seen_exact = set(); shown_unm = set(); seen_pair = set(); pol_seen = collections.defaultdict(set); dir_seen = collections.defaultdict(dict); amt_seen = collections.defaultdict(list); neg_seen = collections.defaultdict(set); st_seen = collections.defaultdict(set); out = []
    KR = ("conflict", "update", "new_link", "new_concept")
    for p, (aid, a) in enumerate(order):
        ev = collections.defaultdict(list)   # verdict -> [(concept, edge id, text, name concept)]
        cev = collections.defaultdict(dict)  # concept -> {verdict: (edge id, name concept)}: facts in which the concept is the subject or the object
        fs_of = {}; n_unm = 0; nfacts = 0; done = set()
        for e, f in sorted(occ.get(aid, []), key=lambda t: t[0]["id"]):
            if f.get("sent") and e["id"] not in fs_of: fs_of[e["id"]] = (f["sent"], f.get("pub"), len(edge_owners(e)))
            if e["id"] in done: continue
            done.add(e["id"]); nfacts += 1
            s = canon(e.get("anchor") or e.get("subj")); o = canon(e.get("obj")); ex = list(dict.fromkeys(x for x in canon.all(e.get("anchor") or e.get("subj")) + canon.all(e.get("obj")) + ROLE.get(e["id"], []) if x))
            ing = [x for x in ex if x in MS and qpos[x] < p]; ent = [x for x in ex if x in MS and qpos[x] == p]; ing = list(dict.fromkeys(ing)); ent = list(dict.fromkeys(ent))
            own = owners_map().get(f.get("pub"), f.get("pub")); key = e.get("key") or e["id"]; pol = f.get("polarity"); dd = f.get("direction")
            pb, pneg = _neg_split(e.get("pred")); ob = _strip_amount(e.get("obj")); am = _amounts(e.get("obj"))
            fam = (s, pb, ob); ps = _status_of(pb); os_ = _obj_status(e.get("obj")); osb = _norm(re.sub(r"\b(" + "|".join(sorted({w for g in STATUS_OBJ for side in g for w in side})) + r")\b", " ", str(e.get("obj") or ""), flags=re.I)) if os_ else None
            conflict = False; why = None
            exact = (key, own, pol, dd) in seen_exact   # a verbatim repeat of a read already judged is never a new conflict
            if ing and not exact:
                if pol and any(q != pol for q in pol_seen[key] if q): conflict = True; why = "polarity reversed against an earlier read"
                elif dd in ("up", "down") and s in ing and any(v != dd and ow != own for ow, v in dir_seen[s].items()): conflict = True; why = "direction reversed against an earlier independent read"
                elif e["id"] in later_conf and first_pos.get(e["id"]) == p: conflict = True; why = "contested pair"
                elif (neg_seen[fam] and (not pneg) in neg_seen[fam]): conflict = True; why = "predicate negated against an earlier read of the same fact"
                elif any(((a0 or am) and a0 != am) for a0 in amt_seen[fam]): conflict = True; why = "amount differs from an earlier read of the same subject and predicate"
                elif ps and any((g == ps[0] and sg == -ps[1]) for g, sg in st_seen[(s, ob)]): conflict = True; why = "status reversed against an earlier read of the same subject and object"
                elif os_ and any((g == os_[0] and sg == -os_[1]) for g, sg in st_seen[(s, "obj:" + str(osb), pb)]): conflict = True; why = "object status reversed"
            if conflict: ev["conflict"].append((ing[0] if ing else None, e["id"], why, s)); [cev[x].setdefault("conflict", (e["id"], s)) for x in ing]
            rep = key in seen_key and own in seen_key[key]
            if not ing and not ent:
                if rep and key in shown_unm and not conflict: ev["known"].append((None, e["id"], "verbatim repeat of an unmapped fact already shown", s))
                else: ev["new_concept"].append((None, e["id"], "fact anchored on no graph concept (unmapped)", s)); n_unm += 1; shown_unm.add(key)
            else:
                for x in ent: ev["new_concept"].append((x, e["id"], "first read of this concept in the graph", s)); cev[x].setdefault("new_concept", (e["id"], s))
                if not ent:
                    pair_new = len(ing) == 2 and s != o and (s, o) not in seen_pair and (o, s) not in seen_pair
                    if pair_new: ev["new_link"].append((s, e["id"], "first link between two graph concepts: %s -> %s" % (s, o), s)); [cev[x].setdefault("new_link", (e["id"], s)) for x in ing]
                    elif key in seen_key:
                        if own not in seen_key[key] and not conflict: ev["update"].append((ing[0], e["id"], "another independent owner reads a known fact", s)); [cev[x].setdefault("update", (e["id"], s)) for x in ing]
                        elif not conflict: ev["known"].append((ing[0], e["id"], "same fact, same owner or copy", s))
                    elif not conflict: ev["update"].append((ing[0], e["id"], "new fact on a graph concept", s)); [cev[x].setdefault("update", (e["id"], s)) for x in ing]
            seen_key.setdefault(key, set()).add(own); seen_exact.add((key, own, pol, dd)); pol_seen[key].add(pol); neg_seen[fam].add(pneg); amt_seen[fam].append(am)
            if ps: st_seen[(s, ob)].add(ps)
            if os_: st_seen[(s, "obj:" + str(osb), pb)].add(os_)
            if dd in ("up", "down") and s in MS: dir_seen[s][own] = dd
            if s and o and s != o: seen_pair.add((s, o))
        for v in ("conflict", "new_concept", "new_link", "update", "known"):
            if ev.get(v): break
        else: v = "known"
        top = ev.get(v) or []; cnt = {k: len(x) for k, x in ev.items()}
        c = collections.Counter(x[0] for x in top if x[0]).most_common(1); concept = c[0][0] if c else None
        det = ("%s: " % v) + ", ".join("%d %s" % (n, k) for k, n in sorted(cnt.items(), key=lambda kv: -kv[1])) if cnt else ("known: article carries no extracted fact (nothing to compare)" if not nfacts else "known: no fact of this article touches a concept in the graph")
        if n_unm: det += " (%d unmapped: anchored on no graph concept)" % n_unm
        def text_of(eid, nm): sent, pub, no = fs_of[eid]; return best_sub(sent, _name_re(_names(nm, D["ents"]))) if nm else best_sub(sent), pub
        # change_text: the single most important change sentence of the article (conflict > update > new link > new concept), a real fragment sentence with its publisher; null on a known row
        ct = None; ck = None; cc = None; ce = []; cpub = None
        for kind in KR:
            cands = [(x, fs_of[x[1]]) for x in ev.get(kind, []) if x[1] in fs_of]
            if cands:
                x, (sent, pub, no) = max(cands, key=lambda t: (t[1][2], -abs(len(t[1][0]) - 140), t[0][1]))
                ct, ck, cc, ce = best_sub(sent, _name_re(_names(x[3] or x[0], D["ents"])) if (x[3] or x[0]) else None), kind, x[0], [x[1]]; cpub = pub; break
        # per concept: only a fact in which the concept is the subject or the object (v2: no co-mentioned fact)
        cch = {}
        for cid_, ks in cev.items():
            for kind in KR:
                if kind in ks and ks[kind][0] in fs_of:
                    eid, nm = ks[kind]; t_, pub_ = text_of(eid, cid_); cch[cid_] = {"kind": kind, "text": t_, "pub": pub_, "edge_ids": [eid]}; break
        touched = sorted(cch)
        out.append({"seq": a["seq"], "art": aid, "title": a["title"], "verdict": v, "concept": concept, "detail": det, "edge_ids": sorted({x[1] for x in top})[:8], "pub": a["pub"], "counts": cnt, "unmapped": n_unm, "facts": nfacts,
                    "graph_before": bisect.bisect_left(qsorted, p),
                    "change_text": ct, "change_kind": ck, "change_pub": cpub if ct else None, "change_concept": cc, "change_edge_ids": ce, "touched": touched[:12], "concept_changes": {k: cch[k] for k in touched[:12]}})
    qseq = {cid: (order[q][1]["seq"] if 0 <= q < len(order) else None) for cid, q in qpos.items()}   # replay position at which each concept entered the graph (None = from the start: resource)
    return out, qseq

# ---------------------------------------------------------------- deep pass
def _windows(skip_td):
    ws = []
    if os.path.isdir(STRUCT):
        for d in sorted(os.listdir(STRUCT)):
            for sub in ("trace", ""):
                p = os.path.join(STRUCT, d, sub, "slow_consolidate", "consolidated.json") if sub else os.path.join(STRUCT, d, "slow_consolidate", "consolidated.json")
                if os.path.exists(p) and os.path.abspath(os.path.dirname(os.path.dirname(p))) != os.path.abspath(skip_td): ws.append((d, p)); break
    return ws
def _hist_edges(path):
    k = ("hist", path); mt = os.path.getmtime(path); c = _CACHE.get(k)
    if c and c[0] == mt: return c[1]
    C = _jl(path, {}) or {}; E = [e for e in C.get("edges") or [] if e.get("kind") == "assertion"]
    _CACHE[k] = (mt, E); return E
def fill_score(sf): return round(sum({"today": 1.0, "partly": 0.5, "cant": 0.0}[v] for v in sf.values()) / max(1, len(sf)), 3)
def deep(td, area, cid, box=BOX_S):
    t0 = time.time(); key = ("deep", os.path.abspath(td), cid); B = build(td, area)
    if not B.get("exists"): return {"exists": False, "why": B.get("why")}
    D = load(td)
    c = _CACHE.get(key)
    if c and c["sig"] == (D["K"].get("as_of"), os.path.getmtime(os.path.join(td, "slow_consolidate", "knowledge.json"))): return {**c["r"], "cached": True}
    cc = next((x for x in B["concepts"] if x["id"] == cid), None)
    if cc is None: return {"exists": False, "why": "no concept %r in this area" % cid}
    canon = make_canon(D["ents"], None); EB = {e["id"]: e for e in (D["C"].get("edges") or [])}; ents = D["ents"]; arts = D["arts"]
    eids = [e for e in cc["edge_ids"] if e in EB]
    # L2 structure: sub-concepts (objects of this concept's facts + typed part_of/is_a links), timeline
    sub = {}
    for l in B["links"]:
        if l["b"] == cid and l["rel"] in ("part_of", "is_a"): sub[l["a"]] = {"id": l["a"], "label": _label_of(l["a"], ents), "rel": l["rel"], "facts": l["n"], "edge_ids": l["edge_ids"][:4]}
    for eid in eids:
        e = EB[eid]
        if canon(e.get("anchor") or e.get("subj")) == cid:
            o = canon(e.get("obj"))
            if o and o != cid and o not in sub and len(_label_of(o, ents).split()) <= 6 and o.split(":", 1)[0] != "resource" and _has_letters(_label_of(o, ents)):
                rel = link_rel(e.get("pred"), _kind(cid, ents), _kind(o, ents)); sub[o] = {"id": o, "label": _label_of(o, ents), "rel": rel if rel != "related" else "related", "facts": 0, "edge_ids": []}
            if o in sub: sub[o]["facts"] += 1; sub[o]["edge_ids"].append(eid) if len(sub[o]["edge_ids"]) < 4 else None
    mset = {c["id"] for c in B["concepts"]}   # rule 6: a subconcept passes the concept rule (is a member of the graph) or appears in >= 2 facts with the parent
    subconcepts = sorted([x for x in sub.values() if x["id"] in mset or x["facts"] >= 2], key=lambda s: (-s["facts"], s["id"]))[:14]
    tl = []
    for eid in eids:
        e = EB[eid]
        if e.get("kind") != "assertion": continue
        for f in (e.get("fragments") or [])[:1]:
            a = arts.get(f.get("art")) or {}; tl.append({"seq": a.get("seq"), "day": f.get("day"), "text": _clip(f.get("sent") or e.get("key")), "edge_id": eid, "pubs": sorted(e.get("publishers") or [f.get("pub")])})
    tl.sort(key=lambda r: ((r["day"] or ""), r["seq"] if r["seq"] is not None else 1e9, r["edge_id"]))
    # L3: competing accounts (speech facts and reversed reads), history before the window (other windows' own caches), open questions
    acc = []
    for eid in eids:
        e = EB[eid]
        if e.get("kind") != "assertion": continue
        pr = (e.get("pred") or "").lower(); pols = {f.get("polarity") for f in e.get("fragments") or []}
        if pr in SPEECH or "negative" in pols:
            sp = canon(e.get("anchor") or e.get("subj")); who = _label_of(sp, ents) if sp else "?"
            acc.append({"claim": _clip((e.get("obj_text") or str(e.get("obj")).split(":", 1)[-1]), 200), "pubs": sorted(e.get("publishers") or []), "stance": ("denied (read negative)" if "negative" in pols else "said by %s" % who), "edge_ids": [eid]})
    if time.time() - t0 > box: return _finish(key, cc, subconcepts, tl, acc, [], [], t0, D, True)
    hist = []; hist_dir = collections.Counter(); hist_pairs = []
    names = {_norm(cc["label"])} | {_norm(a) for a in ((ents.get(cid) or {}).get("aliases") or {})} | {_norm((ents.get(cid) or {}).get("canon"))}
    names.discard("")
    for wname, p in _windows(td):
        if time.time() - t0 > box * 0.8: break
        try: E = _hist_edges(p)
        except Exception: continue
        for e in E:
            an = e.get("anchor") or e.get("subj") or ""
            if an == cid or _norm(an.split(":", 1)[-1]) in names:
                f = (e.get("fragments") or [{}])[0]; hist.append({"window": wname, "text": _clip(f.get("sent") or e.get("key")), "edge_id": e["id"], "day": f.get("day")})
                dd = (e.get("attrs") or {}).get("direction")
                if dd in ("up", "down"): hist_dir[dd] += 1
                if (e.get("pred") or "") in CAUSE: hist_pairs.append(e["id"])
    hist.sort(key=lambda r: (r["window"], r["day"] or "")); hist = [{k: v for k, v in h.items() if k != "day"} for h in hist][:40]
    return _finish(key, cc, subconcepts, tl, acc, hist, (hist_dir, hist_pairs), t0, D, False, B, EB, canon)

def _finish(key, cc, subconcepts, tl, acc, hist, hextra, t0, D, cut, B=None, EB=None, canon=None):
    before = dict(cc["slot_fill"]); after = dict(before); filled = []; oq = []
    hist_dir, hist_pairs = hextra if hextra else (collections.Counter(), [])
    wi = cc["card"]["what_it_is"]
    # try to close what_it_is from the local packs by the nodes the facts landed on
    if not wi and B and EB:
        ip = collections.Counter();
        for eid in cc["edge_ids"]:
            n = ((EB.get(eid) or {}).get("iptc") or {}).get("node")
            if n: ip[n] += 1
        if ip:
            n = ip.most_common(1)[0][0]; d = iptc_defs().get(n) or {}
            if d.get("definition"): wi = {"text": "Topic its facts landed on: %s. %s" % (d.get("label"), d["definition"]), "src": "iptc:%s (the node %d of its facts landed on; not a definition of this concept itself)" % (n, ip[n])}; after["what_it_is"] = "partly"; filled.append("what_it_is")
    if cc["slot_fill"]["direction"] == "cant" and sum(hist_dir.values()) >= 1 and hist_dir: after["direction"] = "partly"; filled.append("direction")
    if cc["slot_fill"]["drivers"] == "cant" and hist_pairs: after["drivers"] = "partly"; filled.append("drivers")
    if cc["slot_fill"]["related"] == "cant" and subconcepts: after["related"] = "partly"; filled.append("related")
    ids = cc["edge_ids"][:6]
    oq.append({"q": "What is %s?" % cc["label"], "status": "answered" if (wi or cc["card"]["what_it_is"]) else "unknown", "answer": (wi or cc["card"]["what_it_is"] or {}).get("text") if (wi or cc["card"]["what_it_is"]) else None, "edge_ids": ids if wi else [], "src": (wi or {}).get("src") if wi else None})
    oq.append({"q": "Which direction is it moving?", "status": "answered" if cc["direction"] else "unknown", "answer": ("%s (>= 2 independent owners)" % cc["direction"]) if cc["direction"] else (("earlier windows read %d up/down fact(s); not enough owners in this window" % sum(hist_dir.values())) if hist_dir else None), "edge_ids": cc.get("dir_edge_ids", [])})
    oq.append({"q": "What drives it?", "status": "answered" if cc["card"]["drivers"] else "unknown", "answer": "; ".join(d.get("text") or d.get("label") or str(d["concept"]) for d in cc["card"]["drivers"]) or None, "edge_ids": [x for d in cc["card"]["drivers"] for x in d["edge_ids"]][:6]})
    oq.append({"q": "Which resources does it touch?", "status": "answered" if cc["card"]["resources"] else "unknown", "answer": ", ".join(r["resource"] for r in cc["card"]["resources"]) or None, "edge_ids": [x for r in cc["card"]["resources"] for x in r["edge_ids"]][:6]})
    oq.append({"q": "Do accounts disagree about it?", "status": "answered" if (cc["conflicts"] or acc) else "unknown", "answer": ("%d speech or denied read(s)%s" % (len(acc), "; conflicts: " + ", ".join(cc["conflicts"]) if cc["conflicts"] else "; no recorded conflict")) if (cc["conflicts"] or acc) else None, "edge_ids": [x for a in acc for x in a["edge_ids"]][:6]})
    depth = "L3" if (not cut) else "L2"
    r = {"concept": cc["id"], "label": cc["label"], "depth": depth, "ms": int((time.time() - t0) * 1000), "subconcepts": subconcepts, "timeline": tl, "accounts": acc[:20], "open_questions": oq, "history": hist,
         "card_fill_before": fill_score(before), "card_fill_after": fill_score(after), "slot_fill_before": before, "slot_fill_after": after, "filled_by_deep": filled, "what_it_is_after": wi, "time_box_s": BOX_S, "time_boxed_cut": cut,
         "note": "PROVISIONAL: own data and local caches only (no network); history = the other windows' consolidated.json, matched by the entity's surface names"}
    sigv = (D["K"].get("as_of"), os.path.getmtime(os.path.join(D["td"], "slow_consolidate", "knowledge.json")))
    _CACHE[key] = {"sig": sigv, "r": r}; return r
