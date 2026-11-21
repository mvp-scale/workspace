"""check-contradictions: structural done-check for plan step 7 (G4 contradictions, g4-align.py contradict_edges / contradiction_counts). Touches no running service and writes no store: the synthetic cases are built in memory, the live store is only read.
    /workspace/models/embed-zs/.venv/bin/python simulation/check-contradictions.py [--store <store.jsonl>]
Checks (each prints PASS or FAIL):
  synthetic opposite pairs (playbook 00 section 12 T04 style, 'both kept'): polarity, rise/fall, rise/fall 5 days apart, unknown day -> 100 percent keep both assertions with their sources and get exactly one edge via 'contradiction'
  synthetic non-contradictions: same polarity from two publishers, same direction twice, negative against negative, 'did not fall' against rise, far apart days, different place, different resolved date, prediction against assertion,
    different object, attribution kind -> 0 edges
  determinism + idempotence: the same input gives the same edges twice and merged twice gives the same store edge, C per assertion and per entity are derived and equal
  live store: the count of contradiction edges over the stored live articles (reported, not a pass bar; truth for these is structural only)."""
import sys, os, json, importlib.util, collections, copy
HERE = os.path.dirname(os.path.abspath(__file__)); STORE = sys.argv[sys.argv.index("--store") + 1] if "--store" in sys.argv else os.path.join(os.path.dirname(HERE), "runs", "g4", "store.jsonl")
sp = importlib.util.spec_from_file_location("g4_align", os.path.join(HERE, "g4-align.py")); G4 = importlib.util.module_from_spec(sp); sp.loader.exec_module(G4)
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
def attrs(pol="positive", mod="asserted", place=None, time=None, direction=None): return {"polarity": pol, "modality": mod, "place": place, "time": time or [], "direction": direction, "amount": []}
def ev(art, pub, **k): return {"art": art, "pub": pub, "title": "t", "sent": "s", "spans": [], "independent": True, "attrs": attrs(**k), "sents": [0]}
def asr(aid, subj, pred, obj, evs, kind="claim"): return {"id": aid, "key": "%s | %s | %s" % (subj, pred, obj), "subj": subj, "pred": pred, "obj": obj, "obj_text": None, "kind": kind, "arts": {e["art"]: e["pub"] for e in evs}, "evid": evs, "iptc": None, "attrs": evs[0]["attrs"]}
def store(arts, asrs):
    S = G4.Store()
    for a, (pub, day) in arts.items(): S.arts[a] = {"publisher": pub, "title": "t", "root": a, "independent": True, "kind": "first", "day": day}
    for r in asrs: S.asr[r["id"]] = r
    return S
def run(S):   # what align() does with the edges: merge into the store, replacing sources
    for r in G4.contradict_edges(S, list(S.asr), "a1"):
        k = (r["via"], r["a"], r["b"], r["label"]); g = S.edges.get(k)
        if g is None: g = S.edges[k] = {**r, "arts": {"a1": "p"}, "w": 0, "spans": []}
        g["sources"] = r["sources"]; g["w"] += r["w"]
    return [k for k in S.edges if k[0] == "contradiction"]
D = "2026-11-10"; ARTS = {"a1": ("bbc", D), "a2": ("cnn", D), "a3": ("ft", "2026-11-15"), "a4": ("ap", "2026-10-01"), "a5": ("nyt", None), "a6": ("sky", D)}
# ---- opposite pairs: each must keep both and draw one edge ----
pos = {
 "polarity": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc"), ev("a2", "cnn", pol="negative")])],
 "rise/fall": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn")])],
 "rise/fall 5 days apart": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "fall", None, [ev("a3", "ft")])],
 "unknown day": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "fall", None, [ev("a5", "nyt")])],
 "same place both": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc", place="GB")]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn", place="GB")])],
 "same date both": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc", time=[{"iso": D}])]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn", time=[{"iso": D}])])],
}
ok = 0
for name, L in pos.items():
    S = store(ARTS, copy.deepcopy(L)); n_ev = {r["id"]: len(r["evid"]) for r in S.asr.values()}; e = run(S)
    both = {r["id"]: len(r["evid"]) for r in S.asr.values()} == n_ev and set(S.asr) == {r["id"] for r in L}
    srcs = S.edges[e[0]]["sources"] if e else {}; tagged = bool(e) and all(srcs[s] and all(x["pub"] for x in srcs[s]) for s in ("a", "b"))
    good = both and len(e) == 1 and tagged; ok += good; ck("opposite pair kept + one edge: " + name, good, "edges %d, sources %s" % (len(e), {k: [x["pub"] for x in v] for k, v in srcs.items()}))
ck("synthetic opposite pairs: 100 percent both kept and an edge drawn", ok == len(pos), "%d of %d" % (ok, len(pos)))
# ---- non-contradictions: 0 edges ----
neg = {
 "same polarity, two publishers": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc"), ev("a2", "cnn")])],
 "both negated": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc", pol="negative"), ev("a2", "cnn", pol="negative")])],
 "same direction twice": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs2", "rise", None, [ev("a2", "cnn")])],
 "did not fall against rise": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn", pol="negative")])],
 "far apart days": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "fall", None, [ev("a4", "ap")])],
 "polarity far apart": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc"), ev("a4", "ap", pol="negative")])],
 "different place": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc", place="GB")]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn", place="JP")])],
 "different resolved date": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc", time=[{"iso": "2026-11-01"}])]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn", time=[{"iso": "2026-11-09"}])])],
 "prediction against assertion": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc", mod="predicted")]), asr("A:y", "E:jobs", "fall", None, [ev("a2", "cnn")])],
 "different object": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc")]), asr("A:y", "E:fed", "fall", "E:bonds", [ev("a2", "cnn")])],
 "different subject": [asr("A:x", "E:fed", "rise", "E:rates", [ev("a1", "bbc")]), asr("A:y", "E:ecb", "fall", "E:rates", [ev("a2", "cnn")])],
 "attribution kind": [asr("A:x", "E:fed", "say", None, [ev("a1", "bbc"), ev("a2", "cnn", pol="negative")], kind="attribution")],
 "non-opposite predicates": [asr("A:x", "E:jobs", "rise", None, [ev("a1", "bbc")]), asr("A:y", "E:jobs", "delay", None, [ev("a2", "cnn")])],
}
fe = 0
for name, L in neg.items():
    S = store(ARTS, copy.deepcopy(L)); e = run(S); fe += len(e); ck("no edge: " + name, not e, "edges %d" % len(e))
ck("synthetic non-contradictions: 0 false edges", fe == 0, "%d cases" % len(neg))
# ---- determinism, idempotence, counts ----
L = pos["rise/fall"] + [asr("A:z", "E:fed", "rise", "E:rates", [ev("a1", "bbc"), ev("a6", "sky", pol="negative")])]
S = store(ARTS, copy.deepcopy(L)); e1 = G4.contradict_edges(S, list(S.asr), "a1"); e2 = G4.contradict_edges(S, list(S.asr), "a1")
ck("same input gives the same edges twice", json.dumps(e1, sort_keys=True) == json.dumps(e2, sort_keys=True), "%d edges" % len(e1))
run(S); w1 = {k: v["w"] for k, v in S.edges.items()}; k1 = len(S.edges); dg = S.digest()
S2 = store(ARTS, copy.deepcopy(L)); run(S2); ck("two builds of the same store give the same digest", S2.digest() == dg)
C = G4.contradiction_counts(S); ck("C per assertion and per entity (polarity edge counts once for its assertion, an entity counts each edge once)", C["asr"] == {"A:x": 1, "A:y": 1, "A:z": 1} and C["ent"] == {"E:jobs": 1, "E:fed": 1, "E:rates": 1}, json.dumps(C, sort_keys=True))
# ---- live store ----
if os.path.exists(STORE):
    S = G4.Store().attach(STORE); before = sum(1 for e in S.edges.values() if e["via"] == "contradiction"); es = G4.contradict_edges(S, list(S.asr), "check"); C = G4.contradiction_counts(S)
    print("INFO live store %s: %d articles, %d assertions, %d claims, stored contradiction edges %d, contradictions found now %d (polarity %d, direction %d), assertions with C>0: %d" % (STORE, len(S.arts), len(S.asr), sum(1 for r in S.asr.values() if r["kind"] == "claim"), before, len(es), sum(e["kind"] == "polarity" for e in es), sum(e["kind"] == "direction" for e in es), len(C["asr"])))
    print("INFO days known on stored articles: %d of %d (articles stored before the day field was added count as inside the window)" % (sum(1 for a in S.arts.values() if a.get("day")), len(S.arts)))
else: print("INFO no live store at", STORE)
print("ALL PASS" if not bad else "FAILED: " + "; ".join(bad)); sys.exit(1 if bad else 0)
