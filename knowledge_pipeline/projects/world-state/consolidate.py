"""consolidate: two clocks v0 (plan step 6; playbook 00 section 18 items 3 and 4). The fast clock writes the durable stores while articles arrive; this is the slow clock: an offline pass run at checkpoints over them. Read-only on the inputs, no model, CPU only.
    python3 consolidate.py [--trace <trace folder or chain.jsonl>] [--journal <journal.jsonl>] [--g4 <store.jsonl> ...] [--ticks <ticks.jsonl> ...] [--out <consolidated.json>]
Inputs (each optional, missing ones are skipped): runs/journal/journal.jsonl (journal.Durable), runs/g4/store.jsonl and runs/g4/archive/store.jsonl-* (G4 stores of earlier runs), the resource tick log written by `ledger_split.py --state <json> --persist <ticks.jsonl>`, and a live-trace folder (its lines carry the story keys, publisher and day).
What it does:
  1. Story identity: every item (trace line, journal row) is replayed through journal.classify in (day, id) order, so a syndicated copy resolves to the root of its story; an item with no key is its own story. This is journal.py's logic, not a second one.
  2. Merge: the same assertion (G4 key: subject | predicate | object) in several runs, stores and days becomes ONE edge that keeps every supporting fragment (article, publisher, day, sentence, spans) and a lineage line per input record merged. A resource tick log gives one edge per (resource, country).
     Fragments are deduplicated by (article, sentence), so replaying an input adds nothing.
  3. Strength = the number of independent publishers (fact-join fix, T158 L2954): fragments are grouped into sources, one group per story root (journal copies, T07) OR per near-identical sentence across outlets (content-token Jaccard >= SYN_JACCARD on >= SYN_MIN_TOK tokens: a wire copy is one source
     even when the journal did not catch it); each source is named by the publisher of its earliest fragment (the fragment's own publisher, not the story root's). Strength = distinct source publishers; `independent` lists the sources and what collapsed. `fragments` and `stories` are listed beside it.
  3b. Fact slots (the join): assertion edges with the same anchor (same subject id; concept-like subjects also meet by head word + containment, 'zoo' in 'cincinnati zoo') are compared pairwise by fact_join.Scorer (ECB+-trained pair scorer, e5-small-v2 features, CPU) and merged by average linkage at the model's threshold,
     with hard gates (different status class, opposite direction, different amount / date bucket, different place ids, disjoint objects, differing numbers in the object text never merge); complete linkage, so every pair in a slot clears the threshold. A merged slot keeps every member (key, predicate, object, fragments) under `slot`, its id is h('slot | ' + sorted member keys), its predicate/object are the member with most fragments.
     Without fact_join (or its model) the fallback is 'same predicate lemma' and `join.mode` says so. Everything PROVISIONAL.
  4. Candidates: a G4 concept entity that is neither an IPTC label nor a WordNet noun, seen in >= MIN_WINDOWS time windows (WINDOW_DAYS days each) and by >= MIN_PUBLISHERS independent publishers, is listed as `ours:<slug>`, status PROVISIONAL. Nothing here promotes it: there is no promote step and no human review; status stays PROVISIONAL (T08).
     A candidate's is_a parent is the IPTC node its entity was placed on (if any); the is_a graph over IPTC + ours is kept acyclic by IsA.add (a parent that would close a cycle is refused and counted).
Output is canonical JSON with a sha256 of its body (no clock inside), so two passes over the same inputs give the same sha256."""
import os, sys, re, json, glob, hashlib, collections, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import journal as J
ROOT = os.path.dirname(os.path.dirname(HERE)); SRC = "/workspace/data/ontology_src"
VERSION = "consolidate-v0"; WINDOW_DAYS = 7; MIN_WINDOWS = 2; MIN_PUBLISHERS = 3
def h(s): return hashlib.sha1(s.encode()).hexdigest()[:12]
def canon(o): return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
def _dec(v):   # the G4 store's tagged JSON (g4-align.Store._enc), without numpy: dict, set, tuple, list
    if isinstance(v, list): return [_dec(x) for x in v]
    if isinstance(v, dict):
        if "__d" in v: return {_dec(k): _dec(x) for k, x in v["__d"]}
        if "__s" in v: return {_dec(x) if not isinstance(_dec(x), list) else tuple(_dec(x)) for x in v["__s"]}
        if "__t" in v: return tuple(_dec(x) for x in v["__t"])
    return v
def window(day):
    try: return datetime.date.fromisoformat(day[:10]).toordinal() // WINDOW_DAYS
    except (TypeError, ValueError): return None
# ---------- loaders: each gives plain dicts, nothing is written ----------
_IRR = {"is": "be", "was": "be", "were": "be", "been": "be", "has": "have", "had": "have", "does": "do", "did": "do", "done": "do", "went": "go", "gone": "go", "made": "make", "said": "say", "took": "take", "taken": "take", "gave": "give", "given": "give", "began": "begin", "begun": "begin", "held": "hold", "led": "lead", "left": "leave", "lost": "lose", "met": "meet", "paid": "pay", "ran": "run", "sold": "sell", "set": "set", "told": "tell", "won": "win", "died": "die", "dying": "die", "dead": "die", "hit": "hit", "cut": "cut", "put": "put", "shot": "shoot", "fell": "fall", "fallen": "fall", "rose": "rise", "risen": "rise", "sent": "send", "built": "build", "brought": "bring", "found": "find", "kept": "keep", "got": "get", "became": "become", "came": "come", "saw": "see", "seen": "see", "knew": "know", "known": "know", "thought": "think", "wrote": "write", "written": "write", "drove": "drive", "driven": "drive"}
_DET = {"a", "an", "the", "its", "his", "her", "their", "our", "my", "your", "this", "that", "these", "those", "some", "any", "of"}
def lemma_verb(w):
    """suffix lemma for a verb token with a small irregular table (no model): carries/carried/carrying -> carry, causing -> cause, stopped -> stop"""
    w = w.lower()
    if w in _IRR: return _IRR[w]
    if len(w) > 4 and w.endswith("ies"): return w[:-3] + "y"
    if len(w) > 4 and w.endswith("ied"): return w[:-3] + "y"
    for suf in ("ing", "ed"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            b = w[:-len(suf)]
            if len(b) > 2 and b[-1] == b[-2] and b[-1] not in "aeiouslz": return b[:-1]   # stopped -> stop
            return b + "e" if re.search(r"(ais|ois|uis|eas|ous|ov|iv|uc|ac|ic|uz|iz|rg|ng|ag|ak|at|ut|ur|ir|us|ad|id|ud|um|im|ip|op|ar|ep)$", b) and not re.search(r"(ent|ount|ist|ast|est)$", b) and (suf == "ed" or not re.search(r"[bcdfghjklmnpqrstvwxz]{2}$", b)) else b
    if len(w) > 3 and w.endswith("es") and w[:-2].endswith(("s", "x", "z", "ch", "sh")): return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"): return w[:-1]
    return w
def cnorm(obj):
    """object phrase -> lower case, no determiners, head noun singular: 'the attacks' -> 'attack', 'energy bills' -> 'energy bill'"""
    t = [x for x in re.findall(r"[a-z0-9]+", obj.lower()) if x not in _DET]
    if t:
        w = t[-1]
        if len(w) > 4 and w.endswith("ies"): w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith(("sses", "xes", "ches", "shes")): w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")): w = w[:-1]
        t[-1] = w
    return " ".join(t)
def norm_cap(label):
    """verb-object label -> 'lemma-verb normalised-object' (defect 5): 'carried out attacks' and 'carry attack' meet; a one-word label is its lemma"""
    t = label.lower().split(None, 1)
    return " ".join(x for x in (lemma_verb(t[0]), cnorm(t[1]) if len(t) > 1 else "") if x) if t else ""
def cap_id(label): return "cap:" + re.sub(r"[^a-z0-9]+", "-", norm_cap(label)).strip("-")
def chain_stage(l, name):
    for s in l.get("stages") or []:
        if s.get("name") == name: return s
    return {}
def chain_caps(l):
    """one chain line -> its capability_list stage as [{id, label, kind}] (recurring first); [] when the stage found none. Ids are slugs of the verb-object label: an id, not a promotion."""
    o = chain_stage(l, "capability_list").get("out") or {}; out = []; seen = set()
    for kind in ("recurring", "candidate"):
        for lab in o.get(kind) or []:
            if cap_id(lab) not in seen: seen.add(cap_id(lab)); out.append({"id": cap_id(lab), "label": norm_cap(lab), "raw": lab, "kind": kind})
    return out
def chain_place(l):
    """one chain line -> (domain, area) as the chain's own roll-up and area head named them (top answer, only when the stage ran), else None"""
    d = chain_stage(l, "domain_rollup"); a = chain_stage(l, "area_function"); t = ((d.get("out") or {}).get("top") or [[None]])[0][0] if d.get("state") == "ran" else None
    u = (((a.get("out") or {}).get("topic") or [[None]])[0][0]) if a.get("state") == "ran" else None
    return t, u
def load_trace(path):
    """live-trace chain.jsonl (or its folder) -> items [{id, source, day, keys, seq, file, caps, domain, area}]"""
    p = os.path.join(path, "chain.jsonl") if os.path.isdir(path) else path; out = []
    if not os.path.exists(p): return out
    for ln in open(p, encoding="utf-8"):
        if not ln.strip(): continue
        l = json.loads(json.loads(ln)["line"])
        if l.get("state") != "traced": continue
        jr = l.get("journal") or {}; dom, area = chain_place(l); out.append({"id": l["id"], "source": l.get("source") or "", "day": (l.get("published") or "")[:10] or None, "keys": jr.get("story_key") or {}, "seq": l.get("seq"), "file": p, "caps": chain_caps(l), "domain": dom, "area": area})
    return out
def load_journal(path):
    out = []
    if not os.path.exists(path): return out
    for ln in open(path, encoding="utf-8"):
        if ln.strip(): r = json.loads(ln); out.append({"id": r["item_id"], "source": r["source"], "day": r.get("day"), "keys": r["raw_keys"], "seq": r.get("gseq"), "file": path})
    return out
def load_g4(path):
    """a G4 store file (append-only, later lines override earlier ones per key) -> {"asr": {id: rec}, "ent": {id: rec}, "arts": {id: rec}, "file": path}"""
    S = {"asr": {}, "ent": {}, "arts": {}, "file": path}
    if not os.path.exists(path): return S
    for ln in open(path, encoding="utf-8"):
        if not ln.strip(): continue
        r = json.loads(ln)
        for sec in ("asr", "ent", "arts"):
            for kj, vj in r.get(sec, []): S[sec][_dec(kj)] = _dec(vj)
    return S
def load_ticks(path):
    out = []
    if not os.path.exists(path): return out
    for ln in open(path, encoding="utf-8"):
        if ln.strip(): t = json.loads(ln); t["file"] = path; out.append(t)
    return out
# ---------- stories (journal.py's logic over every known item) ----------
def story_roots(items):
    """items [{id, source, day, keys}] -> ({item id: root item id}, {item id: item}); deduplicated by id (first one wins), replayed in (day, id) order so the result does not depend on the order of the inputs"""
    by = {}
    for it in items: by.setdefault(it["id"], it)
    idx = J.new_index(); pos = {}; root = {}
    for n, i in enumerate(sorted(by, key=lambda x: (by[x].get("day") or "", x))):
        it = by[i]; pos[n] = i; k = it.get("keys") or {}
        d = J.classify(idx, {"title": k.get("title"), "prefix": k.get("prefix")}, it["source"], n)
        root[i] = pos[d["of_seq"]] if d["of_seq"] is not None else i
    return root, by
class Stories:
    """item id -> (root item id, the publisher counted for it, day). An article the items do not know falls back to the store's own root and publisher, so an unknown copy is still counted once."""
    def __init__(self, items, stores=()):
        self.root, self.by = story_roots(items); self.arts = {}
        for S in stores:
            for a, r in S["arts"].items(): self.arts.setdefault(a, r)
    def story(self, art):
        if art in self.root: return self.root[art]
        r = self.arts.get(art) or {}; return r.get("root") or art
    def pub(self, art, declared=None):
        s = self.story(art); it = self.by.get(s)
        if it: return it["source"]
        r = self.arts.get(s) or {}; return r.get("publisher") or declared or ""
    def day(self, art):
        it = self.by.get(art); return (it or {}).get("day") or (self.arts.get(art) or {}).get("day")
    def strength(self, arts_pubs):
        """arts_pubs: [(article id, declared publisher)] -> (number of independent publishers, number of stories, sorted publishers)"""
        st = {self.story(a) for a, _ in arts_pubs}; pubs = sorted({self.pub(s, dict(arts_pubs).get(s)) for s in st} - {""})
        return len(pubs), len(st), pubs
# ---------- the is_a graph over IPTC + ours ----------
class IsA:
    """child -> parent. IPTC comes from the pack on disk; ours: nodes are added by add(), which refuses a parent that is unknown or would close a cycle."""
    def __init__(self, iptc=None):
        self.par = dict(iptc or {}); self.refused = []
    def add(self, child, parent):
        if parent is not None and parent not in self.par: self.refused.append((child, parent, "unknown parent")); return False
        x = parent
        while x is not None:
            if x == child: self.refused.append((child, parent, "cycle")); return False
            x = self.par.get(x)
        if child in self.par and self.par[child] != parent and not child.startswith("ours:"): self.refused.append((child, parent, "iptc node is fixed")); return False
        self.par[child] = parent; return True
    def acyclic(self):
        state = {}
        for n in self.par:
            path = []; x = n
            while x is not None and x not in state: state[x] = 1; path.append(x); x = self.par.get(x)
            if x is not None and state.get(x) == 1 and x in path: return False   # reached a node still on the current walk
            for p in path: state[p] = 2
        return True
def load_iptc():
    cs = json.load(open(SRC + "/iptc/medtop.json"))["conceptSet"]; u2q = {c["uri"]: c["qcode"] for c in cs}
    par = {c["qcode"]: (u2q.get(c["broader"][0]) if c.get("broader") else None) for c in cs}
    lab = {c["prefLabel"]["en-GB"].lower() for c in cs}
    for c in cs:   # the pack also indexes the parts of "a, b and c" labels
        for x in re.split(r",| and ", c["prefLabel"]["en-GB"].lower()):
            if x.strip(): lab.add(x.strip())
    return par, lab
def load_wordnet():
    s = set()
    for l in open(SRC + "/wordnet/wordnet/index.noun"):
        if not l.startswith(" "): s.add(l.split()[0].replace("_", " "))
    return s
def known_term(term, iptc_labels, wn):
    t = term.lower().strip(); forms = {t, t[:-1] if t.endswith("s") else t, t[:-2] if t.endswith("es") else t}
    return bool(forms & iptc_labels) or bool(forms & wn)
# ---------- the pass ----------
def merge_assertions(stores, ST):
    """G4 stores -> {edge id: edge}. Same key in several stores or days = one edge; fragments deduplicated by (article, sentence); one lineage line per input record merged."""
    E = {}
    for S in stores:
        for aid, r in S["asr"].items():
            if r.get("kind") != "claim": continue
            if r["subj"] == r["obj"]: continue   # self-loop guard (T158 fix r2): 'houthis accuse houthis' is a mis-read of one entity as both sides, not a fact
            e = E.setdefault(h(r["key"]), {"id": h(r["key"]), "kind": "assertion", "key": r["key"], "subj": r["subj"], "pred": r["pred"], "obj": r["obj"], "obj_text": r.get("obj_text"), "iptc": None, "frag": {}, "lineage": set()})
            if r.get("iptc") and (e["iptc"] is None or canon(r["iptc"]) < canon(e["iptc"])): e["iptc"] = r["iptc"]   # the same key in several stores: the smallest canonical form wins, so store order changes nothing
            e["lineage"].add((S["file"], "g4-store", aid))
            at = r.get("attrs") or {}; ea = e.setdefault("attrs", {})
            for k_, v_ in (("status", r.get("status")), ("direction", at.get("direction")), ("place", at.get("place")), ("speaker", at.get("speaker")), ("obj_key", r.get("obj_key"))):
                if v_ is not None and (k_ not in ea or canon(v_) < canon(ea[k_])): ea[k_] = v_
            ea["time"] = sorted(set(ea.get("time") or []) | {t.get("text") for t in at.get("time") or [] if t.get("text")})
            for ev in r["evid"]:
                k = (ev["art"], ev.get("sent") or ""); e["frag"].setdefault(k, {"art": ev["art"], "pub": ev["pub"], "day": ST.day(ev["art"]), "sent": ev.get("sent"), "spans": ev.get("spans"), "polarity": (ev.get("attrs") or {}).get("polarity"), "direction": (ev.get("attrs") or {}).get("direction"), "source": S["file"]})
    return E
def merge_ticks(ticks, ST):
    E = {}
    for t in ticks:
        if not t.get("ind"): continue
        for r, talk, p, n, fd in t["events"]:
            key = "resource:%s | attention | country:%s" % (r, t["country"]); e = E.setdefault(h(key), {"id": h(key), "kind": "resource", "key": key, "subj": "resource:" + r, "pred": "attention", "obj": "country:" + t["country"], "iptc": None, "frag": {}, "lineage": set()})
            e["lineage"].add((t["file"], "tick-log", t["id"]))
            e["frag"].setdefault((t["id"], r), {"art": t["id"], "pub": t["source"], "day": t["day"] if t["day"] != "undated" else ST.day(t["id"]), "sent": None, "spans": [t.get("span")] if t.get("span") else [], "polarity": None, "direction": "up" if p > 0 else ("down" if n > 0 else None), "source": t["file"]})
    return E
def finish(E, ST):
    out = []
    for k in sorted(E):
        e = E[k]; fr = sorted(e["frag"].values(), key=lambda f: (f["day"] or "", f["art"], f["sent"] or "")); n, st, pubs = ST.strength([(f["art"], f["pub"]) for f in fr]); ind = None
        if e["kind"] == "assertion": n, pubs, ind = independence(fr, ST)   # sentence-level syndication: wire copies are one source, publisher = the fragment's own
        days = sorted({f["day"] for f in fr if f["day"]}); wins = sorted({window(d) for d in days} - {None})
        out.append({"id": e["id"], "kind": e["kind"], "key": e["key"], "subj": e["subj"], "pred": e["pred"], "obj": e["obj"], "iptc": e.get("iptc"), "strength": n, "stories": st, "fragments_n": len(fr), "publishers": pubs, "days": days, "windows": len(wins),
                    "fragments": fr, "lineage": [{"file": f, "kind": kd, "ref": r} for f, kd, r in sorted(e["lineage"])]})
        if e["kind"] == "assertion":
            out[-1]["capabilities"] = sorted({c["id"] for f in fr for c in (getattr(ST, "by", {}).get(f["art"]) or {}).get("caps") or []})   # defect 6: capability ids of the articles that support the edge (association, nothing promoted)
            out[-1]["independent"] = ind; out[-1]["obj_text"] = e.get("obj_text"); out[-1]["attrs"] = e.get("attrs") or {}
    return out
# ---------- independence: sentence-level syndication (fact-join fix, T158 L2954) ----------
SYN_JACCARD = 0.7; SYN_MIN_TOK = 8
_STOP = set("the a an and of to in on at for by with from is was were be been has have had that this it its as he she they his her their".split())
def sent_sig(s):
    """sentence -> frozenset of content tokens (lower, alphanumeric, no stopwords; the 'title. # title ...' prefix of a first sentence is cut at the '#'), or None when under SYN_MIN_TOK tokens (too short to prove a copy)"""
    s = str(s or ""); s = s.split("#", 1)[1] if "#" in s[:300] else s
    t = frozenset(x for x in re.findall(r"[a-z0-9]+", s.lower()) if x not in _STOP and len(x) > 1)
    return t if len(t) >= SYN_MIN_TOK else None
def syndication_groups(fr, ST):
    """fragments -> groups of fragment indexes that are ONE source: the same story root (journal copies) or a near-identical sentence across outlets (Jaccard >= SYN_JACCARD). Union-find, deterministic."""
    n = len(fr); par = list(range(n)); how = [set() for _ in range(n)]
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    def union(a, b, why):
        ra, rb = find(a), find(b)
        if ra != rb: par[max(ra, rb)] = min(ra, rb)
        how[a].add(why); how[b].add(why)
    roots = {}; sig = [sent_sig(f.get("sent")) for f in fr]
    for i, f in enumerate(fr):
        r = ST.story(f["art"])
        if r in roots and roots[r] != i: union(i, roots[r], "story root")
        roots.setdefault(r, i)
    for i in range(n):
        if sig[i] is None: continue
        for j in range(i + 1, n):
            if sig[j] is not None and len(sig[i] & sig[j]) / len(sig[i] | sig[j]) >= SYN_JACCARD and (fr[i].get("pub") != fr[j].get("pub") or fr[i]["art"] != fr[j]["art"]): union(i, j, "near-identical sentence")
    g = collections.defaultdict(list)
    for i in range(n): g[find(i)].append(i)
    return [(g[k], sorted({w for i in g[k] for w in how[i]})) for k in sorted(g)]
OWNERS_FILE = os.path.join(HERE, "publisher-owners.json"); _OWN = []
def owner_of(pub):
    """publisher feed name -> its owner (publisher-owners.json, each owner a cited public fact); a feed the map does not list is its own owner"""
    if not _OWN:
        try: _OWN.append({o["publisher"]: o["owner"] for o in json.load(open(OWNERS_FILE, encoding="utf-8"))["publishers"]})
        except Exception: _OWN.append({})
    return _OWN[0].get(pub) or pub
def independence(fr, ST):
    """-> (strength, publishers, independent): one source per syndication group, named by the publisher of its earliest fragment (day, then publisher, then article); sources are then counted per OWNER (T158 fix r2: Guardian US + Guardian World, BBC UK + BBC Business, Boston Globe + Boston.com are one owner, one voice), strength = distinct owners, publishers = the earliest source's own feed name per owner"""
    srcs = []
    for grp, how in syndication_groups(fr, ST):
        fs = sorted((fr[i] for i in grp), key=lambda f: (f.get("day") or "9999", f.get("pub") or "", f["art"])); rep = fs[0]; pub = rep.get("pub") or ST.pub(rep["art"])
        srcs.append({"pub": pub, "owner": owner_of(pub), "arts": sorted({f["art"] for f in fs}), "fragments": len(fs), "day": rep.get("day"), "copies": sorted({f.get("pub") or ST.pub(f["art"]) for f in fs} - {pub}), "how": how or ["single fragment"]})
    first = {}
    for x in sorted(srcs, key=lambda x: (x["day"] or "9999", x["pub"], x["arts"])):
        if x["pub"]: first.setdefault(x["owner"], x["pub"])
    pubs = sorted(first.values())
    return len(pubs), pubs, {"n": len(pubs), "sources": srcs, "owners": sorted(first), "fragments": len(fr), "collapsed": len(fr) - len(srcs), "same_owner_sources": len([x for x in srcs if x["pub"]]) - len(first), "rule": "one source per story root or near-identical sentence (Jaccard >= %.2f, >= %d tokens); publisher = the earliest fragment's own; strength = distinct owners (publisher-owners.json)" % (SYN_JACCARD, SYN_MIN_TOK)}
# ---------- fact slots: the join (fact_join.py scorer; T158 L2954) ----------
CONCEPT_TYPES = {"concept", "facility", "org", "other", "unk", "product", "group", "event", "work"}
def _name(sid): return re.sub(r"[^a-z0-9 ]+", " ", sid.split(":", 1)[-1].lower()).split()
def anchors(subjs):
    """subject ids -> {subject id: anchor id}. Identity only (T158 fix r2): one subject id is one anchor, so facts about different subjects never share a slot. The v0 rule (two concept-like subjects whose names share a head word and one contains the other: 'zoo' in 'cincinnati zoo') merged 'armed group known as Ansar Allah' with 'FutureCoal, formerly known as World Coal Association' on the head word 'group', and a Houthi operation with a coalition operation on 'operation': a head noun is too generic to say two subjects are the same thing. Country names and iso ids are joined where entities are typed (g4_align.ref_ent), not here."""
    return {x: x for x in sorted(set(subjs))}
def _scorer():
    if os.environ.get("FACT_JOIN") == "lemma": return None, "fallback: same predicate lemma (FACT_JOIN=lemma)", None
    try:
        import fact_join as FJ; sc = FJ.Scorer(); ver = getattr(sc, "version", None) or (getattr(sc, "model", None) or {}).get("version") if isinstance(getattr(sc, "model", None), dict) else getattr(sc, "version", None); return sc, "fact_join %s (%s), threshold %.3f" % (ver or "model", getattr(sc, "mode", "?"), sc.threshold), FJ
    except Exception as ex: return None, "fallback: same predicate lemma (fact_join unavailable: %s)" % str(ex)[:120], None
def _mention(e, FJ):
    f = e["fragments"][0]; at = e.get("attrs") or {}; sent = str(f.get("sent") or ""); sent = sent.split("#", 1)[1].strip() if "#" in sent[:300] else sent
    who = [" ".join(_name(e["subj"]))] + ([" ".join(_name(at["speaker"]))] if at.get("speaker") else []); where = [at["place"]] if at.get("place") else []
    obj = e["obj"] if e["obj"] is not None else e.get("obj_text")
    if FJ is None: return {"word": e["pred"], "lemma": e["pred"].split()[0] if e["pred"] else "", "obj": obj}
    return FJ.mention(e["pred"], e["pred"].split()[0] if e["pred"] else "", sent, who=who, where=where, when=at.get("time") or [], obj=(str(obj).lower() if obj is not None else None), day=f.get("day"), art=None, id=e["id"])
def _gate(a, b):
    """-> a reason why two edges can never be one fact, or None"""
    x, y = a.get("attrs") or {}, b.get("attrs") or {}
    if x.get("status") and y.get("status") and x["status"] != y["status"]: return "status %s vs %s" % (x["status"], y["status"])
    if x.get("direction") and y.get("direction") and x["direction"] != y["direction"]: return "direction %s vs %s" % (x["direction"], y["direction"])
    kx, ky = x.get("obj_key") or {}, y.get("obj_key") or {}
    if kx and ky and kx.get("class") == ky.get("class") and kx.get("bucket") != ky.get("bucket") and (kx.get("class") != "amount" or kx.get("unit") == ky.get("unit")): return "%s bucket %s vs %s" % (kx.get("class"), kx.get("bucket"), ky.get("bucket"))
    if a["obj"] and b["obj"] and a["obj"] != b["obj"] and a["obj"].split(":")[0] in ("iso", "place") and b["obj"].split(":")[0] in ("iso", "place"): return "place %s vs %s" % (a["obj"], b["obj"])
    oa, ob = _otoks(a), _otoks(b); na, nb = {t for t in oa if t[0].isdigit()}, {t for t in ob if t[0].isdigit()}
    if na and nb and na != nb: return "number %s vs %s" % ("/".join(sorted(na)), "/".join(sorted(nb)))   # '5 2p' against '7p': two amounts stated as text are two facts
    if oa and ob and not (oa & ob):   # the objects share no content word: a copula ('be hippo' / 'be tragic') or a quote-like clause (>= 4 words each) is a different fact
        if a["pred"] == "be" or b["pred"] == "be" or (len(oa) >= 4 and len(ob) >= 4): return "object disjoint"
    return None
def _otoks(e):
    o = e["obj"] if e["obj"] is not None else e.get("obj_text"); o = str(o or "").split(":", 1)[-1] if o is not None else ""
    return {t for t in re.findall(r"[a-z0-9]+", o.lower()) if t not in _STOP and t not in _DET}
def _link(dist, thr):
    """distance matrix -> labels, COMPLETE linkage cut at thr: every pair inside a slot clears the threshold, so a chain a~b~c never joins a and c and a gated pair (distance 1) never shares a slot (scipy when there; else greedy agglomeration with the same criterion)"""
    n = len(dist)
    if n == 1: return [0]
    try:
        import numpy as np; from scipy.cluster.hierarchy import linkage, fcluster
        D = np.array(dist, dtype=float); iu = np.triu_indices(n, 1); return [int(x) - 1 for x in fcluster(linkage(D[iu], "complete"), thr, "distance")]
    except Exception:
        cl = [[i] for i in range(n)]
        while True:
            best = None
            for i in range(len(cl)):
                for j in range(i + 1, len(cl)):
                    d = max(dist[p][q] for p in cl[i] for q in cl[j])
                    if d <= thr and (best is None or d < best[0]): best = (d, i, j)   # same cut as scipy fcluster (distance <= thr)
            if best is None: break
            _, i, j = best; cl[i] += cl.pop(j)
        lab = [0] * n
        for k, c in enumerate(cl):
            for i in c: lab[i] = k
        return lab
def slot_merge(edges, scorer=None, FJ=None, mode=""):
    """assertion edges (finish output) -> (edges with slots, join report). Edges of one anchor are scored pairwise (scorer.prob, or same-lemma fallback), gated, clustered; a cluster of >= 2 is one slot edge with `slot.members`; resource edges pass through."""
    A = [e for e in edges if e["kind"] == "assertion"]; R = [e for e in edges if e["kind"] != "assertion"]; an = anchors(e["subj"] for e in A)
    thr = getattr(scorer, "threshold", 0.5) if scorer else 0.5; groups = collections.defaultdict(list); out = []; mapping = {}; merges = []; gated = collections.Counter()
    for e in A: groups[an[e["subj"]]].append(e)
    for key in sorted(groups):
        G = sorted(groups[key], key=lambda e: e["id"]); M = [_mention(e, FJ) for e in G]; n = len(G); dist = [[0.0] * n for _ in range(n)]; P = {}
        for i in range(n):
            for j in range(i + 1, n):
                g = _gate(G[i], G[j])
                if g: p = 0.0; gated[g.split()[0]] += 1
                elif scorer: p = round(float(scorer.prob(M[i], M[j])), 4)
                else: p = 1.0 if M[i]["word"] == M[j]["word"] else 0.0
                dist[i][j] = dist[j][i] = 1.0 - p; P[(i, j)] = p
        lab = _link(dist, 1.0 - thr) if n > 1 else [0]; cl = collections.defaultdict(list)
        for i, l in enumerate(lab): cl[l].append(i)
        for l in sorted(cl, key=lambda l: min(G[i]["id"] for i in cl[l])):
            ix = sorted(cl[l], key=lambda i: (-G[i]["fragments_n"], G[i]["key"]))
            if len(ix) == 1: e = dict(G[ix[0]]); e["anchor"] = key; e["slot"] = None; out.append(e); mapping[e["id"]] = e["id"]; continue
            rep = G[ix[0]]; keys = sorted(G[i]["key"] for i in ix); sid = h("slot | " + " || ".join(keys)); frag = {}
            for i in ix:
                for f in G[i]["fragments"]: frag.setdefault((f["art"], f.get("sent") or ""), f)
            fr = sorted(frag.values(), key=lambda f: (f["day"] or "", f["art"], f["sent"] or "")); days = sorted({f["day"] for f in fr if f["day"]})
            pw = [P[(min(a, b), max(a, b))] for a in ix for b in ix if a < b]
            e = {**rep, "id": sid, "anchor": key, "fragments": fr, "fragments_n": len(fr), "days": days, "windows": len({window(d) for d in days} - {None}), "stories": len({f["art"] for f in fr}),
                 "lineage": sorted({canon(l): l for i in ix for l in G[i]["lineage"]}.values(), key=canon), "capabilities": sorted({c for i in ix for c in G[i].get("capabilities") or []}),
                 "slot": {"n": len(ix), "merged_how": mode, "min_pair_prob": min(pw), "mean_pair_prob": round(sum(pw) / len(pw), 4), "members": [{"edge": G[i]["id"], "key": G[i]["key"], "predicate": G[i]["pred"], "object": G[i]["obj"] if G[i]["obj"] is not None else G[i].get("obj_text"), "fragments_n": G[i]["fragments_n"]} for i in ix]}}
            out.append(e); merges.append(sid)
            for i in ix: mapping[G[i]["id"]] = sid
    out.sort(key=lambda e: e["id"]); rep_ = {"mode": mode, "threshold": thr, "facts_raw": len(A), "slots": len(out), "merge_rate": round(1.0 - len(out) / len(A), 4) if A else 0.0, "merged_slots": len(merges), "anchors": len(groups), "anchor_merges": sum(1 for s, a in an.items() if s != a), "gated_pairs": dict(sorted(gated.items())), "map": mapping, "status": "PROVISIONAL"}
    return out + R, rep_
CAP_LIGHT = {"be", "have", "do", "say", "get", "go", "make", "tell", "add", "see", "take", "give", "let", "use", "include", "become", "remain", "seem", "show", "note", "report"}   # verbs that name no capability (stative or reporting)
CAP_MIN_PUBS = 2   # an open verb-object pair needs >= 2 independent publishers (wire copies collapsed) before it is a capability candidate
def edge_cap_labels(e):
    """one assertion edge (and the members of its slot) -> {normalised 'verb object' labels}: lemma verb + head noun of a short object (<= 2 content tokens). The open side of capability_list: the fast pass only matches the closed t230/t222 list (36 of 40 mix articles got none); this reads the triples the slow pass already holds, in any domain."""
    pairs = [(e.get("pred"), e["obj"] if e.get("obj") is not None else e.get("obj_text"))] + [(m.get("predicate"), m.get("object")) for m in (e.get("slot") or {}).get("members") or []]; out = set()
    for p, o in pairs:
        if not p or not o: continue
        v = lemma_verb(str(p).split()[0]); t = [x for x in re.findall(r"[a-z]+", str(o).split(":")[-1].lower()) if x not in _DET]
        if v in CAP_LIGHT or not (0 < len(t) <= 2) or len(t[-1]) < 3: continue
        out.add(v + " " + cnorm(t[-1]))
    return out
def open_caps(ST, edges):
    """{cap id: {label, arts {article: publisher}, edges {edge ids}}} for open verb-object pairs read from the slow pass's assertion edges that meet CAP_MIN_PUBS independent publishers"""
    M = collections.defaultdict(lambda: {"arts": {}, "edges": set()})
    for e in edges:
        if e.get("kind") != "assertion": continue
        for lab in edge_cap_labels(e):
            m = M[cap_id(lab)]; m["label"] = norm_cap(lab); m["edges"].add(e["id"])
            for f in e["fragments"]: m["arts"].setdefault(f["art"], f.get("pub") or ST.pub(f["art"]))
    return {i: m for i, m in M.items() if ST.strength(sorted(m["arts"].items()))[0] >= CAP_MIN_PUBS}
def capability_layer(ST, edges=()):
    """playbook 00 sections 8 and 9: Domain > Area > Capability as a typed graph, not a tree (a capability sits under every area its articles had). Built from the chain's capability_list (t230 / t222 closed verb-object lists) plus open verb-object pairs from the slow pass's assertion edges (>= 2 independent publishers), so every node is PROVISIONAL; nothing here promotes one."""
    N = {}
    for a, it in sorted(ST.by.items()):
        for c in it.get("caps") or []:
            n = N.setdefault(c["id"], {"label": c["label"], "kinds": set(), "arts": {}, "dom": collections.Counter(), "area": collections.Counter(), "pl": collections.Counter()})
            n["kinds"].add(c["kind"]); n["arts"][a] = it["source"]; n["pl"][(it.get("domain"), it.get("area"))] += 1
            if it.get("domain"): n["dom"][it["domain"]] += 1
            if it.get("area"): n["area"][it["area"]] += 1
    for i, m in open_caps(ST, edges).items():   # open verb-object pairs from the slow pass: placed under the Area of each article that stated them
        n = N.setdefault(i, {"label": m["label"], "kinds": set(), "arts": {}, "dom": collections.Counter(), "area": collections.Counter(), "pl": collections.Counter()}); n["kinds"].add("candidate")
        for a, pub in m["arts"].items():
            it = getattr(ST, "by", {}).get(a) or {}
            if a in n["arts"]: continue
            n["arts"][a] = pub; n["pl"][(it.get("domain"), it.get("area"))] += 1
            if it.get("domain"): n["dom"][it["domain"]] += 1
            if it.get("area"): n["area"][it["area"]] += 1
        for e in edges:
            if e["id"] in m["edges"] and i not in (e.get("capabilities") or []): e["capabilities"] = sorted(set(e.get("capabilities") or []) | {i})
    ec = collections.Counter(i for e in edges for i in (e.get("capabilities") or [])); nodes = []; pl = []
    for i in sorted(N):
        n = N[i]; st, stories, pubs = ST.strength(sorted(n["arts"].items()))
        nodes.append({"id": i, "label": n["label"], "kind": "recurring" if "recurring" in n["kinds"] else "candidate", "status": "PROVISIONAL", "articles": len(n["arts"]), "strength": st, "stories": stories, "publishers": pubs, "edges": ec[i], "domains": dict(sorted(n["dom"].items())), "areas": sorted(n["area"]), "areas_n": len(n["area"]), "bridging": len(n["area"]) >= 2, "area_counts": dict(sorted(n["area"].items())), "items": [[a, p, getattr(ST, "by", {}).get(a, {}).get("day")] for a, p in sorted(n["arts"].items())]})
        pl += [{"domain": d, "area": ar, "capability": i, "articles": k} for (d, ar), k in sorted(n["pl"].items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))]
    return {"status": "PROVISIONAL", "model": "Domain > Area > Capability (playbook 00 sections 8-9); placements are co-occurrence in an article, a typed graph, not an is_a tree", "promotion": "none (no promote step, no human review; ids come from the verb-object lists and the slow pass triples, not from learning)",
            "counts": {"capabilities": len(nodes), "recurring": sum(n["kind"] == "recurring" for n in nodes), "candidate": sum(n["kind"] == "candidate" for n in nodes), "articles_with_capability": len({a for n in N.values() for a in n["arts"]}), "placements": len(pl), "bridging": sum(len(n["area"]) >= 2 for n in N.values())}, "nodes": nodes, "placements": pl}
def candidates(stores, ST, iptc_labels, wn, iptc_par):
    """concept entities from every G4 store, merged by (type, canonical name): recurrence by windows and independent publishers, then the distinctness check. Returns (candidate list, counts, the is_a graph)."""
    C = {}
    for S in stores:
        for eid, r in S["ent"].items():
            if r.get("type") != "concept": continue
            c = C.setdefault(r["canon"].lower().strip(), {"arts": {}, "iptc": None, "lineage": set()}); c["lineage"].add((S["file"], "g4-store", eid))
            for a, p in (r.get("arts") or {}).items(): c["arts"].setdefault(a, p)
            ip = r.get("iptc") or {}
            if not c["iptc"] and ip.get("node"): c["iptc"] = ip["node"]
    g = IsA(iptc_par); out = []; cnt = collections.Counter()
    for term in sorted(C):
        c = C[term]; arts = sorted(c["arts"].items()); n, st, pubs = ST.strength(arts); wins = sorted({window(ST.day(a)) for a, _ in arts} - {None})
        if known_term(term, iptc_labels, wn): cnt["known (IPTC or WordNet)"] += 1; continue
        if len(wins) < MIN_WINDOWS or n < MIN_PUBLISHERS: cnt["below the recurrence rule"] += 1; continue
        cid = "ours:" + re.sub(r"[^a-z0-9]+", "-", term).strip("-"); ok = g.add(cid, c["iptc"]) if c["iptc"] else g.add(cid, None)
        out.append({"id": cid, "label": term, "status": "PROVISIONAL", "windows": len(wins), "publishers": pubs, "strength": n, "stories": st, "is_a": g.par.get(cid), "is_a_refused": not ok, "lineage": [{"file": f, "kind": kd, "ref": r} for f, kd, r in sorted(c["lineage"])]}); cnt["candidate"] += 1
    return out, dict(cnt), g
def consolidate(items=(), stores=(), ticks=(), iptc=None, join=True):
    """items: trace/journal items; stores: load_g4 results; ticks: tick rows -> the consolidated body (a dict, no sha256 yet). join=False skips the fact slots (edges stay one per exact key)."""
    ST = Stories(list(items), stores); iptc_par, iptc_labels = iptc or load_iptc(); wn = load_wordnet()
    E = merge_assertions(stores, ST); E.update(merge_ticks(ticks, ST)); edges = finish(E, ST); cands, cc, g = candidates(stores, ST, iptc_labels, wn, iptc_par)
    if join:
        sc, mode, FJ = _scorer(); edges, jrep = slot_merge(edges, sc, FJ, mode)
        for e in edges:
            if e["kind"] == "assertion" and e.get("slot"): e["strength"], e["publishers"], e["independent"] = independence(e["fragments"], ST)
    else: jrep = {"mode": "off", "facts_raw": sum(e["kind"] == "assertion" for e in edges), "slots": sum(e["kind"] == "assertion" for e in edges), "merge_rate": 0.0, "map": {e["id"]: e["id"] for e in edges if e["kind"] == "assertion"}, "status": "PROVISIONAL"}
    jrep["independence"] = {"fragments": sum(e["fragments_n"] for e in edges if e["kind"] == "assertion"), "sources": sum(len((e.get("independent") or {}).get("sources") or []) for e in edges if e["kind"] == "assertion"), "collapsed": sum((e.get("independent") or {}).get("collapsed") or 0 for e in edges if e["kind"] == "assertion"), "rule": "one source per story root or near-identical sentence (Jaccard >= %.2f on >= %d content tokens); strength = distinct owners (publisher-owners.json), each the earliest fragment's own publisher; a claim with subject == object is dropped" % (SYN_JACCARD, SYN_MIN_TOK)}
    stories = collections.Counter(); [stories.update([r]) for r in ST.root.values()]
    body = {"version": VERSION, "rule": {"window_days": WINDOW_DAYS, "min_windows": MIN_WINDOWS, "min_publishers": MIN_PUBLISHERS, "promotion": "none (candidates stay PROVISIONAL; no promote step, no human review)"},
            "inputs": {"items": len(ST.by), "stores": sorted({S["file"] for S in stores}), "tick_rows": len({(t["file"], t["id"]) for t in ticks})},
            "stories": {"items": len(ST.root), "stories": len(stories), "copies": len(ST.root) - len(stories)},
            "edges": edges, "join": jrep, "capabilities": capability_layer(ST, edges), "candidates": cands, "candidate_counts": cc, "is_a": {"nodes": len(g.par), "ours": sum(1 for n in g.par if n.startswith("ours:")), "acyclic": g.acyclic(), "refused": len(g.refused)},
            "counts": {"edges": len(edges), "assertion_edges": sum(e["kind"] == "assertion" for e in edges), "resource_edges": sum(e["kind"] == "resource" for e in edges), "multi_publisher_edges": sum(e["strength"] >= 2 for e in edges), "fragments": sum(e["fragments_n"] for e in edges), "candidates": len(cands),
                       "facts_raw": jrep["facts_raw"], "slots_merged": jrep.get("merged_slots", 0), "merge_rate": jrep["merge_rate"]}}
    return body
def seal(body):
    b = {k: v for k, v in body.items() if k != "sha256"}; return {**b, "sha256": hashlib.sha256(canon(b).encode()).hexdigest()}
def main(a):
    opt = lambda f: a[a.index(f) + 1] if f in a else None; multi = lambda f: [a[i + 1] for i, x in enumerate(a) if x == f]
    items = []; tr = opt("--trace"); jr = opt("--journal") or os.path.join(ROOT, "runs", "journal", "journal.jsonl")
    if tr: items += load_trace(tr)
    items += load_journal(jr)
    g4 = multi("--g4") or ([os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*"))))
    ticks = [t for p in (multi("--ticks") or [os.path.join(ROOT, "runs", "ledger", "ticks.jsonl")]) for t in load_ticks(p)]
    res = seal(consolidate(items, [load_g4(p) for p in g4 if os.path.exists(p)], ticks)); out = opt("--out") or os.path.join(ROOT, "runs", "consolidated", "consolidated.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, "w", encoding="utf-8").write(json.dumps(res, sort_keys=True, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"out": out, "sha256": res["sha256"], "inputs": res["inputs"], "stories": res["stories"], "counts": res["counts"], "candidate_counts": res["candidate_counts"], "is_a": res["is_a"]}, sort_keys=True, indent=1))
if __name__ == "__main__": main(sys.argv[1:])
