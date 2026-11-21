"""check-consolidate: structural done-check for plan step 6 (two clocks v0, projects/world-state/consolidate.py). Truth is structural only: replay, counting rules, graph properties, lineage. No model, no hosted call, no store or service touched (everything synthetic is in memory; real inputs are only read; the tick log is written to a temp folder).
    python3 simulation/check-consolidate.py [--trace <trace folder>] [--ticks <ticks.jsonl>] [--g4 <store.jsonl> ...]
Checks (each prints PASS or FAIL):
  replay     : two passes over the same inputs give the same sha256; the same inputs given twice (items, stores, ticks duplicated) give the same sha256 as once
  T07        : 20 syndicated copies of one story (20 publishers, one title and body) count as strength 1 with 20 fragments kept; 20 distinct stories from 20 publishers count 20; 3 stories from one publisher count 1
  T08        : an unknown term seen in >= 2 windows and >= 3 independent publishers is listed as ours:, PROVISIONAL; below the rule it is not listed; an IPTC label or a WordNet noun is not listed; 3 syndicated copies do not make 3 publishers; nothing is ever promoted
  is_a       : IPTC alone is acyclic; a property test (seeded random parent proposals over IPTC + ours: nodes, 3000 per seed) leaves the graph acyclic and refuses every proposal that would close a cycle; the detector does see a cycle when one is injected
  lineage    : a synthetic edge merged from 3 stores keeps 3 lineage lines and 3 fragments, each with its file; on the real inputs the lineage lines add up to the input records merged (assertions: one per store record; ticks: one per tick event), every edge has >= 1, every fragment's source is in its lineage
  real inputs: counts on the v7 trace + whatever the G4 stores and the tick log hold (reported, not a pass bar)."""
import sys, os, json, glob, copy, random, subprocess, tempfile, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); WS = os.path.join(ROOT, "projects", "world-state"); sys.path.insert(0, WS)
import consolidate as C, journal as J
opt = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None; multi = lambda f: [sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == f]
TRACE = opt("--trace") or "/workspace/demo/mockups/structure-live/runs-v7/trace"
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
IPTC = C.load_iptc(); WN = C.load_wordnet()
def item(i, src, day, title, body): return {"id": i, "source": src, "day": day, "keys": J.story_keys(title, body), "seq": None, "file": "synthetic"}
def ev(art, pub, sent="s"): return {"art": art, "pub": pub, "title": "t", "sent": sent, "spans": [], "independent": True, "attrs": {"polarity": "positive", "direction": None}}
def store(file, asrs=(), ents=(), arts=()): return {"asr": {r["id"]: r for r in asrs}, "ent": {r["id"]: r for r in ents}, "arts": {a: {"publisher": p, "root": a, "day": d} for a, p, d in arts}, "file": file}
def asr(aid, evs, key="E:fed | rise | E:rates"): return {"id": aid, "key": key, "subj": "E:fed", "pred": "rise", "obj": "E:rates", "obj_text": None, "kind": "claim", "evid": evs, "iptc": None}
def ent(eid, canon, arts, node=None): return {"id": eid, "type": "concept", "canon": canon, "arts": dict(arts), "iptc": {"node": node, "how": "sentence"} if node else None}
TXT = ("Central bank raises interest rates by a quarter point", "The central bank raised interest rates by a quarter point on Tuesday, citing inflation. " * 6)
# ---------- replay ----------
tmp = tempfile.mkdtemp(prefix="consolidate-check-")
tf = opt("--ticks"); PYNP = "/workspace/models/embed-zs/.venv/bin/python" if os.path.exists("/workspace/models/embed-zs/.venv/bin/python") else sys.executable   # ledger_split needs numpy
if not tf:
    tf = tmp + "/ticks.jsonl"; r = subprocess.run([PYNP, os.path.join(WS, "ledger_split.py"), TRACE, "--state", tmp + "/state.json", "--persist", tf, "--state-only"], capture_output=True, text=True, cwd=WS)
    if r.returncode: print("tick log could not be written:", r.stderr[-400:]); tf = None
g4 = multi("--g4") or ([os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*"))))
items = C.load_trace(TRACE) if os.path.isdir(TRACE) or os.path.exists(TRACE) else []; stores = [C.load_g4(p) for p in g4 if os.path.exists(p)]; ticks = C.load_ticks(tf) if tf else []
a1 = C.seal(C.consolidate(items, stores, ticks, IPTC)); a2 = C.seal(C.consolidate(items, stores, ticks, IPTC))
ck("replay: two passes over the same inputs give the same sha256", a1["sha256"] == a2["sha256"], a1["sha256"][:16])
a3 = C.seal(C.consolidate(items + items, stores + stores, ticks + ticks, IPTC))
ck("replay: the same inputs given twice give the same sha256 as once (nothing is counted again)", a3["sha256"] == a1["sha256"] and a3["counts"] == a1["counts"], json.dumps(a1["counts"], sort_keys=True))
# ---------- T07 ----------
pubs = ["pub%02d" % i for i in range(20)]; its = [item("c%02d" % i, p, "2026-11-10", *TXT) for i, p in enumerate(pubs)]
S = store("syn-a", [asr("A:1", [ev("c%02d" % i, p) for i, p in enumerate(pubs)])]); b = C.consolidate(its, [S], [], IPTC); e = b["edges"][0]
ck("T07: 20 syndicated copies count as 1 independent publisher (20 fragments kept, 1 story)", (e["strength"], e["fragments_n"], e["stories"]) == (1, 20, 1) and b["stories"]["copies"] == 19, "strength %d, fragments %d, stories %d, publisher %s" % (e["strength"], e["fragments_n"], e["stories"], e["publishers"]))
its2 = [item("d%02d" % i, p, "2026-11-10", "Story number %d about something entirely different here" % i, "Body text number %d " % i * 20) for i, p in enumerate(pubs)]
b2 = C.consolidate(its2, [store("syn-b", [asr("A:1", [ev("d%02d" % i, p) for i, p in enumerate(pubs)])])], [], IPTC)["edges"][0]
ck("T07 control: 20 distinct stories from 20 publishers count 20", b2["strength"] == 20 and b2["stories"] == 20, "strength %d" % b2["strength"])
its3 = [item("e%d" % i, "onepub", "2026-11-10", "Another distinct story number %d on the same wire here" % i, "Different body %d " % i * 20) for i in range(3)]
b3 = C.consolidate(its3, [store("syn-c", [asr("A:1", [ev("e%d" % i, "onepub") for i in range(3)])])], [], IPTC)["edges"][0]
ck("T07 control: 3 stories from one publisher count 1 publisher", (b3["strength"], b3["stories"]) == (1, 3), "strength %d, stories %d" % (b3["strength"], b3["stories"]))
# ---------- T08 ----------
days = ["2026-11-02", "2026-11-12", "2026-11-22"]
def cand(term, plan, extra_items=None):
    its = []; arts = {}
    for k, (p, d) in enumerate(plan): i = "%s-%d" % (term, k); its.append(item(i, p, d, "Distinct headline %s %d is a thing of its own" % (term, k), "Unique body %s %d " % (term, k) * 20)); arts[i] = p
    return its, ent("E:" + term, term, arts, node="medtop:20000574")
t1, e1 = cand("zorbulation", [("a", days[0]), ("b", days[1]), ("c", days[2])])      # 3 windows, 3 publishers: listed
t2, e2 = cand("quibbleflux", [("a", days[0]), ("b", days[0]), ("c", days[0])])      # 1 window: not
t3, e3 = cand("snarfmatter", [("a", days[0]), ("b", days[1]), ("a", days[2])])      # 2 publishers: not
t4, e4 = cand("election", [("a", days[0]), ("b", days[1]), ("c", days[2])])         # an IPTC label: not
t5, e5 = cand("tree", [("a", days[0]), ("b", days[1]), ("c", days[2])])             # a WordNet noun: not
syn = [item("s%d" % i, "sp%d" % i, days[i], *TXT) for i in range(3)]; e6 = ent("E:wibblezap", "wibblezap", {"s%d" % i: "sp%d" % i for i in range(3)})   # 3 syndicated copies on 3 days: one publisher
bb = C.consolidate(t1 + t2 + t3 + t4 + t5 + syn, [store("syn-d", ents=[e1, e2, e3, e4, e5, e6])], [], IPTC); ids = {c["label"]: c for c in bb["candidates"]}
ck("T08: an unknown term past the recurrence rule is listed as ours: and PROVISIONAL", "zorbulation" in ids and ids["zorbulation"]["id"] == "ours:zorbulation" and ids["zorbulation"]["status"] == "PROVISIONAL", json.dumps(ids.get("zorbulation", {}).get("status")))
ck("T08: below the rule (1 window / 2 publishers / 3 syndicated copies), an IPTC label and a WordNet noun are not listed", set(ids) == {"zorbulation"}, "listed %s, counts %s" % (sorted(ids), bb["candidate_counts"]))
ck("T08: nothing is promoted (every status PROVISIONAL, no ours: node leaves PROVISIONAL, the promotion rule says none)", all(c["status"] == "PROVISIONAL" for c in bb["candidates"]) and "none" in bb["rule"]["promotion"] and not hasattr(C, "promote"))
ck("T08: the IPTC part of the is_a graph is unchanged by candidates (1 ours: node added, its parent is the IPTC node it was placed on)", bb["is_a"]["nodes"] == len(IPTC[0]) + 1 and ids["zorbulation"]["is_a"] == "medtop:20000574", json.dumps(bb["is_a"], sort_keys=True))
# ---------- is_a ----------
ck("is_a: IPTC alone is acyclic", C.IsA(IPTC[0]).acyclic(), "%d nodes" % len(IPTC[0]))
tot_ref = 0; ok_all = True; q = sorted(IPTC[0])
for seed in range(5):
    rnd = random.Random(seed); g = C.IsA(IPTC[0]); ours = []
    for k in range(3000):
        c = rnd.choice(ours) if ours and rnd.random() < 0.5 else "ours:n%d" % rnd.randrange(400); par = rnd.choice(ours + q + [None]) if rnd.random() < 0.9 else "nowhere"
        before = dict(g.par); added = g.add(c, par)
        if added: ours.append(c) if c not in ours else None
        else: tot_ref += 1; ok_all &= g.par == before   # a refused proposal changes nothing
        if k % 500 == 499: ok_all &= g.acyclic()
    ok_all &= g.acyclic()
ck("is_a property test: 5 seeds x 3000 random proposals, graph acyclic throughout, refused proposals change nothing", ok_all and tot_ref > 0, "%d proposals refused (cycle, unknown parent)" % tot_ref)
g = C.IsA({"a": None, "b": "a"}); g.par["a"] = "b"; ck("is_a: the detector sees an injected cycle", not g.acyclic())
g = C.IsA({"r": None}); ok1 = g.add("ours:x", "r"); ok2 = g.add("ours:y", "ours:x"); ok3 = g.add("ours:x", "ours:y"); ck("is_a: a parent that would close a cycle is refused", ok1 and ok2 and not ok3 and g.acyclic() and g.refused[-1][2] == "cycle")
# ---------- lineage ----------
ss = [store("run-%d" % i, [asr("A:%d" % i, [ev("m%d" % i, "p%d" % i, "same sentence")])]) for i in range(3)]; its4 = [item("m%d" % i, "p%d" % i, "2026-11-1%d" % i, "Unrelated story number %d with plenty of words" % i, "Own body %d " % i * 20) for i in range(3)]
for s_ in ss: s_["asr"] = {"A:x": {**s_["asr"][next(iter(s_["asr"]))], "id": "A:x"}}   # the same assertion id and key in three run files
b4 = C.consolidate(its4, ss, [], IPTC)["edges"]; e = b4[0]
ck("lineage: one assertion merged from 3 stores is one edge keeping 3 lineage lines and 3 fragments, each tagged with its file", len(b4) == 1 and len(e["lineage"]) == 3 and e["fragments_n"] == 3 and {f["source"] for f in e["fragments"]} == {"run-0", "run-1", "run-2"} and e["strength"] == 3, json.dumps([l["file"] for l in e["lineage"]]))
exp_asr = sum(1 for S_ in stores for r in S_["asr"].values() if r.get("kind") == "claim"); got_asr = sum(len(x["lineage"]) for x in a1["edges"] if x["kind"] == "assertion")
exp_tk = sum(len(t["events"]) for t in ticks if t.get("ind")); got_tk = sum(len(x["lineage"]) for x in a1["edges"] if x["kind"] == "resource")
ck("lineage (real inputs): assertion edges carry one lineage line per store record merged", got_asr == exp_asr, "%d lines for %d claim records in %d stores" % (got_asr, exp_asr, len(stores)))
ck("lineage (real inputs): resource edges carry one lineage line per tick event", got_tk == exp_tk, "%d lines for %d tick events" % (got_tk, exp_tk))
ck("lineage (real inputs): every edge has >= 1 lineage line and every fragment's source is in its lineage", all(x["lineage"] and {f["source"] for f in x["fragments"]} <= {l["file"] for l in x["lineage"]} for x in a1["edges"]), "%d edges" % len(a1["edges"]))
# ---------- real inputs ----------
print("INFO real inputs: trace %s (%d items), %d G4 stores (%d claims), tick log %s (%d rows)" % (TRACE, len(items), len(stores), exp_asr, tf, len(ticks)))
print("INFO stories %s; edges %s; multi-publisher edges %d; candidates %d (%s); is_a nodes %d, ours %d, acyclic %s" % (a1["stories"], a1["counts"], a1["counts"]["multi_publisher_edges"], len(a1["candidates"]), a1["candidate_counts"], a1["is_a"]["nodes"], a1["is_a"]["ours"], a1["is_a"]["acyclic"]))
print("INFO sha256 %s; journal.jsonl present: %s; stored G4 articles found in the trace: %d of %d" % (a1["sha256"], os.path.exists(os.path.join(ROOT, "runs", "journal", "journal.jsonl")), sum(1 for S_ in stores for a in S_["arts"] if a in {i["id"] for i in items}), sum(len(S_["arts"]) for S_ in stores)))
print("temp folder kept:", tmp)
print("ALL PASS" if not bad else "FAILED: " + "; ".join(bad)); sys.exit(1 if bad else 0)
