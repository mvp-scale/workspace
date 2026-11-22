"""concepts_v0: concept layer v0 (PROVISIONAL, unmeasured). Builds, from what the pipeline already wrote for one window, a graph of concept cards + typed links + a per-article triage,
and a time-boxed "deep pass" for one concept. Design: concept-delta-design.md sections 1.1-1.6 (card, relations, certainty, states, triage); owner zoom levels L0 street map / L1 card / L2 structure / L3 deep.
Inputs (read only, nothing is written, no network, no hosted model, no download): <trace>/slow_consolidate/knowledge.json + consolidated.json, <trace>/g4/store.jsonl (identity entities),
<trace>/chain.jsonl (article seq/title/publisher), /workspace/data/anchors/wikidata_cache (cache only), IPTC medtop.json + WordNet data.noun (local packs), probes/persona/rules_v2/resources.csv,
and, for the deep pass, the other windows under demo/mockups/structure-live/*/trace/slow_consolidate (history before this window).
Rules (all stated guesses): certainty = sum(decayed weight of independent owners) / (that + decayed contradiction support + 1); direction needs >= 2 independent owners reading up/down else null;
what_it_is only from a cached Wikidata hit (exact label), the IPTC definition of the node the facts landed on, or a WordNet gloss for a plain noun, never invented; links typed by predicate class rules, else 'related'.
Contract: GET /api/raw/concepts and /api/raw/deep (simulation/server.py -> raw-units.py concepts(), deep())."""
import os, re, sys, json, time, collections

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import wikidata_cache as WC
STRUCT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "demo", "mockups", "structure-live"))
RES_CSV = "/workspace/probes/persona/rules_v2/resources.csv"; IPTC = "/workspace/data/ontology_src/iptc/medtop.json"; WN = "/workspace/data/ontology_src/wordnet/wordnet"
MIN_FACTS = 2; MIN_OWNERS_ACTIVE = 3; CONCEPT_MIN_FACTS = 3; CONCEPT_MIN_OWNERS = 2; BOX_S = 120.0
SPEECH = {"say", "tell", "report", "claim", "add", "state", "warn", "say in", "say that", "according", "note", "announce", "confirm", "deny", "describe", "write"}
CAUSE = {"cause", "lead to", "trigger", "spark", "result in", "prompt", "force", "drive", "provoke", "induce", "contribute to", "bring about", "set off"}
PART = {"belong to", "part of", "include", "contain", "member of", "comprise", "consist of", "host", "have", "own"}
ISA = {"be", "become", "be a", "serve as", "remain"}
OPPOSE = {"strike", "target", "attack", "hit", "destroy", "intercept", "fight", "threaten", "fire at", "shoot", "bomb", "oppose", "clash with", "kill", "launch at", "retaliate", "sanction", "blame", "accuse", "condemn"}
AGENT_KINDS = {"person", "org", "place"}
_CACHE = {}; _RES = {}; _WN = {}; _IP = {}; _OW = {}

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
    return {"person": "person", "org": "org", "group": "org", "iso": "place", "place": "place", "facility": "place", "resource": "resource", "cap": "capability", "concept": "concept"}.get(p, "entity" if p in ("event", "work", "product", "disease", "substance", "other", "unk") else "concept")
def make_canon(ents, edge_ids_seen):
    """concept: names that equal a typed entity's label (or one of its aliases) merge into that entity ('merge iso/concept names already handled' by G4; the leftover same-label concept: ids are merged here)"""
    typed = {}
    for cid, e in ents.items():
        if cid.split(":", 1)[0] in ("concept", "resource", "cap"): continue
        names = {_norm(e.get("canon"))} | {_norm(a) for a in (e.get("aliases") or {})}
        for n in names:
            if n and n not in typed: typed[n] = cid
    def canon(x):
        if not x: return None
        if not x.startswith("concept:"): return x
        return typed.get(_norm(x[8:]), x)
    return canon
def link_rel(pred, a_kind, b_kind):
    p = (pred or "").lower().strip()
    if p in ISA: return "is_a"
    if p in PART: return "part_of"
    if p in CAUSE: return "causes"
    if p in OPPOSE and a_kind in AGENT_KINDS and b_kind in AGENT_KINDS: return "opposes"
    return "related"

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

def build(td, area=None):
    D = load(td); K, C, arts, ents = D["K"], D["C"], D["arts"], D["ents"]
    if not isinstance(K, dict) or not C: return {"exists": False, "why": "this window has no slow_consolidate/knowledge.json + consolidated.json"}
    canon = make_canon(ents, None); kedges = K.get("edges") or {}
    A = [e for e in C.get("edges") or [] if e.get("kind") == "assertion"]; R = [e for e in C.get("edges") or [] if e.get("kind") == "resource"]
    # per concept: facts (edges anchored on or pointing at it), owner weights, articles
    F = collections.defaultdict(dict)   # cid -> {edge id: role}
    for e in A:
        s = canon(e.get("anchor") or e.get("subj")); o = canon(e.get("obj"))
        if s: F[s][e["id"]] = "subject"
        if o and o != s: F[o].setdefault(e["id"], "object")
    EB = {e["id"]: e for e in A}
    for e in R: F[e["subj"]][e["id"]] = "resource"; EB[e["id"]] = e
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
    members = []
    for cid, fe in F.items():
        k = _kind(cid, ents); n = len(fe); no = len(meta[cid]["owners"])
        if cid.startswith("resource:"):
            if n >= MIN_FACTS: members.append(cid)
        elif k == "concept":
            if n >= CONCEPT_MIN_FACTS and no >= CONCEPT_MIN_OWNERS: members.append(cid)
        elif n >= MIN_FACTS: members.append(cid)
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
        links.append({"a": l["a"], "b": l["b"], "rel": l["rel"], "direction": d, "certainty": _cert(sup, ag), "owners": len(l["ow"]), "edge_ids": sorted(set(l["edge_ids"]))[:12], "n": len(set(l["edge_ids"])), "preds": [p for p, _ in l["preds"].most_common(3)], **({"note": l["note"]} if l.get("note") else {})})
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
        drivers = [{"concept": l["a"], "rel": "causes", "certainty": l["certainty"], "edge_ids": l["edge_ids"][:6]} for l in links if l["b"] == cid and l["rel"] == "causes"]
        resources = [{"resource": l["b"], "direction": l["direction"], "edge_ids": l["edge_ids"][:6]} for l in links if l["a"] == cid and l["rel"] == "affects_resource"]
        rel_n = collections.defaultdict(lambda: {"n": 0, "cert": 0.0, "rel": "related"})
        for l in links:
            if l["rel"] in ("affects_resource",): continue
            other = l["b"] if l["a"] == cid else l["a"] if l["b"] == cid else None
            if other is None: continue
            x = rel_n[other]; x["n"] += l["n"]; x["cert"] = max(x["cert"], l["certainty"]);
            if l["rel"] != "related" or x["rel"] == "related": x["rel"] = l["rel"]
        related = [{"concept": o, "rel": x["rel"], "n": x["n"], "certainty": x["cert"]} for o, x in sorted(rel_n.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:8]]
        gaps = []
        if wi is None: gaps.append("what_it_is: no Wikidata hit, IPTC node or WordNet gloss in the local caches")
        if direction is None: gaps.append("direction: %d independent owner(s) read up/down, 2 needed" % nread)
        if not drivers: gaps.append("drivers: no causal read (causes) with this concept as the object")
        if not resources: gaps.append("resources: no resource read in the same articles")
        if len(ow) < 2: gaps.append("one owner only")
        sf = {"what_it_is": "today" if wi else "cant", "direction": "today" if direction else ("partly" if nread == 1 else "cant"),
              "drivers": "today" if any(d["certainty"] >= .5 for d in drivers) else ("partly" if drivers else "cant"), "resources": "today" if resources else "cant",
              "related": "today" if any(r["n"] >= 2 for r in related) else ("partly" if related else "cant")}
        eids = sorted(fe)
        out.append({"id": cid, "label": label, "kind": kind, "depth": "L1", "state": state, "certainty": _cert(sup, ag), "direction": direction, "owners": len(ow), "facts": len(fe),
                    "first_seq": min(m["seqs"]) if m["seqs"] else None, "last_seq": max(m["seqs"]) if m["seqs"] else None,
                    "card": {"what_it_is": wi, "drivers": drivers, "resources": resources, "related": related, "gaps": gaps}, "slot_fill": sf, "edge_ids": eids[:200], "dir_edge_ids": dir_edges[:10], "conflicts": [c["src"] for c in cf][:3]})
    focus = out[0]["id"] if out else None
    # focus = the area's main concept: most facts among entities (not resource, not plain noun) when any
    ent_first = [c for c in out if c["kind"] not in ("resource",)]; focus = (ent_first[0]["id"] if ent_first else focus)
    tri = triage(D, canon, A, EB, MS, F, links, conflicts)
    dc = {k[2]: v["r"]["depth"] for k, v in _CACHE.items() if k[0] == "deep" and k[1] == os.path.abspath(td)}
    for c in out:
        if c["id"] in dc: c["depth"] = dc[c["id"]]
    return {"exists": True, "area": area, "as_of": K.get("as_of"), "n_articles": K.get("articles"), "concepts": out, "links": [{k: v for k, v in l.items() if k not in ("preds",)} for l in links], "triage": tri, "focus": focus,
            "provisional": True, "rules": "PROVISIONAL v0: certainty = decayed independent-owner support / (support + contradictions + 1); states per design 1.5 (single window: 'settled' = >= 3 owners, nothing new in the last day of the window); triage replays articles in seq order"}

# ---------------------------------------------------------------- triage
def triage(D, canon, A, EB, MS, F, links, conflicts):
    arts = D["arts"]; order = sorted(arts.items(), key=lambda kv: (kv[1]["seq"] if kv[1]["seq"] is not None else 1e9))
    occ = collections.defaultdict(list)   # art -> [(edge, fragment)]
    for e in A:
        for f in e.get("fragments") or []:
            if f.get("art") in arts: occ[f["art"]].append((e, f))
    later_conf = {c.get("later_edge"): c for c in conflicts}
    seen_key = {}; seen_c = set(); seen_pair = set(); pol_seen = collections.defaultdict(set); dir_seen = collections.defaultdict(dict); out = []
    for aid, a in order:
        ev = collections.defaultdict(list)   # verdict -> [(concept, edge id, text)]
        for e, f in sorted(occ.get(aid, []), key=lambda t: t[0]["id"]):
            s = canon(e.get("anchor") or e.get("subj")); o = canon(e.get("obj")); touch = [x for x in (s, o) if x in MS]
            if not touch: continue
            own = owners_map().get(f.get("pub"), f.get("pub")); key = e.get("key") or e["id"]; pol = f.get("polarity"); dd = f.get("direction")
            conflict = False
            if pol and any(p != pol for p in pol_seen[key] if p): conflict = True
            if dd in ("up", "down") and s in MS and any(v != dd and ow != own for ow, v in dir_seen[s].items()): conflict = True
            if e["id"] in later_conf: conflict = True
            if conflict: ev["conflict"].append((s if s in MS else o, e["id"], "polarity/direction reversed against an earlier read"))
            new_c = [x for x in touch if x not in seen_c]
            for x in new_c: ev["new_concept"].append((x, e["id"], "first read of this concept"))
            pair_new = s in MS and o in MS and s != o and (s, o) not in seen_pair and (o, s) not in seen_pair
            if pair_new and not new_c: ev["new_link"].append((s, e["id"], "first link between two known concepts: %s -> %s" % (s, o)))
            elif key in seen_key:
                if own not in seen_key[key] and not conflict: ev["update"].append((touch[0], e["id"], "another independent owner reads a known fact"))
                else: ev["known"].append((touch[0], e["id"], "same fact, same owner or copy"))
            elif not conflict and not new_c and not pair_new: ev["update"].append((touch[0], e["id"], "new fact on a known concept"))
            seen_key.setdefault(key, set()).add(own); pol_seen[key].add(pol)
            if dd in ("up", "down") and s in MS: dir_seen[s][own] = dd
            seen_c.update(touch)
            if s in MS and o in MS: seen_pair.add((s, o))
        for v in ("conflict", "new_concept", "new_link", "update", "known"):
            if ev.get(v): break
        else: v = "known"
        top = ev.get(v) or []; cnt = {k: len(x) for k, x in ev.items()}
        c = collections.Counter(x[0] for x in top).most_common(1); concept = c[0][0] if c else None
        det = ("%s: " % v) + ", ".join("%d %s" % (n, k) for k, n in sorted(cnt.items(), key=lambda kv: -kv[1])) if cnt else "known: no fact of this article touches a concept in the graph"
        out.append({"seq": a["seq"], "art": aid, "title": a["title"], "verdict": v, "concept": concept, "detail": det, "edge_ids": sorted({x[1] for x in top})[:8], "pub": a["pub"], "counts": cnt})
    return out

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
            if o and o != cid and o not in sub and len(_label_of(o, ents).split()) <= 6 and o.split(":", 1)[0] != "resource":
                rel = link_rel(e.get("pred"), _kind(cid, ents), _kind(o, ents)); sub[o] = {"id": o, "label": _label_of(o, ents), "rel": rel if rel != "related" else "related", "facts": 0, "edge_ids": []}
            if o in sub: sub[o]["facts"] += 1; sub[o]["edge_ids"].append(eid) if len(sub[o]["edge_ids"]) < 4 else None
    subconcepts = sorted(sub.values(), key=lambda s: (-s["facts"], s["id"]))[:14]
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
    oq.append({"q": "What drives it?", "status": "answered" if cc["card"]["drivers"] else "unknown", "answer": ", ".join(d["concept"] for d in cc["card"]["drivers"]) or None, "edge_ids": [x for d in cc["card"]["drivers"] for x in d["edge_ids"]][:6]})
    oq.append({"q": "Which resources does it touch?", "status": "answered" if cc["card"]["resources"] else "unknown", "answer": ", ".join(r["resource"] for r in cc["card"]["resources"]) or None, "edge_ids": [x for r in cc["card"]["resources"] for x in r["edge_ids"]][:6]})
    oq.append({"q": "Do accounts disagree about it?", "status": "answered" if (cc["conflicts"] or acc) else "unknown", "answer": ("%d speech or denied read(s)%s" % (len(acc), "; conflicts: " + ", ".join(cc["conflicts"]) if cc["conflicts"] else "; no recorded conflict")) if (cc["conflicts"] or acc) else None, "edge_ids": [x for a in acc for x in a["edge_ids"]][:6]})
    depth = "L3" if (not cut) else "L2"
    r = {"concept": cc["id"], "label": cc["label"], "depth": depth, "ms": int((time.time() - t0) * 1000), "subconcepts": subconcepts, "timeline": tl, "accounts": acc[:20], "open_questions": oq, "history": hist,
         "card_fill_before": fill_score(before), "card_fill_after": fill_score(after), "slot_fill_before": before, "slot_fill_after": after, "filled_by_deep": filled, "what_it_is_after": wi, "time_box_s": BOX_S, "time_boxed_cut": cut,
         "note": "PROVISIONAL: own data and local caches only (no network); history = the other windows' consolidated.json, matched by the entity's surface names"}
    sigv = (D["K"].get("as_of"), os.path.getmtime(os.path.join(D["td"], "slow_consolidate", "knowledge.json")))
    _CACHE[key] = {"sig": sigv, "r": r}; return r
