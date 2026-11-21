"""consolidate: two clocks v0 (plan step 6; playbook 00 section 18 items 3 and 4). The fast clock writes the durable stores while articles arrive; this is the slow clock: an offline pass run at checkpoints over them. Read-only on the inputs, no model, CPU only.
    python3 consolidate.py [--trace <trace folder or chain.jsonl>] [--journal <journal.jsonl>] [--g4 <store.jsonl> ...] [--ticks <ticks.jsonl> ...] [--out <consolidated.json>]
Inputs (each optional, missing ones are skipped): runs/journal/journal.jsonl (journal.Durable), runs/g4/store.jsonl and runs/g4/archive/store.jsonl-* (G4 stores of earlier runs), the resource tick log written by `ledger_split.py --state <json> --persist <ticks.jsonl>`, and a live-trace folder (its lines carry the story keys, publisher and day).
What it does:
  1. Story identity: every item (trace line, journal row) is replayed through journal.classify in (day, id) order, so a syndicated copy resolves to the root of its story; an item with no key is its own story. This is journal.py's logic, not a second one.
  2. Merge: the same assertion (G4 key: subject | predicate | object) in several runs, stores and days becomes ONE edge that keeps every supporting fragment (article, publisher, day, sentence, spans) and a lineage line per input record merged. A resource tick log gives one edge per (resource, country).
     Fragments are deduplicated by (article, sentence), so replaying an input adds nothing.
  3. Strength = the number of independent publishers: one publisher per story (the publisher of the story's root item), so 20 syndicated copies count 1 (T07). `fragments` and `stories` are listed beside it.
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
def load_trace(path):
    """live-trace chain.jsonl (or its folder) -> items [{id, source, day, keys, seq, file}]"""
    p = os.path.join(path, "chain.jsonl") if os.path.isdir(path) else path; out = []
    if not os.path.exists(p): return out
    for ln in open(p, encoding="utf-8"):
        if not ln.strip(): continue
        l = json.loads(json.loads(ln)["line"])
        if l.get("state") != "traced": continue
        jr = l.get("journal") or {}; out.append({"id": l["id"], "source": l.get("source") or "", "day": (l.get("published") or "")[:10] or None, "keys": jr.get("story_key") or {}, "seq": l.get("seq"), "file": p})
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
            e = E.setdefault(h(r["key"]), {"id": h(r["key"]), "kind": "assertion", "key": r["key"], "subj": r["subj"], "pred": r["pred"], "obj": r["obj"], "obj_text": r.get("obj_text"), "iptc": r.get("iptc"), "frag": {}, "lineage": set()})
            e["lineage"].add((S["file"], "g4-store", aid))
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
        e = E[k]; fr = sorted(e["frag"].values(), key=lambda f: (f["day"] or "", f["art"], f["sent"] or "")); n, st, pubs = ST.strength([(f["art"], f["pub"]) for f in fr])
        days = sorted({f["day"] for f in fr if f["day"]}); wins = sorted({window(d) for d in days} - {None})
        out.append({"id": e["id"], "kind": e["kind"], "key": e["key"], "subj": e["subj"], "pred": e["pred"], "obj": e["obj"], "strength": n, "stories": st, "fragments_n": len(fr), "publishers": pubs, "days": days, "windows": len(wins),
                    "fragments": fr, "lineage": [{"file": f, "kind": kd, "ref": r} for f, kd, r in sorted(e["lineage"])]})
    return out
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
def consolidate(items=(), stores=(), ticks=(), iptc=None):
    """items: trace/journal items; stores: load_g4 results; ticks: tick rows -> the consolidated body (a dict, no sha256 yet)"""
    ST = Stories(list(items), stores); iptc_par, iptc_labels = iptc or load_iptc(); wn = load_wordnet()
    E = merge_assertions(stores, ST); E.update(merge_ticks(ticks, ST)); edges = finish(E, ST); cands, cc, g = candidates(stores, ST, iptc_labels, wn, iptc_par)
    stories = collections.Counter(); [stories.update([r]) for r in ST.root.values()]
    body = {"version": VERSION, "rule": {"window_days": WINDOW_DAYS, "min_windows": MIN_WINDOWS, "min_publishers": MIN_PUBLISHERS, "promotion": "none (candidates stay PROVISIONAL; no promote step, no human review)"},
            "inputs": {"items": len(ST.by), "stores": sorted({S["file"] for S in stores}), "tick_rows": len({(t["file"], t["id"]) for t in ticks})},
            "stories": {"items": len(ST.root), "stories": len(stories), "copies": len(ST.root) - len(stories)},
            "edges": edges, "candidates": cands, "candidate_counts": cc, "is_a": {"nodes": len(g.par), "ours": sum(1 for n in g.par if n.startswith("ours:")), "acyclic": g.acyclic(), "refused": len(g.refused)},
            "counts": {"edges": len(edges), "assertion_edges": sum(e["kind"] == "assertion" for e in edges), "resource_edges": sum(e["kind"] == "resource" for e in edges), "multi_publisher_edges": sum(e["strength"] >= 2 for e in edges), "fragments": sum(e["fragments_n"] for e in edges), "candidates": len(cands)}}
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
