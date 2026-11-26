"""check-concepts: the gate of the concept layer v0 (projects/world-state/concepts_v0.py; page feed /api/raw/concepts and /api/raw/deep via raw-units.py concepts() / deep()). PROVISIONAL: weak numbers are reported, only STRUCTURAL assertions fail.
Reads the two staged area windows (demo/mockups/structure-live/area-c1, area-mix: knowledge.json, consolidated.json, g4 store, chain.jsonl) read only; the seeded-change control works on a scratch copy. CPU only, offline, no hosted call, no network.
  C1 build       both areas build: exists, concepts > 0, links list, triage one row per article
  C2 contract    every field of the contract on every concept / link / triage row (names and enums as agreed with the page)
  C3 evidence    every edge id cited (concepts, links, card drivers / resources, triage, deep timeline / accounts / open questions / subconcepts) resolves in knowledge.json (resource edges: consolidated.json, counted apart); history ids resolve in their own window
  C4 sources     no what_it_is without src (and a null what_it_is has slot_fill 'cant'); card gaps present when a slot is 'cant'
  C5 triage      verdict counts per area, every verdict in the enum, a concept id from the graph or null
  C6 deep        deep on the focus concept < 120 s, card_fill_after >= card_fill_before, 5 open questions, depth L2|L3; a second call is cached; a concept with history in another window shows history rows
  C7 seeded      5 synthetic changed facts injected into a scratch copy (6 edges, 5 new articles): triage never labels them 'known' (hidden changes = 0)
  C9 v1 slots    directions cite edges and quote a fragment sentence; drivers quote sentences that exist in the cited edges' fragments; no stoplisted generic concept (WordNet rule + named list); every non-known triage row has change_text that is a real fragment sentence of its cited edge;
                 process concepts have >= 3 owners and part_of links from their actors; subconcepts are graph concepts or appear in >= 2 facts with the parent
  C8 determinism two builds equal; module has no network import
    /workspace/models/embed-zs/.venv/bin/python simulation/check-concepts.py [--area c1,mix] [--keep]"""
import sys, os, json, time, shutil, tempfile, importlib.util, collections, re
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state"); sys.path.insert(0, WS)
STRUCT = os.path.abspath(os.path.join(KP, "..", "demo", "mockups", "structure-live"))
import concepts_v0 as CV
args = sys.argv[1:]; AREAS = (args[args.index("--area") + 1].split(",") if "--area" in args else ["c1", "mix"]); KEEP = "--keep" in args
KINDS = {"entity", "place", "org", "person", "resource", "process", "capability", "concept"}; STATES = {"gap", "emerging", "active", "settled", "contested"}; RELS = {"is_a", "part_of", "causes", "affects_resource", "opposes", "precedes", "related"}
VERD = {"known", "update", "new_link", "new_concept", "conflict"}; FILL = {"today", "partly", "cant"}; SLOTS = {"what_it_is", "direction", "drivers", "resources", "related"}
res = []
def ok(name, cond, msg=""): res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (("  " + msg) if msg else ""), flush=True)
def td_of(a): return os.path.join(STRUCT, "area-" + a, "trace")
def ids_of_build(B):
    out = []
    for c in B["concepts"]:
        out += c["edge_ids"] + [x for d in c["card"]["drivers"] for x in d["edge_ids"]] + [x for r in c["card"]["resources"] for x in r["edge_ids"]]
    for l in B["links"]: out += l["edge_ids"]
    for t in B["triage"]: out += (t.get("edge_ids") or []) + (t.get("change_edge_ids") or [])
    for c in B["concepts"]:
        cd = c["card"]
        out += [x for d in c.get("directions", []) for x in d["edge_ids"]] + [x for k in ("did", "allies", "opponents", "effect", "disputed", "new") for it in cd.get(k, []) for x in it.get("edge_ids", [])] + ((cd.get("role") or {}).get("edge_ids") or [])
    return out
def ids_of_deep(d):
    out = [r["edge_id"] for r in d["timeline"]] + [x for a in d["accounts"] for x in a.get("edge_ids", [])] + [x for q in d["open_questions"] for x in q["edge_ids"]] + [x for s in d["subconcepts"] for x in s.get("edge_ids", [])]
    return out
t_all = time.time(); BS = {}
for a in AREAS:
    td = td_of(a)
    if not os.path.exists(os.path.join(td, "slow_consolidate", "knowledge.json")): ok("C1 build %s" % a, False, "area window not staged (start the server once, or run build_area)"); continue
    t0 = time.time(); B = CV.build(td, a); BS[a] = B; K = json.load(open(os.path.join(td, "slow_consolidate", "knowledge.json"))); C = json.load(open(os.path.join(td, "slow_consolidate", "consolidated.json")))
    rel = collections.Counter(l["rel"] for l in B["links"]); st = collections.Counter(c["state"] for c in B["concepts"]); kd = collections.Counter(c["kind"] for c in B["concepts"])
    fill = collections.Counter(v for c in B["concepts"] for v in c["slot_fill"].values()); tot = sum(fill.values()) or 1
    ok("C1 build %s" % a, B.get("exists") and len(B["concepts"]) > 0 and len(B["triage"]) == K["articles"] and B["focus"], "%d concepts, %d links %s, states %s, kinds %s, slot fill today %.0f%% partly %.0f%% cant %.0f%%, %.2f s" % (len(B["concepts"]), len(B["links"]), dict(rel), dict(st), dict(kd), 100 * fill["today"] / tot, 100 * fill["partly"] / tot, 100 * fill["cant"] / tot, time.time() - t0))
    B2 = CV.build(td, a); ok("C8 determinism %s" % a, json.dumps(B, sort_keys=True) == json.dumps(B2, sort_keys=True))
    # C2 contract
    bad = []
    for k in ("exists", "area", "as_of", "n_articles", "concepts", "links", "triage", "focus"):
        if k not in B: bad.append("top:" + k)
    for c in B["concepts"]:
        for k in ("id", "label", "kind", "depth", "state", "certainty", "direction", "owners", "facts", "first_seq", "last_seq", "card", "slot_fill"):
            if k not in c: bad.append("concept.%s" % k)
        if c["kind"] not in KINDS or c["state"] not in STATES or c["depth"] not in ("L0", "L1", "L2", "L3") or c["direction"] not in ("up", "down", "flat", None) or not (0 <= c["certainty"] <= 1): bad.append("enum:" + c["id"])
        for k in ("what_it_is", "drivers", "resources", "related", "gaps"):
            if k not in c["card"]: bad.append("card.%s" % k)
        if set(c["slot_fill"]) != SLOTS or set(c["slot_fill"].values()) - FILL: bad.append("slot_fill:" + c["id"])
        for d in c["card"]["drivers"]:
            if set(d) < {"concept", "rel", "certainty", "edge_ids"}: bad.append("driver:" + c["id"])
        for r in c["card"]["resources"]:
            if set(r) < {"resource", "direction", "edge_ids"}: bad.append("resource:" + c["id"])
        for r in c["card"]["related"]:
            if set(r) < {"concept", "rel", "n", "certainty"}: bad.append("related:" + c["id"])
    ids = {c["id"] for c in B["concepts"]}
    for l in B["links"]:
        if set(l) < {"a", "b", "rel", "direction", "certainty", "owners", "edge_ids"} or l["rel"] not in RELS or l["a"] not in ids or l["b"] not in ids: bad.append("link:%s>%s" % (l["a"], l["b"]))
    for t in B["triage"]:
        if set(t) < {"seq", "art", "title", "verdict", "concept", "detail"} or t["verdict"] not in VERD or (t["concept"] is not None and t["concept"] not in ids): bad.append("triage:%s" % t["art"][:8])
    ok("C2 contract %s" % a, not bad and B["focus"] in ids, "%d problems %s" % (len(bad), bad[:5]))
    # C3 evidence
    allids = ids_of_build(B); kn = K["edges"]; cons = {e["id"] for e in C["edges"]}
    in_k = [i for i in allids if i in kn]; in_c_only = [i for i in allids if i not in kn and i in cons]; miss = [i for i in allids if i not in kn and i not in cons]
    nonres_miss = [c["id"] for c in B["concepts"] if not c["id"].startswith("resource:") for i in c["edge_ids"] if i not in kn]
    ok("C3 evidence %s" % a, not miss and not nonres_miss, "%d ids cited: %d in knowledge.json, %d resource edges only in consolidated.json, %d unresolved" % (len(allids), len(in_k), len(in_c_only), len(miss)))
    # C4 sources
    noscr = [c["id"] for c in B["concepts"] if c["card"]["what_it_is"] and not (c["card"]["what_it_is"].get("src") and c["card"]["what_it_is"].get("text"))]
    nocant = [c["id"] for c in B["concepts"] if not c["card"]["what_it_is"] and c["slot_fill"]["what_it_is"] != "cant"]
    nogap = [c["id"] for c in B["concepts"] if any(v == "cant" for v in c["slot_fill"].values()) and not c["card"]["gaps"]]
    wi = sum(1 for c in B["concepts"] if c["card"]["what_it_is"]); srcs = collections.Counter((c["card"]["what_it_is"]["src"].split(":")[0] if c["card"]["what_it_is"] else "none") for c in B["concepts"])
    ok("C4 sources %s" % a, not noscr and not nocant and not nogap, "what_it_is on %d of %d concepts %s; without src %d" % (wi, len(B["concepts"]), dict(srcs), len(noscr)))
    # C5 triage
    tc = collections.Counter(t["verdict"] for t in B["triage"]); seqs = [t["seq"] for t in B["triage"]]
    ok("C5 triage %s" % a, set(tc) <= VERD and seqs == sorted(seqs) and sum(tc.values()) == K["articles"], "verdicts %s" % dict(tc))
    # C6 deep
    t0 = time.time(); d = CV.deep(td, a, B["focus"]); ms = int((time.time() - t0) * 1000)
    dids = ids_of_deep(d); dmiss = [i for i in dids if i not in kn and i not in cons]
    t1 = time.time(); d2 = CV.deep(td, a, B["focus"]); cached = d2.get("cached") is True
    ok("C6 deep %s focus %s" % (a, B["focus"]), ms < 120000 and d["card_fill_after"] >= d["card_fill_before"] and len(d["open_questions"]) == 5 and d["depth"] in ("L2", "L3") and not dmiss and cached and all(k in d for k in ("concept", "depth", "ms", "subconcepts", "timeline", "accounts", "open_questions", "history", "card_fill_before", "card_fill_after")),
       "%d ms, card fill %.2f -> %.2f (filled %s), %d subconcepts, %d timeline, %d accounts, %d history, open questions answered %d / unknown %d, cached second call %s, unresolved ids %d" % (ms, d["card_fill_before"], d["card_fill_after"], d["filled_by_deep"], len(d["subconcepts"]), len(d["timeline"]), len(d["accounts"]), len(d["history"]), sum(q["status"] == "answered" for q in d["open_questions"]), sum(q["status"] == "unknown" for q in d["open_questions"]), cached, len(dmiss)))
    # history: a concept that other windows also read; each history edge resolves in its own window
    hc = next((c["id"] for c in B["concepts"] if c["id"].startswith("iso:")), None); hmiss = 0; hn = 0
    for cid in [c["id"] for c in B["concepts"] if c["id"].startswith("iso:")][:6]:
        dh = CV.deep(td, a, cid); hn += len(dh["history"])
        for h in dh["history"]:
            p = [pp for w, pp in CV._windows(td) if w == h["window"]]
            if not p or h["edge_id"] not in {e["id"] for e in CV._hist_edges(p[0])}: hmiss += 1
    ok("C6 history %s" % a, hmiss == 0, "%d history rows over the first 6 place concepts, %d unresolved (history = other windows' own consolidated.json, no network)" % (hn, hmiss))
    # C9 v1 slots
    allsent = collections.defaultdict(list)
    for e in C["edges"]:
        for f in e.get("fragments") or []:
            if f.get("sent"): allsent[e["id"]].append(f["sent"])
    quoted = lambda sent, ids: bool(sent) and any(sent in x for i in ids for x in allsent.get(i, []))
    bad = []; nd = nobj = 0
    for c in B["concepts"]:
        for d in c["directions"]:
            nd += 1; nobj += 1 if d["object"] else 0
            if not d["edge_ids"] or not quoted(d["sentence"], d["edge_ids"]) or d["dir"] not in ("up", "down"): bad.append("dir:%s" % c["id"])
        for d in c["card"]["drivers"]:
            if not d["edge_ids"] or not quoted(d["sentence"], d["edge_ids"]) or not d.get("rule") or (d.get("marker") not in ("causes",) and d["marker"] not in d["sentence"].lower() and d["marker"] not in d["text"].lower()): bad.append("driver:%s" % c["id"])
        for k in ("did", "allies", "opponents", "effect"):
            for it in c["card"][k]:
                if not it.get("edge_ids"): bad.append("%s:%s" % (k, c["id"]))
        if c["card"]["role"] and not c["card"]["role"].get("basis"): bad.append("role:" + c["id"])
        for k in c["card"]["new"]:
            if not quoted(k["change_text"], k["edge_ids"]): bad.append("new:" + c["id"])
        if c["kind"] == "process":
            pl = [l for l in B["links"] if l["b"] == c["id"] and l["rel"] == "part_of"]
            if c["owners"] < 3 or not pl: bad.append("process:" + c["id"])
    GEN = {"kingdom", "capital", "attack", "government", "conflict", "strike", "people", "statement", "war", "group", "threat", "price"}
    gen = [c["label"] for c in B["concepts"] if c["kind"] == "concept" and (c["label"].lower().split()[-1] in GEN or CV.generic_why(c["label"].split()[-1].lower(), 0.0))]
    nonk = [t for t in B["triage"] if t["verdict"] != "known"]; noct = [t["art"][:8] for t in nonk if not t.get("change_text") or t["change_kind"] not in ("conflict", "update", "new_link", "new_concept") or not quoted(t["change_text"], t["change_edge_ids"])]
    mset = {c["id"] for c in B["concepts"]}; dsub = 0
    for c in B["concepts"][:12]:
        for sc in CV.deep(td, a, c["id"])["subconcepts"]:
            if sc["id"] not in mset and sc["facts"] < 2: dsub += 1
    pr = [c for c in B["concepts"] if c["kind"] == "process"]
    ok("C9 v1 slots %s" % a, not bad and not gen and not noct and not dsub, "directions %d (%d with an object), drivers %d concepts filled, generic concepts kept %s, dropped %d, non-known rows %d without a quoted change_text %s, process concepts %s, weak subconcepts %d, problems %s" % (nd, nobj, sum(1 for c in B["concepts"] if c["card"]["drivers"]), gen, len(B["dropped"]), len(noct), noct[:3], [p_["label"] for p_ in pr], dsub, bad[:5]))
    # C10 v2 triage (T158 triage v1): incremental membership, unmapped never known, 'known' = every fact a repeat, per-concept 'New' only from a fact where the concept is subject or object
    Dx = CV.load(td); cn = CV.make_canon(Dx["ents"], None); EBx = {e["id"]: e for e in Dx["C"]["edges"]}; cm = {c["id"]: c for c in B["concepts"]}; bad10 = []; gb = [t["graph_before"] for t in B["triage"]]
    if gb != sorted(gb): bad10.append("graph_before not monotone")
    for t in B["triage"]:
        if t["verdict"] == "known" and (t["unmapped"] or any(k != "known" for k in t["counts"])): bad10.append("known:%s" % t["art"][:8])
        if t["unmapped"] and t["verdict"] == "known": bad10.append("unmapped known:%s" % t["art"][:8])
        if t["concept"] and cm[t["concept"]]["in_graph_from_seq"] is not None and cm[t["concept"]]["in_graph_from_seq"] > t["seq"]: bad10.append("concept before entry:%s" % t["art"][:8])
        for cid, ch in t["concept_changes"].items():
            e = EBx.get(ch["edge_ids"][0]); ends = {cn((e or {}).get("anchor") or (e or {}).get("subj")), cn((e or {}).get("obj"))} if e else set()
            if cid not in ends: bad10.append("touch:%s:%s" % (cid, t["art"][:8]))
    ok("C10 v2 triage %s" % a, not bad10, "graph_before %d -> %d over %d articles; unmapped-only rows %d; known rows %d; problems %s" % (gb[0] if gb else 0, gb[-1] if gb else 0, len(gb), sum(1 for t in B["triage"] if t["verdict"] == "new_concept" and t["counts"].get("new_concept") == t["unmapped"]), sum(1 for t in B["triage"] if t["verdict"] == "known"), bad10[:4]))
src = open(os.path.join(WS, "concepts_v0.py")).read(); ok("C8 no network import", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|httpx|aiohttp)", src, re.M))
# raw-units wrapper
try:
    spec = importlib.util.spec_from_file_location("raw_units", os.path.join(HERE, "raw-units.py")); RU = importlib.util.module_from_spec(spec); os.chdir(WS); spec.loader.exec_module(RU)
    a0 = next(iter(BS)); r = RU.concepts("trace:" + td_of(a0)); d = RU.deep("trace:" + td_of(a0), BS[a0]["focus"])
    ok("C1 raw-units wrapper", r.get("exists") and len(r["concepts"]) == len(BS[a0]["concepts"]) and d.get("concept") == BS[a0]["focus"], "concepts() and deep() answer through raw-units.py")
except Exception as e: ok("C1 raw-units wrapper", False, repr(e))
# C7 seeded-change control on a scratch copy
def seed(a):
    B = BS[a]; td = td_of(a); tmp = tempfile.mkdtemp(prefix="seed-%s-" % a); tt = os.path.join(tmp, "trace"); os.makedirs(os.path.join(tt, "slow_consolidate"))
    for n in ("g4", "slow.jsonl", "a"):
        if os.path.exists(os.path.join(td, n)): os.symlink(os.path.join(td, n), os.path.join(tt, n))
    for n in ("knowledge.json", "consolidated.json"): shutil.copy(os.path.join(td, "slow_consolidate", n), os.path.join(tt, "slow_consolidate", n))
    K = json.load(open(os.path.join(tt, "slow_consolidate", "knowledge.json"))); C = json.load(open(os.path.join(tt, "slow_consolidate", "consolidated.json")))
    rows = [l for l in open(os.path.join(td, "chain.jsonl"), encoding="utf-8")]; mx = max(json.loads(json.loads(l)["line"] if isinstance(json.loads(l).get("line"), str) else "{}").get("seq", 0) if isinstance(json.loads(l).get("line"), str) else json.loads(l).get("seq", 0) for l in rows)
    ents = [c for c in B["concepts"] if c["kind"] != "resource"]; foc = next(c for c in ents if c["id"] == B["focus"]); linked = {(l["a"], l["b"]) for l in B["links"]} | {(l["b"], l["a"]) for l in B["links"]}
    plain = [c["id"] for c in ents if c["kind"] != "concept"]; pair = next(((x, y) for x in plain for y in plain if x < y and (x, y) not in linked and x != foc["id"] and y != foc["id"]), (plain[1], plain[2]))
    edges = [e for e in C["edges"] if e["kind"] == "assertion" and (e.get("anchor") or e.get("subj")) == foc["id"]]; base = max(edges, key=lambda e: len((e.get("independent") or {}).get("sources") or []))
    mk = lambda i, subj, pred, obj, pol="positive", dr=None, key=None: {"anchor": subj, "attrs": {"direction": dr} if dr else {}, "capabilities": [], "days": ["2026-11-21"], "decay": {"weight": 1.0, "age_days": 0, "half_life_days": 7}, "id": "seed%02d" % i, "kind": "assertion", "key": key or "%s | %s | %s" % (subj, pred, obj), "subj": subj, "pred": pred, "obj": obj, "obj_text": None, "slot": None, "iptc": None, "publishers": ["Seed Wire %d" % i], "strength": 1, "stories": 1,
        "fragments": [{"art": "seedart%02d" % i, "day": "2026-11-21", "direction": dr, "polarity": pol, "pub": "Seed Wire %d" % i, "sent": "SEEDED synthetic fact %d: %s %s %s." % (i, subj, pred, obj)}], "fragments_n": 1, "independent": {"n": 1, "owners": ["Seed Owner %d" % i], "sources": [{"pub": "Seed Wire %d" % i, "owner": "Seed Owner %d" % i, "day": "2026-11-21", "arts": ["seedart%02d" % i], "fragments": 1, "how": ["single fragment"]}]}}
    spec_ = [(1, base["subj"], base["pred"], base["obj"], "negative", None, base["key"]), (2, pair[0], "meet", pair[1], "positive", None, None), (3, foc["id"], "announce", "concept:seeded news", "positive", "down", None), (4, foc["id"], "praise", "concept:seeded object", "positive", None, None), (5, "person:seeded newcomer", "arrive", foc["id"], "positive", None, None), (5, "person:seeded newcomer", "visit", pair[0], "positive", None, None)]
    expect = {1: "conflict", 2: "new_link", 3: "update", 4: "update", 5: "new_concept"}; arts = {}
    for n, (i, s, p, o, pol, dr, k) in enumerate(spec_):
        e = mk(i, s, p, o, pol, dr, k); e["id"] = "seed%02d%d" % (i, n); e["fragments"][0]["art"] = "seedart%02d" % i; e["independent"]["sources"][0]["arts"] = ["seedart%02d" % i]; C["edges"].append(e)
        K["edges"][e["id"]] = {"anchor": s, "subject": s, "predicate": p, "object": o, "kind": "assertion", "strength": 1, "publishers": e["publishers"], "fragments": [{"art": e["fragments"][0]["art"], "pub": e["publishers"][0], "sent": e["fragments"][0]["sent"]}], "independent": e["independent"], "slot": None}; arts.setdefault(i, []).append(e["id"])
    with open(os.path.join(tt, "chain.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(rows)
        for j, i in enumerate(sorted(arts)):
            ln = {"id": "seedart%02d" % i, "seq": mx + 1 + j, "source": "Seed Wire %d" % i, "title": "SEEDED synthetic article %d" % i, "published": "2026-11-21T12:00:00Z", "state": "traced", "stages": {}}; f.write(json.dumps({"seq": mx + 1 + j, "prev": "seed", "sha": "seed", "line": json.dumps(ln)}) + "\n")
    json.dump(K, open(os.path.join(tt, "slow_consolidate", "knowledge.json"), "w")); json.dump(C, open(os.path.join(tt, "slow_consolidate", "consolidated.json"), "w"))
    return tmp, tt, expect
for a in BS:
    tmp, tt, expect = seed(a)
    try:
        S = CV.build(tt, a); tri = {t["art"]: t for t in S["triage"]}; got = {i: (tri.get("seedart%02d" % i) or {}).get("verdict") for i in expect}
        hidden = sum(1 for v in got.values() if v in ("known", None)); match = sum(1 for i, v in got.items() if v == expect[i] or (i == 3 and v == "conflict"))
        base_known = collections.Counter(t["verdict"] for t in BS[a]["triage"])["known"]
        sct = sum(1 for i in expect if (tri.get("seedart%02d" % i) or {}).get("change_text"))
        ok("C7 seeded %s" % a, hidden == 0 and sct == 5, "hidden changes %d of 5 (labelled known); verdicts %s; exactly as designed %d of 5; change_text on %d of 5 seeded rows; the unseeded replay still has %d known article(s)" % (hidden, {"seed%d" % i: v for i, v in got.items()}, match, sct, base_known))
    finally:
        if not KEEP: shutil.rmtree(tmp, ignore_errors=True)
# C11 coverage rules (T158 round 4, PROVISIONAL): unit cases on a synthetic identity store, then fact coverage on the staged areas against the pre-round numbers
def _E(cid, canon, aliases=(), arts=2): return {"id": cid, "type": cid.split(":")[0], "canon": canon, "aliases": {a: 1 for a in (canon,) + tuple(aliases)}, "arts": {"a%d" % i: "P%d" % i for i in range(arts)}}
_ents = {e["id"]: e for e in [_E("iso:US", "United States", ("US",)), _E("iso:IR", "Iran"), _E("iso:TR", "Turkey"), _E("place:chelsea", "Chelsea"), _E("person:joe mazzulla", "Joe Mazzulla"), _E("org:state government", "State Government")]}
_cn = CV.make_canon(_ents, None)
ok("C11 coord split", _cn.all("place:united states and iran") == ["iso:US", "iso:IR"] and _cn.rule("place:united states and iran") == "coord" and _cn("place:united states and iran") == "iso:US", "%s" % _cn.all("place:united states and iran"))
ok("C11 np-name", _cn.all("concept:celtics coach joe mazzulla") == ["person:joe mazzulla"] and _cn.rule("concept:celtics coach joe mazzulla") == "np-name", "longest typed name inside a noun phrase")
ok("C11 np-demonym", _cn.all("concept:iranian drone attacks") == ["iso:IR"] and _cn.rule("concept:iranian drone attacks") == "np-demonym")
ok("C11 np guards", all(_cn.all(x) == [x] for x in ("concept:who that is here in iran", "concept:coach chelsea cunningham", "concept:frozen turkey", "concept:the state government", "concept:orders of 9 iran")), "clause words, one-word name inside a phrase, ambiguous common word, all-common-word org, number: no mapping")
ok("C11 no invented labels", all(_cn.rule(x) is None and _cn.all(x) == [x] for x in ("concept:random plain noun", "iso:IR", "person:joe mazzulla")))
BEFORE_COV = {"c1": 36.3, "mix": 42.0}
for a in BS:
    Dx = CV.load(td_of(a)); cnx = CV.make_canon(Dx["ents"], None); MSx = {c["id"] for c in BS[a]["concepts"]}; EBx = [e for e in Dx["C"]["edges"] if e.get("kind") == "assertion"]
    mp = sum(1 for e in EBx if (set(cnx.all(e.get("anchor") or e.get("subj"))) | set(cnx.all(e.get("obj")))) & MSx); cov = round(100.0 * mp / max(1, len(EBx)), 1)
    ok("C11 fact coverage %s" % a, cov >= BEFORE_COV.get(a, 0), "%s%% of %d facts have a subject or object that is a graph concept (before this round %s%%)" % (cov, len(EBx), BEFORE_COV.get(a)))
n = sum(res); print("\n%d / %d checks passed in %.1f s (PROVISIONAL)" % (n, len(res), time.time() - t_all)); sys.exit(0 if res and n == len(res) else 1)
