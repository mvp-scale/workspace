"""evolve: G5 evolution v0 (lean wave 0, ledger L2868; playbook 00 section 9 and section 18 items 7 and 8). Offline, read-only on the inputs, no model, CPU only, deterministic.
    python3 evolve.py [--trace <trace folder or chain.jsonl>] [--journal <journal.jsonl>] [--g4 <store.jsonl> ...] [--ticks <ticks.jsonl> ...] [--prev <evolved.json of the earlier version>] [--out <evolved.json>]
Inputs: the same as consolidate.py (it is called, not copied: story identity, independent publishers, windows, IPTC and WordNet lists, IsA graph), i.e. runs/g4/store.jsonl (+ archive) and the resource tick log written by `ledger_split.py --persist`. Missing inputs are skipped.
What it does:
  1. Residual: a G4 concept term is UNPLACED when every one of its entity records sits only on the article-topic fallback path (iptc.how is article-topic or absent): nothing in the sentence, WordNet or an exact label placed it. These terms are the residual observations (playbook 00 section 9: novelty runs on what does not align).
  2. Residual clusters: unplaced terms that share a head word (last word, plural folded) form one cluster; a term with no sibling is a cluster of one. Plain and deterministic, a bounded baseline: no embeddings, no DenStream. A cluster keeps the union of its terms' articles.
  3. Gates (section 9 promotion checks that can be counted): >= MIN_WINDOWS time windows, >= MIN_PUBLISHERS independent publishers (syndicated copies count once, consolidate.Stories), and the cluster label is neither an IPTC label nor a WordNet noun. A cluster that passes all three is stage `candidate`, status PROVISIONAL. One that does not is stage `accumulating`, status RESIDUAL, with the failing gates listed. NOTHING is ever above PROVISIONAL: there is no promote or validate step, no human review, no automatic promotion (section 9: promotion needs a human-reviewed evaluation regime, so the node stays provisional).
  4. Hierarchy: a node's is_a parent is the IPTC node its terms were placed on by the fallback (the most common one); the graph is built with consolidate.IsA, which refuses unknown parents and cycles.
  5. Versioned labels and lineage (section 18 item 8): every node carries `labels`, one entry per version: {version, definition (sha1 of rule + member terms), label, inherited_from}. With --prev (an earlier evolved.json), a node whose id is unchanged is the same node, version + 1 when its members changed; a new node whose terms came out of ONE earlier node that continues under another id is a split child: it is_a the earlier node and INHERITS its label (label field kept, inherited_from = parent id); a node fed by SEVERAL earlier nodes is a merge (merged_from); an earlier node that no cluster continues is ARCHIVED with superseded_by and its history kept. Each event is in `events`. Without --prev every node is version 1 and there are no events.
  6. Lineage: every node lists the input records (file, kind, ref) of its terms; together the nodes' lineage equals the input records of the unplaced terms, no more, no fewer.
Output is canonical JSON with a sha256 of its body (no clock; paths relative to the workspace), so two passes over the same inputs give the same sha256."""
import os, sys, re, json, glob, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import consolidate as C
ROOT = C.ROOT; VERSION = "evolve-v0"; MIN_WINDOWS = C.MIN_WINDOWS; MIN_PUBLISHERS = C.MIN_PUBLISHERS; FALLBACK = (None, "article-topic")
STATUS_ORDER = ("RESIDUAL", "PROVISIONAL")   # the only statuses this module can write; there is nothing above PROVISIONAL
def sha(s): return hashlib.sha1(s.encode()).hexdigest()[:12]
def rel(p): return os.path.relpath(p, ROOT) if os.path.isabs(p) and p.startswith(ROOT) else p
def slug(t): return "ours:" + re.sub(r"[^a-z0-9]+", "-", t).strip("-")
def head(term):
    w = term.split()[-1] if term.split() else term; return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
def unplaced(stores):
    """G4 stores -> {canonical term: {"arts": {article: publisher}, "nodes": Counter(IPTC fallback node), "lineage": {(file, kind, ref)}}} for terms whose every concept record is fallback-only"""
    T = {}
    for S in stores:
        for eid, r in S["ent"].items():
            if r.get("type") != "concept": continue
            t = T.setdefault(r["canon"].lower().strip(), {"arts": {}, "nodes": collections.Counter(), "lineage": set(), "hows": set()}); ip = r.get("iptc") or {}
            t["hows"].add(ip.get("how")); t["lineage"].add((rel(S["file"]), "g4-store", eid))
            if ip.get("node"): t["nodes"][ip["node"]] += 1
            for a, p in (r.get("arts") or {}).items(): t["arts"].setdefault(a, p)
    return {k: v for k, v in T.items() if v["hows"] <= set(FALLBACK)}, len(T)
def cluster(terms):
    """terms {term: info} -> [[terms]] by shared head word (union by head), each sorted, clusters sorted by first term"""
    by = collections.defaultdict(list)
    for t in terms: by[head(t)].append(t)
    return sorted((sorted(v) for v in by.values()), key=lambda v: v[0])
def gates(arts, label, ST, iptc_labels, wn):
    n, st, pubs = ST.strength(sorted(arts.items())); wins = sorted({C.window(ST.day(a)) for a in arts} - {None})
    g = {"windows": len(wins) >= MIN_WINDOWS, "publishers": n >= MIN_PUBLISHERS, "not_known": not C.known_term(label, iptc_labels, wn)}
    return g, {"windows": len(wins), "strength": n, "stories": st, "publishers": pubs}
def label_of(members, T):
    return members[0] if len(members) == 1 else head(members[0])
def evolve(items=(), stores=(), ticks=(), iptc=None, prev=None):
    """-> the evolved body (a dict, no sha256 yet). prev: an earlier sealed/unsealed evolved body or None."""
    ST = C.Stories(list(items), stores); iptc_par, iptc_labels = iptc or C.load_iptc(); wn = C.load_wordnet()
    cons = C.seal(C.consolidate(items, stores, ticks, (iptc_par, iptc_labels))); T, n_concepts = unplaced(stores); CL = cluster(T)
    pn = {n["id"]: n for n in (prev or {}).get("nodes", []) if n["status"] != "ARCHIVED"}; pterm = {t: i for i, n in pn.items() for t in n["members"]}
    g = C.IsA(iptc_par); nodes = []; events = []; used = set()
    for members in CL:
        label = label_of(members, T); nid = slug(label)
        if nid in used: nid = nid + "-" + sha("|".join(members))[:4]
        used.add(nid); arts = {}; nodes_c = collections.Counter(); lin = set()
        for t in members: arts.update({a: p for a, p in T[t]["arts"].items() if a not in arts}); nodes_c.update(T[t]["nodes"]); lin |= T[t]["lineage"]
        gt, ms = gates(arts, label, ST, iptc_labels, wn); ok = all(gt.values()); iptc_node = sorted(nodes_c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if nodes_c else None
        node = {"id": nid, "label": label, "members": members, "stage": "candidate" if ok else "accumulating", "status": "PROVISIONAL" if ok else "RESIDUAL", "gates": gt, "gates_failed": sorted(k for k, v in gt.items() if not v), **ms,
                "is_a": iptc_node, "definition": sha(json.dumps({"rule": [MIN_WINDOWS, MIN_PUBLISHERS], "members": members})), "lineage": [{"file": f, "kind": k, "ref": r} for f, k, r in sorted(lin)]}
        old = pn.get(nid); from_ids = sorted({pterm[t] for t in members if t in pterm})
        if old: node["labels"] = list(old["labels"]) + ([{"version": old["labels"][-1]["version"] + 1, "definition": node["definition"], "label": label, "inherited_from": None}] if old["members"] != members else [])
        else: node["labels"] = [{"version": 1, "definition": node["definition"], "label": label, "inherited_from": None}]
        node["_from"] = from_ids; nodes.append(node)
    ids = {n["id"] for n in nodes}; recv = collections.defaultdict(set)   # earlier node -> the nodes that now hold any of its terms
    for n in nodes:
        for i in n["_from"]: recv[i].add(n["id"])
    for n in nodes:
        fr = [i for i in n.pop("_from") if i != n["id"]]; old = n["id"] in pn
        if len(fr) >= 2 or (old and fr):   # several earlier nodes feed it, or it continues one and absorbs another
            events.append({"event": "merge", "into": n["id"], "merged_from": fr}); n["merged_from"] = fr
        elif not old and len(fr) == 1:
            P = pn[fr[0]]
            if len(recv[fr[0]]) >= 2:   # split: the earlier node's terms went to several nodes; this one is a child, it hangs under the earlier node and inherits its label
                n["split_from"] = fr[0]; n["is_a"] = fr[0]; n["inherited_label"] = P["labels"][-1]["label"]; n["labels"] = [{"version": P["labels"][-1]["version"] + 1, "definition": n["definition"], "label": P["labels"][-1]["label"], "inherited_from": fr[0]}]
            else:   # carried: the earlier node's terms now live under one new id (grown or renamed); history kept, no hierarchy change
                n["carried_from"] = fr[0]; n["labels"] = list(P["labels"]) + [{"version": P["labels"][-1]["version"] + 1, "definition": n["definition"], "label": n["label"], "inherited_from": None}]; events.append({"event": "carry", "from": fr[0], "into": n["id"]})
    archived = []
    for i, o in sorted(pn.items()):
        if i in ids: continue
        kids = sorted(n["id"] for n in nodes if n.get("split_from") == i or n.get("carried_from") == i or i in n.get("merged_from", []))
        archived.append({**{k: o[k] for k in ("id", "label", "members", "is_a", "labels", "definition")}, "stage": "archived", "status": "ARCHIVED", "superseded_by": kids, **({} if kids else {"note": "its terms are no longer residual (placed, or gone)"})})
    for i in sorted(recv):   # a split is one event per earlier node: from, into (the children, not the node itself)
        ch = sorted(n["id"] for n in nodes if n.get("split_from") == i)
        if ch: events.append({"event": "split", "from": i, "into": ch})
    todo = sorted(nodes + archived, key=lambda x: x["id"]); pending = {x["id"] for x in todo}
    while todo:   # parents first: an entry whose ours: parent is still to come waits for it; a parent that is not an entry of this version is refused by IsA as unknown
        now = [x for x in todo if not (x["is_a"] in pending and x["is_a"] != x["id"])] or todo
        for x in now:
            ok = g.add(x["id"], x["is_a"]); x["is_a_refused"] = not ok
            if not ok: x["is_a"] = None; g.par[x["id"]] = None
        todo = [x for x in todo if x not in now]; pending -= {x["id"] for x in now}
    nodes.sort(key=lambda n: n["id"]); events = sorted({json.dumps(e, sort_keys=True) for e in events}); events = [json.loads(e) for e in events]
    cnt = collections.Counter(n["stage"] for n in nodes); fail = collections.Counter(f for n in nodes for f in n["gates_failed"])
    return {"version": VERSION, "rule": {"window_days": C.WINDOW_DAYS, "min_windows": MIN_WINDOWS, "min_publishers": MIN_PUBLISHERS, "residual": "concept terms with only article-topic fallback paths", "cluster": "shared head word", "promotion": "none (nothing above PROVISIONAL; no promote step, no human review)"},
            "inputs": {"stores": sorted({rel(S["file"]) for S in stores}), "tick_rows": len({(t["file"], t["id"]) for t in ticks}), "items": len(ST.by), "consolidated_sha256": cons["sha256"], "consolidated_counts": cons["counts"], "prev": bool(prev)},
            "capabilities": cons["capabilities"], "nodes": nodes, "archived": archived, "events": events, "is_a": {"nodes": len(g.par), "ours": sum(1 for n in g.par if n.startswith("ours:")), "acyclic": g.acyclic(), "refused": len(g.refused), "refused_detail": [list(x) for x in g.refused[:20]]},
            "counts": {"concept_terms": n_concepts, "unplaced_terms": len(T), "clusters": len(nodes), "singleton_clusters": sum(len(n["members"]) == 1 for n in nodes), "multi_term_clusters": sum(len(n["members"]) > 1 for n in nodes), "candidates": cnt["candidate"], "accumulating": cnt["accumulating"], "failed_" + "windows": fail["windows"], "failed_publishers": fail["publishers"], "failed_not_known": fail["not_known"],
                       "split_events": sum(e["event"] == "split" for e in events), "merge_events": sum(e["event"] == "merge" for e in events), "carry_events": sum(e["event"] == "carry" for e in events), "archived": len(archived), "capabilities": cons["capabilities"]["counts"]["capabilities"], "capabilities_recurring": cons["capabilities"]["counts"]["recurring"], "consolidate_candidates": cons["counts"]["candidates"], "consolidate_candidates_also_residual": sum(1 for c in cons["candidates"] if c["label"] in T)}}
def seal(body):
    b = {k: v for k, v in body.items() if k != "sha256"}; return {**b, "sha256": hashlib.sha256(C.canon(b).encode()).hexdigest()}
def main(a):
    opt = lambda f: a[a.index(f) + 1] if f in a else None; multi = lambda f: [a[i + 1] for i, x in enumerate(a) if x == f]
    items = []; tr = opt("--trace"); jr = opt("--journal") or os.path.join(ROOT, "runs", "journal", "journal.jsonl")
    if tr: items += C.load_trace(tr)
    items += C.load_journal(jr)
    g4 = multi("--g4") or ([os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*"))))
    ticks = [t for p in (multi("--ticks") or [os.path.join(ROOT, "runs", "ledger", "ticks.jsonl")]) for t in C.load_ticks(p)]
    pv = json.load(open(opt("--prev"))) if opt("--prev") else None
    res = seal(evolve(items, [C.load_g4(p) for p in g4 if os.path.exists(p)], ticks, None, pv)); out = opt("--out") or os.path.join(ROOT, "runs", "evolved", "evolved.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, "w", encoding="utf-8").write(json.dumps(res, sort_keys=True, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"out": out, "sha256": res["sha256"], "inputs": res["inputs"], "counts": res["counts"], "is_a": res["is_a"]}, sort_keys=True, indent=1))
if __name__ == "__main__": main(sys.argv[1:])
