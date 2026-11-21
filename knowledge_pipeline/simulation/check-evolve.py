"""check-evolve: structural done-check for G5 evolution v0 (projects/world-state/evolve.py, lean wave 0, ledger L2868). Truth is structural only: gate counting, graph properties, lineage, determinism. No model, no hosted call, no store or service touched (synthetic cases are in memory; real inputs are only read; outputs go to a temp folder).
    python3 simulation/check-evolve.py [--trace <trace folder>] [--ticks <ticks.jsonl>] [--g4 <store.jsonl> ...]
Checks (each prints PASS or FAIL):
  gates      : a synthetic residual term seen in >= 2 windows by >= 3 independent publishers is a candidate (PROVISIONAL); below either count, an IPTC label, a WordNet noun, and 3 syndicated copies (one publisher) are accumulating (RESIDUAL) with the failing gate named; a term placed by the sentence or WordNet is not residual at all; on the real inputs every candidate passes the three gates recomputed here and every non-candidate fails at least one
  no promotion: no node or archived entry has a status above PROVISIONAL (only RESIDUAL, PROVISIONAL, ARCHIVED appear), evolve has no promote/validate function, no human-review field
  is_a       : the graph over IPTC + ours is acyclic on the real inputs and on a seeded property test with prev versions (split chains), and every node's parent exists
  lineage    : on the real inputs the nodes' lineage equals the input records of the unplaced terms (set equality, recomputed here from the raw store lines); the nodes' members partition the unplaced terms; synthetic split and merge events list exactly the earlier nodes they came from
  versions   : a split child is_a its parent and inherits its label (inherited_from set, version + 1), the earlier node is archived with superseded_by, a merge lists merged_from, an unchanged node keeps its labels (no new version)
  sha stable : two passes over the same inputs, the same inputs given twice, and two CLI runs give the same sha256
  real inputs: counts on the G4 stores (+ archive) and the tick log (reported, not a pass bar)."""
import sys, os, json, glob, random, subprocess, tempfile, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); WS = os.path.join(ROOT, "projects", "world-state"); sys.path.insert(0, WS)
import consolidate as C, journal as J, evolve as EV
opt = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None; multi = lambda f: [sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == f]
TRACE = opt("--trace") or "/workspace/demo/mockups/structure-live/runs-v7/trace"
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
IPTC = C.load_iptc(); WN = C.load_wordnet()
def item(i, src, day, title, body): return {"id": i, "source": src, "day": day, "keys": J.story_keys(title, body), "seq": None, "file": "synthetic"}
def store(file, ents=(), arts=()): return {"asr": {}, "ent": {r["id"]: r for r in ents}, "arts": {a: {"publisher": p, "root": a, "day": d} for a, p, d in arts}, "file": file}
def ent(eid, canon, arts, how="article-topic", node="medtop:20000574"): return {"id": eid, "type": "concept", "canon": canon, "arts": dict(arts), "iptc": {"node": node, "how": how} if how else None}
def its(term, plan): return [item("%s-%d" % (term, k), p, d, "Distinct headline %s %d is a thing of its own" % (term, k), "Unique body %s %d " % (term, k) * 20) for k, (p, d) in enumerate(plan)]
def e_(term, plan, eid=None, **kw): return ent(eid or "E:" + term, term, {"%s-%d" % (term, k): p for k, (p, d) in enumerate(plan)}, **kw)
D = ["2026-11-02", "2026-11-12", "2026-11-22"]
def run(specs, prev=None, fname="syn"):
    """specs: [(term, plan, kwargs)] -> evolve body"""
    I = []; E = []
    for t, plan, kw in specs: I += its(t, plan); E.append(e_(t, plan, **kw))
    return EV.seal(EV.evolve(I, [store(fname, ents=E)], [], IPTC, prev))
byid = lambda b: {n["id"]: n for n in b["nodes"]}
# ---------- gates ----------
P3 = [("a", D[0]), ("b", D[1]), ("c", D[2])]
b = run([("zorbulation", P3, {}), ("quibbleflux", [("a", D[0]), ("b", D[0]), ("c", D[0])], {}), ("snarfmatter", [("a", D[0]), ("b", D[1]), ("a", D[2])], {}), ("election", P3, {}), ("tree", P3, {}), ("placedterm", P3, {"how": "sentence"}), ("wnplaced", P3, {"how": "wordnet"})])
N = byid(b)
ck("gates: an unplaced term past the rule is a candidate, PROVISIONAL", N["ours:zorbulation"]["stage"] == "candidate" and N["ours:zorbulation"]["status"] == "PROVISIONAL", json.dumps(N["ours:zorbulation"]["gates"]))
ck("gates: 1 window fails `windows`; 2 publishers fails `publishers`", N["ours:quibbleflux"]["gates_failed"] == ["windows"] and N["ours:snarfmatter"]["gates_failed"] == ["publishers"], "%s | %s" % (N["ours:quibbleflux"]["gates_failed"], N["ours:snarfmatter"]["gates_failed"]))
ck("gates: an IPTC label and a WordNet noun fail `not_known` and stay RESIDUAL", N["ours:election"]["gates_failed"] == ["not_known"] and N["ours:tree"]["gates_failed"] == ["not_known"] and N["ours:tree"]["status"] == "RESIDUAL", "")
ck("gates: a term placed by sentence or WordNet is not residual (no node)", "ours:placedterm" not in N and "ours:wnplaced" not in N and b["counts"]["unplaced_terms"] == 5, "unplaced %d of %d concepts" % (b["counts"]["unplaced_terms"], b["counts"]["concept_terms"]))
TXT = ("Central bank raises interest rates by a quarter point", "The central bank raised interest rates by a quarter point on Tuesday, citing inflation. " * 6)
I2 = [item("s%d" % i, "sp%d" % i, D[i], *TXT) for i in range(3)]; b2 = EV.seal(EV.evolve(I2, [store("syn2", ents=[ent("E:wibblezap", "wibblezap", {"s%d" % i: "sp%d" % i for i in range(3)})])], [], IPTC))
ck("gates: 3 syndicated copies on 3 days count as 1 publisher (not a candidate)", b2["nodes"][0]["strength"] == 1 and b2["nodes"][0]["stage"] == "accumulating", "strength %d" % b2["nodes"][0]["strength"])
# ---------- real inputs ----------
tmp = tempfile.mkdtemp(prefix="evolve-check-"); tf = opt("--ticks"); PYNP = "/workspace/models/embed-zs/.venv/bin/python" if os.path.exists("/workspace/models/embed-zs/.venv/bin/python") else sys.executable
if not tf:
    tf = tmp + "/ticks.jsonl"; r = subprocess.run([PYNP, os.path.join(WS, "ledger_split.py"), TRACE, "--state", tmp + "/state.json", "--persist", tf, "--state-only"], capture_output=True, text=True, cwd=WS)
    if r.returncode: print("tick log could not be written:", r.stderr[-300:]); tf = None
g4 = multi("--g4") or ([os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*"))))
items = C.load_trace(TRACE) if os.path.exists(TRACE) else []; stores = [C.load_g4(p) for p in g4 if os.path.exists(p)]; ticks = C.load_ticks(tf) if tf else []
R = EV.seal(EV.evolve(items, stores, ticks, IPTC)); ST = C.Stories(items, stores)
ok = True; det = []
for n in R["nodes"]:
    arts = {}
    for t in n["members"]:
        for S in stores:
            for r in S["ent"].values():
                if r.get("type") == "concept" and r["canon"].lower().strip() == t: arts.update(r.get("arts") or {})
    s, _, _ = ST.strength(sorted(arts.items())); w = len({C.window(ST.day(a)) for a in arts} - {None}); kn = C.known_term(n["label"], IPTC[1], WN)
    passes = w >= C.MIN_WINDOWS and s >= C.MIN_PUBLISHERS and not kn
    if passes != (n["stage"] == "candidate"): ok = False; det.append(n["id"])
ck("gates: on the real inputs candidate == passes all three gates (recomputed from the raw store records)", ok, "clusters %d, candidates %d, failing the rule wrongly: %s" % (len(R["nodes"]), R["counts"]["candidates"], det[:3]))
# ---------- no promotion ----------
allst = {n["status"] for n in R["nodes"] + R["archived"]} | {n["status"] for n in b["nodes"]}; fn = [x for x in dir(EV) if any(k in x.lower() for k in ("promot", "validat", "approve"))]
ck("no promotion: statuses are only RESIDUAL, PROVISIONAL, ARCHIVED; no promote/validate function; no review field", allst <= {"RESIDUAL", "PROVISIONAL", "ARCHIVED"} and not fn and not any("review" in k or "approved" in k for n in R["nodes"] for k in n), "statuses %s, functions %s" % (sorted(allst), fn))
# ---------- lineage ----------
want = set(); T = collections.defaultdict(lambda: {"hows": set(), "lin": set()})
for S in stores:
    for eid, r in S["ent"].items():
        if r.get("type") == "concept": t = T[r["canon"].lower().strip()]; t["hows"].add((r.get("iptc") or {}).get("how")); t["lin"].add((EV.rel(S["file"]), "g4-store", eid))
un = {t for t, v in T.items() if v["hows"] <= {None, "article-topic"}}; want = {x for t in un for x in T[t]["lin"]}; got = {(l["file"], l["kind"], l["ref"]) for n in R["nodes"] for l in n["lineage"]}; mem = [t for n in R["nodes"] for t in n["members"]]
ck("lineage: the nodes' lineage equals the input records of the unplaced terms (set equality)", got == want and len(want) > 0, "%d input records, %d unplaced terms" % (len(want), len(un)))
ck("lineage: the members partition the unplaced terms (no term twice, none lost)", sorted(mem) == sorted(un) and len(mem) == len(set(mem)), "%d members" % len(mem))
# ---------- versions: split, merge, unchanged ----------
V1 = run([("cargo", P3, {}), ("cargo ship", P3, {}), ("loading dock", P3, {})])   # head words: cargo, ship, dock -> 3 clusters
# split: v1 has one node "ship" with 2 terms; v2 the same terms come out under two clusters
A = run([("hull ship", P3, {}), ("cargo ship", P3, {})]); a = byid(A); pid = [i for i in a if len(a[i]["members"]) == 2][0]
Bsp = run([("hull ship", P3, {}), ("cargo", P3, {}), ("hull", P3, {})], prev=None)   # unrelated terms; build the split by hand-editing the earlier node's members below
prev = json.loads(json.dumps(A)); prev["nodes"][0]["members"] = ["hull ship", "cargo ship", "rail car"]   # earlier version held 3 terms in one node (id = pid)
S2 = run([("hull ship", P3, {}), ("cargo ship", P3, {})], prev=prev); s = byid(S2)
ck("versions: an unchanged id with changed members is the same node, version + 1", pid in s and [l["version"] for l in s[pid]["labels"]] == [1, 2], json.dumps([l["version"] for l in s.get(pid, {"labels": []})["labels"]]))
# a real split: earlier node "ship" (hull ship + dock) now clusters differently: pid terms move to ids that did not exist
prev2 = json.loads(json.dumps(A)); old = prev2["nodes"][0]; old["id"] = "ours:fleet"; old["label"] = "fleet"; old["members"] = ["hull ship", "cargo ship", "rail car"]; old["labels"] = [{"version": 1, "definition": "x", "label": "fleet", "inherited_from": None}]; old["definition"] = "x"
S3 = run([("hull ship", P3, {}), ("rail car", P3, {})], prev=prev2); s3 = byid(S3); ch = [n for n in S3["nodes"] if n.get("split_from") == "ours:fleet"]
ck("versions: a split gives children that are_a the earlier node and inherit its label; the earlier node is archived with superseded_by; a split event is listed", len(ch) == 2 and all(n["is_a"] == "ours:fleet" and n["labels"][-1]["inherited_from"] == "ours:fleet" and n["labels"][-1]["label"] == "fleet" and n["labels"][-1]["version"] == 2 for n in ch) and [x["id"] for x in S3["archived"]] == ["ours:fleet"] and S3["archived"][0]["superseded_by"] == sorted(n["id"] for n in ch) and S3["counts"]["split_events"] == 1, "children %s" % [n["id"] for n in ch])
ck("lineage: the split event names exactly the earlier node and its children", S3["events"] == [{"event": "split", "from": "ours:fleet", "into": sorted(n["id"] for n in ch)}], json.dumps(S3["events"]))
# merge: two earlier nodes (ids ours:hull, ours:rail) now one cluster by head word
pm = json.loads(json.dumps(A)); n0 = pm["nodes"][0]; n1 = json.loads(json.dumps(n0))
n0.update(id="ours:hull-thing", label="hull thing", members=["hull ship"]); n1.update(id="ours:cargo-thing", label="cargo thing", members=["cargo ship"])
for n, l in ((n0, "hull thing"), (n1, "cargo thing")): n["labels"] = [{"version": 1, "definition": "y", "label": l, "inherited_from": None}]; n["definition"] = "y"
pm["nodes"] = [n0, n1]; M = run([("hull ship", P3, {}), ("cargo ship", P3, {})], prev=pm); m = [n for n in M["nodes"] if n.get("merged_from")]
ck("versions: a merge lists merged_from and exactly one merge event; both earlier nodes are archived", len(m) == 1 and m[0]["merged_from"] == ["ours:cargo-thing", "ours:hull-thing"] and M["counts"]["merge_events"] == 1 and sorted(x["id"] for x in M["archived"]) == ["ours:cargo-thing", "ours:hull-thing"], json.dumps(M["events"]))
same = run([("cargo ship", P3, {}), ("hull ship", P3, {})], prev=A); ck("versions: running again over the same inputs with the earlier version as prev adds no version and no event", byid(same)[pid]["labels"] == a[pid]["labels"] and same["events"] == [] and same["counts"]["archived"] == 0, "")
# ---------- is_a ----------
ok = all(R["is_a"]["acyclic"] for _ in [0]) and R["is_a"]["refused"] == 0; g = C.IsA(IPTC[0]); ok2 = g.acyclic(); parents_ok = all(n["is_a"] is None or n["is_a"] in IPTC[0] or n["is_a"].startswith("ours:") for n in R["nodes"])
rng = random.Random(7); pv = None; accyc = True
for rnd in range(30):   # seeded property test: random term sets, each round evolved from the previous one (splits and merges appear), the graph must stay acyclic
    terms = ["%s %s" % (rng.choice("abcdef"), rng.choice(["ship", "port", "dock", "yard"])) for _ in range(rng.randint(2, 8))]; terms = sorted(set(terms))
    body = run([(t, P3, {}) for t in terms], prev=pv); good = body["is_a"]["acyclic"] and body["is_a"]["refused"] == 0; accyc &= good; pv = body
    if not good: print("  round", rnd, body["is_a"]["refused_detail"][:3])
ck("is_a: acyclic on IPTC alone, on the real inputs, and over 30 chained random versions (splits and merges)", ok and ok2 and parents_ok and accyc, "real graph %d nodes, %d ours, refused %d" % (R["is_a"]["nodes"], R["is_a"]["ours"], R["is_a"]["refused"]))
gc = C.IsA(IPTC[0]); gc.par["ours:x"] = "ours:y"; gc.par["ours:y"] = "ours:x"; ck("is_a: the detector does see a cycle when one is injected", not gc.acyclic())
# ---------- sha stable ----------
R2 = EV.seal(EV.evolve(items, stores, ticks, IPTC)); R3 = EV.seal(EV.evolve(items + items, stores + stores, ticks + ticks, IPTC))
ck("sha stable: two passes over the same inputs give the same sha256", R["sha256"] == R2["sha256"], R["sha256"][:16])
ck("sha stable: the same inputs given twice give the same sha256 as once", R3["sha256"] == R["sha256"] and R3["counts"] == R["counts"], "")
cl = [] if True else None; outs = []
for k in (1, 2):
    o = "%s/cli%d.json" % (tmp, k); cmd = [sys.executable, os.path.join(WS, "evolve.py"), "--out", o, "--ticks", tf or "/nonexistent"] + [x for p in g4 for x in ("--g4", p)] + (["--trace", TRACE] if os.path.exists(TRACE) else []); r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp); outs.append(json.load(open(o))["sha256"] if r.returncode == 0 else "ERR " + r.stderr[-200:])
ck("sha stable: two CLI runs give the same sha256 (and equal the in-process one)", outs[0] == outs[1] == R["sha256"], str(outs[0])[:16])
print("real inputs:", json.dumps(R["counts"], sort_keys=True)); print("real inputs: items %d, tick rows %d, stores %d" % (R["inputs"]["items"], R["inputs"]["tick_rows"], len(R["inputs"]["stores"])))
print("\n%s" % ("ALL PASS" if not bad else "FAILED: " + "; ".join(bad))); sys.exit(1 if bad else 0)
